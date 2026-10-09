import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dibs import hooks  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


def git(cwd, *args, check=True):
    env = dict(os.environ, **GIT_ENV)
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=check, env=env)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in GIT_ENV:
        monkeypatch.setenv(k, GIT_ENV[k])
    monkeypatch.delenv("DIBS_ROOT", raising=False)
    monkeypatch.delenv("DIBS_GUARD", raising=False)
    monkeypatch.delenv("DIBS_AGENT", raising=False)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    (root / "app.py").write_text("def f():\n    timeout = 10\n    return timeout\n")
    (root / "README.md").write_text("# demo\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "init")
    monkeypatch.chdir(root)
    return root


def hook(tool, event, root, **payload):
    payload.setdefault("cwd", str(root))
    out, code = hooks.main(tool, event, json.dumps(payload))
    return json.loads(out), code


def edit(path, old, new):
    p = Path(path)
    s = p.read_text()
    assert old in s, (old, s)
    p.write_text(s.replace(old, new))
