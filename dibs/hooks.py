"""Adapters between agent hook payloads (Claude Code, Codex, Cursor, Gemini CLI) and dibs.

Every handler fails open: an error is logged and the agent continues.
"""
from __future__ import annotations

import json
import os
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

from .core import Dibs, Verdict
from .repo import Repo
from .store import read_file

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "write_file", "replace", "apply_patch",
              "StrReplace", "Delete", "edit_file", "search_replace", "create_file"}
SHELL_TOOLS = {"Bash", "Shell", "run_shell_command", "exec_command", "shell", "local_shell"}


# --------------------------------------------------------------- tool inputs
def _path_of(ti: Dict[str, Any]) -> Optional[str]:
    for k in ("file_path", "path", "notebook_path", "target_file", "filePath", "filename"):
        v = ti.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def _apply(cur: str, old: str, new: str, count: int) -> Optional[str]:
    if old == "":
        return None
    if old not in cur:
        return None
    return cur.replace(old, new) if count < 0 else cur.replace(old, new, count)


def proposed_text(tool: str, ti: Dict[str, Any], cur: Optional[str]) -> Optional[str]:
    """Best-effort new file content for an edit-tool call; None when unknown."""
    for k in ("content", "contents", "file_text", "new_file_content"):
        if isinstance(ti.get(k), str) and tool not in ("Edit", "replace"):
            return ti[k]
    if cur is None:
        return None
    edits = ti.get("edits")
    if isinstance(edits, list) and edits:
        text = cur
        for e in edits:
            if not isinstance(e, dict):
                return None
            r = _apply(text, e.get("old_string", ""), e.get("new_string", ""), -1 if e.get("replace_all") else 1)
            if r is None:
                return None
            text = r
        return text
    if isinstance(ti.get("old_string"), str) and isinstance(ti.get("new_string"), str):
        count = -1 if ti.get("replace_all") else int(ti.get("expected_replacements") or 1)
        if count > 1:
            count = -1
        return _apply(cur, ti["old_string"], ti["new_string"], count)
    return None


def parse_patch(text: str) -> List[Dict[str, Any]]:
    """Parse Codex apply_patch text into per-file minus/plus lines."""
    files: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None
    for line in text.splitlines():
        for marker, op in (("*** Add File: ", "A"), ("*** Update File: ", "M"), ("*** Delete File: ", "D")):
            if line.startswith(marker):
                cur = {"op": op, "path": line[len(marker):].strip(), "minus": [], "plus": []}
                files.append(cur)
                break
        else:
            if cur is None:
                continue
            if line.startswith("*** Move to: "):
                cur["move_to"] = line[len("*** Move to: "):].strip()
            elif line.startswith("***") or line.startswith("@@"):
                continue
            elif line.startswith("+"):
                cur["plus"].append(line[1:])
            elif line.startswith("-") and cur["op"] == "M":
                cur["minus"].append(line[1:])
    return files


# ----------------------------------------------------------------- handlers
class Ctx:
    def __init__(self, tool: str, event: str, payload: Dict[str, Any]):
        self.tool = tool
        self.event = event
        self.p = payload
        roots = payload.get("workspace_roots") or []
        self.cwd = payload.get("cwd") or (roots[0] if roots else None) or os.environ.get(
            "CLAUDE_PROJECT_DIR") or os.environ.get("GEMINI_PROJECT_DIR") or os.environ.get("CURSOR_PROJECT_DIR") or os.getcwd()
        self.dibs = Dibs(Repo.discover(self.cwd))
        self.agent = os.environ.get("DIBS_AGENT") or tool
        self.session = payload.get("session_id") or payload.get("conversation_id")
        self.tool_name = payload.get("tool_name") or ""
        ti = payload.get("tool_input")
        if isinstance(ti, str):
            try:
                ti = json.loads(ti)
            except ValueError:
                ti = {"command": ti}
        self.ti: Dict[str, Any] = ti if isinstance(ti, dict) else {}

    def rel(self, path: str) -> Optional[str]:
        return self.dibs.repo.rel(path, self.cwd)

    def edit_paths(self) -> Optional[List[str]]:
        """Repo paths an edit tool touched; None means 'scan everything'."""
        if self.tool_name == "apply_patch":
            paths = []
            for f in parse_patch(str(self.ti.get("command") or self.ti.get("input") or "")):
                for p in (f["path"], f.get("move_to")):
                    r = self.rel(p) if p else None
                    if r:
                        paths.append(r)
            return paths or None
        p = _path_of(self.ti) or self.p.get("file_path")
        if p:
            r = self.rel(p)
            return [r] if r else []
        return None

    def mode(self) -> str:
        m = str(self.dibs.cfg.get("guard", "auto"))
        if m == "auto":
            return "ask" if self.tool == "claude" else "deny"
        if m == "ask" and self.tool != "claude":
            return "deny"
        return m

    def verdicts(self) -> List[Verdict]:
        """Run the revert guard on a pending edit-tool call."""
        out: List[Verdict] = []
        if self.tool_name == "apply_patch":
            for f in parse_patch(str(self.ti.get("command") or self.ti.get("input") or "")):
                rel = self.rel(f["path"])
                if not rel:
                    continue
                if f["op"] == "D":
                    cur = read_file(self.dibs.repo, rel)
                    minus = (cur or b"").decode("utf-8", "replace").splitlines()
                    out.append(self.dibs.check_edit(self.agent, rel, minus=minus, plus=[]))
                elif f["op"] == "M":
                    out.append(self.dibs.check_edit(self.agent, rel, minus=f["minus"], plus=f["plus"]))
            return out
        p = _path_of(self.ti) or self.p.get("file_path")
        if not p:
            return out
        rel = self.rel(p)
        if not rel:
            return out
        raw = read_file(self.dibs.repo, rel)
        cur = raw.decode("utf-8", "replace") if raw is not None else None
        if self.tool_name in ("Delete",):
            out.append(self.dibs.check_edit(self.agent, rel, minus=(cur or "").splitlines(), plus=[]))
            return out
        new = proposed_text(self.tool_name, self.ti, cur)
        if new is not None:
            out.append(self.dibs.check_edit(self.agent, rel, new_text=new))
        return out


def _revert_note(evs: List[Dict[str, Any]], agent: str) -> str:
    notes = []
    for e in evs:
        r = e.get("reverts")
        if not r:
            continue
        ks = (r["dropped"] + r["resurrected"])[:5]
        notes.append(f"[dibs] Your change to {e['path']} undid lines the human edited by hand: "
                     + " | ".join(ks)
                     + f". Unless the user asked for this, put the human's version back (or ask them to run `dibs restore {e['path']}`).")
    return "\n".join(notes)


def _ctx_out(tool: str, event: str, text: str) -> Dict[str, Any]:
    if not text:
        return {}
    if tool == "cursor":
        return {"additional_context": text}
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def _deny(c: Ctx, msg: str, mode: str) -> Tuple[Dict[str, Any], int]:
    if c.tool == "cursor":
        return {"permission": "deny", "user_message": "dibs blocked an edit that would undo your manual changes.",
                "agent_message": msg}, 0
    if c.tool == "gemini":
        return {"decision": "deny", "reason": msg}, 0
    out: Dict[str, Any] = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": mode,
                                                  "permissionDecisionReason": msg}}
    if c.tool == "claude" and mode == "ask":
        # The permission dialog does not show the hook's reason, so tell the user why it appeared.
        out["systemMessage"] = user_summary(c, msg)
    return out, 0


def user_summary(c: "Ctx", msg: str) -> str:
    lines = [l.strip() for l in msg.splitlines() if l.startswith("  ")][:3]
    return ("dibs: this edit would undo lines you changed by hand"
            + (": " + " | ".join(lines) if lines else "")
            + ". Answer No to keep your version (or run `dibs allow <file>` if the change is wanted).")


def handle(tool: str, event: str, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    c = Ctx(tool, event, payload)
    d = c.dibs
    ev = event.lower()

    # turn start ---------------------------------------------------------
    if ev in ("userpromptsubmit", "beforeagent", "beforesubmitprompt"):
        brief = d.turn_start(c.agent, c.session)
        if tool == "cursor":
            # Cursor 2026.x passes additional_context from beforeSubmitPrompt to the model; older
            # builds ignore it, so the brief is also handed over once at the first postToolUse.
            return ({"continue": True, "additional_context": brief} if brief else {"continue": True}), 0
        return _ctx_out(tool, "BeforeAgent" if tool == "gemini" else "UserPromptSubmit", brief), 0

    # before an edit -------------------------------------------------------
    if ev in ("pretooluse", "beforetool"):
        allow = {"permission": "allow"} if tool == "cursor" else {}
        if c.tool_name not in EDIT_TOOLS:
            return allow, 0
        mode = c.mode()
        if mode in ("off", "warn"):
            return allow, 0
        bad = [v for v in c.verdicts() if v.reverts]
        if not bad:
            return allow, 0
        return _deny(c, "\n\n".join(v.message(c.agent) for v in bad), mode)

    # after a tool -------------------------------------------------------
    if ev in ("posttooluse", "aftertool", "afterfileedit", "aftershellexecution"):
        notes: List[str] = []
        if tool == "cursor" and ev == "posttooluse":
            pending = d.take_pending_brief(c.agent)
            if pending:
                notes.append("[dibs] (repeating the turn brief in case your client did not show it with the prompt)\n"
                             + pending)
        if ev == "afterfileedit":
            paths = c.edit_paths()
            evs = d.touch(c.agent, paths if paths is not None else None, c.session) if paths != [] else []
        elif c.tool_name in EDIT_TOOLS:
            paths = c.edit_paths()
            evs = d.touch(c.agent, paths, c.session) if paths else []
        elif c.tool_name in SHELL_TOOLS or ev == "aftershellexecution":
            evs = d.touch(c.agent, None, c.session)
        else:
            evs = []
        warn = _revert_note(evs, c.agent)
        if warn:
            notes.append(warn)
        if ev in ("afterfileedit", "aftershellexecution"):
            return {}, 0
        return _ctx_out(tool, "AfterTool" if tool == "gemini" else "PostToolUse", "\n".join(notes)), 0

    # turn end -----------------------------------------------------------
    if ev in ("stop", "afteragent", "sessionend", "subagentstop"):
        if ev != "subagentstop":
            d.turn_end(c.agent, session=c.session)
        return {}, 0

    return {}, 0


def neutral(tool: str, event: str) -> Dict[str, Any]:
    ev = event.lower()
    if tool == "cursor" and ev == "pretooluse":
        return {"permission": "allow"}
    if tool == "cursor" and ev == "beforesubmitprompt":
        return {"continue": True}
    return {}


def from_cursor(payload: Dict[str, Any]) -> bool:
    """Cursor also runs hooks from .claude/settings.json ("third-party hooks"); spot its payloads."""
    return bool(payload.get("cursor_version") or os.environ.get("CURSOR_VERSION"))


def cursor_has_own_hooks(cwd: Optional[str]) -> bool:
    try:
        repo = Repo.discover(cwd)
        data = json.loads((repo.root / ".cursor" / "hooks.json").read_text("utf-8"))
        return "dibs" in json.dumps(data.get("hooks", {}))
    except Exception:
        return False


CURSOR_EVENTS = {"userpromptsubmit": "beforeSubmitPrompt", "pretooluse": "preToolUse", "posttooluse": "postToolUse",
                 "stop": "stop", "sessionend": "sessionEnd"}


def main(tool: str, event: str, stdin_text: str) -> Tuple[str, int]:
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        if tool == "claude" and from_cursor(payload):
            # A Claude Code hook that Cursor is running: never attribute Cursor's work to Claude.
            cwd = payload.get("cwd") or (payload.get("workspace_roots") or [None])[0]
            if cursor_has_own_hooks(cwd):
                return json.dumps({}), 0  # dibs' Cursor hooks handle this event
            tool = "cursor"
            event = CURSOR_EVENTS.get(event.lower(), payload.get("hook_event_name") or event)
        out, code = handle(tool, event, payload)
    except Exception:  # fail open, but leave a trace
        try:
            repo = Repo.discover()
            repo.state_dir.mkdir(parents=True, exist_ok=True)
            with open(repo.state_dir / "hook-errors.log", "a", encoding="utf-8") as fh:
                fh.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {tool} {event}\n{traceback.format_exc()}\n")
        except Exception:
            pass
        out, code = neutral(tool, event), 0
    return json.dumps(out), code
