# Contributing to dibs

Thanks for helping! Issues and pull requests in **English or Persian** are welcome.
Good places to start: issues labelled [`good first issue`](https://github.com/mrzroot/dibs/labels/good%20first%20issue).

## Development setup

```bash
git clone https://github.com/mrzroot/dibs && cd dibs
python -m venv .venv && . .venv/bin/activate
pip install -e . pytest
python -m pytest -q
```

dibs has **no runtime dependencies** (standard library only, Python 3.9+). Please keep it that way.

## Where things live

| Path | What |
|---|---|
| `dibs/core.py` | Journal, attribution, turn briefs, revert detection, restore |
| `dibs/hooks.py` | Hook entry points for Claude Code, Codex, Gemini CLI and Cursor (one payload/answer format each) |
| `dibs/install.py` | What `dibs init` writes for every agent, and `dibs uninstall` |
| `dibs/doctor.py` | `dibs doctor` checks (hook trust, disabled hooks, pre-commit) |
| `dibs/mcp.py` | MCP server for Copilot and other MCP clients |
| `tests/` | pytest suites; `conftest.py` has a temp git repo fixture |
| `scripts/e2e/` | End-to-end runs against the **real** agent CLIs with a mock model (no accounts needed) |
| `scripts/bench.py` | Large-repository timings |

## Changing hooks

Agent hook formats change between versions. When you touch `hooks.py` or `install.py`:

1. Take payloads and answers from the agent's docs **or its source**, not from memory, and cite the version.
2. Add a unit test with that payload.
3. If you can, run the matching script in `scripts/e2e/` and update the "Verified with" table in the README.

## Security

Please report vulnerabilities privately via [GitHub security advisories](https://github.com/mrzroot/dibs/security/advisories/new).
