import json, os, subprocess, sys, shutil
MOCK = os.environ.get("MOCK_DIR", "/tmp/mock")
ENV = dict(os.environ)
# dibs from this checkout's venv (if any) first, then the agent CLIs (npm -g / uv tool installs)
_HERE = os.path.dirname(os.path.abspath(__file__))
_VENV = os.path.join(_HERE, "..", "..", ".venv", "bin")
ENV["PATH"] = os.pathsep.join([_VENV, os.path.expanduser("~/.local/bin"), ENV.get("PATH", "")])
for k in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"): ENV[k] = "t"
for k in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"): ENV[k] = "t@t"

def sh(cmd, cwd=None, env=None, check=False, quiet=False, timeout=240, stdin=subprocess.DEVNULL):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, env=env or ENV, capture_output=True, text=True, timeout=timeout, stdin=stdin)
    if not quiet:
        out = (r.stdout + r.stderr).strip()
        if out: print(out)
    if check and r.returncode: raise SystemExit(f"FAILED {cmd}: {r.returncode}")
    return r

def script(steps):
    json.dump(steps, open(f"{MOCK}/script.json", "w"))

def clear_log():
    open(f"{MOCK}/log.jsonl", "w").close()

def log():
    return [json.loads(l) for l in open(f"{MOCK}/log.jsonl")]

def newrepo(path):
    shutil.rmtree(path, ignore_errors=True); os.makedirs(path)
    sh("git init -qb main && echo '# demo' > README.md && git add . && git commit -qm init", cwd=path, check=True)

V1 = 'import requests\n\n\ndef fetch(url):\n    r = requests.get(url, timeout=10)\n    return r.json()\n'
HUMAN = '    r = requests.get(url, timeout=30, verify="ca.pem")'
V2 = 'import logging\nimport requests\n\nlog = logging.getLogger(__name__)\n\n\ndef fetch(url):\n    log.info("GET %s", url)\n    r = requests.get(url, timeout=10)\n    return r.json()\n'
GOOD = V2.replace('    r = requests.get(url, timeout=10)', HUMAN)

def human_edit(repo):
    p = os.path.join(repo, "api.py")
    s = open(p).read().replace('    r = requests.get(url, timeout=10)', HUMAN)
    open(p, "w").write(s)

def show(repo, f="api.py"):
    print("---", f); print(open(os.path.join(repo, f)).read().rstrip()); print("---")

def ok(cond, label):
    print(("PASS " if cond else "FAIL ") + label)
    RESULTS.append((label, bool(cond)))
RESULTS = []

def tool_results():
    """tool_result/function output texts that the agent got back, in order."""
    out = []
    for e in log():
        b = e.get("body", {})
        for m in b.get("messages", [])[-1:]:
            c = m.get("content")
            if isinstance(c, list):
                for x in c:
                    if x.get("type") == "tool_result":
                        out.append(json.dumps(x.get("content")))
        for it in (b.get("input") or [])[-3:] if isinstance(b.get("input"), list) else []:
            if isinstance(it, dict) and it.get("type") in ("function_call_output", "custom_tool_call_output"):
                out.append(json.dumps(it.get("output")))
        for c in (b.get("contents") or [])[-1:]:
            for p in c.get("parts", []):
                if "functionResponse" in p: out.append(json.dumps(p["functionResponse"]))
    return out

def all_text():
    return "\n".join(json.dumps(e.get("body")) for e in log())
