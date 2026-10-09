# Changelog

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
