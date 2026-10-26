"""End-to-end: real Claude Code against the mock model, with dibs hooks installed.

Turns: (1) Claude writes api.py; the human edits a line by hand; (2) Claude rewrites the file from memory, which
PreToolUse must block; (3) an Edit that keeps the human line is allowed; (4) a Bash `sed` revert cannot be stopped in
advance, so PostToolUse tells the model, `dibs status` lists it and the pre-commit hook refuses until `dibs restore`.
"""
import os
import shutil

from lib import (
    ENV, HUMAN, MOCK_URL, SED_REVERT, V1, V2,
    all_text, clear_log, finish, human_edit, ok, read_file, script, setup_repo, sh, show, tool_results,
)

REPO = "/tmp/e2e-claude"
CLAUDE_HOME = "/tmp/cc-home"

setup_repo(REPO, "claude")
CLAUDE_ENV = dict(
    ENV, CLAUDE_CONFIG_DIR=CLAUDE_HOME, ANTHROPIC_BASE_URL=MOCK_URL, ANTHROPIC_API_KEY="sk-ant-dummy",
    DISABLE_AUTOUPDATER="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
)
shutil.rmtree(CLAUDE_HOME, ignore_errors=True)
os.makedirs(CLAUDE_HOME)


def claude(prompt, mode="acceptEdits", cont=True):
    """One `claude -p` turn in REPO; *cont* continues the previous session."""
    args = ["claude", "-p", prompt, "--permission-mode", mode, "--model", "claude-sonnet-4-5", "--output-format", "text"]
    if cont:
        args.insert(1, "--continue")
    return sh(args, cwd=REPO, env=CLAUDE_ENV)


def commit_wip():
    return sh("git add -A && git commit -qm wip", cwd=REPO)


clear_log()
print("== turn 1: claude writes api.py")
script([{"tool": "Write", "input": {"file_path": f"{REPO}/api.py", "content": V1}}, {"text": "wrote api.py"}])
claude("create api.py", cont=False)
ok(read_file(REPO) == V1, "claude Write created api.py")

print("== human edits api.py by hand")
human_edit(REPO)

clear_log()
print("== turn 2: claude reads, then rewrites from memory")
script([
    {"tool": "Read", "input": {"file_path": f"{REPO}/api.py"}},
    {"tool": "Write", "input": {"file_path": f"{REPO}/api.py", "content": V2}},
    {"text": "added logging"},
])
claude("add logging")
ok("Since your last turn" in all_text() and "timeout=30" in all_text(), "UserPromptSubmit brief reached the model")
results = tool_results()
print("tool results:", [t[:300] for t in results])
ok(any("would undo changes the human made" in t for t in results), "PreToolUse guard message reached the model")
ok(HUMAN in read_file(REPO), "human line survived the Write")

clear_log()
print("== turn 3: claude builds on the human line")
script([
    {"tool": "Edit", "input": {
        "file_path": f"{REPO}/api.py", "old_string": "import requests\n", "new_string": "import logging\nimport requests\n",
    }},
    {"text": "ok"},
])
claude("add logging import")
ok(read_file(REPO).startswith("import logging\nimport requests") and HUMAN in read_file(REPO), "non-reverting Edit allowed")

clear_log()
print("== turn 4: claude reverts through Bash (cannot be stopped in advance)")
script([{"tool": "Bash", "input": {"command": SED_REVERT, "description": "reset timeout"}}, {"text": "reset"}])
claude("reset the timeout", mode="bypassPermissions")
show(REPO)
results = tool_results()
print("tool results:", [t[:400] for t in results])
ok("undid lines the human edited" in all_text(), "PostToolUse revert note reached the model")
status = sh("NO_COLOR=1 dibs status", cwd=REPO)
ok("Reverted human lines" in status.stdout, "dibs status lists the revert")
ok(commit_wip().returncode != 0, "pre-commit blocks the commit")
sh("dibs restore api.py", cwd=REPO)
show(REPO)
ok(HUMAN in read_file(REPO) and read_file(REPO).startswith("import logging"),
   "restore put back the human line and kept the agent's import")
ok(commit_wip().returncode == 0, "commit allowed after restore")
finish(REPO)
