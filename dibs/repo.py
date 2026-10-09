"""Repository discovery, state files, locking and configuration."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    # How the revert guard reacts when an agent edit would undo human lines:
    # auto = ask where the agent supports it (Claude Code), otherwise deny;
    # ask | deny | warn | off.
    "guard": "auto",
    # Pre-commit hook: block | warn | off.
    "precommit": "block",
    # Human lines stay protected for this many hours after the edit.
    "protect_hours": 72,
    # First brief for an agent dibs has never seen covers this window.
    "brief_window_hours": 24,
    # Maximum diff lines shown per file in a brief.
    "brief_lines_per_file": 8,
    # Maximum files listed in a brief.
    "brief_max_files": 20,
    # Files bigger than this are tracked by hash only (no content, no lines).
    "max_file_bytes": 2_000_000,
    # Include the git sync line in agent briefs.
    "brief_sync": True,
}

AGENTS = ("claude", "cursor", "codex", "gemini", "copilot", "aider")
HUMANISH = ("human", "unknown")


def run_git(args: List[str], cwd: Path, input: Optional[bytes] = None) -> Optional[subprocess.CompletedProcess]:
    """Run git; return None when git is not installed."""
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, input=input)
    except (FileNotFoundError, NotADirectoryError):
        return None


def git_out(args: List[str], cwd: Path) -> Optional[str]:
    p = run_git(args, cwd)
    if p is None or p.returncode != 0:
        return None
    return p.stdout.decode("utf-8", "replace")


class Repo:
    def __init__(self, root: Path, git_dir: Optional[Path] = None):
        self.root = Path(root).resolve()
        self.git_dir = Path(git_dir).resolve() if git_dir else None
        self.is_git = self.git_dir is not None
        self.state_dir = (self.git_dir / "dibs") if self.git_dir else (self.root / ".dibs")

    @classmethod
    def discover(cls, start: Optional[os.PathLike] = None) -> "Repo":
        env = os.environ.get("DIBS_ROOT")
        start_path = Path(env or start or os.getcwd()).resolve()
        if start_path.is_file():
            start_path = start_path.parent
        out = git_out(["rev-parse", "--show-toplevel", "--absolute-git-dir"], start_path)
        if out:
            lines = out.splitlines()
            if len(lines) >= 2 and lines[0]:
                return cls(Path(lines[0]), Path(lines[1]))
        for d in [start_path, *start_path.parents]:
            if (d / ".dibs").is_dir():
                return cls(d)
        return cls(start_path)

    # paths ---------------------------------------------------------------
    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def journal_file(self) -> Path:
        return self.state_dir / "journal.jsonl"

    @property
    def initialized(self) -> bool:
        return self.state_file.exists()

    def rel(self, path: os.PathLike, base: Optional[os.PathLike] = None) -> Optional[str]:
        """Return the repo-relative POSIX path, or None if outside the repo."""
        p = Path(path)
        if not p.is_absolute():
            p = Path(base or os.getcwd()) / p
        try:
            p = Path(os.path.normpath(str(p)))
            try:
                p = p.resolve()
            except OSError:
                pass
            r = p.relative_to(self.root)
        except ValueError:
            return None
        s = r.as_posix()
        if s in ("", "."):
            return None
        if self.is_git and (s == ".git" or s.startswith(".git/")):
            return None
        if s == ".dibs" or s.startswith(".dibs/"):
            return None
        return s

    # config --------------------------------------------------------------
    def config(self) -> Dict[str, Any]:
        cfg = dict(DEFAULT_CONFIG)
        for f in (self.root / ".dibs.json", self.state_dir / "config.json"):
            try:
                cfg.update(json.loads(f.read_text("utf-8")))
            except (OSError, ValueError):
                pass
        env_guard = os.environ.get("DIBS_GUARD")
        if env_guard:
            cfg["guard"] = env_guard
        return cfg

    def set_config(self, key: str, value: Any) -> None:
        f = self.state_dir / "config.json"
        try:
            cur = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            cur = {}
        cur[key] = value
        self.state_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(f, json.dumps(cur, indent=2).encode())

    def lock(self, timeout: float = 15.0) -> "Lock":
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return Lock(self.state_dir / "lock", timeout)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


class Lock:
    """Tiny cross-platform lock file; stale locks (>30 s) are broken."""

    def __init__(self, path: Path, timeout: float):
        self.path = path
        self.timeout = timeout
        self.held = False

    def __enter__(self) -> "Lock":
        deadline = time.time() + self.timeout
        while True:
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self.held = True
                return self
            except FileExistsError:
                try:
                    if time.time() - self.path.stat().st_mtime > 30:
                        os.remove(str(self.path))
                        continue
                except OSError:
                    pass
                if time.time() > deadline:
                    raise TimeoutError(f"dibs: could not lock {self.path}")
                time.sleep(0.03)

    def __exit__(self, *exc: Any) -> None:
        if self.held:
            try:
                os.remove(str(self.path))
            except OSError:
                pass
            self.held = False
