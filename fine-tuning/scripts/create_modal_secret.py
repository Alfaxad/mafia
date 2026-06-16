#!/usr/bin/env python3
"""Create the Modal secret used by the Mafia Gemma 4 fine-tune.

This script deliberately prints only key names, never secret values.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "env.txt"
SECRET_NAME = "mafia-finetune-secrets"
REQUIRED_KEYS = ("HF_API_KEY", "WANDB_API_KEY", "OPEN_AI_KEY")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = pattern.match(raw)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        values[key] = value
    return values


def main() -> None:
    env = read_env(ENV_PATH)
    missing = [key for key in REQUIRED_KEYS if not env.get(key)]
    if missing:
        raise SystemExit(f"Missing required keys in {ENV_PATH}: {', '.join(missing)}")

    args = ["modal", "secret", "create", SECRET_NAME, "--force"]
    args.extend(f"{key}={env[key]}" for key in REQUIRED_KEYS)
    subprocess.run(args, check=True)
    print(f"Created Modal secret {SECRET_NAME} with keys: {', '.join(REQUIRED_KEYS)}")


if __name__ == "__main__":
    main()
