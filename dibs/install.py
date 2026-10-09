"""`dibs init` / `dibs uninstall`: wire dibs into each agent's hooks and instruction files."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional

from .repo import AGENTS, Repo, git_out

START, END = "<!-- dibs:start -->", "<!-- dibs:end -->"

GUIDE = """## dibs: keep the human's edits

This repository uses [dibs](https://github.com/mrzroot/dibs) to track which changes the human made by hand
and which an AI agent made.

- Start every task by running `dibs brief --agent {agent}` (skip this if dibs hooks already show you a
  "[dibs]" brief). Lines the human changed since your last turn are intentional: read the current file,
  build on them, and never revert or "fix" them back to your earlier version unless the user asks.
- If dibs reports that an edit would undo human lines, keep the human's version. Only when the user
  explicitly asked for that change, run `dibs allow <path>` and retry.
- When you finish, run `dibs done --agent {agent}` and mention anything `dibs sync` reports as
  uncommitted or unpushed instead of discarding it.
"""


def _hook_cmd(base: str, tool: str, event: str) -> str:
    return f"{base} hook {tool} {event}"


def _load_json(p: Path) -> Dict[str, Any]:
    try:
        data = json.loads(p.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_json(p: Path, data: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", "utf-8")


def _is_dibs(cmd: Any) -> bool:
    return isinstance(cmd, str) and " hook " in cmd and "dibs" in cmd


def _strip_nested(hooks: Dict[str, Any]) -> None:
    """Remove dibs handlers from a Claude/Codex/Gemini style hooks object."""
    for ev in list(hooks):
        groups = []
        for g in hooks[ev] or []:
            hs = [h for h in (g.get("hooks") or []) if not _is_dibs(h.get("command"))]
            if hs:
                g["hooks"] = hs
                groups.append(g)
        if groups:
            hooks[ev] = groups
        else:
            del hooks[ev]


def _nested(base: str, tool: str, spec: Dict[str, Optional[str]], named: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for ev, matcher in spec.items():
        h: Dict[str, Any] = {"type": "command", "command": _hook_cmd(base, tool, ev)}
        if named:
            h["name"] = f"dibs-{ev}"
        g: Dict[str, Any] = {"hooks": [h]}
        if matcher:
            g["matcher"] = matcher
        out[ev] = [g]
    return out


def _merge_nested(path: Path, new: Dict[str, Any]) -> None:
    data = _load_json(path)
    hooks = data.setdefault("hooks", {})
    _strip_nested(hooks)
    for ev, groups in new.items():
        hooks.setdefault(ev, []).extend(groups)
    _save_json(path, data)


def _block(path: Path, text: str) -> None:
    body = f"{START}\n{text.rstrip()}\n{END}\n"
    old = path.read_text("utf-8") if path.exists() else ""
    if START in old and END in old:
        new = re.sub(re.escape(START) + r".*?" + re.escape(END) + r"\n?", lambda m: body, old, flags=re.S)
    else:
        new = (old.rstrip() + "\n\n" if old.strip() else "") + body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new, "utf-8")


def _unblock(path: Path) -> bool:
    if not path.exists():
        return False
    old = path.read_text("utf-8")
    if START not in old:
        return False
    new = re.sub(r"\n*" + re.escape(START) + r".*?" + re.escape(END) + r"\n?", "\n", old, flags=re.S).strip()
    if new:
        path.write_text(new + "\n", "utf-8")
    else:
        path.unlink()
    return True


def detect(root: Path) -> List[str]:
    found = []
    checks = {
        "claude": [".claude", "CLAUDE.md"], "cursor": [".cursor", ".cursorrules"],
        "codex": [".codex", "AGENTS.md"], "gemini": [".gemini", "GEMINI.md"],
        "copilot": [".github/copilot-instructions.md", ".vscode"], "aider": [".aider.conf.yml", ".aider.chat.history.md"],
    }
    for agent, files in checks.items():
        if any((root / f).exists() for f in files) or shutil.which(agent):
            found.append(agent)
    return found or list(AGENTS)


def init(repo: Repo, agents: List[str], base: str = "dibs", git_hook: bool = True,
         agents_md: bool = True) -> List[str]:
    root = repo.root
    done: List[str] = []
    if "claude" in agents:
        p = root / ".claude" / "settings.json"
        _merge_nested(p, _nested(base, "claude", {
            "UserPromptSubmit": None,
            "PreToolUse": "Edit|Write|MultiEdit",
            "PostToolUse": "Edit|Write|MultiEdit|NotebookEdit|Bash",
            "Stop": None}))
        done.append(".claude/settings.json (Claude Code hooks)")
    if "codex" in agents:
        p = root / ".codex" / "hooks.json"
        _merge_nested(p, _nested(base, "codex", {
            "UserPromptSubmit": None,
            "PreToolUse": "apply_patch",
            "PostToolUse": "apply_patch|Bash",
            "Stop": None}))
        done.append(".codex/hooks.json (Codex hooks: start `codex` here once and pick \"Trust all and continue\", or review them with /hooks)")
    if "gemini" in agents:
        p = root / ".gemini" / "settings.json"
        _merge_nested(p, _nested(base, "gemini", {
            "BeforeAgent": "*",
            "BeforeTool": "write_file|replace",
            "AfterTool": "write_file|replace|run_shell_command",
            "AfterAgent": "*"}, named=True))
        done.append(".gemini/settings.json (Gemini CLI hooks: Gemini only runs them in a trusted folder)")
    if "cursor" in agents:
        p = root / ".cursor" / "hooks.json"
        data = _load_json(p)
        data.setdefault("version", 1)
        hooks = data.setdefault("hooks", {})
        for ev in list(hooks):
            hooks[ev] = [h for h in hooks[ev] if not _is_dibs(h.get("command"))]
            if not hooks[ev]:
                del hooks[ev]
        spec = {"beforeSubmitPrompt": None, "preToolUse": "Write|Delete", "postToolUse": "Write|Delete|Shell",
                "afterFileEdit": None, "stop": None}
        for ev, matcher in spec.items():
            h: Dict[str, Any] = {"command": _hook_cmd(base, "cursor", ev)}
            if matcher:
                h["matcher"] = matcher
            hooks.setdefault(ev, []).append(h)
        _save_json(p, data)
        rule = root / ".cursor" / "rules" / "dibs.mdc"
        rule.parent.mkdir(parents=True, exist_ok=True)
        rule.write_text("---\ndescription: Keep the human's manual edits (dibs)\nalwaysApply: true\n---\n\n"
                        + GUIDE.format(agent="cursor"), "utf-8")
        done.append(".cursor/hooks.json + .cursor/rules/dibs.mdc (Cursor)")
    if "copilot" in agents:
        _block(root / ".github" / "copilot-instructions.md", GUIDE.format(agent="copilot"))
        p = root / ".vscode" / "mcp.json"
        data = _load_json(p)
        data.setdefault("servers", {})["dibs"] = {"type": "stdio", "command": base, "args": ["mcp", "--agent", "copilot"]}
        _save_json(p, data)
        done.append(".github/copilot-instructions.md + .vscode/mcp.json (Copilot)")
    if agents_md and any(a in agents for a in ("codex", "aider", "copilot", "gemini")):
        _block(root / "AGENTS.md", GUIDE.format(agent="<your name: codex, aider, gemini…>"))
        done.append("AGENTS.md (instructions for Codex, Aider and any agent that reads it)")
    if git_hook and repo.is_git:
        hp = git_out(["rev-parse", "--git-path", "hooks"], root)
        if hp:
            hooks_dir = Path(hp.strip())
            if not hooks_dir.is_absolute():
                hooks_dir = root / hooks_dir
            f = hooks_dir / "pre-commit"
            line = (f"if command -v {base.split()[0]} >/dev/null 2>&1; then {base} guard --pre-commit || exit 1; fi"
                    "  # dibs\n")
            old = f.read_text("utf-8") if f.exists() else "#!/bin/sh\n"
            if "# dibs" not in old:
                # Put the check right after the shebang: hooks written by other tools often end with
                # `exec ...`, and anything appended after that line would never run.
                lines = old.splitlines(True)
                if lines and lines[0].startswith("#!"):
                    new_text = lines[0].rstrip("\n") + "\n" + line + "".join(lines[1:])
                else:
                    new_text = "#!/bin/sh\n" + line + old
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(new_text, "utf-8")
                f.chmod(f.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            done.append(f"{os.path.relpath(f, root)} (revert check before each commit)")
    return done


def uninstall(repo: Repo) -> List[str]:
    root = repo.root
    done = []
    for rel in (".claude/settings.json", ".claude/settings.local.json", ".codex/hooks.json", ".gemini/settings.json"):
        p = root / rel
        if p.exists():
            data = _load_json(p)
            if "hooks" in data:
                _strip_nested(data["hooks"])
                if not data["hooks"]:
                    del data["hooks"]
                _save_json(p, data)
                done.append(rel)
    p = root / ".cursor" / "hooks.json"
    if p.exists():
        data = _load_json(p)
        hooks = data.get("hooks", {})
        for ev in list(hooks):
            hooks[ev] = [h for h in hooks[ev] if not _is_dibs(h.get("command"))]
            if not hooks[ev]:
                del hooks[ev]
        _save_json(p, data)
        done.append(".cursor/hooks.json")
    rule = root / ".cursor" / "rules" / "dibs.mdc"
    if rule.exists():
        rule.unlink()
        done.append(".cursor/rules/dibs.mdc")
    p = root / ".vscode" / "mcp.json"
    if p.exists():
        data = _load_json(p)
        if data.get("servers", {}).pop("dibs", None) is not None:
            _save_json(p, data)
            done.append(".vscode/mcp.json")
    for rel in ("AGENTS.md", ".github/copilot-instructions.md"):
        if _unblock(root / rel):
            done.append(rel)
    if repo.is_git:
        hp = git_out(["rev-parse", "--git-path", "hooks"], root)
        if hp:
            f = Path(hp.strip())
            f = (f if f.is_absolute() else root / f) / "pre-commit"
            if f.exists():
                lines = [l for l in f.read_text("utf-8").splitlines(True) if "# dibs" not in l]
                if "".join(lines).strip() in ("", "#!/bin/sh"):
                    f.unlink()
                else:
                    f.write_text("".join(lines), "utf-8")
                done.append("pre-commit hook")
    return done
