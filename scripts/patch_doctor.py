#!/usr/bin/env python3
from __future__ import annotations

import shutil
import time
from pathlib import Path


def main() -> int:
    hermes_bin = shutil.which("hermes") or str(Path.home() / ".local/bin/hermes")
    doctor = Path.home() / ".hermes/hermes-agent/hermes_cli/doctor.py"
    if not doctor.exists():
        print(f"Could not find Hermes doctor.py at {doctor}")
        print(f"Your hermes command was: {hermes_bin}")
        return 1

    text = doctor.read_text(encoding="utf-8")
    if '"commandcode",' in text:
        print("Hermes doctor already allows commandcode.")
        return 0

    marker = '                "kilocode",\n'
    if marker not in text:
        print("Could not find doctor allowlist marker. Patch skipped.")
        return 1

    backup = doctor.with_suffix(doctor.suffix + f".before-commandcode-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(doctor, backup)
    doctor.write_text(text.replace(marker, marker + '                "commandcode",\n', 1), encoding="utf-8")
    print(f"Patched {doctor}")
    print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
