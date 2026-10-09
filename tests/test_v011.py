"""Tests for the 0.1.1 hardening: payloads taken from the real CLIs, doctor, lock, watch, run."""
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import edit, git, hook

from dibs import doctor
from dibs.cli import main
from dibs.core import Dibs
from dibs.hooks import main as hook_main
from dibs.repo import Lock, Repo


def _human(repo):
    hook("claude", "UserPromptSubmit", repo, prompt="hi")
    hook("claude", "Stop", repo)
    edit(repo / "app.py", "timeout = 10", "timeout = 30  # slow network")


def _cursor_payload(repo, **kw):
    # field names copied from the Cursor agent 2026.10.01 hook runner
    base = {"conversation_id": "c1", "generation_id": "g1", "session_id": "s1", "cursor_version": "2026.10.01",
            "workspace_roots": [str(repo)], "hook_event_name": "preToolUse", "user_email": None, "model": "x"}
    base.update(kw)
    return base


def test_claude_ask_carries_user_visible_system_message(repo):
    _human(repo)
    out, _ = hook("claude", "PreToolUse", repo, tool_name="Write", tool_input={
        "file_path": str(repo / "app.py"), "content": "def f():\n    timeout = 10\n    return timeout\n"})
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "slow network" in out["systemMessage"] and "Answer No" in out["systemMessage"]


def test_cursor_write_payload_from_source(repo):
    _human(repo)
    p = _cursor_payload(repo, tool_name="Write", tool_input={
        "file_path": str(repo / "app.py"), "content": "def f():\n    timeout = 10\n    return timeout\n"})
    out, code = hook_main("cursor", "preToolUse", json.dumps(p))
    out = json.loads(out)
    assert code == 0 and out["permission"] == "deny" and "slow network" in out["agent_message"]


def test_claude_hooks_run_by_cursor_are_attributed_to_cursor(repo, monkeypatch):
    monkeypatch.delenv("CURSOR_VERSION", raising=False)
    _human(repo)
    p = _cursor_payload(repo, hook_event_name="UserPromptSubmit", prompt="x", cwd=str(repo))
    out, _ = hook_main("claude", "UserPromptSubmit", json.dumps(p))
    assert json.loads(out)["continue"] is True  # answered in Cursor's format
    st = Dibs(Repo.discover(repo)).load_state()
    assert st["agents"]["cursor"]["active"] and not st["agents"]["claude"].get("active")


def test_claude_hooks_run_by_cursor_defer_to_cursor_hooks(repo):
    (repo / ".cursor").mkdir()
    (repo / ".cursor" / "hooks.json").write_text(json.dumps(
        {"version": 1, "hooks": {"stop": [{"command": "dibs hook cursor stop"}]}}))
    p = _cursor_payload(repo, hook_event_name="Stop", cwd=str(repo))
    assert json.loads(hook_main("claude", "Stop", json.dumps(p))[0]) == {}


def test_precommit_line_goes_before_exec(repo):
    pc = repo / ".git" / "hooks" / "pre-commit"
    pc.write_text("#!/bin/sh\nexec other-tool run\n")
    pc.chmod(0o755)
    assert main(["init", "--agents", "claude"]) == 0
    lines = pc.read_text().splitlines()
    assert lines[0] == "#!/bin/sh" and "dibs guard --pre-commit" in lines[1] and lines[-1] == "exec other-tool run"
    assert ("ok", "git pre-commit guard installed") in doctor.check_git(Repo.discover(repo))


def test_doctor_codex_trust(repo, tmp_path, monkeypatch):
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    main(["init", "--agents", "codex"])
    assert doctor.check_codex(repo)[-1][0] == "fail"
    hf = str(repo / ".codex" / "hooks.json")
    (home / "config.toml").write_text("".join(
        f'[hooks.state."{hf}:{ev}:0:0"]\ntrusted_hash = "sha256:ab"\n\n'
        for ev in ("user_prompt_submit", "pre_tool_use", "post_tool_use", "stop")))
    assert doctor.check_codex(repo)[-1][0] == "ok"
    (home / "config.toml").write_text("[features]\nhooks = false\n")
    assert any(l == "fail" and "turned off" in m for l, m in doctor.check_codex(repo))


def test_doctor_gemini_trust(repo, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_CLI_HOME", str(tmp_path / "gh"))
    main(["init", "--agents", "gemini"])
    assert doctor.check_gemini(repo)[-1][0] == "fail"
    g = tmp_path / "gh" / ".gemini"
    g.mkdir(parents=True)
    (g / "trustedFolders.json").write_text(json.dumps({str(repo): "TRUST_FOLDER"}))
    assert doctor.check_gemini(repo)[-1][0] == "ok"
    (g / "trustedFolders.json").write_text(json.dumps({str(repo / "app.py"): "TRUST_PARENT"}))
    assert doctor.check_gemini(repo)[-1][0] == "ok"
    (g / "trustedFolders.json").write_text(json.dumps({str(repo.parent): "TRUST_FOLDER", str(repo): "DO_NOT_TRUST"}))
    assert doctor.check_gemini(repo)[-1][0] == "fail"


def test_doctor_cli_json(repo):
    main(["init", "--agents", "claude"])
    r = subprocess.run([sys.executable, "-m", "dibs", "doctor", "--json"], cwd=repo, capture_output=True, text=True)
    levels = {c["message"].split(":")[0]: c["level"] for c in json.loads(r.stdout)}
    assert levels["Claude Code"] == "ok"


def test_events_tail_reader_matches_full_read(repo):
    d = Dibs(Repo.discover(repo))
    d.ensure()
    for i in range(40):
        (repo / f"f{i}.txt").write_text(str(i))
        d.record("human")
    allev = d.events()
    assert [e["seq"] for e in d.events(min_seq=allev[-5]["seq"])] == [e["seq"] for e in allev[-4:]]
    assert len(d.events(min_ts=time.time() + 3600)) == 0
    assert len(d.events(min_ts=0)) == len(allev)


@pytest.mark.skipif(os.name != "posix", reason="PID check is POSIX only")
def test_lock_breaks_when_owner_is_dead(tmp_path):
    p = tmp_path / "lock"
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    p.write_text(str(dead.pid))
    old = time.time() - 5
    os.utime(p, (old, old))
    with Lock(p, timeout=1.0) as lk:
        assert lk.held
    p.write_text(str(os.getpid()))  # live owner, fresh: must wait and time out
    with pytest.raises(TimeoutError):
        with Lock(p, timeout=0.3):
            pass


def test_watch_rounds_records_human(repo):
    main(["init", "--agents", "claude"])
    edit(repo / "app.py", "timeout = 10", "timeout = 99")
    assert main(["watch", "--interval", "0.2", "--rounds", "1"]) == 0
    ev = Dibs(Repo.discover(repo)).events()[-1]
    assert ev["actor"] == "human" and ev["path"] == "app.py"


@pytest.mark.skipif(os.name != "posix", reason="shell script stand-in for aider")
def test_run_hands_brief_to_aider_and_warns(repo, tmp_path, capfd):
    _human(repo)
    fake = tmp_path / "bin" / "aider"
    fake.parent.mkdir()
    # a fake aider: records its argv, then "rewrites from memory", undoing the human line
    fake.write_text("#!/bin/sh\necho \"$@\" > \"$ARGS_OUT\"\n"
                    "printf 'def f():\\n    timeout = 10\\n    return timeout\\n' > app.py\n")
    fake.chmod(0o755)
    os.environ["ARGS_OUT"] = str(tmp_path / "args")
    try:
        assert main(["run", "--agent", "aider", "--", str(fake), "--yes"]) == 0
    finally:
        del os.environ["ARGS_OUT"]
    args = (tmp_path / "args").read_text()
    assert "--read" in args and "brief-aider.md" in args
    err = capfd.readouterr().err
    assert "undid lines you edited by hand in app.py" in err and "dibs restore app.py" in err
    assert main(["restore", "app.py"]) == 0
    assert "slow network" in (repo / "app.py").read_text()


def test_baseline_on_many_files_is_fast(repo):
    for i in range(3000):
        (repo / f"m{i}.txt").write_text(f"line {i}\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "many")
    (repo / "m1.txt").write_text("dirty\n")
    t = time.time()
    Dibs(Repo.discover(repo)).ensure()
    assert time.time() - t < 15
    objs = list((repo / ".git" / "dibs").rglob("*"))
    assert len([o for o in objs if o.is_file()]) < 100  # committed files are not copied into the blob store
