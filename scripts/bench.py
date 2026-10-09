"""Rough timing of dibs on a big repo: python scripts/bench.py /path/to/repo [file-to-edit]."""
import json, os, subprocess, sys, time
root = os.path.abspath(sys.argv[1]); target = sys.argv[2] if len(sys.argv) > 2 else None
def run(name, args, payload=None):
    t = time.perf_counter()
    r = subprocess.run(args, cwd=root, input=json.dumps(payload).encode() if payload is not None else None,
                       capture_output=True)
    dt = time.perf_counter() - t
    print(f"{dt:7.2f}s  {name}" + ("" if r.returncode == 0 else f"  (exit {r.returncode}: {r.stderr[-200:]!r})"))
    return dt
base = {"session_id": "bench", "cwd": root}
run("dibs init", ["dibs", "init", "--agents", "claude", "--no-agents-md"])
run("dibs status (first)", ["dibs", "status"])
run("dibs status (warm)", ["dibs", "status"])
run("UserPromptSubmit (no changes)", ["dibs", "hook", "claude", "UserPromptSubmit"], dict(base, prompt="x"))
if target:
    with open(os.path.join(root, target), "a") as fh: fh.write("\nX = 1\n")
    run("UserPromptSubmit (1 human edit)", ["dibs", "hook", "claude", "UserPromptSubmit"], dict(base, prompt="x"))
    run("PreToolUse Edit", ["dibs", "hook", "claude", "PreToolUse"],
        dict(base, tool_name="Edit", tool_input={"file_path": os.path.join(root, target), "old_string": "X = 1", "new_string": "X = 2"}))
    run("PostToolUse Edit", ["dibs", "hook", "claude", "PostToolUse"],
        dict(base, tool_name="Edit", tool_input={"file_path": os.path.join(root, target)}))
run("PostToolUse Bash (full scan)", ["dibs", "hook", "claude", "PostToolUse"], dict(base, tool_name="Bash", tool_input={"command": "ls"}))
run("Stop", ["dibs", "hook", "claude", "Stop"], base)
sd = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=root, capture_output=True, text=True).stdout.strip()
st = os.path.join(sd, "dibs", "state.json")
print(f"state.json {os.path.getsize(st)/1e6:.1f} MB")
