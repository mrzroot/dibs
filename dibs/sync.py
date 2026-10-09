"""What is not committed, not pushed, or not on any remote."""
from __future__ import annotations

from typing import Any, Dict, List

from .repo import Repo, git_out


def sync_status(repo: Repo, fetch: bool = False) -> Dict[str, Any]:
    s: Dict[str, Any] = {"git": repo.is_git, "warnings": [], "ok": []}
    if not repo.is_git:
        s["warnings"].append("not a git repository: there is no history and nothing is backed up")
        return s
    root = repo.root
    if fetch:
        git_out(["fetch", "--all", "--quiet"], root)
    remotes = [r for r in (git_out(["remote"], root) or "").split() if r]
    s["remotes"] = remotes
    head = (git_out(["symbolic-ref", "--quiet", "--short", "HEAD"], root) or "").strip()
    s["branch"] = head or None
    has_commits = git_out(["rev-parse", "--verify", "--quiet", "HEAD"], root) is not None
    s["has_commits"] = has_commits

    # working tree
    porcelain = git_out(["status", "--porcelain=v1", "-z", "--untracked-files=all"], root) or ""
    staged = modified = untracked = conflicted = 0
    files: List[str] = []
    entries = porcelain.split("\0")
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        x, y, path = e[0], e[1], e[3:]
        if x in "RC":
            i += 1  # skip the original path of a rename/copy
        files.append(path)
        if x == "?" and y == "?":
            untracked += 1
        elif "U" in (x + y) or (x == y and x in "AD"):
            conflicted += 1
        else:
            if x not in " ?":
                staged += 1
            if y not in " ?":
                modified += 1
    s.update(staged=staged, modified=modified, untracked=untracked, conflicted=conflicted,
             dirty_files=files)
    n_dirty = len(files)
    if n_dirty:
        parts = []
        if modified:
            parts.append(f"{modified} modified")
        if staged:
            parts.append(f"{staged} staged")
        if untracked:
            parts.append(f"{untracked} untracked")
        if conflicted:
            parts.append(f"{conflicted} conflicted")
        s["warnings"].append(f"{n_dirty} file{'s' if n_dirty != 1 else ''} not committed ({', '.join(parts)})")
    else:
        s["ok"].append("working tree clean")

    if not remotes:
        s["warnings"].append("no git remote: nothing in this repository is backed up anywhere")
    if not head:
        if has_commits:
            s["warnings"].append("detached HEAD: new commits here belong to no branch")
    elif has_commits and remotes:
        upstream = (git_out(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], root) or "").strip()
        s["upstream"] = upstream or None
        if upstream:
            counts = (git_out(["rev-list", "--left-right", "--count", f"{upstream}...HEAD"], root) or "0 0").split()
            behind, ahead = int(counts[0]), int(counts[1])
            s.update(ahead=ahead, behind=behind)
            if ahead:
                s["warnings"].append(f"{ahead} commit{'s' if ahead != 1 else ''} on {head} not pushed to {upstream}")
            if behind:
                s["warnings"].append(f"{head} is {behind} commit{'s' if behind != 1 else ''} behind {upstream} (as of the last fetch)")
            if not ahead and not behind:
                s["ok"].append(f"{head} is in sync with {upstream} (as of the last fetch)")
        else:
            n = (git_out(["rev-list", "--count", "HEAD", "--not", "--remotes"], root) or "0").strip()
            s["unpushed"] = int(n or 0)
            s["warnings"].append(f"branch {head} has never been pushed ({n} commit{'s' if n != '1' else ''} on no remote)")
    elif has_commits and not remotes:
        n = (git_out(["rev-list", "--count", "HEAD"], root) or "0").strip()
        s["unpushed"] = int(n or 0)

    # other local branches with commits that exist on no remote
    if remotes and has_commits:
        refs = git_out(["for-each-ref", "refs/heads", "--format=%(refname:short)"], root) or ""
        others = []
        for b in refs.split():
            if b == head:
                continue
            n = (git_out(["rev-list", "--count", b, "--not", "--remotes"], root) or "0").strip()
            if n and n != "0":
                others.append(f"{b} ({n})")
        if others:
            s["unpushed_branches"] = others
            s["warnings"].append("local branches with commits on no remote: " + ", ".join(others))
    stash = git_out(["stash", "list"], root) or ""
    n_stash = len([l for l in stash.splitlines() if l.strip()])
    if n_stash:
        s["stashes"] = n_stash
        s["warnings"].append(f"{n_stash} stash{'es' if n_stash != 1 else ''} (stashes are never pushed)")
    return s


def sync_line(s: Dict[str, Any]) -> str:
    if not s["warnings"]:
        return "git: everything committed and pushed."
    return "git: " + "; ".join(s["warnings"]) + "."
