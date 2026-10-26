"""End-to-end: real aider against the mock model, run under `dibs run` (aider has no hook system).

Turns: (1) aider writes api.py; the human edits a line by hand; (2) aider rewrites the whole file from memory and
commits it; `dibs run` records that, so `dibs status` lists the revert and `dibs restore`
puts the human line back while keeping aider's logging change.
aider speaks OpenAI Chat Completions; start mock.py with MOCK_MAIN_ALWAYS=1 so every chat request consumes a scripted step.
"""
import json
import os

from lib import (
    ENV, HUMAN, MOCK_URL, V1, V2,
    clear_log, finish, human_edit, log, ok, read_file, script, setup_repo, sh, show,
)

REPO = "/tmp/e2e-aider"
AIDER_HOME = "/tmp/aider-home"

setup_repo(REPO, "aider")
AIDER_ENV = dict(
    ENV, OPENAI_API_BASE=f"{MOCK_URL}/v1", OPENAI_API_KEY="x", AIDER_ANALYTICS="false", HOME=AIDER_HOME,
)
os.makedirs(AIDER_HOME, exist_ok=True)


def whole(content):
    """A reply in aider's 'whole' edit format: the file name, then the full new content in a code fence."""
    return {"text": "api.py\n```python\n" + content + "```\n"}


def aider(message, steps):
    """One `aider --message` turn under `dibs run`, replaying *steps*; prints the tail of aider's output."""
    script(steps)
    result = sh(
        ["dibs", "run", "--agent", "aider", "--", "aider", "--model", "openai/mock", "--edit-format", "whole",
         "--yes-always", "--no-check-update", "--no-show-model-warnings", "--no-pretty", "--no-stream",
         "--weak-model", "openai/mock", "--message", message, "api.py"],
        cwd=REPO, env=AIDER_ENV, quiet=True,
    )
    print("  rc", result.returncode, "|", "\n  ".join((result.stdout + result.stderr).strip().splitlines()[-14:]))
    return result


# aider edits files it is given, so api.py must already exist and be tracked
with open(f"{REPO}/api.py", "w") as fh:
    fh.write("")
sh("git add api.py && git commit -qm 'empty api'", cwd=REPO)

clear_log()
print("== turn 1: aider writes api.py")
aider("create api.py", [whole(V1), {"text": "feat: add api.py"}])
ok(read_file(REPO) == V1, "aider wrote api.py")
sh("git log --oneline -3", cwd=REPO)

print("== human edits")
human_edit(REPO)

clear_log()
print("== turn 2: aider rewrites from memory")
aider("add logging", [whole(V2), {"text": "feat: add logging"}])
show(REPO)
sh("git log --oneline -4; git status --short", cwd=REPO)
status = sh("NO_COLOR=1 dibs status", cwd=REPO)
ok("Reverted human lines" in status.stdout, "dibs status lists aider's revert")
sh("dibs restore api.py", cwd=REPO)
ok(HUMAN in read_file(REPO) and "import logging" in read_file(REPO), "restore put back the human line, kept aider's logging")
for entry in log():
    print("REQ", entry["path"], json.dumps(entry["body"].get("messages", [{}])[-1])[:200])
finish(REPO)
