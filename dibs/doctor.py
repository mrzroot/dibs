"""`dibs doctor`: check that every wired agent will really run the dibs hooks."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .repo import Repo, git_out

Check = Tuple[str, str]  # (level: ok|warn|fail|info, message)


def _json(p: Path) -> Optional[Dict[str, Any]]:
    try:
        d = json.loads(p.read_text("utf-8"))
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def _has_dibs(obj: Any) -> bool:
    return " hook " in json.dumps(obj) and "dibs" in json.dumps(obj)


def _under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def gemini_home() -> Path:
    return Path(os.environ.get("GEMINI_CLI_HOME") or Path.home()) / ".gemini"


def check_codex(root: Path) -> List[Check]:
    out: List[Check] = []
    data = _json(root / ".codex" / "hooks.json")
    if data is None:
        return out
    if not _has_dibs(data.get("hooks", {})):
        return [("warn", "Codex: .codex/hooks.json has no dibs hooks (run `dibs init --agents codex`)")]
    cfg_path = codex_home() / "config.toml"
    try:
        cfg = cfg_path.read_text("utf-8")
    except OSError:
        cfg = ""
    if re.search(r"^\s*(codex_)?hooks\s*=\s*false", cfg, re.M):
        out.append(("fail", f"Codex: hooks are turned off in {cfg_path} ([features] hooks = false)"))
    hooks_file = str(root / ".codex" / "hooks.json")
    events = ["user_prompt_submit", "pre_tool_use", "post_tool_use", "stop"]
    trusted = [ev for ev in events if re.search(re.escape(f'[hooks.state."{hooks_file}:{ev}:') + r'[^\]]*\]\s*\n\s*trusted_hash', cfg)]
    if len(trusted) == len(events):
        out.append(("ok", "Codex: dibs hooks are trusted (if you edit .codex/hooks.json, trust them again)"))
    else:
        out.append(("fail", "Codex: dibs hooks are not trusted yet, so Codex skips them silently. Start `codex` in this "
                    "repo once and choose \"Trust all and continue\" (or review them with /hooks)."))
    return out


def gemini_trusted(root: Path) -> Optional[bool]:
    home = gemini_home()
    settings = _json(home / "settings.json") or {}
    if (settings.get("security") or {}).get("folderTrust", {}).get("enabled") is False:
        return True
    folders = _json(home / "trustedFolders.json")
    if folders is None:
        return False
    rp = root.resolve()
    verdict = None
    best = -1
    for path, level in folders.items():
        p = Path(path).expanduser()
        if level == "TRUST_PARENT":
            p = p.parent
        if _under(rp, p) and len(str(p)) > best:
            best = len(str(p))
            verdict = level in ("TRUST_FOLDER", "TRUST_PARENT")
    return bool(verdict)


def check_gemini(root: Path) -> List[Check]:
    data = _json(root / ".gemini" / "settings.json")
    if data is None:
        return []
    if not _has_dibs(data.get("hooks", {})):
        return [("warn", "Gemini CLI: .gemini/settings.json has no dibs hooks (run `dibs init --agents gemini`)")]
    out: List[Check] = []
    for f in (gemini_home() / "settings.json", root / ".gemini" / "settings.json"):
        s = _json(f) or {}
        if (s.get("hooksConfig") or {}).get("enabled") is False:
            out.append(("fail", f"Gemini CLI: hooks are disabled in {f} (hooksConfig.enabled = false)"))
    if gemini_trusted(root):
        out.append(("ok", "Gemini CLI: this folder is trusted, so its project hooks run"))
    else:
        out.append(("fail", "Gemini CLI: this folder is not trusted, so Gemini ignores .gemini/settings.json "
                    "(and the dibs hooks). Trust it when Gemini asks, or with /permissions."))
    return out


def check_claude(root: Path) -> List[Check]:
    out: List[Check] = []
    proj = _json(root / ".claude" / "settings.json")
    if proj is None:
        return out
    if not _has_dibs(proj.get("hooks", {})):
        return [("warn", "Claude Code: .claude/settings.json has no dibs hooks (run `dibs init --agents claude`)")]
    for f in (root / ".claude" / "settings.json", root / ".claude" / "settings.local.json",
              Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"):
        s = _json(f) or {}
        if s.get("disableAllHooks"):
            out.append(("fail", f"Claude Code: disableAllHooks is set in {f}"))
    if not any(l == "fail" for l, _ in out):
        out.append(("ok", "Claude Code: dibs hooks configured (they run once you accept Claude Code's folder-trust prompt)"))
    return out


def check_cursor(root: Path) -> List[Check]:
    data = _json(root / ".cursor" / "hooks.json")
    if data is None:
        return []
    if data.get("version") != 1 or not _has_dibs(data.get("hooks", {})):
        return [("warn", "Cursor: .cursor/hooks.json is missing dibs hooks or `\"version\": 1`")]
    out = [("ok", "Cursor: dibs hooks configured")]
    if (root / ".claude" / "settings.json").exists():
        out.append(("info", "Cursor also runs .claude/settings.json hooks; dibs notices and lets its Cursor hooks do the work"))
    return out


def check_copilot(root: Path) -> List[Check]:
    data = _json(root / ".vscode" / "mcp.json")
    if data is None or "dibs" not in (data.get("servers") or {}):
        return []
    return [("info", "Copilot: dibs MCP server configured in .vscode/mcp.json; Copilot is asked (not forced) to call it")]


def check_git(repo: Repo) -> List[Check]:
    if not repo.is_git:
        return [("warn", "not a git repository: the pre-commit guard and sync warnings are unavailable")]
    hp = git_out(["rev-parse", "--git-path", "hooks"], repo.root)
    if not hp:
        return []
    f = Path(hp.strip())
    f = (f if f.is_absolute() else repo.root / f) / "pre-commit"
    if not f.exists():
        return [("warn", "git pre-commit guard is not installed (run `dibs init`)")]
    text = f.read_text("utf-8", "replace")
    if "# dibs" not in text:
        return [("warn", f"{f} exists but has no dibs line (run `dibs init`)")]
    lines = text.splitlines()
    idx = next(i for i, l in enumerate(lines) if "# dibs" in l)
    if any(re.match(r"\s*exec\s", l) for l in lines[:idx]):
        return [("fail", f"{f}: an `exec` line runs before the dibs check, so it never runs")]
    if os.name == "posix" and not os.access(f, os.X_OK):
        return [("fail", f"{f} is not executable")]
    return [("ok", "git pre-commit guard installed")]


def run(repo: Repo) -> List[Check]:
    root = repo.root
    out: List[Check] = []
    exe = shutil.which("dibs")
    out.append(("ok", f"dibs on PATH: {exe}") if exe else
               ("fail", "`dibs` is not on PATH, so every agent hook will fail (install with pipx or uv tool)"))
    out += check_git(repo)
    for fn in (check_claude, check_codex, check_gemini, check_cursor, check_copilot):
        out += fn(root)
    log = repo.state_dir / "hook-errors.log"
    if log.exists() and log.stat().st_size:
        n = log.read_text("utf-8", "replace").count("\n--- ") + 1
        out.append(("warn", f"{n} hook error(s) logged in {log}"))
    return out
