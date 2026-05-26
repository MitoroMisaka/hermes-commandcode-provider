#!/usr/bin/env python3
"""Verify Command Code reasoning events survive the OpenAI-compatible bridge."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    spec = importlib.util.spec_from_file_location(
        "commandcode_proxy_test",
        ROOT / "commandcode_proxy.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load commandcode_proxy.py")
    proxy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(proxy)

    def fake_events(payload, api_key):
        yield {"type": "reasoning-delta", "text": "thinking"}
        yield {"type": "reasoning-end"}
        yield {"type": "text-delta", "text": "done"}
        yield {
            "type": "finish",
            "finishReason": "stop",
            "totalUsage": {"inputTokens": 1, "outputTokens": 2},
        }

    proxy._iter_alpha_events = fake_events
    response = proxy._non_stream({"params": {"model": "test-model"}}, "test-key")
    message = response["choices"][0]["message"]
    assert message["reasoning_content"] == "thinking"
    assert message["content"] == "done"
    print("reasoning mapping ok")


if __name__ == "__main__":
    main()
