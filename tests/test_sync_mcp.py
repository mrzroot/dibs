import json
import os
import subprocess
import sys

from conftest import git

from dibs.repo import Repo
from dibs.sync import sync_status


def test_sync_no_remote(repo):
    s = sync_status(Repo.discover(repo))
    assert any("no git remote" in w for w in s["warnings"])
    assert s["unpushed"] == 1


def test_sync_ahead_never_pushed_and_stash(repo, tmp_path):
    bare = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(bare))
    git(repo, "remote", "add", "origin", str(bare))
    git(repo, "push", "-q", "-u", "origin", "main")
    s = sync_status(Repo.discover(repo))
    assert s["warnings"] == [] and s["ahead"] == 0
    (repo / "x.txt").write_text("1")
    git(repo, "add", "x.txt")
    git(repo, "commit", "-qm", "x")
    git(repo, "switch", "-q", "-c", "feature")
    (repo / "y.txt").write_text("1")
    git(repo, "add", "y.txt")
    git(repo, "commit", "-qm", "y")
    (repo / "README.md").write_text("changed\n")
    git(repo, "stash", "-q")
    (repo / "z.txt").write_text("untracked")
    s = sync_status(Repo.discover(repo))
    text = " | ".join(s["warnings"])
    assert "branch feature has never been pushed (2 commits on no remote)" in text
    assert "1 file not committed (1 untracked)" in text
    assert "1 stash" in text
    git(repo, "switch", "-q", "main")
    s = sync_status(Repo.discover(repo))
    text = " | ".join(s["warnings"])
    assert "1 commit on main not pushed to origin/main" in text
    assert "local branches with commits on no remote: feature (2)" in text


def test_mcp_server(repo):
    subprocess.run([sys.executable, "-m", "dibs", "status"], cwd=repo, capture_output=True)
    (repo / "README.md").write_text("# edited by hand\n")
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "dibs_brief", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "dibs_check_edit", "arguments": {
            "path": "README.md", "new_content": "# demo\n"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "dibs_sync_status", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 6, "method": "nope"},
    ]
    env = dict(os.environ)
    r = subprocess.run([sys.executable, "-m", "dibs", "mcp", "--agent", "copilot"], cwd=repo, env=env,
                       input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, timeout=60)
    out = [json.loads(l) for l in r.stdout.splitlines()]
    assert [o["id"] for o in out] == [1, 2, 3, 4, 5, 6]
    assert out[0]["result"]["serverInfo"]["name"] == "dibs"
    assert {t["name"] for t in out[1]["result"]["tools"]} >= {"dibs_brief", "dibs_check_edit", "dibs_done"}
    assert "README.md — edited by human" in out[2]["result"]["content"][0]["text"]
    assert "would undo" in out[3]["result"]["content"][0]["text"]
    assert "not committed" in out[4]["result"]["content"][0]["text"]
    assert out[5]["error"]["code"] == -32601
