"""Attribution journal, agent turns, briefs, the revert guard and restore."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import textdiff as td
from .repo import HUMANISH, Repo, atomic_write, run_git
from .store import Store, git_missing, is_binary, read_file, scan
from .sync import sync_line, sync_status

MAX_EVENT_LINES = 400
ACTIVE_TTL = 3 * 3600  # an agent turn with no end after this long is considered over


def now() -> float:
    return time.time()


def ago(ts: float, ref: Optional[float] = None) -> str:
    d = max(0, int((ref or now()) - ts))
    if d < 60:
        return f"{d}s ago"
    if d < 3600:
        return f"{d // 60} min ago"
    if d < 86400:
        return f"{d // 3600} h ago"
    return f"{d // 86400} d ago"


class Verdict:
    def __init__(self, path: str, dropped: List[str], resurrected: List[str], human: Dict[str, int]):
        self.path = path
        self.dropped = dropped
        self.resurrected = resurrected
        self.human = human  # line key -> seq of the human edit

    @property
    def reverts(self) -> bool:
        return bool(self.dropped or self.resurrected)

    def message(self, agent: str) -> str:
        lines = [f"dibs: this edit to {self.path} would undo changes the human made by hand."]
        if self.dropped:
            lines.append("It removes lines the human added or changed:")
            lines += [f"  + {k}" for k in self.dropped[:8]]
        if self.resurrected:
            lines.append("It brings back lines the human deleted:")
            lines += [f"  - {k}" for k in self.resurrected[:8]]
        lines.append("Keep the human's version and make your change around it. Only if the user explicitly "
                     f"asked to change these lines, run `dibs allow {self.path}` and retry.")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "reverts": self.reverts, "dropped": self.dropped,
                "resurrected": self.resurrected}


class Dibs:
    def __init__(self, repo: Optional[Repo] = None):
        self.repo = repo or Repo.discover()
        self.store = Store(self.repo)
        self.cfg = self.repo.config()

    # ------------------------------------------------------------------ state
    def load_state(self) -> Dict[str, Any]:
        try:
            st = json.loads(self.repo.state_file.read_text("utf-8"))
        except (OSError, ValueError):
            st = {}
        st.setdefault("version", 1)
        st.setdefault("seq", 0)
        st.setdefault("manifest", {})
        st.setdefault("agents", {})
        st.setdefault("pending_reverts", [])
        st.setdefault("allows", {})
        return st

    def save_state(self, st: Dict[str, Any]) -> None:
        atomic_write(self.repo.state_file, json.dumps(st, separators=(",", ":")).encode())

    def events(self, min_seq: Optional[int] = None, min_ts: Optional[float] = None) -> List[Dict[str, Any]]:
        """Journal events in order. With ``min_seq``/``min_ts`` only the tail is read (seq > min_seq,
        ts >= min_ts), so hooks stay fast however long the journal grows."""
        if min_seq is None and min_ts is None:
            out = []
            try:
                with open(self.repo.journal_file, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            try:
                                out.append(json.loads(line))
                            except ValueError:
                                pass
            except FileNotFoundError:
                pass
            return out
        rev: List[Dict[str, Any]] = []
        for e in self._read_reverse():
            if min_seq is not None and e.get("seq", 0) <= min_seq:
                break
            if min_ts is not None and e.get("ts", 0) < min_ts - 300:  # small slack for clock jitter
                break
            if min_ts is None or e.get("ts", 0) >= min_ts:
                rev.append(e)
        rev.reverse()
        return rev

    def _read_reverse(self, block: int = 1 << 16):
        try:
            fh = open(self.repo.journal_file, "rb")
        except FileNotFoundError:
            return
        with fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            rest = b""
            while pos > 0:
                n = min(block, pos)
                pos -= n
                fh.seek(pos)
                chunk = fh.read(n) + rest
                lines = chunk.split(b"\n")
                rest = lines[0]
                for line in reversed(lines[1:]):
                    if line.strip():
                        try:
                            yield json.loads(line.decode("utf-8"))
                        except ValueError:
                            pass
            if rest.strip():
                try:
                    yield json.loads(rest.decode("utf-8"))
                except ValueError:
                    pass

    def _append(self, evs: List[Dict[str, Any]]) -> None:
        if not evs:
            return
        self.repo.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.repo.journal_file, "a", encoding="utf-8") as fh:
            for ev in evs:
                fh.write(json.dumps(ev, ensure_ascii=False, separators=(",", ":")) + "\n")

    # ------------------------------------------------------------------- init
    def ensure(self) -> None:
        if not self.repo.initialized:
            with self.repo.lock():
                if not self.repo.initialized:
                    self._baseline()

    def _baseline(self) -> None:
        manifest, data = scan(self.repo, {})
        maxb = int(self.cfg["max_file_bytes"])
        dirty = None
        if self.repo.is_git:
            r = run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], self.repo.root)
            if r is not None and r.returncode == 0:
                dirty = set()
                parts = r.stdout.decode("utf-8", "surrogateescape").split("\0")
                for p in parts:
                    if len(p) > 3:
                        dirty.add(p[3:])
        # Store every file git can't give back later (dirty, untracked, or stored with filters such as CRLF).
        missing = git_missing(self.repo, (manifest[rel][0] for rel in data)) if self.repo.is_git else None
        for rel, blob in data.items():
            if len(blob) <= maxb and (missing is None or (dirty is not None and rel in dirty)
                                      or manifest[rel][0] in missing):
                self.store.put(blob)
        st = self.load_state()
        st["created"] = now()
        if dirty and self.repo.is_git:
            # Uncommitted work that predates dibs: compare it with HEAD and record it as "unknown"
            # (human or an earlier agent), so it is protected and shown to agents like human edits.
            head: Dict[str, str] = {}
            r = run_git(["ls-tree", "-r", "-z", "HEAD"], self.repo.root)
            if r is not None and r.returncode == 0:
                for item in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
                    meta, _, path = item.partition("\t")
                    parts = meta.split()
                    if path and len(parts) == 3 and parts[1] == "blob":
                        head[path] = parts[2]
                base = dict(manifest)
                for rel in dirty:
                    if rel in head:
                        base[rel] = [head[rel], -1, -1]
                    else:
                        base.pop(rel, None)
                st["manifest"] = base
                self._record(st, "unknown", note="uncommitted when dibs started")
                self.save_state(st)
                return
        st["manifest"] = manifest
        self.save_state(st)

    # -------------------------------------------------------------- recording
    def _record(self, st: Dict[str, Any], actor: str, paths: Optional[Iterable[str]] = None,
                session: Optional[str] = None, note: Optional[str] = None) -> List[Dict[str, Any]]:
        old = st["manifest"]
        new, data = scan(self.repo, old, paths=paths)
        changed = sorted(p for p in set(old) | set(new)
                         if (old.get(p) or [None])[0] != (new.get(p) or [None])[0])
        if not changed:
            st["manifest"] = new
            return []
        maxb = int(self.cfg["max_file_bytes"])
        t = now()
        history = None
        allows = {p: exp for p, exp in st.get("allows", {}).items() if exp > t}
        st["allows"] = allows
        evs = []
        for rel in changed:
            b = (old.get(rel) or [None])[0]
            a = (new.get(rel) or [None])[0]
            after = data.get(rel) if a else None
            if a and after is None:
                after = read_file(self.repo, rel)
            if after is not None and len(after) <= maxb:
                self.store.put(after)
            before = self.store.get(b) if b else None
            st["seq"] += 1
            ev: Dict[str, Any] = {"seq": st["seq"], "kind": "change", "ts": round(t, 3), "actor": actor,
                                  "path": rel, "op": "A" if not b else ("D" if not a else "M"),
                                  "before": b, "after": a}
            if session:
                ev["session"] = session
            if note:
                ev["note"] = note
            bl = td.to_lines(before) if (b is None or before is not None) else None
            al = td.to_lines(after) if (a is None or (after is not None and len(after) <= maxb)) else None
            if bl is None or al is None:
                ev["binary"] = True
            else:
                plus, minus = td.line_delta(bl, al)
                ev["np"], ev["nm"] = len(plus), len(minus)
                ev["plus"] = plus[:MAX_EVENT_LINES]
                ev["minus"] = minus[:MAX_EVENT_LINES]
                if actor not in HUMANISH:
                    if rel in allows:
                        ev["override"] = True
                    else:
                        if history is None:
                            history = self.events(min_ts=t - float(self.cfg["protect_hours"]) * 3600)
                        added, removed = self._protected(history + evs, rel, t)
                        v = self._verdict(rel, bl, plus, minus, added, removed)
                        if v.reverts:
                            ev["reverts"] = {"dropped": v.dropped, "resurrected": v.resurrected}
                            st["pending_reverts"].append(ev["seq"])
            evs.append(ev)
        st["manifest"] = new
        self._append(evs)
        return evs

    def record(self, actor: str, paths: Optional[Iterable[str]] = None, session: Optional[str] = None,
               note: Optional[str] = None) -> List[Dict[str, Any]]:
        self.ensure()
        with self.repo.lock():
            st = self.load_state()
            evs = self._record(st, actor, paths, session, note)
            self.save_state(st)
        return evs

    def absorb(self, paths: Optional[Iterable[str]] = None) -> None:
        """Accept the current content of ``paths`` (or everything) without recording events."""
        self.ensure()
        with self.repo.lock():
            st = self.load_state()
            new, data = scan(self.repo, st["manifest"], paths=paths)
            maxb = int(self.cfg["max_file_bytes"])
            for blob in data.values():
                if len(blob) <= maxb:
                    self.store.put(blob)
            st["manifest"] = new
            self.save_state(st)

    def _pending_actor(self, st: Dict[str, Any], agent: Optional[str]) -> str:
        """Who made changes nobody has claimed yet: the human, unless another agent is mid-turn."""
        t = now()
        for name, a in st["agents"].items():
            if name != agent and a.get("active") and t - a.get("started", 0) < ACTIVE_TTL:
                return "unknown"
        return "human"

    # ------------------------------------------------------------------ turns
    def turn_start(self, agent: str, session: Optional[str] = None) -> str:
        self.ensure()
        with self.repo.lock():
            st = self.load_state()
            self._record(st, self._pending_actor(st, agent))
            a = st["agents"].setdefault(agent, {})
            since = a.get("seen_seq")
            a.update(active=True, started=now(), session=session, touched=[], seen_seq=st["seq"])
            self.save_state(st)
        text = self.render_brief(agent, since, st)
        if agent == "cursor":
            with self.repo.lock():
                st2 = self.load_state()
                st2["agents"].setdefault(agent, {})["pending_brief"] = text
                self.save_state(st2)
        return text

    def take_pending_brief(self, agent: str) -> str:
        with self.repo.lock():
            st = self.load_state()
            a = st["agents"].get(agent) or {}
            text = a.pop("pending_brief", "") or ""
            self.save_state(st)
        return text

    def touch(self, agent: str, paths: Optional[List[str]], session: Optional[str] = None) -> List[Dict[str, Any]]:
        """Record an agent's tool call: given paths, or the whole tree when paths is None."""
        self.ensure()
        with self.repo.lock():
            st = self.load_state()
            a = st["agents"].setdefault(agent, {})
            if not a.get("active"):
                a.update(active=True, started=now(), touched=[])
            evs = self._record(st, agent, paths, session)
            touched = a.setdefault("touched", [])
            for p in (paths or []) + [e["path"] for e in evs]:
                if p not in touched:
                    touched.append(p)
            self.save_state(st)
        return evs

    def turn_end(self, agent: str, full: bool = False, session: Optional[str] = None) -> List[Dict[str, Any]]:
        self.ensure()
        with self.repo.lock():
            st = self.load_state()
            a = st["agents"].setdefault(agent, {})
            evs: List[Dict[str, Any]] = []
            if full:
                evs = self._record(st, agent, None, session)
            elif a.get("touched"):
                evs = self._record(st, agent, a["touched"], session)
            a.update(active=False, ended=now(), touched=[])
            self.save_state(st)
        return evs

    # ------------------------------------------------------------------ brief
    def changes_since(self, agent: str, since: Optional[int], st: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if since is None:
            cutoff = now() - float(self.cfg["brief_window_hours"]) * 3600
            evs = self.events(min_ts=cutoff)
        else:
            evs = self.events(min_seq=since)
        return [e for e in evs if e.get("kind") == "change" and e["actor"] != agent]

    def render_brief(self, agent: str, since: Optional[int], st: Optional[Dict[str, Any]] = None,
                     include_sync: Optional[bool] = None) -> str:
        evs = self.changes_since(agent, since, st)
        files: Dict[str, Dict[str, Any]] = {}
        for e in evs:
            f = files.setdefault(e["path"], {"before": e["before"], "events": [], "actors": []})
            f["events"].append(e)
            f["after"] = e["after"]
            if e["actor"] not in f["actors"]:
                f["actors"].append(e["actor"])
        per_file = int(self.cfg["brief_lines_per_file"])
        out: List[str] = []
        shown = 0
        human_files = 0
        for path, f in files.items():
            if f["before"] == f["after"]:
                continue
            if shown >= int(self.cfg["brief_max_files"]):
                shown += 1
                continue
            shown += 1
            who = ", ".join("someone (you or an earlier agent)" if x == "unknown" else x for x in f["actors"])
            if any(x in HUMANISH for x in f["actors"]):
                human_files += 1
            if f["before"] is None:
                op = "created"
            elif f["after"] is None:
                op = "deleted"
            else:
                op = "edited"
            before = self.store.get(f["before"]) if f["before"] else b""
            after = self.store.get(f["after"]) if f["after"] else b""
            if f["after"] and after is None:
                after = read_file(self.repo, path)
            bl, al = td.to_lines(before), td.to_lines(after)
            if bl is None or al is None or before is None or after is None:
                out.append(f"• {path} — {op} by {who} (binary or large file)")
                continue
            plus, minus = td.line_delta(bl, al)
            out.append(f"• {path} — {op} by {who} (+{len(plus)} −{len(minus)}, {ago(f['events'][-1]['ts'])})")
            if op != "deleted":
                out += ["    " + l for l in td.unified(bl, al, per_file)]
        if shown > int(self.cfg["brief_max_files"]):
            out.append(f"… and {shown - int(self.cfg['brief_max_files'])} more files (run `dibs log`)")
        msg: List[str] = []
        if out:
            head = ("[dibs] Since your last turn these files were changed outside your session"
                    + (" — by the human, by hand." if human_files and len(files) == human_files else "."))
            msg.append(head)
            msg.append("Human edits are intentional: read the current file before editing, build on them, and do not "
                       "revert or \"fix\" them back to your earlier version unless the user asks.")
            msg += out
        reverts = self.pending_reverts()
        if reverts:
            msg.append("[dibs] Human lines that an agent reverted and nobody has restored yet:")
            for r in reverts[:5]:
                ks = (r["dropped"] + r["resurrected"])[:3]
                msg.append(f"• {r['path']} (#{r['seq']} by {r['actor']}): " + " | ".join(ks)
                           + f" — restore them (`dibs restore {r['path']}`) unless the user asked for this.")
        if include_sync if include_sync is not None else self.cfg.get("brief_sync", True):
            s = sync_status(self.repo)
            if s["warnings"]:
                msg.append("[dibs] " + sync_line(s) + " Do not discard uncommitted work; mention unpushed work to the user when relevant.")
        return "\n".join(msg)

    # ------------------------------------------------------------------ guard
    def _protected(self, events: List[Dict[str, Any]], rel: str, t: float) -> Tuple[Dict[str, int], Dict[str, int]]:
        cutoff = t - float(self.cfg["protect_hours"]) * 3600
        added: Dict[str, int] = {}
        removed: Dict[str, int] = {}
        for ev in events:
            if ev.get("kind") != "change" or ev.get("path") != rel or ev.get("binary"):
                continue
            if ev["actor"] in HUMANISH:
                if ev["ts"] < cutoff:
                    continue
                for l in ev.get("minus", []):
                    if td.significant(l):
                        k = td.key(l)
                        removed[k] = ev["seq"]
                        added.pop(k, None)
                for l in ev.get("plus", []):
                    if td.significant(l):
                        k = td.key(l)
                        added[k] = ev["seq"]
                        removed.pop(k, None)
            elif ev.get("override"):
                for l in ev.get("minus", []):
                    added.pop(td.key(l), None)
                for l in ev.get("plus", []):
                    removed.pop(td.key(l), None)
        return added, removed

    @staticmethod
    def _verdict(rel: str, old_lines: List[str], plus: List[str], minus: List[str],
                 added: Dict[str, int], removed: Dict[str, int]) -> Verdict:
        oc, pc, mc = td.counts(old_lines), td.counts(plus), td.counts(minus)
        dropped = [k for k in added if oc[k] > 0 and mc[k] > pc[k]]
        resurrected = [k for k in removed if oc[k] == 0 and pc[k] > mc[k]]
        human = {k: added.get(k) or removed.get(k) for k in dropped + resurrected}
        return Verdict(rel, dropped, resurrected, human)  # type: ignore[arg-type]

    def check_edit(self, agent: str, rel: str, new_text: Optional[str] = None,
                   minus: Optional[List[str]] = None, plus: Optional[List[str]] = None) -> Verdict:
        """Would this proposed edit undo human lines? Pass the full new text, or minus/plus lines."""
        self.ensure()
        st = self.load_state()
        t = now()
        if st.get("allows", {}).get(rel, 0) > t:
            return Verdict(rel, [], [], {})
        cur = read_file(self.repo, rel)
        old_lines = td.to_lines(cur) or []
        if new_text is not None:
            plus, minus = td.line_delta(old_lines, new_text.splitlines())
        added, removed = self._protected(self.events(min_ts=t - float(self.cfg["protect_hours"]) * 3600), rel, t)
        # human edits not recorded yet (made since the last scan) count too
        rec = (st["manifest"].get(rel) or [None])[0]
        if cur is not None and rec and self.store.get(rec) is not None:
            from .store import blob_id
            if blob_id(cur) != rec:
                hp, hm = td.line_delta(td.to_lines(self.store.get(rec)) or [], old_lines)
                for l in hm:
                    if td.significant(l):
                        removed[td.key(l)] = 0
                        added.pop(td.key(l), None)
                for l in hp:
                    if td.significant(l):
                        added[td.key(l)] = 0
                        removed.pop(td.key(l), None)
        return self._verdict(rel, old_lines, plus or [], minus or [], added, removed)

    def allow(self, rel: str, minutes: float = 10) -> None:
        self.ensure()
        with self.repo.lock():
            st = self.load_state()
            st["allows"][rel] = now() + minutes * 60
            self.save_state(st)

    # ---------------------------------------------------------------- reverts
    def pending_reverts(self) -> List[Dict[str, Any]]:
        st = self.load_state()
        if not st["pending_reverts"]:
            return []
        by_seq = {e["seq"]: e for e in self.events(min_seq=min(st["pending_reverts"]) - 1) if e.get("kind") == "change"}
        out = []
        keep = []
        cache: Dict[str, Any] = {}
        for seq in st["pending_reverts"]:
            e = by_seq.get(seq)
            if not e or "reverts" not in e:
                continue
            if e["path"] not in cache:
                cache[e["path"]] = td.counts(td.to_lines(read_file(self.repo, e["path"])) or [])
            c = cache[e["path"]]
            dropped = [k for k in e["reverts"]["dropped"] if c[k] == 0]
            resurrected = [k for k in e["reverts"]["resurrected"] if c[k] > 0]
            if dropped or resurrected:
                keep.append(seq)
                out.append({"seq": seq, "path": e["path"], "actor": e["actor"], "ts": e["ts"],
                            "dropped": dropped, "resurrected": resurrected})
        if keep != st["pending_reverts"]:
            with self.repo.lock():
                st2 = self.load_state()
                st2["pending_reverts"] = [s for s in st2["pending_reverts"] if s in keep or s > max(st["pending_reverts"])]
                self.save_state(st2)
        return out

    def ack(self, seqs: Optional[List[int]] = None) -> int:
        with self.repo.lock():
            st = self.load_state()
            before = len(st["pending_reverts"])
            st["pending_reverts"] = [] if seqs is None else [s for s in st["pending_reverts"] if s not in seqs]
            self.save_state(st)
        return before - len(st["pending_reverts"])

    def restore(self, rel: str, whole: bool = False, seq: Optional[int] = None,
                dry_run: bool = False) -> Dict[str, Any]:
        """Undo an agent's revert of human lines (3-way), or restore the last human version of a file."""
        self.ensure()
        evs = [e for e in self.events() if e.get("kind") == "change" and e["path"] == rel]
        cur = read_file(self.repo, rel)
        if whole:
            human = [e for e in evs if e["actor"] in HUMANISH and (seq is None or e["seq"] == seq)]
            if not human:
                raise LookupError(f"no human edit of {rel} in the journal")
            target = human[-1]
            if target["after"] is None:
                result = None
            else:
                result = self.store.get(target["after"])
                if result is None:
                    raise LookupError(f"content of #{target['seq']} is not stored (file too large?)")
            conflicts = 0
        else:
            cand = [e for e in evs if "reverts" in e and (seq is None or e["seq"] == seq)]
            if seq is None:
                pend = {r["seq"] for r in self.pending_reverts()}
                cand = [e for e in cand if e["seq"] in pend] or cand
            if not cand:
                raise LookupError(f"no agent revert of human lines recorded for {rel}; use --whole to restore the last human version")
            target = cand[-1]
            base = self.store.get(target["after"]) if target["after"] else b""
            other = self.store.get(target["before"]) if target["before"] else b""
            if base is None or other is None:
                raise LookupError(f"content of #{target['seq']} is not stored")
            current = cur if cur is not None else b""
            fixed = partial_undo(other, base, target["reverts"]["dropped"], target["reverts"]["resurrected"])
            if current == base:
                result, conflicts = fixed, 0
            else:
                result, conflicts = merge3(current, base, fixed)
        out = {"path": rel, "seq": target["seq"], "conflicts": conflicts, "changed": result != cur}
        if dry_run:
            out["content"] = (result or b"").decode("utf-8", "replace")
            return out
        full = self.repo.root / rel
        if result is None:
            if full.exists():
                full.unlink()
        else:
            full.parent.mkdir(parents=True, exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(result)
        self.record("human", [rel], note=f"restore #{target['seq']}")
        if not whole:
            self.ack([target["seq"]])
        return out

    # ------------------------------------------------------------------ blame
    def blame(self, rel: str) -> List[Tuple[int, str, Optional[Dict[str, Any]]]]:
        who: Dict[str, Dict[str, Any]] = {}
        for e in self.events():
            if e.get("kind") != "change" or e["path"] != rel or e.get("binary"):
                continue
            if e["op"] == "D":
                who.clear()
                continue
            for l in e.get("plus", []):
                who[td.key(l)] = {"actor": e["actor"], "ts": e["ts"], "seq": e["seq"]}
        lines = td.to_lines(read_file(self.repo, rel))
        if lines is None:
            raise ValueError(f"{rel} is binary or too large")
        return [(i + 1, l, who.get(td.key(l)) if l.strip() else None) for i, l in enumerate(lines)]


def partial_undo(before: bytes, after: bytes, dropped: List[str], resurrected: List[str]) -> bytes:
    """``after`` with only the hunks that removed human lines (or revived deleted ones) put back."""
    import difflib
    b = before.decode("utf-8", "surrogateescape").splitlines(True)
    a = after.decode("utf-8", "surrogateescape").splitlines(True)
    drop, res = set(dropped), set(resurrected)
    out: List[str] = []
    sm = difflib.SequenceMatcher(None, [td.key(x) for x in b], [td.key(x) for x in a], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out += a[j1:j2]
            continue
        bseg, aseg = b[i1:i2], a[j1:j2]
        n = min(len(bseg), len(aseg))
        for x, y in zip(bseg[:n], aseg[:n]):  # changed lines, paired in order
            out.append(x if (td.key(x) in drop or td.key(y) in res) else y)
        out += [x for x in bseg[n:] if td.key(x) in drop]      # deleted lines: bring back human ones
        out += [y for y in aseg[n:] if td.key(y) not in res]   # inserted lines: drop revived ones
    return "".join(out).encode("utf-8", "surrogateescape")


def merge3(current: bytes, base: bytes, other: bytes) -> Tuple[bytes, int]:
    """Apply base->other on top of current with `git merge-file`."""
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, data in (("current", current), ("agent", base), ("human", other)):
            p = os.path.join(d, name)
            with open(p, "wb") as fh:
                fh.write(data)
            paths.append(p)
        try:
            r = subprocess.run(["git", "merge-file", "-p", "-L", "current", "-L", "agent revert", "-L", "human",
                                *paths], capture_output=True)
        except FileNotFoundError:
            raise RuntimeError("git is needed for a 3-way restore; use --whole instead")
        if r.returncode < 0:
            raise RuntimeError(r.stderr.decode("utf-8", "replace"))
        return r.stdout, r.returncode
