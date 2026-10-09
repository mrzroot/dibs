import json

from conftest import edit, hook

from dibs.core import Dibs
from dibs.hooks import parse_patch
from dibs.repo import Repo


def _setup_human_edit(repo):
    hook("claude", "UserPromptSubmit", repo, prompt="hi")
    hook("claude", "Stop", repo)
    edit(repo / "app.py", "timeout = 10", "timeout = 30  # slow network")


def test_claude_prompt_injects_brief(repo):
    _setup_human_edit(repo)
    out, code = hook("claude", "UserPromptSubmit", repo, prompt="add logging")
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert code == 0 and out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "timeout = 30  # slow network" in ctx


def test_claude_pretool_asks_on_revert_and_allows_others(repo):
    _setup_human_edit(repo)
    hook("claude", "UserPromptSubmit", repo, prompt="x")
    out, _ = hook("claude", "PreToolUse", repo, tool_name="Edit", tool_input={
        "file_path": str(repo / "app.py"), "old_string": "timeout = 30  # slow network", "new_string": "timeout = 10"})
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "ask" and "dibs allow app.py" in hso["permissionDecisionReason"]
    out, _ = hook("claude", "PreToolUse", repo, tool_name="Edit", tool_input={
        "file_path": str(repo / "app.py"), "old_string": "    return timeout", "new_string": "    return timeout * 2"})
    assert out == {}


def test_multiedit_and_write(repo):
    _setup_human_edit(repo)
    out, _ = hook("claude", "PreToolUse", repo, tool_name="MultiEdit", tool_input={
        "file_path": str(repo / "app.py"),
        "edits": [{"old_string": "def f():", "new_string": "def f2():"},
                  {"old_string": "  # slow network", "new_string": ""}]})
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    out, _ = hook("claude", "PreToolUse", repo, tool_name="Write", tool_input={
        "file_path": str(repo / "app.py"), "content": "def f():\n    timeout = 30  # slow network\n    return 1\n"})
    assert out == {}


def test_guard_modes(repo, monkeypatch):
    _setup_human_edit(repo)
    payload = dict(tool_name="Edit", tool_input={"file_path": "app.py", "old_string": "30  # slow network",
                                                  "new_string": "10"})
    monkeypatch.setenv("DIBS_GUARD", "deny")
    out, _ = hook("claude", "PreToolUse", repo, **payload)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    monkeypatch.setenv("DIBS_GUARD", "warn")
    assert hook("claude", "PreToolUse", repo, **payload)[0] == {}
    monkeypatch.setenv("DIBS_GUARD", "off")
    assert hook("claude", "PreToolUse", repo, **payload)[0] == {}


def test_codex_apply_patch_denied(repo):
    _setup_human_edit(repo)
    patch = "*** Begin Patch\n*** Update File: app.py\n@@\n-    timeout = 30  # slow network\n+    timeout = 10\n*** End Patch\n"
    out, _ = hook("codex", "PreToolUse", repo, tool_name="apply_patch", tool_input={"command": patch})
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    out, _ = hook("codex", "Stop", repo)
    assert out == {}


def test_codex_post_apply_patch_attributes(repo):
    hook("codex", "UserPromptSubmit", repo, prompt="x")
    (repo / "new.py").write_text("print(1)\n")
    patch = "*** Begin Patch\n*** Add File: new.py\n+print(1)\n*** End Patch"
    hook("codex", "PostToolUse", repo, tool_name="apply_patch", tool_input={"command": patch})
    evs = Dibs(Repo.discover(repo)).events()
    assert [(e["actor"], e["path"]) for e in evs] == [("codex", "new.py")]


def test_gemini_flow(repo):
    hook("gemini", "BeforeAgent", repo, prompt="x")
    hook("gemini", "AfterAgent", repo)
    edit(repo / "app.py", "timeout = 10", "timeout = 30  # slow network")
    out, _ = hook("gemini", "BeforeAgent", repo, prompt="y")
    assert "slow network" in out["hookSpecificOutput"]["additionalContext"]
    out, _ = hook("gemini", "BeforeTool", repo, tool_name="replace", tool_input={
        "file_path": "app.py", "old_string": "timeout = 30  # slow network", "new_string": "timeout = 10"})
    assert out["decision"] == "deny"
    edit(repo / "README.md", "# demo", "# demo 2")
    out, _ = hook("gemini", "AfterTool", repo, tool_name="write_file", tool_input={"file_path": "README.md", "content": "x"})
    assert out == {}
    assert Dibs(Repo.discover(repo)).events()[-1]["actor"] == "gemini"


def test_cursor_flow_brief_after_first_tool(repo):
    roots = {"workspace_roots": [str(repo)], "cwd": None}
    hook("cursor", "beforeSubmitPrompt", repo, **roots)
    hook("cursor", "stop", repo, **roots)
    edit(repo / "app.py", "timeout = 10", "timeout = 30  # slow network")
    out, _ = hook("cursor", "beforeSubmitPrompt", repo, prompt="x", **roots)
    assert out == {"continue": True}
    out, _ = hook("cursor", "postToolUse", repo, tool_name="Read", tool_input={"file_path": "app.py"}, **roots)
    assert "slow network" in out["additional_context"]
    out, _ = hook("cursor", "postToolUse", repo, tool_name="Read", tool_input={}, **roots)
    assert out == {}  # delivered once
    out, _ = hook("cursor", "preToolUse", repo, tool_name="Write", tool_input={
        "file_path": str(repo / "app.py"), "content": "def f():\n    timeout = 10\n"}, **roots)
    assert out["permission"] == "deny" and "dibs allow" in out["agent_message"]
    out, _ = hook("cursor", "preToolUse", repo, tool_name="Write", tool_input={
        "file_path": str(repo / "README.md"), "content": "# hi\n"}, **roots)
    assert out == {"permission": "allow"}


def test_bash_revert_warns_in_post_tool(repo):
    _setup_human_edit(repo)
    hook("claude", "UserPromptSubmit", repo, prompt="x")
    edit(repo / "app.py", "timeout = 30  # slow network", "timeout = 10")
    out, _ = hook("claude", "PostToolUse", repo, tool_name="Bash", tool_input={"command": "sed -i ..."})
    assert "undid lines the human edited" in out["hookSpecificOutput"]["additionalContext"]


def test_hook_fails_open_on_garbage(repo):
    from dibs.hooks import main
    out, code = main("cursor", "preToolUse", "{not json")
    assert code == 0 and json.loads(out) == {"permission": "allow"}
    assert (repo / ".git" / "dibs" / "hook-errors.log").exists()


def test_parse_patch():
    files = parse_patch("*** Begin Patch\n*** Update File: a.py\n*** Move to: b.py\n@@ def x\n a\n-b\n+c\n"
                        "*** Delete File: d.py\n*** Add File: e.py\n+new\n*** End Patch")
    assert files[0] == {"op": "M", "path": "a.py", "move_to": "b.py", "minus": ["b"], "plus": ["c"]}
    assert files[1]["op"] == "D" and files[2] == {"op": "A", "path": "e.py", "minus": [], "plus": ["new"]}


def test_persian_text_through_cli_hook(repo):
    import os
    import subprocess
    import sys
    run = lambda ev, p: subprocess.run([sys.executable, "-m", "dibs", "hook", "codex", ev], cwd=repo,
                                       input=json.dumps(p, ensure_ascii=False).encode("utf-8"), capture_output=True)
    (repo / "fa.md").write_text("سلام دنیا\n", encoding="utf-8")
    run("UserPromptSubmit", {"cwd": str(repo), "prompt": "x"})
    run("Stop", {"cwd": str(repo)})
    (repo / "fa.md").write_text("سلام دنیای زیبا\n", encoding="utf-8")
    r = run("UserPromptSubmit", {"cwd": str(repo), "prompt": "ادامه بده"})
    assert "سلام دنیای زیبا" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    patch = "*** Begin Patch\n*** Update File: fa.md\n@@\n-سلام دنیای زیبا\n+سلام دنیا\n*** End Patch"
    r = run("PreToolUse", {"cwd": str(repo), "tool_name": "apply_patch", "tool_input": {"command": patch}})
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
