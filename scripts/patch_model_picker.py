#!/usr/bin/env python3
from __future__ import annotations

import shutil
import time
from pathlib import Path


PATCH = '''    try:
        from providers import list_providers as _list_provider_profiles

        for _profile in _list_provider_profiles():
            _name = getattr(_profile, "name", "")
            _fallbacks = list(getattr(_profile, "fallback_models", ()) or ())
            if _name and _fallbacks and not curated.get(_name):
                curated[_name] = _fallbacks
    except Exception:
        pass
'''


def main() -> int:
    target = Path.home() / ".hermes/hermes-agent/hermes_cli/model_switch.py"
    if not target.exists():
        print(f"Could not find Hermes model_switch.py at {target}")
        return 1

    text = target.read_text(encoding="utf-8")
    if "_list_provider_profiles" in text and "fallback_models" in text:
        print("Hermes model picker already reads plugin fallback models.")
        return 0

    marker = '    curated["openrouter"] = [mid for mid, _ in OPENROUTER_MODELS]\n'
    if marker not in text:
        print("Could not find model picker curated-list marker. Patch skipped.")
        return 1

    backup = target.with_suffix(target.suffix + f".before-commandcode-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(target, backup)
    target.write_text(text.replace(marker, marker + PATCH, 1), encoding="utf-8")
    print(f"Patched {target}")
    print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
