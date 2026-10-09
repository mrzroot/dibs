# dibs

**Call dibs on your edits.** dibs keeps AI coding agents (Claude Code, Codex, Cursor, Gemini CLI,
Copilot, Aider…) from overwriting what you changed by hand, and tells everyone what is not committed
or pushed yet.

[فارسی](README.fa.md) · [Website](https://mrzroot.github.io/dibs/) · MIT · Python 3.9+ · no dependencies

```text
you:    fix the timeout by hand (10 → 30, add the corporate CA)
agent:  "add logging" … rewrites the function from memory, timeout=10 is back
```

That second line is the bug dibs exists for. Agents do not see the edits you made between their
turns, so they "fix" them back. Cursor's staff call it a known issue on their forum, with no fix planned.

## What dibs does

| | |
|---|---|
| **Attribution journal** | Every file change is recorded with who made it: `human`, `claude`, `cursor`, `codex`, `gemini`, `copilot`, `aider` or any name, plus the changed lines. Hooks report the agents' edits; everything else between turns is yours. |
| **Brief at every turn** | When you send a prompt, the agent first gets a short "[dibs]" note: the files you changed since its last turn, with the lines, and "do not revert these". Other agents' edits are listed too. |
| **Revert guard** | Before an agent edit runs, dibs checks whether it would remove lines you added or bring back lines you deleted. Claude Code asks you to approve; Codex, Cursor and Gemini get a denial that explains which lines are yours. |
| **After-the-fact detection** | Reverts done through shell commands (`sed`, `cat >`, scripts) are caught after the command, reported to the agent, shown in `dibs status`, and stopped at `git commit` by a pre-commit hook. |
| **Restore** | `dibs restore file` puts back only your lines and keeps the agent's other work (3-way). `--whole` restores your last version of the file. |
| **Sync status** | Uncommitted files, commits not pushed, branches never pushed, branches on no remote, stashes, repositories with no remote at all, folders that are not git repos. Shown to you (`dibs status`) and to the agent in each brief. |

The journal lives in `.git/dibs/` (or `.dibs/` outside git). It is never committed and nothing leaves your machine.

## Install

dibs is not on PyPI yet. Install the command from GitHub:

```bash
pipx install git+https://github.com/mrzroot/dibs@v0.1.1
# or
uv tool install git+https://github.com/mrzroot/dibs@v0.1.1
# or the wheel attached to the release
pip install dibs-0.1.1-py3-none-any.whl
```

Then, in each repository:

```bash
cd your-project
dibs init            # detects your agents; or: dibs init --all / --agents claude,cursor
dibs status
```

`dibs` must be on your `PATH`, because the hooks call it by name. If a teammate does not have dibs,
Claude Code and the others report a failing hook and carry on; the git pre-commit hook skips itself.

## What `dibs init` wires

| Agent | How dibs plugs in | Brief | Guard before edit | Records edits |
|---|---|---|---|---|
| Claude Code | `.claude/settings.json` hooks: UserPromptSubmit, PreToolUse, PostToolUse, Stop | yes | asks you | Edit, Write, MultiEdit, Bash |
| Codex CLI | `.codex/hooks.json` (trust once: start `codex`, pick "Trust all and continue") + AGENTS.md | yes | denies | apply_patch, exec_command / shell |
| Cursor | `.cursor/hooks.json` + `.cursor/rules/dibs.mdc` | with the prompt (`additional_context`), repeated after the first tool call | denies | Write, Delete, Shell |
| Gemini CLI | `.gemini/settings.json` hooks: BeforeAgent, BeforeTool, AfterTool, AfterAgent (trusted folders only) | yes | denies | write_file, replace, shell |
| Copilot (VS Code) | `.vscode/mcp.json` MCP server + `.github/copilot-instructions.md` | via `dibs_brief` tool | via `dibs_check_edit` tool | at `dibs_done` |
| Aider and others | AGENTS.md block, or `dibs run --agent aider -- aider` | printed at start (aider: passed with `--read`) | after the fact | whole run |
| Any MCP client | `dibs mcp --agent NAME` | `dibs_brief` | `dibs_check_edit` | `dibs_done` |

Plus a git **pre-commit** hook (`dibs guard --pre-commit`). `dibs uninstall` removes all of it and
leaves your own hooks alone. Run `dibs doctor` to check that each agent will really run them
(dibs on PATH, Codex hook trust, Gemini folder trust, disabled hooks, a pre-commit `exec` that would skip dibs).

## A turn, step by step

```text
$ dibs init --agents claude
… you edit api.py by hand: timeout=10 → timeout=30, verify="corp-ca.pem"
… you ask Claude Code: "add logging"

[dibs] Since your last turn these files were changed outside your session — by the human, by hand.
Human edits are intentional: read the current file before editing, build on them, and do not
revert or "fix" them back to your earlier version unless the user asks.
• api.py — edited by human (+1 −1, 0s ago)
    - r = requests.get(url, timeout=10)
    + r = requests.get(url, timeout=30, verify="corp-ca.pem")
[dibs] git: 1 file not committed (1 modified); 1 commit on main not pushed to origin/main.

… Claude tries an Edit that puts timeout=10 back. Claude Code asks you:

dibs: this edit to api.py would undo changes the human made by hand.
It removes lines the human added or changed:
  + r = requests.get(url, timeout=30, verify="corp-ca.pem")
It brings back lines the human deleted:
  - r = requests.get(url, timeout=10)
Keep the human's version and make your change around it. Only if the user explicitly asked
to change these lines, run `dibs allow api.py` and retry.
```

## Commands

```text
dibs init [--agents a,b | --all] [--no-git-hook] [--no-agents-md] [--command CMD]
dibs status [--json]             sync state, agents, reverted lines, recent changes
dibs sync [--fetch] [--strict]   uncommitted / unpushed / no remote
dibs log [-n N] [--actor A] [--path P] [--diff] [--json]
dibs blame FILE [--json]         who last wrote each line (human or which agent)
dibs restore FILE [--whole] [--event N] [--dry-run]
dibs ack [N … | --all]           accept a revert as intended
dibs allow FILE [--minutes 10]   let agents change your lines in FILE for a while
dibs brief --agent A [--peek]    start a turn for an agent without hooks and print its brief
dibs done --agent A              end that turn and attribute its changes
dibs run --agent A -- CMD …      run a whole agent session as one turn
dibs watch [--interval 2]        record your edits continuously, with exact timestamps
dibs doctor [--json]             check that every wired agent will really run the hooks
dibs record [FILES] [--actor A]  attribute current changes now
dibs mcp [--agent A]             MCP server on stdio
dibs guard FILE --new NEWFILE    check a proposed version from scripts
dibs config [KEY [VALUE]]        guard=auto|ask|deny|warn|off, precommit=block|warn|off, protect_hours=72 …
dibs uninstall [--purge]
```

Settings can also live in a committed `.dibs.json`. `DIBS_GUARD=warn` overrides the guard for one session;
`DIBS_ALLOW_REVERTS=1 git commit` skips the pre-commit check once.

## Verified with

Tested on Linux (October 2026) with the **real agent CLIs** and a local mock model
([`scripts/e2e`](scripts/e2e)): the CLI, its config parser, hook runner and tools are real; only the
model's replies are scripted. Scenario: agent writes a file → you edit a line by hand → the agent
rewrites the file from memory → dibs blocks or flags it → `dibs restore` / pre-commit guard.

| Agent | Version | Hook config accepted | Guard before the edit | Shell-revert detection | Brief reaches the model | How it was run |
|---|---|---|---|---|---|---|
| Claude Code | 2.1.295 | ✅ | ✅ `ask` (rejected in `-p`; dialog in the TUI, also in accept-edits mode) | ✅ | ✅ | `claude -p` 10/10 checks; interactive TUI in tmux |
| Codex CLI | 0.162.0 | ✅ | ✅ `deny` on `apply_patch` (reason reaches the model) | ✅ `exec_command` | ✅ | `codex exec` 7/7; TUI "Trust all and continue" flow |
| Gemini CLI | 0.63.0 | ✅ (trusted folder only) | ✅ `write_file` / `replace` | ✅ `run_shell_command` | ✅ | `gemini -p` 8/8 |
| aider | 0.86.2 | – (no hooks) | ✗ after the run only | ✅ after the run | ✅ via `--read` | `dibs run --agent aider` 3/3 |
| Cursor agent | 2026.10.01 | payloads and output validators read from the installed CLI's source | unit-tested only | unit-tested only | unit-tested only | needs a Cursor login to run a model |
| GitHub Copilot | – | not run | – (MCP + instructions, not forced) | – | – | needs VS Code + a GitHub Copilot account |

Not verified, because it needs an account: how real models (Claude, GPT, Gemini, Cursor's models)
react to the dibs messages; Cursor end to end (Cursor account); Copilot (VS Code + Copilot
subscription); Claude Code's subscription login (the API-key path was used).

Things the real CLIs taught us, now handled or reported by `dibs doctor`:

- **Codex** skips untrusted project hooks without a word. Start `codex` in the repo once and pick
  "Trust all and continue" (or `/hooks`). Codex does not support `ask`, so dibs denies.
- **Gemini CLI** ignores `.gemini/settings.json` (hooks included) unless the folder is trusted.
- **Claude Code** shows its own overwrite dialog for `ask`, but not the hook's reason; dibs adds a
  `systemMessage` so you know why. Claude Code also refuses a `Write` to a file it has not read.
- **Cursor** also runs `.claude/settings.json` hooks; dibs recognises Cursor's payloads so the work is
  not credited to Claude, and lets its own Cursor hooks handle the event when both are installed.
- **aider** commits mid-run with `--no-verify`, so the pre-commit guard cannot stop it; `dibs run`
  reports the revert when aider exits and `dibs restore` fixes it.

## How attribution works

dibs keeps a manifest of the working tree (git blob ids, size, mtime). It compares it with the disk:

- when a turn starts, so whatever changed while no agent was working is the human's;
- after each agent tool call, for the files that tool touched (the whole tree after shell commands);
- when the turn stops, for the files the agent touched.

A human edit made in another file *while* an agent is working stays the human's. Uncommitted work
that already exists when dibs starts is recorded as `unknown` and protected like human edits.

The guard protects significant lines (not lone braces or `else`) that a human added or deleted in the
last 72 hours (`protect_hours`). A line counts as reverted when the agent removes it while it is still
there, or brings back a line the human deleted. `dibs allow FILE` lifts the protection for 10 minutes
and the journal marks those edits as approved overrides.

## Limits

- Hooks are the agents' own feature and change between versions. See "Verified with" for the exact
  versions tested; run `dibs doctor` after upgrading an agent.
- If you edit a file while an agent's shell command runs, that change is attributed to the agent.
- Line matching ignores whitespace and only looks at whole lines; a revert that rewrites a line into
  something new is not a "revert" to dibs.
- `dibs blame` covers changes since dibs started; older lines show `·`.
- With `core.autocrlf=true` (the Git for Windows default) a CRLF working copy has a different blob id
  than the LF copy git stores, so `dibs init` copies those files into its blob store too: more disk,
  still correct.
- Large files (> 2 MB) and binaries are tracked by hash only. On a 30,000-file repository `dibs init`
  takes ~1.2 s and each hook 0.1–0.4 s (`scripts/bench.py`).

## How it differs from similar tools

- **git-ai**, **Agent Blame**, **agentdiff** record which lines AI wrote and attach that to commits,
  for review and statistics. dibs works during the session: it protects the human's uncommitted
  edits before an agent overwrites them, and reports what is not pushed.
- **agentrec** and **flashpoint** snapshot each agent turn so you can undo or travel back after the
  damage. dibs tries to stop the damage, and its restore puts back only your lines.
- **sigil** stamps functions and tells Claude Code when they drifted. dibs works on lines in any file
  type, for six agents, and blocks reverts instead of only reporting drift.
- Cursor checkpoints and Claude Code rewind restore whole files to an earlier state and only inside
  one tool.

## Development

```bash
git clone https://github.com/mrzroot/dibs && cd dibs
python -m venv .venv && . .venv/bin/activate
pip install -e . pytest
pytest -q
```

## License

MIT © Mohammadreza Zare ([mrzroot](https://github.com/mrzroot))
