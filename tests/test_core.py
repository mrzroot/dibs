import subprocess

from conftest import edit, git, hook

from dibs.core import Dibs
from dibs.repo import Repo
from dibs.store import blob_id


def test_blob_id_matches_git(repo):
    data = (repo / "app.py").read_bytes()
    assert blob_id(data) == git(repo, "hash-object", "--no-filters", "app.py").stdout.strip()


def test_human_edit_shows_in_brief_with_lines(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    assert "app.py" not in d.turn_start("claude")
    d.turn_end("claude")
    edit(repo / "app.py", "timeout = 10", "timeout = 30")
    brief = d.turn_start("claude")
    assert "app.py — edited by human" in brief
    assert "+ timeout = 30" in brief and "- timeout = 10" in brief
    # seen now: the next turn is quiet about it
    d.turn_end("claude")
    assert "app.py" not in d.turn_start("claude")


def test_agent_does_not_see_its_own_changes_but_others_do(repo):
    d = Dibs(Repo.discover(repo))
    d.turn_start("claude")
    d.turn_start("cursor")
    d.turn_end("cursor")
    (repo / "new.py").write_text("x = 1\n")
    d.touch("claude", ["new.py"])
    d.turn_end("claude")
    assert "new.py" not in d.turn_start("claude")
    brief = d.turn_start("cursor")
    assert "new.py — created by claude" in brief


def test_human_edit_during_agent_turn_stays_human(repo):
    d = Dibs(Repo.discover(repo))
    d.turn_start("claude")
    (repo / "agent.py").write_text("a = 1\n")
    d.touch("claude", ["agent.py"])
    edit(repo / "README.md", "# demo", "# demo by hand")  # human, mid-turn, other file
    d.turn_end("claude")
    d.turn_start("claude")
    by_path = {e["path"]: e["actor"] for e in d.events() if e.get("kind") == "change"}
    assert by_path == {"agent.py": "claude", "README.md": "human"}


def test_revert_detected_and_3way_restore_keeps_later_agent_work(repo):
    d = Dibs(Repo.discover(repo))
    d.turn_start("claude")
    d.turn_end("claude")
    edit(repo / "app.py", "timeout = 10", "timeout = 30  # slow VPN")
    d.turn_start("claude")
    # the agent rewrites the file from its stale memory, adding a function too
    (repo / "app.py").write_text("def f():\n    timeout = 10\n    return timeout\n\ndef g():\n    return 2\n")
    evs = d.touch("claude", None)
    assert evs[0]["reverts"]["dropped"] == ["timeout = 30 # slow VPN"]
    assert evs[0]["reverts"]["resurrected"] == ["timeout = 10"]
    assert [r["path"] for r in d.pending_reverts()] == ["app.py"]
    r = d.restore("app.py")
    assert r["conflicts"] == 0
    text = (repo / "app.py").read_text()
    assert "timeout = 30  # slow VPN" in text and "timeout = 10" not in text and "def g()" in text
    assert d.pending_reverts() == []


def test_revert_resolved_by_hand_clears_pending(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    edit(repo / "app.py", "timeout = 10", "timeout = 30")
    d.turn_start("codex")
    edit(repo / "app.py", "timeout = 30", "timeout = 10")
    d.touch("codex", None)
    assert d.pending_reverts()
    edit(repo / "app.py", "timeout = 10", "timeout = 30")
    assert d.pending_reverts() == []


def test_restore_whole(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    edit(repo / "README.md", "# demo", "# mine")
    d.record("human")
    (repo / "README.md").write_text("totally different\n")
    d.touch("aider", None)
    d.restore("README.md", whole=True)
    assert (repo / "README.md").read_text() == "# mine\n"


def test_trivial_lines_are_not_protected(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    (repo / "x.js").write_text("if (a) {\n  go();\n}\n")
    d.record("human")
    v = d.check_edit("claude", "x.js", new_text="if (a) {\n  go();\n  stop();\n")
    assert not v.reverts  # removing a lone "}" is not a revert worth blocking


def test_allow_overrides_guard(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    edit(repo / "app.py", "timeout = 10", "timeout = 30")
    d.record("human")
    new = (repo / "app.py").read_text().replace("timeout = 30", "timeout = 99")
    assert d.check_edit("claude", "app.py", new_text=new).reverts
    d.allow("app.py")
    assert not d.check_edit("claude", "app.py", new_text=new).reverts
    (repo / "app.py").write_text(new)
    evs = d.touch("claude", ["app.py"])
    assert evs[0].get("override") and "reverts" not in evs[0]


def test_unrecorded_human_edit_is_protected_too(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    edit(repo / "app.py", "timeout = 10", "timeout = 45")  # not recorded yet
    new = (repo / "app.py").read_text().replace("timeout = 45", "timeout = 10")
    assert d.check_edit("claude", "app.py", new_text=new).reverts


def test_blame(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    edit(repo / "app.py", "    return timeout", "    log(timeout)\n    return timeout")
    d.record("human")
    edit(repo / "app.py", "def f():", "def f():  # cached")
    d.touch("claude", ["app.py"])
    rows = {n: (w or {}).get("actor") for n, _, w in d.blame("app.py")}
    assert rows == {1: "claude", 2: None, 3: "human", 4: None}


def test_non_git_directory(tmp_path, monkeypatch):
    (tmp_path / "a.txt").write_text("one\n")
    monkeypatch.chdir(tmp_path)
    d = Dibs(Repo.discover(tmp_path))
    assert not d.repo.is_git
    d.ensure()
    assert (tmp_path / ".dibs" / "state.json").exists()
    (tmp_path / "a.txt").write_text("two\n")
    brief = d.turn_start("claude")
    assert "a.txt — edited by human" in brief
    assert "not a git repository" in brief


def test_binary_files_tracked_by_hash(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    (repo / "img.bin").write_bytes(b"\x00\x01\x02" * 10)
    evs = d.record("human")
    assert evs[0]["binary"] and evs[0]["op"] == "A"
    assert "img.bin" in d.turn_start("claude")
