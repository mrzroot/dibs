"""Content-addressed blob store and working-tree scanning."""
from __future__ import annotations

import hashlib
import os
import stat
import time
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .repo import Repo, atomic_write, run_git

SKIP_DIRS = {".git", ".dibs", "node_modules", "__pycache__", ".venv", "venv", ".tox",
             ".mypy_cache", ".pytest_cache", ".ruff_cache", ".hg", ".svn", ".idea"}

# manifest entry: [blob_id, size, mtime_ns]
Manifest = Dict[str, list]


def blob_id(data: bytes) -> str:
    """Same id git uses for a blob, so clean files can be read back from git."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def is_binary(data: bytes) -> bool:
    return b"\0" in data[:8000]


class Store:
    def __init__(self, repo: Repo):
        self.repo = repo
        self.dir = repo.state_dir / "objects"

    def _path(self, sha: str) -> Path:
        return self.dir / sha[:2] / sha[2:]

    def put(self, data: bytes) -> str:
        sha = blob_id(data)
        p = self._path(sha)
        if not p.exists():
            atomic_write(p, zlib.compress(data, 6))
        return sha

    def has(self, sha: str) -> bool:
        return self._path(sha).exists()

    def get(self, sha: Optional[str]) -> Optional[bytes]:
        if not sha:
            return None
        p = self._path(sha)
        if p.exists():
            try:
                return zlib.decompress(p.read_bytes())
            except (OSError, zlib.error):
                return None
        if self.repo.is_git:
            r = run_git(["cat-file", "blob", sha], self.repo.root)
            if r is not None and r.returncode == 0:
                return r.stdout
        return None


def list_files(repo: Repo) -> List[str]:
    if repo.is_git:
        r = run_git(["ls-files", "-z", "-c", "-o", "--exclude-standard"], repo.root)
        if r is not None and r.returncode == 0:
            names = {n for n in r.stdout.decode("utf-8", "surrogateescape").split("\0") if n}
            return sorted(n for n in names if not n.startswith(".dibs/"))
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(repo.root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            rel = os.path.relpath(os.path.join(dirpath, f), repo.root).replace(os.sep, "/")
            out.append(rel)
    return sorted(out)


def read_file(repo: Repo, rel: str) -> Optional[bytes]:
    try:
        with open(repo.root / rel, "rb") as fh:
            return fh.read()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError):
        return None


def scan(repo: Repo, old: Manifest, paths: Optional[Iterable[str]] = None,
         force: bool = False) -> Tuple[Manifest, Dict[str, bytes]]:
    """Return (new manifest, freshly read contents).

    With ``paths`` only those files are re-checked (and always re-hashed);
    everything else is carried over from ``old``.
    """
    data_cache: Dict[str, bytes] = {}
    if paths is not None:
        new = dict(old)
        targets = list(dict.fromkeys(paths))
        force = True
    else:
        new = {}
        targets = list_files(repo)
    for rel in targets:
        full = repo.root / rel
        try:
            st = os.stat(full)
        except OSError:
            new.pop(rel, None)
            continue
        if not stat.S_ISREG(st.st_mode):
            new.pop(rel, None)
            continue
        prev = old.get(rel)
        if not force and prev and prev[1] == st.st_size and prev[2] == st.st_mtime_ns:
            new[rel] = prev
            continue
        data = read_file(repo, rel)
        if data is None:
            new.pop(rel, None)
            continue
        # "racy" entries (modified within the last 2 s) are re-hashed next time, like git's index
        racy = st.st_mtime_ns >= time.time_ns() - 2_000_000_000
        new[rel] = [blob_id(data), len(data), 0 if racy else st.st_mtime_ns]
        data_cache[rel] = data
    return new, data_cache
