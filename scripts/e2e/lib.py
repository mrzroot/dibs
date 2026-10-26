"""Shared helpers for the end-to-end scripts (cc.py, codex.py, gemini.py, aider.py).

Each script drives a real agent CLI against mock.py. This module holds what they have in common:
running shell commands, scripting the mock's next replies, reading what the agent sent back to the
mock, and a tiny PASS/FAIL recorder.
"""
import json
import os
import shutil
import subprocess

MOCK_PORT = int(os.environ.get("MOCK_PORT", "18800"))
MOCK_URL = f"http://127.0.0.1:{MOCK_PORT}"
MOCK_DIR = os.environ.get("MOCK_DIR", "/tmp/mock")
MOCK_SCRIPT = os.path.join(MOCK_DIR, "script.json")  # steps the mock will play, consumed in order
MOCK_LOG = os.path.join(MOCK_DIR, "log.jsonl")       # every request the mock received

API_FILE = "api.py"

# The file the "agent" creates (V1), the line the human then edits by hand (HUMAN), and what the agent
# rewrites the file to from its stale memory (V2), which would silently undo that human line.
V1 = 'import requests\n\n\ndef fetch(url):\n    r = requests.get(url, timeout=10)\n    return r.json()\n'
AGENT_LINE = '    r = requests.get(url, timeout=10)'
HUMAN = '    r = requests.get(url, timeout=30, verify="ca.pem")'
V2 = (
    'import logging\nimport requests\n\nlog = logging.getLogger(__name__)\n\n\n'
    'def fetch(url):\n    log.info("GET %s", url)\n    r = requests.get(url, timeout=10)\n    return r.json()\n'
)
# The same revert as a shell command, for the turns where the agent undoes the human line through Bash.
SED_REVERT = "sed -i 's/timeout=30, verify=\"ca.pem\")/timeout=10)/' api.py"

# dibs comes from this checkout's venv (if any) first, then the agent CLIs (npm -g / uv tool installs).
_HERE = os.path.dirname(os.path.abspath(__file__))
_VENV_BIN = os.path.join(_HERE, "..", "..", ".venv", "bin")

ENV = dict(os.environ)
ENV["PATH"] = os.pathsep.join([_VENV_BIN, os.path.expanduser("~/.local/bin"), ENV.get("PATH", "")])
for _var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
    ENV[_var] = "t"
for _var in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
    ENV[_var] = "t@t"

RESULTS = []  # (label, passed) for every ok() call in this run


def sh(cmd, cwd=None, env=None, check=False, quiet=False, timeout=240, stdin=subprocess.DEVNULL):
    """Run *cmd* (a string goes through the shell, a list does not) and print its output unless *quiet*.

    stdin defaults to /dev/null so an agent CLI never waits for a prompt. With *check*, a non-zero exit stops the run.
    """
    result = subprocess.run(
        cmd, shell=isinstance(cmd, str), cwd=cwd, env=env or ENV,
        capture_output=True, text=True, timeout=timeout, stdin=stdin,
    )
    if not quiet:
        output = (result.stdout + result.stderr).strip()
        if output:
            print(output)
    if check and result.returncode:
        raise SystemExit(f"FAILED {cmd}: {result.returncode}")
    return result


def script(steps):
    """Set the mock's next replies: {"tool": name, "input": {...}} calls a tool, {"text": "..."} ends the turn."""
    with open(MOCK_SCRIPT, "w") as fh:
        json.dump(steps, fh)


def clear_log():
    open(MOCK_LOG, "w").close()


def log():
    with open(MOCK_LOG) as fh:
        return [json.loads(line) for line in fh]


def newrepo(path):
    """A fresh git repository at *path* with one commit."""
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    sh("git init -qb main && echo '# demo' > README.md && git add . && git commit -qm init", cwd=path, check=True)


def setup_repo(path, agent, quiet=False):
    """newrepo(), then `dibs init --agents <agent>` committed, so the hooks are live from the first turn."""
    newrepo(path)
    sh(f"dibs init --agents {agent}", cwd=path, quiet=quiet)
    sh("git add -A && git commit -qm 'dibs init'", cwd=path)


def read_file(repo, name=API_FILE):
    """The file's text, or "" if it does not exist (so a missing file is a FAIL, not a crash)."""
    try:
        with open(os.path.join(repo, name)) as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def human_edit(repo):
    """The human changes one line of api.py by hand, outside any agent."""
    edited = read_file(repo).replace(AGENT_LINE, HUMAN)  # read before open("w") truncates the file
    with open(os.path.join(repo, API_FILE), "w") as fh:
        fh.write(edited)


def show(repo, name=API_FILE):
    print("---", name)
    print(read_file(repo, name).rstrip())
    print("---")


def ok(cond, label):
    """Print and record PASS/FAIL for one expectation."""
    print(("PASS " if cond else "FAIL ") + label)
    RESULTS.append((label, bool(cond)))


def finish(repo):
    """Print dibs's own view of the run (log, hook errors) and the PASS tally."""
    sh("NO_COLOR=1 dibs log -n 20", cwd=repo)
    sh("cat .git/dibs/hook-errors.log", cwd=repo)
    print("RESULTS", sum(passed for _, passed in RESULTS), "/", len(RESULTS))


def tool_results():
    """The tool-result texts the agent sent back to the mock, in order, whatever the API dialect.

    Anthropic: a tool_result block in the last message. OpenAI Responses (Codex): function_call_output or
    custom_tool_call_output items among the last three inputs. Gemini: a functionResponse part in the last content.
    """
    results = []
    for entry in log():
        body = entry.get("body", {})
        for message in body.get("messages", [])[-1:]:
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result":
                        results.append(json.dumps(block.get("content")))
        inputs = body.get("input")
        for item in (inputs or [])[-3:] if isinstance(inputs, list) else []:
            if isinstance(item, dict) and item.get("type") in ("function_call_output", "custom_tool_call_output"):
                results.append(json.dumps(item.get("output")))
        for content in (body.get("contents") or [])[-1:]:
            for part in content.get("parts", []):
                if "functionResponse" in part:
                    results.append(json.dumps(part["functionResponse"]))
    return results


def all_text():
    """Everything the agent sent to the mock, as one string to search for the dibs messages."""
    return "\n".join(json.dumps(entry.get("body")) for entry in log())
