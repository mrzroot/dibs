import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import edit, git

from dibs.cli import main

import sysconfig

BIN = Path(sysconfig.get_path("scripts"))


def run(*args, cwd=None, input=None):
    env = dict(os.environ, PATH=str(BIN) + os.pathsep + os.environ.get("PATH", ""), NO_COLOR="1")
    return subprocess.run([sys.executable, "-m", "dibs", *args], cwd=cwd, capture_output=True, text=True,
                          input=input, env=env)


def test_init_is_idempotent_and_uninstall_keeps_foreign_hooks(repo):
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "say done"}]}]},
                                    "model": "x"}))
    assert main(["init", "--all"]) == 0
    assert main(["init", "--all"]) == 0
    data = json.loads(settings.read_text())
    stop_cmds = [h["command"] for g in data["hooks"]["Stop"] for h in g["hooks"]]
    assert stop_cmds == ["say done", "dibs hook claude Stop"]
    assert data["model"] == "x"
    assert (repo / "AGENTS.md").read_text().count("dibs:start") == 1
    cursor = json.loads((repo / ".cursor" / "hooks.json").read_text())
    assert cursor["version"] == 1 and len(cursor["hooks"]["preToolUse"]) == 1
    assert "dibs guard --pre-commit" in (repo / ".git" / "hooks" / "pre-commit").read_text()
    assert main(["uninstall"]) == 0
    data = json.loads(settings.read_text())
    assert [h["command"] for g in data["hooks"]["Stop"] for h in g["hooks"]] == ["say done"]
    assert not (repo / "AGENTS.md").exists()
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


def test_init_files_are_not_reported_as_human_edits(repo):
    assert main(["init", "--agents", "claude,codex"]) == 0
    r = run("brief", "--agent", "claude", cwd=repo)
    assert ".claude/settings.json" not in r.stdout and "AGENTS.md" not in r.stdout


def test_precommit_blocks_reverted_human_lines(repo):
    assert run("init", "--agents", "claude", cwd=repo).returncode == 0
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "dibs")
    edit(repo / "app.py", "timeout = 10", "timeout = 30")
    run("record", cwd=repo)
    run("brief", "--agent", "codex", cwd=repo)
    edit(repo / "app.py", "timeout = 30", "timeout = 10")
    edit(repo / "app.py", "return timeout", "return timeout + 1")
    run("done", "--agent", "codex", cwd=repo)
    git(repo, "add", "app.py")
    env = dict(os.environ, PATH=str(BIN) + os.pathsep + os.environ.get("PATH", ""))
    r = subprocess.run(["git", "commit", "-qm", "agent work"], cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode != 0 and "undid lines you edited by hand" in r.stderr
    assert run("restore", "app.py", cwd=repo).returncode == 0
    text = (repo / "app.py").read_text()
    assert "timeout = 30" in text and "return timeout + 1" in text
    git(repo, "add", "app.py")
    r = subprocess.run(["git", "commit", "-qm", "agent work"], cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr


def test_status_log_blame_json(repo):
    run("status", cwd=repo)
    edit(repo / "README.md", "# demo", "# demo!")
    r = run("status", "--json", cwd=repo)
    data = json.loads(r.stdout)
    assert data["recent"][-1]["path"] == "README.md" and data["recent"][-1]["actor"] == "human"
    assert any("no git remote" in w for w in data["sync"]["warnings"])
    r = run("log", "--json", cwd=repo)
    assert json.loads(r.stdout)[0]["path"] == "README.md"
    r = run("blame", "README.md", "--json", cwd=repo)
    assert json.loads(r.stdout)[0]["actor"] == "human"
    r = run("status", cwd=repo)
    assert "Recent changes" in r.stdout and "README.md" in r.stdout


def test_run_wrapper_attributes_to_agent(repo):
    run("status", cwd=repo)
    edit(repo / "README.md", "# demo", "# human")
    r = run("run", "--agent", "aider", "--", sys.executable, "-c",
            "import os; open('gen.py','w').write('x = 1\\n'); print(os.environ['DIBS_AGENT'])", cwd=repo)
    assert r.returncode == 0 and r.stdout.strip() == "aider"
    assert "README.md — edited by human" in r.stderr
    evs = json.loads(run("log", "--json", cwd=repo).stdout)
    assert [(e["actor"], e["path"]) for e in evs] == [("human", "README.md"), ("aider", "gen.py")]


def test_guard_cli_and_config(repo):
    edit(repo / "app.py", "timeout = 10", "timeout = 30")
    run("record", cwd=repo)
    r = run("guard", "app.py", "--new", "-", cwd=repo, input="def f():\n    timeout = 10\n    return timeout\n")
    assert r.returncode == 1 and "would undo" in r.stdout
    assert run("config", "guard", "warn", cwd=repo).returncode == 0
    assert run("config", "guard", cwd=repo).stdout.strip() == "warn"


def test_hook_entrypoint(repo):
    r = run("hook", "claude", "UserPromptSubmit", cwd=repo, input=json.dumps({"cwd": str(repo), "prompt": "x"}))
    assert r.returncode == 0
    json.loads(r.stdout)


def test_uncommitted_work_before_dibs_is_protected(repo):
    edit(repo / "app.py", "timeout = 10", "timeout = 30")
    (repo / "notes.txt").write_text("my notes\n")
    r = run("brief", "--agent", "claude", cwd=repo)
    assert "app.py — edited by someone (you or an earlier agent)" in r.stdout
    assert "notes.txt — created by someone" in r.stdout
    r = run("guard", "app.py", "--new", "-", cwd=repo, input="def f():\n    timeout = 10\n    return timeout\n")
    assert r.returncode == 1
