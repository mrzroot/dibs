"""Scripted mock LLM server for Anthropic Messages, OpenAI Responses/Chat, and Gemini APIs.

Main-agent requests (ones that offer file-edit tools) consume steps from SCRIPT (a JSON file);
everything else gets a short text answer. Every request is logged to LOG.
"""
import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("MOCK_PORT", "18800"))
DIR = os.environ.get("MOCK_DIR", "/tmp/mock")
os.makedirs(DIR, exist_ok=True)
LOG = os.path.join(DIR, "log.jsonl")
lock = threading.Lock()

def next_step():
    """Pop the next scripted step (script.json is rewritten without it); {"text": "done"} once the script runs out."""
    with lock:
        path = os.path.join(DIR, "script.json")
        try:
            steps = json.load(open(path))
        except Exception:
            steps = []
        if not steps:
            return {"text": "done"}
        st = steps.pop(0)
        json.dump(steps, open(path, "w"))
        return st

def log(entry):
    with lock:
        with open(LOG, "a") as fh:
            fh.write(json.dumps(entry) + "\n")

EDIT_NAMES = {"Edit", "Write", "apply_patch", "write_file", "replace", "shell", "exec_command", "Bash", "run_shell_command"}

class MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"  # keep-alive, which the agent SDKs expect

    def log_message(self, *args):
        """Silence the default per-request stderr line; requests go to LOG instead."""

    def _body(self):
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw or b"{}")
        except Exception:
            return {"_raw": raw.decode("utf-8", "replace")}

    def _send(self, code, obj, ctype="application/json"):
        data = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _sse_start(self):
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        self.close_connection = True

    def _sse(self, event, data):
        s = (f"event: {event}\n" if event else "") + "data: " + json.dumps(data) + "\n\n"
        self.wfile.write(s.encode())
        self.wfile.flush()

    def do_GET(self):
        log({"t": time.time(), "method": "GET", "path": self.path})
        if "/models" in self.path:
            return self._send(200, {"object": "list", "data": [{"id": "mock", "object": "model"}], "models": []})
        self._send(200, {})

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("content-length", "0")
        self.end_headers()

    def do_POST(self):
        """Log the request, pick the next scripted step if it is a main-agent request, answer in the caller's dialect."""
        b = self._body()
        tools = b.get("tools") or []
        names = set()
        for t in tools:
            if isinstance(t, dict):
                names.add(t.get("name") or (t.get("function") or {}).get("name") or "")
                for fd in t.get("functionDeclarations") or t.get("function_declarations") or []:
                    names.add(fd.get("name", ""))
        # Only requests that offer an edit/shell tool are the agent's main turn; title or summary side-calls get "ok".
        main = bool(names & EDIT_NAMES)
        if os.environ.get("MOCK_MAIN_ALWAYS") == "1" and "/chat/completions" in self.path:
            main = True
        step = next_step() if main else {"text": "ok"}
        log({"t": time.time(), "path": self.path, "main": main, "tools": sorted(n for n in names if n)[:80], "step": step, "body": b})
        p = self.path
        if p.startswith("/v1/messages") and "count_tokens" in p:
            return self._send(200, {"input_tokens": 10})
        if p.startswith("/v1/messages"):
            return self.anthropic(b, step)
        if p.endswith("/responses"):
            return self.oai_responses(b, step)
        if p.endswith("/chat/completions"):
            return self.chat(b, step)
        if ":generateContent" in p or ":streamGenerateContent" in p:
            return self.gemini(b, step, stream="stream" in p)
        if ":countTokens" in p:
            return self._send(200, {"totalTokens": 10})
        self._send(404, {"error": "unknown " + p})

    # ---------------- Anthropic
    def anthropic(self, b, step):
        """Anthropic Messages. A stream is message_start, one content block (start/delta/stop), message_delta, message_stop.

        A tool call streams its input as a single input_json_delta; the block is opened with an empty input.
        """
        mid = "msg_" + uuid.uuid4().hex[:20]
        if "tool" in step:
            block = {"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:20], "name": step["tool"], "input": step["input"]}
            stop = "tool_use"
        else:
            block = {"type": "text", "text": step["text"]}
            stop = "end_turn"
        usage = {"input_tokens": 10, "output_tokens": 5}
        msg = {"id": mid, "type": "message", "role": "assistant", "model": b.get("model", "mock"), "content": [block],
               "stop_reason": stop, "stop_sequence": None, "usage": usage}
        if not b.get("stream"):
            return self._send(200, msg)
        self._sse_start()
        self._sse("message_start", {"type": "message_start", "message": dict(msg, content=[], stop_reason=None)})
        if block["type"] == "text":
            self._sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}})
            self._sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": block["text"]}})
        else:
            self._sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": dict(block, input={})})
            self._sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}})
        self._sse("content_block_stop", {"type": "content_block_stop", "index": 0})
        self._sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None}, "usage": {"output_tokens": 5}})
        self._sse("message_stop", {"type": "message_stop"})

    # ---------------- OpenAI Responses (Codex)
    def oai_responses(self, b, step):
        """OpenAI Responses (Codex). apply_patch is a *custom* tool call: free-form `input`, not JSON `arguments`."""
        rid = "resp_" + uuid.uuid4().hex[:16]
        if "tool" in step:
            if step.get("custom"):
                item = {"type": "custom_tool_call", "id": "ctc_" + uuid.uuid4().hex[:12], "status": "completed",
                        "call_id": "call_" + uuid.uuid4().hex[:12], "name": step["tool"], "input": step["input"]}
            else:
                item = {"type": "function_call", "id": "fc_" + uuid.uuid4().hex[:12], "status": "completed",
                        "call_id": "call_" + uuid.uuid4().hex[:12], "name": step["tool"], "arguments": json.dumps(step["input"])}
        else:
            item = {"type": "message", "id": "msg_" + uuid.uuid4().hex[:12], "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": step["text"], "annotations": []}]}
        resp = {"id": rid, "object": "response", "status": "completed", "model": b.get("model", "mock"), "output": [item],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                          "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}
        if not b.get("stream"):
            return self._send(200, resp)
        self._sse_start()
        self._sse("response.created", {"type": "response.created", "response": dict(resp, status="in_progress", output=[])})
        self._sse("response.output_item.added", {"type": "response.output_item.added", "output_index": 0, "item": item})
        self._sse("response.output_item.done", {"type": "response.output_item.done", "output_index": 0, "item": item})
        self._sse("response.completed", {"type": "response.completed", "response": resp})

    # ---------------- OpenAI Chat (Aider)
    def chat(self, b, step):
        """OpenAI Chat Completions (aider): text only, so the 'edit' is whatever file block the script's text contains."""
        text = step.get("text", "")
        cid = "chatcmpl-" + uuid.uuid4().hex[:12]
        if not b.get("stream"):
            return self._send(200, {"id": cid, "object": "chat.completion", "created": int(time.time()), "model": "mock",
                                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        self._sse_start()
        self._sse(None, {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "mock",
                         "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]})
        self._sse(None, {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "mock",
                         "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
        self.wfile.write(b"data: [DONE]\n\n")  # OpenAI streams end with this sentinel, not an event
        self.wfile.flush()

    # ---------------- Gemini
    def gemini(self, b, step, stream):
        """Gemini generateContent. Streaming sends the whole answer as one SSE data chunk without an event name."""
        if "tool" in step:
            part = {"functionCall": {"name": step["tool"], "args": step["input"]}}
        else:
            part = {"text": step["text"]}
        resp = {"candidates": [{"content": {"role": "model", "parts": [part]}, "finishReason": "STOP", "index": 0}],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15}, "modelVersion": "mock"}
        if not stream:
            return self._send(200, resp)
        self._sse_start()
        self._sse(None, resp)

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), MockHandler).serve_forever()
