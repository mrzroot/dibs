# End-to-end tests with the real agent CLIs

These scripts drive the **real** Claude Code, Codex, Gemini CLI and aider binaries against
`mock.py`, a tiny local server that speaks the Anthropic Messages, OpenAI Responses / Chat
Completions and Gemini streamGenerateContent APIs and replays a scripted list of tool calls.
No account or API key is needed: the "model" is the script, while the CLIs, their hook
runners, their config parsing and their tools are the real thing.

Each scenario: the agent writes `api.py` -> the human edits a line by hand -> the agent
rewrites the file from memory (which would undo the human line) -> dibs blocks or flags it ->
`dibs restore` / pre-commit guard.

```sh
npm i -g @anthropic-ai/claude-code @openai/codex @google/gemini-cli
uv tool install aider-chat --python 3.12
MOCK_DIR=/tmp/mock python3 mock.py &            # aider needs MOCK_MAIN_ALWAYS=1
python3 cc.py; python3 codex.py; python3 gemini.py; python3 aider.py
```

What the mock cannot tell you: how a real model reacts to the dibs messages. That needs real
accounts (see "Verified with" in the main README).
