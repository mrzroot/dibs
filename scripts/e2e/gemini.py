"""End-to-end: real Gemini CLI against the mock model, with dibs hooks installed.

Turns: (1) write_file creates api.py; the human edits a line by hand; (2) write_file from stale memory, which
BeforeTool must deny; (3) a `replace` that keeps the human line is allowed; (4) a `replace` that reverts it is blocked;
(5) a run_shell_command `sed` revert is noticed afterwards (AfterTool note) until `dibs restore`.
Pass `notrust` to leave the folder out of trustedFolders.json.
"""
import json
import os
import shutil
import sys

from lib import (
    AGENT_LINE, ENV, HUMAN, MOCK_URL, SED_REVERT, V1, V2,
    all_text, clear_log, finish, human_edit, ok, read_file, script, setup_repo, sh, show, tool_results,
)

REPO = "/tmp/e2e-gemini"
GEMINI_HOME = "/tmp/gm-home"
TRUST_FOLDER = sys.argv[1:] != ["notrust"]

setup_repo(REPO, "gemini", quiet=True)

shutil.rmtree(GEMINI_HOME, ignore_errors=True)
os.makedirs(f"{GEMINI_HOME}/.gemini")
with open(f"{GEMINI_HOME}/.gemini/settings.json", "w") as fh:
    json.dump({"security": {"auth": {"selectedType": "gemini-api-key"}}}, fh)
if TRUST_FOLDER:
    with open(f"{GEMINI_HOME}/.gemini/trustedFolders.json", "w") as fh:
        json.dump({REPO: "TRUST_FOLDER"}, fh)

GEMINI_ENV = dict(ENV, GEMINI_CLI_HOME=GEMINI_HOME, GOOGLE_GEMINI_BASE_URL=MOCK_URL, GEMINI_API_KEY="x")


def gemini(prompt):
    """One non-interactive `gemini -p` turn in REPO (--yolo: no tool confirmation prompts)."""
    result = sh(["gemini", "-p", prompt, "--yolo", "-m", "gemini-2.5-pro"], cwd=REPO, env=GEMINI_ENV, quiet=True)
    print("  out:", result.stdout.strip()[-200:])
    return result


def replace_step(old, new, instruction):
    """A step that calls Gemini's `replace` tool (exact old_string -> new_string inside one file)."""
    return {"tool": "replace", "input": {
        "file_path": f"{REPO}/api.py", "old_string": old, "new_string": new, "instruction": instruction,
    }}


clear_log()
print("== turn 1: gemini write_file")
script([{"tool": "write_file", "input": {"file_path": f"{REPO}/api.py", "content": V1}}, {"text": "created"}])
gemini("create api.py")
ok(read_file(REPO) == V1, "gemini write_file created api.py")

print("== human edits")
human_edit(REPO)

clear_log()
print("== turn 2: gemini rewrites from memory with write_file")
script([{"tool": "write_file", "input": {"file_path": f"{REPO}/api.py", "content": V2}}, {"text": "added logging"}])
gemini("add logging")
ok("Since your last turn" in all_text() and "timeout=30" in all_text(), "BeforeAgent brief reached the model")
results = tool_results()
print("tool results:", [t[:300] for t in results])
ok(any("would undo changes the human made" in t for t in results), "BeforeTool deny reason reached the model")
ok(HUMAN in read_file(REPO), "human line survived write_file")

clear_log()
print("== turn 3: gemini replace that builds on the human line")
script([replace_step("import requests\n", "import logging\nimport requests\n", "add import"), {"text": "ok"}])
gemini("add import")
ok(read_file(REPO).startswith("import logging") and HUMAN in read_file(REPO), "non-reverting replace allowed")

clear_log()
print("== turn 4: gemini replace that reverts")
script([replace_step(HUMAN, AGENT_LINE, "reset"), {"text": "ok"}])
gemini("reset timeout")
ok(HUMAN in read_file(REPO), "reverting replace blocked")

clear_log()
print("== turn 5: gemini reverts via run_shell_command")
script([{"tool": "run_shell_command", "input": {"command": SED_REVERT, "description": "reset"}}, {"text": "reset"}])
gemini("reset timeout via shell")
show(REPO)
ok("undid lines the human edited" in all_text(), "AfterTool revert note reached the model")
sh("dibs restore api.py", cwd=REPO)
ok(HUMAN in read_file(REPO) and read_file(REPO).startswith("import logging"), "restore put back the human line")
finish(REPO)
