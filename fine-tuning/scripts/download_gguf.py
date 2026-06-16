from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


REPO = "build-small-hackathon/mafia-gemma-4-12B-it-gguf"
FILENAME = "gemma-4-12b-it.Q8_0.gguf"
EXPECTED_SIZE = 12_669_630_432
URL = f"https://huggingface.co/{REPO}/resolve/main/{FILENAME}?download=true"


def load_hf_token(env_path: Path) -> str:
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("HF_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"HF_API_KEY not found in {env_path}")


def remote_size(token: str) -> int:
    response = requests.head(URL, headers={"Authorization": f"Bearer {token}"}, allow_redirects=True, timeout=60)
    response.raise_for_status()
    length = response.headers.get("content-length")
    if length and length.isdigit():
        return int(length)
    range_response = requests.get(
        URL,
        headers={"Authorization": f"Bearer {token}", "Range": "bytes=0-0"},
        allow_redirects=True,
        timeout=60,
    )
    range_response.raise_for_status()
    content_range = range_response.headers.get("content-range", "")
    match = re.search(r"/(\d+)$", content_range)
    return int(match.group(1)) if match else EXPECTED_SIZE


def download(token: str, output: Path, expected: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = output.stat().st_size if output.exists() else 0
    if existing == expected:
        print(f"complete {output} {existing} bytes")
        return
    if existing > expected:
        raise RuntimeError(f"Local file is larger than expected: {existing} > {expected}")

    headers = {"Authorization": f"Bearer {token}"}
    mode = "wb"
    if existing:
        headers["Range"] = f"bytes={existing}-"
        mode = "ab"
        print(f"resuming at {existing}/{expected} bytes ({existing / expected:.2%})")
    else:
        print(f"starting download {expected} bytes")

    with requests.get(URL, headers=headers, stream=True, allow_redirects=True, timeout=(60, 120)) as response:
        if existing and response.status_code != 206:
            raise RuntimeError(f"Server did not honor Range resume: HTTP {response.status_code}")
        response.raise_for_status()
        downloaded = existing
        last_print = time.monotonic()
        with output.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=32 * 1024 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_print >= 30:
                    print(f"downloaded {downloaded}/{expected} bytes ({downloaded / expected:.2%})", flush=True)
                    last_print = now

    final_size = output.stat().st_size
    if final_size != expected:
        raise RuntimeError(f"Download incomplete: {final_size} != {expected}")
    print(f"complete {output} {final_size} bytes")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="env.txt")
    parser.add_argument("--output", default=f"fine-tuning/gguf/{FILENAME}")
    args = parser.parse_args()

    token = load_hf_token(Path(args.env))
    output = Path(args.output)
    expected = remote_size(token)
    download(token, output, expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
