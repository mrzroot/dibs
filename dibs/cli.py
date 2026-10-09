"""Command line interface."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from typing import List, Optional

from . import __version__
from .core import Dibs, ago
from .repo import AGENTS, HUMANISH, Repo
from .sync import sync_status

USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def warn(t: str) -> str:
    return c("!", "33") + " " + t


def ok(t: str) -> str:
    return c("✓", "32") + " " + t


def actor_c(a: str) -> str:
    return c(a, "36" if a in HUMANISH else "35")


def hhmm(ts: float) -> str:
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


# ------------------------------------------------------------------- commands
def cmd_init(a: argparse.Namespace) -> int:
    from .install import detect, init
    repo = Repo.discover()
    if a.all:
        agents = list(AGENTS)
    elif a.agents:
        agents = [x.strip() for x in a.agents.split(",") if x.strip()]
        bad = [x for x in agents if x not in AGENTS]
        if bad:
            print(f"unknown agent(s): {', '.join(bad)}; choose from {', '.join(AGENTS)}", file=sys.stderr)
            return 2
    else:
        agents = detect(repo.root)
    d = Dibs(repo)
    d.ensure()
    done = init(repo, agents, base=a.command, git_hook=not a.no_git_hook, agents_md=not a.no_agents_md)
    d.absorb([p for p in (".claude/settings.json", ".codex/hooks.json", ".gemini/settings.json", ".cursor/hooks.json",
                          ".cursor/rules/dibs.mdc", ".github/copilot-instructions.md", ".vscode/mcp.json", "AGENTS.md")])
    print(c("dibs is watching", "1") + f" {repo.root}")
    print(f"  journal: {os.path.relpath(repo.state_dir, repo.root)}/ (never committed)")
    print(f"  agents:  {', '.join(agents)}")
    for x in done:
        print(f"  wrote    {x}")
    if "aider" in agents:
        print("  aider:   no hook API; run it as `dibs run --agent aider -- aider` (or rely on AGENTS.md)")
    if not repo.is_git:
        print(warn("not a git repository: dibs still works, but nothing here is versioned or backed up"))
    print("Next: `dibs status` any time; `dibs watch` in a terminal gives exact timestamps for your edits.")
    return 0


def cmd_uninstall(a: argparse.Namespace) -> int:
    from .install import uninstall
    import shutil
    repo = Repo.discover()
    for x in uninstall(repo):
        print(f"removed dibs from {x}")
    if a.purge and repo.state_dir.exists():
        shutil.rmtree(repo.state_dir)
        print(f"deleted {repo.state_dir}")
    return 0


def _print_sync(s: dict) -> None:
    for w in s["warnings"]:
        print("  " + warn(w))
    for o in s["ok"]:
        print("  " + ok(o))


def cmd_status(a: argparse.Namespace) -> int:
    d = Dibs()
    d.ensure()
    st0 = d.load_state()
    d.record(d._pending_actor(st0, None))
    st = d.load_state()
    s = sync_status(d.repo)
    evs = [e for e in d.events() if e.get("kind") == "change"]
    reverts = d.pending_reverts()
    if a.json:
        agents = {}
        for name, ag in st["agents"].items():
            unseen = sorted({e["path"] for e in evs if e["seq"] > ag.get("seen_seq", 0) and e["actor"] in HUMANISH})
            agents[name] = {"active": bool(ag.get("active")), "started": ag.get("started"), "ended": ag.get("ended"),
                            "unseen_human_files": unseen}
        print(json.dumps({"root": str(d.repo.root), "sync": s, "agents": agents, "reverts": reverts,
                          "recent": evs[-10:]}, indent=2, default=str))
        return 0
    branch = f"  ({s.get('branch') or 'no branch'})" if s.get("git") else ""
    print(c("dibs", "1") + f" · {d.repo.root}{branch}")
    print(c("\nSync", "1"))
    _print_sync(s)
    print(c("\nAgents", "1"))
    if not st["agents"]:
        print("  no agent turns recorded yet (run `dibs init` to wire the hooks)")
    for name, ag in sorted(st["agents"].items()):
        if ag.get("active"):
            state = c("working", "33") + f"  since {ago(ag.get('started', 0))}"
        else:
            state = "idle     " + (f"  last turn ended {ago(ag['ended'])}" if ag.get("ended") else "")
        unseen = sorted({e["path"] for e in evs if e["seq"] > ag.get("seen_seq", 0) and e["actor"] in HUMANISH})
        extra = f"  · {len(unseen)} file(s) with your edits it has not seen yet" if unseen else "  · up to date with your edits"
        print(f"  {name:<8} {state}{extra}")
    if reverts:
        print(c("\nReverted human lines", "1;31"))
        for r in reverts:
            ks = (r["dropped"] + r["resurrected"])[:2]
            print(f"  #{r['seq']} {r['path']} by {r['actor']} {ago(r['ts'])}: " + " | ".join(ks))
            print(f"      → dibs restore {r['path']}    (or `dibs ack {r['seq']}` if it was wanted)")
    print(c("\nRecent changes", "1"))
    if not evs:
        print("  none yet")
    for e in evs[-a.n:]:
        _print_event(e)
    return 0


def _print_event(e: dict) -> None:
    flag = c("  REVERTED HUMAN LINES", "31") if e.get("reverts") else ""
    note = f"  ({e['note']})" if e.get("note") else ""
    lines = "" if e.get("binary") else f" +{e.get('np', 0)} −{e.get('nm', 0)}"
    who = actor_c(f"{e['actor']:<8}")
    print(f"  #{e['seq']:<4} {hhmm(e['ts'])}  {who} {e['op']} {e['path']}{lines}{note}{flag}")


def cmd_sync(a: argparse.Namespace) -> int:
    d = Dibs()
    s = sync_status(d.repo, fetch=a.fetch)
    if a.json:
        print(json.dumps(s, indent=2))
    else:
        _print_sync(s)
    return 1 if (a.strict and s["warnings"]) else 0


def cmd_log(a: argparse.Namespace) -> int:
    d = Dibs()
    evs = [e for e in d.events() if e.get("kind") == "change"]
    if a.actor:
        evs = [e for e in evs if e["actor"] == a.actor]
    if a.path:
        rel = d.repo.rel(a.path) or a.path
        evs = [e for e in evs if e["path"] == rel]
    evs = evs[-a.n:]
    if a.json:
        print(json.dumps(evs, indent=2, ensure_ascii=False))
        return 0
    for e in evs:
        _print_event(e)
        if a.diff and not e.get("binary"):
            for l in e.get("minus", [])[:20]:
                print("        " + c("- " + l, "31"))
            for l in e.get("plus", [])[:20]:
                print("        " + c("+ " + l, "32"))
    if not evs:
        print("no changes recorded yet")
    return 0


def cmd_blame(a: argparse.Namespace) -> int:
    d = Dibs()
    d.ensure()
    rel = d.repo.rel(a.path)
    if not rel:
        print("path is outside the repository", file=sys.stderr)
        return 2
    st = d.load_state()
    d.record(d._pending_actor(st, None), [rel])
    rows = d.blame(rel)
    if a.json:
        print(json.dumps([{"line": n, "text": t, **(w or {})} for n, t, w in rows], indent=2, ensure_ascii=False))
        return 0
    for n, text, w in rows:
        who = f"{w['actor']:<8} {hhmm(w['ts'])}" if w else f"{'·':<8} {'':<11}"
        print(f"{actor_c(who) if w else c(who, '2')} {n:>5}│ {text}")
    return 0


def cmd_restore(a: argparse.Namespace) -> int:
    d = Dibs()
    rel = d.repo.rel(a.path)
    if not rel:
        print("path is outside the repository", file=sys.stderr)
        return 2
    try:
        r = d.restore(rel, whole=a.whole, seq=a.event, dry_run=a.dry_run)
    except (LookupError, RuntimeError) as e:
        print(f"dibs: {e}", file=sys.stderr)
        return 1
    if a.dry_run:
        sys.stdout.write(r["content"])
        return 0
    if r["conflicts"]:
        print(warn(f"restored {rel} from #{r['seq']} with {r['conflicts']} conflict(s): resolve the <<<<<<< markers"))
        return 1
    print(ok(f"restored the human lines in {rel} (undoing #{r['seq']})" if not a.whole
             else f"restored {rel} to the human version from #{r['seq']}"))
    return 0


def cmd_ack(a: argparse.Namespace) -> int:
    d = Dibs()
    n = d.ack(None if a.all or not a.seq else a.seq)
    print(f"acknowledged {n} revert(s)")
    return 0


def cmd_allow(a: argparse.Namespace) -> int:
    d = Dibs()
    rel = d.repo.rel(a.path)
    if not rel:
        print("path is outside the repository", file=sys.stderr)
        return 2
    d.allow(rel, a.minutes)
    print(f"agents may change human lines in {rel} for the next {a.minutes:g} minutes")
    return 0


def cmd_brief(a: argparse.Namespace) -> int:
    d = Dibs()
    if a.peek:
        st = d.load_state()
        text = d.render_brief(a.agent, (st["agents"].get(a.agent) or {}).get("seen_seq"))
    else:
        text = d.turn_start(a.agent)
    print(text or "[dibs] Nothing changed outside your session since your last turn.")
    return 0


def cmd_done(a: argparse.Namespace) -> int:
    d = Dibs()
    evs = d.turn_end(a.agent, full=True)
    print(f"[dibs] {len(evs)} change(s) attributed to {a.agent}.")
    for e in evs:
        if e.get("reverts"):
            print(warn(f"{e['path']}: this undid human lines: " + " | ".join((e['reverts']['dropped'] + e['reverts']['resurrected'])[:3])))
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        print("usage: dibs run --agent NAME -- command ...", file=sys.stderr)
        return 2
    d = Dibs()
    brief = d.turn_start(a.agent)
    bf = d.repo.state_dir / f"brief-{a.agent}.md"
    bf.write_text((brief or "[dibs] No changes by the human or other agents since your last turn.") + "\n", "utf-8")
    if brief:
        print(brief, file=sys.stderr)
    sys.stderr.flush()
    sys.stdout.flush()
    exe = os.path.basename(cmd[0]).lower()
    if brief and exe in ("aider", "aider.exe") and "--read" not in cmd:
        # aider has no hooks, but it accepts read-only context files: hand it the brief that way
        cmd = [cmd[0], "--read", str(bf)] + list(cmd[1:])
    env = dict(os.environ, DIBS_AGENT=a.agent, DIBS_BRIEF_FILE=str(bf))
    try:
        code = subprocess.call(cmd, env=env)
    except FileNotFoundError:
        print(f"dibs: command not found: {cmd[0]}", file=sys.stderr)
        code = 127
    except KeyboardInterrupt:
        code = 130
    finally:
        evs = d.turn_end(a.agent, full=True)
        print(f"[dibs] {len(evs)} change(s) attributed to {a.agent}.", file=sys.stderr)
        bad = [e for e in evs if e.get("reverts")]
        for e in bad:
            ks = (e["reverts"]["dropped"] + e["reverts"]["resurrected"])[:3]
            print(warn(f"{a.agent} undid lines you edited by hand in {e['path']} (#{e['seq']}): " + " | ".join(ks)),
                  file=sys.stderr)
        if bad:
            print(f"  → dibs restore {bad[0]['path']}    (or `dibs ack` if it was wanted)", file=sys.stderr)
    return code


def cmd_record(a: argparse.Namespace) -> int:
    d = Dibs()
    paths = [p for p in (d.repo.rel(x) for x in a.paths) if p] if a.paths else None
    evs = d.record(a.actor, paths)
    for e in evs:
        _print_event(e)
    return 0


def cmd_watch(a: argparse.Namespace) -> int:
    """Poll the tree and record changes made outside agent turns as the human's, with exact times.

    Robust for long runs: errors are reported once and retried, a busy lock is skipped, a stale
    "active" agent (crashed without its stop hook) stops pausing the watcher, and the poll interval
    backs off on big repositories so a scan never takes more than ~1/3 of the time.
    """
    d = Dibs()
    d.ensure()
    print(f"dibs watching {d.repo.root} (Ctrl-C to stop)", flush=True)
    interval = max(0.2, float(a.interval))
    last_err = None
    rounds = 0
    try:
        while True:
            t0 = time.time()
            try:
                if not d.repo.state_dir.parent.exists():
                    print(warn("repository is gone; stopping"), file=sys.stderr)
                    return 1
                st = d.load_state()
                busy = [n for n, ag in st["agents"].items()
                        if ag.get("active") and time.time() - ag.get("started", 0) < float(a.agent_timeout)]
                if not busy:  # during an agent turn the hooks decide who changed what
                    for e in d.record("human"):
                        _print_event(e)
                    sys.stdout.flush()
                last_err = None
            except TimeoutError:
                pass  # a hook holds the lock; try again next round
            except Exception as ex:  # keep watching; report each distinct error once
                msg = f"{type(ex).__name__}: {ex}"
                if msg != last_err:
                    print(warn(f"watch error (will retry): {msg}"), file=sys.stderr, flush=True)
                    last_err = msg
            rounds += 1
            if a.rounds and rounds >= a.rounds:
                return 0
            took = time.time() - t0
            time.sleep(max(interval, took * 2))
    except KeyboardInterrupt:
        return 0


def cmd_doctor(a: argparse.Namespace) -> int:
    from .doctor import run
    checks = run(Repo.discover())
    if a.json:
        print(json.dumps([{"level": l, "message": m} for l, m in checks], indent=2))
    else:
        marks = {"ok": c("✓", "32"), "warn": c("!", "33"), "fail": c("✗", "31"), "info": c("·", "2")}
        for level, msg in checks:
            print(f"  {marks[level]} {msg}")
    return 1 if any(l == "fail" for l, _ in checks) else 0


def cmd_hook(a: argparse.Namespace) -> int:
    from .hooks import main as hook_main
    raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode()
    out, code = hook_main(a.tool, a.event, raw.decode("utf-8", "replace"))
    sys.stdout.write(out + "\n")
    return code


def cmd_mcp(a: argparse.Namespace) -> int:
    from .mcp import Server
    import io
    inp = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8", errors="replace") if hasattr(sys.stdin, "buffer") else sys.stdin
    Server(a.agent, a.root).serve(inp, sys.stdout)
    return 0


def cmd_guard(a: argparse.Namespace) -> int:
    d = Dibs()
    if a.pre_commit:
        mode = d.cfg.get("precommit", "block")
        if mode == "off" or os.environ.get("DIBS_ALLOW_REVERTS"):
            return 0
        from .repo import git_out
        staged = set((git_out(["diff", "--cached", "--name-only", "-z"], d.repo.root) or "").split("\0"))
        bad = [r for r in d.pending_reverts() if r["path"] in staged]
        if not bad:
            return 0
        print("dibs: this commit contains files where an AI agent undid lines you edited by hand:", file=sys.stderr)
        for r in bad:
            print(f"  #{r['seq']} {r['path']} ({r['actor']}): " + " | ".join((r["dropped"] + r["resurrected"])[:3]), file=sys.stderr)
        print("Restore them with `dibs restore <path>`, or accept with `dibs ack` (or DIBS_ALLOW_REVERTS=1 git commit).",
              file=sys.stderr)
        return 1 if mode == "block" else 0
    if not a.path or a.new is None:
        print("usage: dibs guard --pre-commit | dibs guard PATH --new FILE", file=sys.stderr)
        return 2
    rel = d.repo.rel(a.path)
    if not rel:
        return 2
    new = sys.stdin.read() if a.new == "-" else open(a.new, encoding="utf-8").read()
    v = d.check_edit(a.agent, rel, new_text=new)
    print(v.message(a.agent) if v.reverts else "ok: keeps every human change")
    return 1 if v.reverts else 0


def cmd_config(a: argparse.Namespace) -> int:
    repo = Repo.discover()
    if a.key and a.value is not None:
        val: object = a.value
        if a.value.lower() in ("true", "false"):
            val = a.value.lower() == "true"
        else:
            try:
                val = int(a.value)
            except ValueError:
                pass
        repo.set_config(a.key, val)
    cfg = repo.config()
    if a.key and a.value is None:
        print(cfg.get(a.key))
    else:
        for k, v in cfg.items():
            print(f"{k} = {v}")
    return 0


# --------------------------------------------------------------------- parser
def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="dibs", description="Call dibs on your edits: keep AI coding agents from "
                                "overwriting what you changed by hand, and see what is not pushed yet.")
    p.add_argument("--version", action="version", version=f"dibs {__version__}")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("init", help="start tracking and wire hooks for your agents")
    s.add_argument("--agents", help=f"comma list: {','.join(AGENTS)} (default: detect)")
    s.add_argument("--all", action="store_true", help="wire every supported agent")
    s.add_argument("--command", default="dibs", help="how hooks call dibs (default: dibs)")
    s.add_argument("--no-git-hook", action="store_true")
    s.add_argument("--no-agents-md", action="store_true")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("uninstall", help="remove dibs hooks and instruction blocks")
    s.add_argument("--purge", action="store_true", help="also delete the journal")
    s.set_defaults(fn=cmd_uninstall)

    s = sub.add_parser("status", help="sync state, agents, reverted lines, recent changes")
    s.add_argument("-n", type=int, default=8)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("sync", help="what is uncommitted, unpushed or on no remote")
    s.add_argument("--fetch", action="store_true", help="git fetch first")
    s.add_argument("--json", action="store_true")
    s.add_argument("--strict", action="store_true", help="exit 1 when there is anything to warn about")
    s.set_defaults(fn=cmd_sync)

    s = sub.add_parser("log", help="attributed change history")
    s.add_argument("-n", type=int, default=30)
    s.add_argument("--actor")
    s.add_argument("--path")
    s.add_argument("--diff", action="store_true", help="show changed lines")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_log)

    s = sub.add_parser("blame", help="who last wrote each line (human or which agent)")
    s.add_argument("path")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_blame)

    s = sub.add_parser("restore", help="bring back human lines an agent reverted")
    s.add_argument("path")
    s.add_argument("--whole", action="store_true", help="restore the whole file to the last human version")
    s.add_argument("--event", type=int, help="journal event (#seq) to undo or restore")
    s.add_argument("--dry-run", action="store_true", help="print the result instead of writing it")
    s.set_defaults(fn=cmd_restore)

    s = sub.add_parser("ack", help="accept reverts as intended")
    s.add_argument("seq", nargs="*", type=int)
    s.add_argument("--all", action="store_true")
    s.set_defaults(fn=cmd_ack)

    s = sub.add_parser("allow", help="let agents change human lines in a file for a while")
    s.add_argument("path")
    s.add_argument("--minutes", type=float, default=10)
    s.set_defaults(fn=cmd_allow)

    s = sub.add_parser("brief", help="start an agent turn and print the human edits it has not seen")
    s.add_argument("--agent", required=True)
    s.add_argument("--peek", action="store_true", help="do not start a turn")
    s.set_defaults(fn=cmd_brief)

    s = sub.add_parser("done", help="end an agent turn and attribute its changes")
    s.add_argument("--agent", required=True)
    s.set_defaults(fn=cmd_done)

    s = sub.add_parser("run", help="run an agent command as one turn: dibs run --agent aider -- aider")
    s.add_argument("--agent", required=True)
    s.add_argument("cmd", nargs=argparse.REMAINDER)
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("record", help="attribute current changes now (default actor: human)")
    s.add_argument("paths", nargs="*")
    s.add_argument("--actor", default="human")
    s.set_defaults(fn=cmd_record)

    s = sub.add_parser("watch", help="record your edits continuously with exact timestamps")
    s.add_argument("--interval", type=float, default=2.0)
    s.add_argument("--agent-timeout", type=float, default=3 * 3600,
                   help="treat an agent turn older than this many seconds as finished (default 3 h)")
    s.add_argument("--rounds", type=int, default=0, help=argparse.SUPPRESS)
    s.set_defaults(fn=cmd_watch)

    s = sub.add_parser("doctor", help="check that each agent will really run the dibs hooks")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("hook", help="entry point for agent hooks (reads JSON on stdin)")
    s.add_argument("tool", choices=["claude", "codex", "cursor", "gemini"])
    s.add_argument("event")
    s.set_defaults(fn=cmd_hook)

    s = sub.add_parser("mcp", help="run the MCP server on stdio")
    s.add_argument("--agent", default="mcp")
    s.add_argument("--root")
    s.set_defaults(fn=cmd_mcp)

    s = sub.add_parser("guard", help="revert checks: pre-commit, or a proposed file version")
    s.add_argument("path", nargs="?")
    s.add_argument("--new", help="file with the proposed content (- for stdin)")
    s.add_argument("--agent", default="agent")
    s.add_argument("--pre-commit", action="store_true")
    s.set_defaults(fn=cmd_guard)

    s = sub.add_parser("config", help="show or set settings (guard, precommit, protect_hours, …)")
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.set_defaults(fn=cmd_config)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass
    args = parser().parse_args(argv)
    if not getattr(args, "fn", None):
        parser().print_help()
        return 0
    try:
        return int(args.fn(args) or 0)
    except TimeoutError as e:
        print(str(e), file=sys.stderr)
        return 3
