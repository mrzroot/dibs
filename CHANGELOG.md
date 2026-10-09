# Changelog

## v0.1.1 (2026-10-09)

Tested end to end against the real Claude Code 2.1.295, Codex 0.162.0, Gemini CLI 0.63.0 and aider
0.86.2 (with a scripted local model, see `scripts/e2e`), and against the hook payloads and output
validators of the Cursor agent CLI 2026.10.01. Fixes for everything that turned up:

- New `dibs doctor [--json]`: checks dibs is on PATH, the pre-commit hook really runs, Claude Code
  `disableAllHooks`, Codex hook trust (Codex skips untrusted project hooks silently), Gemini folder
  trust (Gemini ignores project settings in untrusted folders), disabled hooks, and logged hook errors.
- Claude Code: the `ask` dialog does not show the hook's reason, so dibs adds a `systemMessage` for you.
- Cursor: the turn brief now goes out with the prompt (`beforeSubmitPrompt` `additional_context`) and is
  repeated after the first tool call; the postToolUse matcher is `Write|Delete|Shell` (Cursor's real tool
  names). Cursor also runs `.claude/settings.json` hooks: dibs now recognises them so Cursor's work is not
  credited to Claude, and defers to its Cursor hooks when both are installed.
- aider: `dibs run` passes the brief to aider with `--read` (it was printed but never reached the model),
  and prints a warning plus the `dibs restore` command when the run undid your lines.
- pre-commit: the dibs line is inserted right after the shebang; appended after another tool's
  `exec ...` line it never ran.
- Large repositories: `dibs init` on 30,000 files went from 52 s to 1.2 s (one `git cat-file --batch-check`
  instead of a process per file, faster scanning); hooks read only the tail of the journal
  (0.1–0.4 s per hook on that repository). `scripts/bench.py` measures it.
- Lock: a lock is broken when its owner process died, and otherwise only after 120 s, so a slow scan is
  not interrupted by a second process.
- `dibs watch`: keeps running through errors (each reported once), skips a round when a hook holds the
  lock, stops when the repository disappears, no longer pauses forever for an agent that crashed mid-turn
  (`--agent-timeout`, default 3 h), and backs off on big trees.
- Init messages now say how to trust the hooks in Codex and Gemini.

## v0.1.0 (2026-10-09)

First release.

- Attribution journal: every file change is recorded with who made it (`human`, `claude`, `cursor`,
  `codex`, `gemini`, `copilot`, `aider`, or any name), with the changed lines. Stored in `.git/dibs/`
  (or `.dibs/` outside git), never committed.
- Agent hooks for Claude Code, Codex, Cursor and Gemini CLI; an MCP server for Copilot and any MCP client;
  instruction blocks for AGENTS.md, Copilot and Cursor rules; `dibs run` for agents without hooks (Aider).
- Turn briefs: at the start of every turn the agent is told which files the human (or another agent)
  changed since its last turn, with the lines, plus git sync warnings.
- Revert guard: an agent edit that would remove lines the human added or bring back lines the human
  deleted is sent to the user for approval (Claude Code) or denied with an explanation (Codex, Cursor,
  Gemini). Reverts done through shell commands are detected after the fact and reported to the agent.
- Pre-commit hook that stops a commit containing reverted human lines; `dibs restore` puts back only the
  reverted lines (3-way, keeping the agent's other work) or the whole last human version.
- `dibs status`, `sync`, `log`, `blame`, `restore`, `ack`, `allow`, `brief`, `done`, `run`, `watch`,
  `init`, `uninstall`, `config`.
- Uncommitted work that exists when dibs starts is recorded as `unknown` and protected like human edits.
