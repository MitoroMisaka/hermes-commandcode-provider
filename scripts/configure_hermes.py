#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


MODELS = {
    "claude-sonnet-4-6": 1000000,
    "claude-opus-4-7": 1000000,
    "claude-haiku-4-5-20251001": 200000,
    "gpt-5.5": 200000,
    "gpt-5.4": 400000,
    "gpt-5.3-codex": 400000,
    "gpt-5.4-mini": 400000,
    "moonshotai/Kimi-K2.6": 256000,
    "moonshotai/Kimi-K2.5": 256000,
    "zai-org/GLM-5.1": 200000,
    "zai-org/GLM-5": 200000,
    "MiniMaxAI/MiniMax-M2.7": 200000,
    "MiniMaxAI/MiniMax-M2.5": 200000,
    "deepseek/deepseek-v4-pro": 1000000,
    "deepseek/deepseek-v4-flash": 1000000,
    "Qwen/Qwen3.6-Max-Preview": 200000,
    "Qwen/Qwen3.6-Plus": 200000,
    "Qwen/Qwen3.7-Max": 1000000,
    "stepfun/Step-3.5-Flash": 1000000,
    "google/gemini-3.5-flash": 1000000,
    "google/gemini-3.1-flash-lite": 1000000,
}


def import_yaml():
    try:
        import yaml  # type: ignore

        return yaml
    except Exception:
        return None


def main() -> int:
    yaml = import_yaml()
    if yaml is None:
        print("PyYAML is required to update config.yaml. Install Hermes first or edit config manually.", file=sys.stderr)
        return 1

    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
    config_path = hermes_home / "config.yaml"
    config: dict = {}
    if config_path.exists():
        backup = config_path.with_suffix(
            config_path.suffix + f".before-commandcode-{time.strftime('%Y%m%d-%H%M%S')}"
        )
        shutil.copy2(config_path, backup)
        with config_path.open(encoding="utf-8") as fh:
            config = yaml.safe_load(fh) or {}

    if not isinstance(config, dict):
        config = {}

    model_cfg = config.setdefault("model", {})
    model_cfg["provider"] = "commandcode"
    model_cfg["default"] = "moonshotai/Kimi-K2.5"
    model_cfg["base_url"] = "http://127.0.0.1:8788/v1"

    providers = config.setdefault("providers", {})
    providers["commandcode"] = {
        "name": "Command Code",
        "base_url": "http://127.0.0.1:8788/v1",
        "key_env": "COMMANDCODE_API_KEY",
        "transport": "chat_completions",
        "model": "moonshotai/Kimi-K2.5",
        "default_model": "moonshotai/Kimi-K2.5",
        "models": {model: {"context_length": context} for model, context in MODELS.items()},
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False, allow_unicode=True)

    print(f"Updated {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
