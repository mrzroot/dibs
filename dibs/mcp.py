"""A minimal MCP server (stdio, JSON-RPC 2.0) exposing dibs to any MCP-capable agent."""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, IO, Optional

from . import __version__
from .core import Dibs, ago
from .repo import Repo
from .sync import sync_line, sync_status

INSTRUCTIONS = (
    "dibs tracks which changes in this repository were made by the human and which by AI agents. "
    "Call dibs_brief at the start of every task to see the human's manual edits since your last turn, and keep them. "
    "Before rewriting a file the human touched, call dibs_check_edit. Call dibs_done when you finish a task."
)

TOOLS = [
    {"name": "dibs_brief",
     "description": "Start of a turn: list files the human (or other agents) changed since your last turn, with the changed lines, plus git sync warnings. Treat human edits as intentional.",
     "inputSchema": {"type": "object", "properties": {"agent": {"type": "string", "description": "Your name, e.g. copilot, codex, claude"}}}},
    {"name": "dibs_check_edit",
     "description": "Before writing a file: would this edit undo lines the human changed by hand? Give the full new content, or old_string/new_string.",
     "inputSchema": {"type": "object", "required": ["path"], "properties": {
         "path": {"type": "string"}, "new_content": {"type": "string"},
         "old_string": {"type": "string"}, "new_string": {"type": "string"}}}},
    {"name": "dibs_done",
     "description": "End of a turn: attribute the files you changed to you.",
     "inputSchema": {"type": "object", "properties": {"agent": {"type": "string"}}}},
    {"name": "dibs_sync_status",
     "description": "What is not committed, not pushed, or not on any remote in this repository.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "dibs_log",
     "description": "Recent attributed changes (who changed which file).",
     "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}, "path": {"type": "string"}}}},
]


class Server:
    def __init__(self, agent: str, root: Optional[str] = None):
        self.agent = agent
        self.root = root

    def dibs(self) -> Dibs:
        return Dibs(Repo.discover(self.root))

    def call(self, name: str, args: Dict[str, Any]) -> str:
        agent = args.get("agent") or self.agent
        d = self.dibs()
        if name == "dibs_brief":
            return d.turn_start(agent) or "[dibs] No changes by anyone else since your last turn."
        if name == "dibs_done":
            evs = d.turn_end(agent, full=True)
            return f"[dibs] Turn closed; {len(evs)} file change(s) attributed to {agent}."
        if name == "dibs_sync_status":
            s = sync_status(d.repo)
            return sync_line(s) + ("\n" + json.dumps({k: v for k, v in s.items() if k != "dirty_files"}) if s.get("git") else "")
        if name == "dibs_check_edit":
            rel = d.repo.rel(args["path"], d.repo.root)
            if not rel:
                return "Path is outside the repository."
            if "new_content" in args:
                v = d.check_edit(agent, rel, new_text=args["new_content"])
            else:
                from .store import read_file
                cur = (read_file(d.repo, rel) or b"").decode("utf-8", "replace")
                old, new = args.get("old_string", ""), args.get("new_string", "")
                if not old or old not in cur:
                    return "old_string not found in the current file; re-read the file (the human may have changed it)."
                v = d.check_edit(agent, rel, new_text=cur.replace(old, new, 1))
            return v.message(agent) if v.reverts else "OK: this edit keeps every human change."
        if name == "dibs_log":
            evs = [e for e in d.events() if e.get("kind") == "change"]
            if args.get("path"):
                evs = [e for e in evs if e["path"] == args["path"]]
            evs = evs[-int(args.get("limit") or 20):]
            return "\n".join(f"#{e['seq']} {ago(e['ts'])} {e['actor']} {e['op']} {e['path']} +{e.get('np', 0)} -{e.get('nm', 0)}"
                             for e in evs) or "No changes recorded yet."
        raise KeyError(name)

    def handle(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = msg.get("method")
        mid = msg.get("id")
        if mid is None:
            return None  # notification
        if method == "initialize":
            pv = (msg.get("params") or {}).get("protocolVersion") or "2025-06-18"
            return self._ok(mid, {"protocolVersion": pv, "capabilities": {"tools": {"listChanged": False}},
                                  "serverInfo": {"name": "dibs", "version": __version__},
                                  "instructions": INSTRUCTIONS})
        if method == "ping":
            return self._ok(mid, {})
        if method == "tools/list":
            return self._ok(mid, {"tools": TOOLS})
        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name", "")
            try:
                text = self.call(name, params.get("arguments") or {})
                return self._ok(mid, {"content": [{"type": "text", "text": text}], "isError": False})
            except KeyError:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"unknown tool {name}"}}
            except Exception as e:  # report tool errors to the model
                return self._ok(mid, {"content": [{"type": "text", "text": f"dibs error: {e}"}], "isError": True})
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}

    @staticmethod
    def _ok(mid: Any, result: Dict[str, Any]) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def serve(self, inp: IO[str] = sys.stdin, out: IO[str] = sys.stdout) -> None:
        for line in inp:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                out.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
                out.flush()
                continue
            msgs = msg if isinstance(msg, list) else [msg]
            for m in msgs:
                resp = self.handle(m) if isinstance(m, dict) else None
                if resp is not None:
                    out.write(json.dumps(resp) + "\n")
                    out.flush()
