"""End-to-end: real Codex CLI (`codex exec`) against the mock model, with dibs hooks installed.

Turns: (1) Codex adds api.py with apply_patch; the human edits a line by hand; (2) Codex patches from its stale memory,
which PreToolUse must deny; (3) a shell `sed` revert is only noticed afterwards (PostToolUse note, `dibs status`),
until `dibs restore`. Pass `notrust` to run without --dangerously-bypass-hook-trust (hooks stay untrusted).
"""
import sys

from lib import (
    ENV, HUMAN, SED_REVERT, V1,
    all_text, clear_log, finish, human_edit, log, ok, read_file, script, setup_repo, sh, show, tool_results,
)

REPO = "/tmp/e2e-codex"
TRUST_HOOKS = sys.argv[1:] != ["notrust"]

setup_repo(REPO, "codex")
CODEX_ENV = dict(ENV, CODEX_HOME="/tmp/codex-home", MOCK_API_KEY="x")


def codex(prompt, resume=True):
    """One `codex exec` turn in REPO; *resume* continues the last session."""
    args = ["codex", "exec", "--skip-git-repo-check"]
    if TRUST_HOOKS:
        args.append("--dangerously-bypass-hook-trust")
    if resume:
        args += ["resume", "--last"]
    return sh(args + [prompt], cwd=REPO, env=CODEX_ENV, quiet=True)


def hook_lines(result, *words):
    """The first 12 stderr lines that mention one of *words* (case-insensitive): Codex logs hook activity there."""
    return [line for line in result.stderr.splitlines() if any(w in line.lower() for w in words)][:12]


def patch(body):
    """A step that calls Codex's apply_patch, which is a 'custom' tool (free-form input, not JSON arguments)."""
    return {"tool": "apply_patch", "custom": True, "input": body}


ADD_API_PY = (
    "*** Begin Patch\n*** Add File: api.py\n"
    + "".join("+" + line + "\n" for line in V1.rstrip("\n").split("\n"))
    + "*** End Patch\n"
)
STALE_UPDATE = (
    "*** Begin Patch\n*** Update File: api.py\n@@\n-import requests\n+import logging\n+import requests\n"
    '@@ def fetch(url):\n-    r = requests.get(url, timeout=30, verify="ca.pem")\n'
    '+    log.info("GET %s", url)\n+    r = requests.get(url, timeout=10)\n*** End Patch\n'
)

clear_log()
print("== turn 1: codex adds api.py via apply_patch")
script([patch(ADD_API_PY), {"text": "created"}])
result = codex("create api.py", resume=False)
print(result.stdout[-300:], hook_lines(result, "hook"))
first_requests = log()
print("tools:", first_requests[0]["tools"] if first_requests else None)
ok(read_file(REPO) == V1, "codex apply_patch created api.py")

print("== human edits")
human_edit(REPO)

clear_log()
print("== turn 2: codex patches from its stale memory")
script([patch(STALE_UPDATE), {"text": "added logging"}])
result = codex("add logging")
print(hook_lines(result, "hook", "dibs"))
ok("Since your last turn" in all_text() and "timeout=30" in all_text(), "UserPromptSubmit brief reached the model")
results = tool_results()
print("tool results:", [t[:300] for t in results])
ok(any("would undo changes the human made" in t for t in results), "PreToolUse deny reason reached the model")
ok(HUMAN in read_file(REPO), "human line survived the patch")

clear_log()
print("== turn 3: codex reverts via shell")
script([{"tool": "exec_command", "input": {"cmd": SED_REVERT}}, {"text": "reset"}])
result = codex("reset timeout")
print(hook_lines(result, "hook"))
show(REPO)
ok("undid lines the human edited" in all_text(), "PostToolUse revert note reached the model")
status = sh("NO_COLOR=1 dibs status", cwd=REPO, quiet=True)
ok("Reverted human lines" in status.stdout, "dibs status lists the revert")
sh("dibs restore api.py", cwd=REPO)
ok(HUMAN in read_file(REPO), "restore put back the human line")
finish(REPO)
