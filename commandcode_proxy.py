#!/usr/bin/env python3
"""OpenAI-compatible local bridge for Command Code's alpha/generate endpoint."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


API_BASE = os.environ.get("COMMANDCODE_API_BASE", "https://api.commandcode.ai").rstrip("/")
DEFAULT_MODELS = [
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "context_length": 1000000},
    {"id": "claude-opus-4-7", "name": "Claude Opus 4.7", "context_length": 1000000},
    {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "context_length": 200000},
    {"id": "gpt-5.5", "name": "GPT-5.5", "context_length": 200000},
    {"id": "gpt-5.4", "name": "GPT-5.4", "context_length": 400000},
    {"id": "gpt-5.3-codex", "name": "GPT-5.3 Codex", "context_length": 400000},
    {"id": "gpt-5.4-mini", "name": "GPT-5.4 Mini", "context_length": 400000},
    {"id": "moonshotai/Kimi-K2.6", "name": "Kimi K2.6", "context_length": 256000},
    {"id": "moonshotai/Kimi-K2.5", "name": "Kimi K2.5", "context_length": 256000},
    {"id": "zai-org/GLM-5.1", "name": "GLM-5.1", "context_length": 200000},
    {"id": "zai-org/GLM-5", "name": "GLM-5", "context_length": 200000},
    {"id": "MiniMaxAI/MiniMax-M2.7", "name": "MiniMax M2.7", "context_length": 200000},
    {"id": "MiniMaxAI/MiniMax-M2.5", "name": "MiniMax M2.5", "context_length": 200000},
    {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "context_length": 1000000},
    {"id": "deepseek/deepseek-v4-flash", "name": "DeepSeek V4 Flash", "context_length": 1000000},
    {"id": "Qwen/Qwen3.6-Max-Preview", "name": "Qwen 3.6 Max Preview", "context_length": 200000},
    {"id": "Qwen/Qwen3.6-Plus", "name": "Qwen 3.6 Plus", "context_length": 200000},
    {"id": "Qwen/Qwen3.7-Max", "name": "Qwen 3.7 Max", "context_length": 1000000},
    {"id": "stepfun/Step-3.5-Flash", "name": "Step 3.5 Flash", "context_length": 1000000},
    {"id": "google/gemini-3.5-flash", "name": "Gemini 3.5 Flash", "context_length": 1000000},
    {"id": "google/gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "context_length": 1000000},
]
DEFAULT_MAX_COMPLETION_TOKENS = 32000


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "authorization, content-type")
    handler.end_headers()
    handler.wfile.write(body)


def _error(handler: BaseHTTPRequestHandler, status: int, message: str) -> None:
    _json_response(
        handler,
        status,
        {
            "error": {
                "message": message,
                "type": "commandcode_bridge_error",
                "code": status,
            }
        },
    )


def _auth_from_files() -> str:
    paths = [
        Path.home() / ".commandcode" / "auth.json",
        Path.home() / ".pi" / "agent" / "auth.json",
    ]
    for path in paths:
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        direct = data.get("apiKey") or data.get("commandcode")
        if isinstance(direct, str) and direct:
            return direct
        commandcode = data.get("commandcode")
        if isinstance(commandcode, dict):
            access = commandcode.get("access")
            if isinstance(access, str) and access:
                return access
    return ""


def _api_key(headers: Any) -> str:
    auth = headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token and token not in {"x", "none", "null", "dummy"}:
            return token
    return os.environ.get("COMMANDCODE_API_KEY", "") or _auth_from_files()


def _model_entry(model: dict[str, Any]) -> dict[str, Any]:
    model_id = str(model.get("id") or "").strip()
    context_length = model.get("context_length")
    try:
        context_length = int(context_length)
    except Exception:
        context_length = None

    entry: dict[str, Any] = {
        "id": model_id,
        "object": "model",
        "created": int(model.get("created") or time.time()),
        "owned_by": model.get("owned_by") or "command-code",
        "name": model.get("name") or model_id,
        "max_completion_tokens": DEFAULT_MAX_COMPLETION_TOKENS,
        "top_provider": {"max_completion_tokens": DEFAULT_MAX_COMPLETION_TOKENS},
    }
    if context_length and context_length > 0:
        entry["context_length"] = context_length
        entry["max_context_length"] = context_length
    return entry


def _fallback_model_entries() -> list[dict[str, Any]]:
    return [_model_entry(model) for model in DEFAULT_MODELS]


def _fetch_commandcode_models(api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        return _fallback_model_entries()

    config_path = ""
    try:
        config = "\n".join(
            [
                f'url = "{API_BASE}/provider/v1/models"',
                'header = "Accept: application/json"',
                f'header = "Authorization: Bearer {api_key}"',
                'user-agent = "node"',
                "silent",
                "show-error",
                "fail-with-body",
                "",
            ]
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as config_file:
            config_path = config_file.name
            os.chmod(config_path, 0o600)
            config_file.write(config)

        proc = subprocess.run(
            ["curl", "--config", config_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if proc.returncode != 0:
            return _fallback_model_entries()
        payload = json.loads(proc.stdout)
        items = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return _fallback_model_entries()
        entries = [_model_entry(item) for item in items if isinstance(item, dict) and item.get("id")]
        return entries or _fallback_model_entries()
    except Exception:
        return _fallback_model_entries()
    finally:
        if config_path:
            try:
                os.unlink(config_path)
            except OSError:
                pass


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif item.get("type") == "input_text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return "" if content is None else str(content)


def _parse_arguments(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _openai_messages_to_commandcode(messages: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []

    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")

        if role in {"system", "developer"}:
            text = _text_from_content(content)
            if text:
                system_parts.append(text)
            continue

        if role == "user":
            converted.append({"role": "user", "content": _text_from_content(content)})
            continue

        if role == "assistant":
            parts: list[dict[str, Any]] = []
            text = _text_from_content(content)
            if text:
                parts.append({"type": "text", "text": text})
            reasoning = message.get("reasoning_content") or message.get("reasoning")
            if isinstance(reasoning, str) and reasoning:
                parts.append({"type": "reasoning", "text": reasoning})
            for call in message.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") if isinstance(call.get("function"), dict) else {}
                parts.append(
                    {
                        "type": "tool-call",
                        "toolCallId": call.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                        "toolName": fn.get("name") or call.get("name") or "",
                        "input": _parse_arguments(fn.get("arguments") or call.get("arguments")),
                    }
                )
            if parts:
                converted.append({"role": "assistant", "content": parts})
            continue

        if role == "tool":
            tool_call_id = message.get("tool_call_id") or message.get("toolCallId") or ""
            tool_name = message.get("name") or message.get("tool_name") or ""
            converted.append(
                {
                    "role": "tool",
                    "content": [
                        {
                            "type": "tool-result",
                            "toolCallId": tool_call_id,
                            "toolName": tool_name,
                            "output": {"type": "text", "value": _text_from_content(content)},
                        }
                    ],
                }
            )

    return "\n\n".join(system_parts), converted


def _openai_tools_to_commandcode(tools: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(tools, list):
        return out
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
        name = fn.get("name")
        if not isinstance(name, str) or not name:
            continue
        out.append(
            {
                "type": "function",
                "name": name,
                "description": fn.get("description") if isinstance(fn.get("description"), str) else "",
                "input_schema": fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {},
            }
        )
    return out


def _build_alpha_payload(request: dict[str, Any]) -> dict[str, Any]:
    system, messages = _openai_messages_to_commandcode(request.get("messages") or [])
    max_tokens = request.get("max_tokens") or request.get("max_completion_tokens") or 32000
    try:
        max_tokens = max(1, min(int(max_tokens), 200000))
    except Exception:
        max_tokens = 32000

    return {
        "config": {
            "workingDir": os.getcwd(),
            "date": time.strftime("%Y-%m-%d"),
            "environment": f"{sys.platform}-{platform.machine()}, Python {platform.python_version()}",
            "structure": [],
            "isGitRepo": False,
            "currentBranch": "",
            "mainBranch": "",
            "gitStatus": "",
            "recentCommits": [],
        },
        "memory": "",
        "taste": "",
        "skills": None,
        "permissionMode": "standard",
        "params": {
            "model": request.get("model") or DEFAULT_MODELS[0]["id"],
            "messages": messages,
            "tools": _openai_tools_to_commandcode(request.get("tools")),
            "system": system,
            "max_tokens": max_tokens,
            "stream": True,
        },
    }


def _iter_alpha_events(payload: dict[str, Any], api_key: str):
    body_path = ""
    config_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as body_file:
            body_path = body_file.name
            os.chmod(body_path, 0o600)
            json.dump(payload, body_file, ensure_ascii=False)

        config = "\n".join(
            [
                f'url = "{API_BASE}/alpha/generate"',
                'request = "POST"',
                'header = "Content-Type: application/json"',
                'header = "Accept: text/event-stream, application/x-ndjson, application/json"',
                f'header = "Authorization: Bearer {api_key}"',
                'header = "x-command-code-version: 0.24.1"',
                'header = "x-cli-environment: production"',
                'header = "x-project-slug: hermes-cc"',
                'header = "x-taste-learning: false"',
                'header = "x-co-flag: false"',
                f'header = "x-session-id: {uuid.uuid4()}"',
                'user-agent = "node"',
                "silent",
                "show-error",
                "no-buffer",
                "fail-with-body",
                f'data-binary = "@{body_path}"',
                "",
            ]
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as config_file:
            config_path = config_file.name
            os.chmod(config_path, 0o600)
            config_file.write(config)

        proc = subprocess.Popen(
            ["curl", "--config", config_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        raw_error_lines: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line or line.startswith(":") or line.startswith("event:"):
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                raw_error_lines.append(line)
                raw_error_lines = raw_error_lines[-5:]
                continue
            if isinstance(event, dict):
                yield event

        stderr = ""
        if proc.stderr is not None:
            stderr = proc.stderr.read().strip()
        return_code = proc.wait()
        if return_code:
            detail = "\n".join(raw_error_lines)
            if stderr:
                detail = f"{stderr}\n{detail}".strip()
            raise RuntimeError(f"Command Code API error from curl ({return_code}): {detail[:1000]}")
    finally:
        for path in (body_path, config_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def _map_finish_reason(reason: Any, has_tool_calls: bool = False) -> str:
    if reason in {"tool-calls", "toolUse", "tool_calls"} or has_tool_calls:
        return "tool_calls"
    if reason in {"length", "max_tokens", "max-tokens", "max_output_tokens"}:
        return "length"
    return "stop"


def _openai_usage(finish_event: dict[str, Any] | None) -> dict[str, Any]:
    usage = finish_event.get("totalUsage") if isinstance(finish_event, dict) else None
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    input_tokens = int(usage.get("inputTokens") or 0)
    completion = int(usage.get("outputTokens") or 0)
    cache = usage.get("inputTokenDetails")
    cache_read = 0
    cache_write = 0
    if isinstance(cache, dict):
        cache_read = int(cache.get("cacheReadTokens") or 0)
        cache_write = int(cache.get("cacheWriteTokens") or 0)
    prompt = input_tokens + cache_read + cache_write
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "prompt_tokens_details": {
            "cached_tokens": cache_read,
            "cache_write_tokens": cache_write,
        },
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": cache_write,
    }


def _sse(handler: BaseHTTPRequestHandler, payload: dict[str, Any], api_key: str) -> None:
    model = payload["params"]["model"]
    created = int(time.time())
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    events = _iter_alpha_events(payload, api_key)
    try:
        first_event = next(events)
    except StopIteration:
        first_event = None

    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "close")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()

    def send(data: dict[str, Any]) -> None:
        handler.wfile.write(f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8"))
        handler.wfile.flush()

    send(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
    )

    finish_reason = "stop"
    finish_event: dict[str, Any] | None = None
    tool_index = 0
    has_tool_calls = False

    def handle_event(event: dict[str, Any]) -> None:
        nonlocal finish_reason, finish_event, has_tool_calls, tool_index
        event_type = event.get("type")
        if event_type == "text-delta":
            text = event.get("text")
            if isinstance(text, str) and text:
                send(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {"index": 0, "delta": {"content": text}, "finish_reason": None}
                        ],
                    }
                )
        elif event_type == "reasoning-delta":
            text = event.get("text")
            if isinstance(text, str) and text:
                send(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"reasoning_content": text},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
        elif event_type == "reasoning-end":
            return
        elif event_type == "tool-call":
            has_tool_calls = True
            arguments = event.get("input") or event.get("args") or event.get("arguments") or {}
            send(
                {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": tool_index,
                                        "id": event.get("toolCallId") or f"call_{uuid.uuid4().hex[:12]}",
                                        "type": "function",
                                        "function": {
                                            "name": event.get("toolName") or "",
                                            "arguments": json.dumps(arguments, ensure_ascii=False),
                                        },
                                    }
                                ]
                            },
                            "finish_reason": None,
                        }
                    ],
                }
            )
            tool_index += 1
        elif event_type == "finish":
            finish_event = event
            finish_reason = _map_finish_reason(event.get("finishReason"), has_tool_calls)
        elif event_type == "error":
            message = event.get("error")
            if isinstance(message, dict):
                message = message.get("message")
            raise RuntimeError(str(message or "Command Code stream error"))

    if isinstance(first_event, dict):
        handle_event(first_event)
    for event in events:
        handle_event(event)

    send(
        {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
            "usage": _openai_usage(finish_event),
        }
    )
    handler.wfile.write(b"data: [DONE]\n\n")
    handler.wfile.flush()


def _non_stream(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    content: list[str] = []
    reasoning_content: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    finish_event: dict[str, Any] | None = None

    for event in _iter_alpha_events(payload, api_key):
        event_type = event.get("type")
        if event_type == "text-delta" and isinstance(event.get("text"), str):
            content.append(event["text"])
        elif event_type == "reasoning-delta" and isinstance(event.get("text"), str):
            reasoning_content.append(event["text"])
        elif event_type == "reasoning-end":
            continue
        elif event_type == "tool-call":
            arguments = event.get("input") or event.get("args") or event.get("arguments") or {}
            tool_calls.append(
                {
                    "id": event.get("toolCallId") or f"call_{uuid.uuid4().hex[:12]}",
                    "type": "function",
                    "function": {
                        "name": event.get("toolName") or "",
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        elif event_type == "finish":
            finish_event = event
        elif event_type == "error":
            message = event.get("error")
            if isinstance(message, dict):
                message = message.get("message")
            raise RuntimeError(str(message or "Command Code stream error"))

    message: dict[str, Any] = {"role": "assistant", "content": "".join(content)}
    if reasoning_content:
        message["reasoning_content"] = "".join(reasoning_content)
    if tool_calls:
        message["tool_calls"] = tool_calls
    finish_reason = _map_finish_reason(
        finish_event.get("finishReason") if isinstance(finish_event, dict) else None,
        bool(tool_calls),
    )
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload["params"]["model"],
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
        "usage": _openai_usage(finish_event),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "CommandCodeBridge/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("COMMANDCODE_PROXY_VERBOSE"):
            super().log_message(fmt, *args)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "authorization, content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if path in {"", "/health"}:
            _json_response(self, 200, {"ok": True})
            return
        if path in {"/models", "/v1/models"}:
            _json_response(
                self,
                200,
                {"object": "list", "data": _fetch_commandcode_models(_api_key(self.headers))},
            )
            return
        _error(self, 404, f"Unknown path: {path}")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if path not in {"/chat/completions", "/v1/chat/completions"}:
            _error(self, 404, f"Unknown path: {path}")
            return

        api_key = _api_key(self.headers)
        if not api_key:
            _error(self, 401, "Missing COMMANDCODE_API_KEY or ~/.commandcode/auth.json")
            return

        try:
            request = _read_json(self)
            payload = _build_alpha_payload(request)
            if request.get("stream") is True:
                _sse(self, payload, api_key)
            else:
                _json_response(self, 200, _non_stream(payload, api_key))
        except Exception as exc:
            _error(self, 502, str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="Command Code OpenAI-compatible bridge")
    parser.add_argument("--host", default=os.environ.get("COMMANDCODE_PROXY_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("COMMANDCODE_PROXY_PORT", "8788")))
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Command Code bridge listening on http://{args.host}:{args.port}/v1", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
