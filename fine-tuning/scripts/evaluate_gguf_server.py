#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import time
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "fine-tuning" / "configs" / "sft_v0.json"
TRAINING_EXAMPLES_PATH = ROOT / "mafia-dataset" / "data" / "examples" / "training_examples.full.jsonl"
REPORT_DIR = ROOT / "fine-tuning" / "reports" / "modal" / "mafia-gemma4-12b-sft-v0" / "reports_latest" / "reports"
MERGED_DETAIL_PATH = REPORT_DIR / "merged_generation_eval.jsonl"
GGUF_PATH = ROOT / "fine-tuning" / "gguf" / "gemma-4-12b-it.Q8_0.gguf"
GGUF_SHA_PATH = ROOT / "fine-tuning" / "gguf" / "gemma-4-12b-it.Q8_0.gguf.sha256"
MODAL_HELPER_PATH = ROOT / "fine-tuning" / "modal" / "mafia_gemma4_modal.py"


def load_modal_helper() -> Any:
    spec = importlib.util.spec_from_file_location("mafia_gemma4_modal", MODAL_HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {MODAL_HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_eval_ids(limit: int | None) -> list[str]:
    ids: list[str] = []
    with MERGED_DETAIL_PATH.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            ids.append(row["example_id"])
            if limit is not None and len(ids) >= limit:
                break
    return ids


def load_examples_by_id(ids: list[str], config: dict[str, Any], helper: Any) -> list[dict[str, Any]]:
    wanted = set(ids)
    found: dict[str, dict[str, Any]] = {}
    with TRAINING_EXAMPLES_PATH.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            example_id = row.get("example_id")
            if example_id in wanted:
                found[example_id] = helper.build_conversation(row, config)
                if len(found) == len(wanted):
                    break
    missing = [example_id for example_id in ids if example_id not in found]
    if missing:
        raise RuntimeError(f"missing {len(missing)} eval examples, first missing: {missing[:3]}")
    return [found[example_id] for example_id in ids]


def sha_text() -> str | None:
    if not GGUF_SHA_PATH.exists():
        return None
    return GGUF_SHA_PATH.read_text().strip().split()[0]


def request_completion(
    server_url: str,
    prompt: str,
    max_tokens: int,
    timeout: int,
    seed: int,
) -> tuple[str, dict[str, Any], float]:
    payload = {
        "model": "mafia-gemma-4-12b-it-gguf",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "top_k": 1,
        "seed": seed,
        "max_tokens": max_tokens,
    }
    start = time.perf_counter()
    response = requests.post(
        f"{server_url.rstrip('/')}/v1/chat/completions",
        json=payload,
        timeout=timeout,
    )
    elapsed = time.perf_counter() - start
    response.raise_for_status()
    data = response.json()
    text = data["choices"][0]["message"]["content"]
    return text, data, elapsed


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    helper = load_modal_helper()
    config = json.loads(CONFIG_PATH.read_text())
    ids = load_eval_ids(args.limit)
    examples = load_examples_by_id(ids, config, helper)
    output_json = Path(args.output_json)
    detail_path = output_json.with_suffix(".jsonl")
    output_json.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    prompt_tps: list[float] = []
    generation_tps: list[float] = []

    with detail_path.open("w") as detail:
        for index, example in enumerate(examples, 1):
            prompt = example["conversations"][0]["content"][0]["text"]
            try:
                prediction, raw, elapsed = request_completion(
                    args.server_url,
                    prompt,
                    args.max_tokens,
                    args.timeout,
                    int(config["seed"]),
                )
                row = helper.evaluate_prediction(example, prediction)
                row["prediction"] = prediction[:2000]
                row["latency_seconds"] = elapsed
                timings = raw.get("timings") or {}
                usage = raw.get("usage") or {}
                row["prompt_tokens"] = usage.get("prompt_tokens")
                row["completion_tokens"] = usage.get("completion_tokens")
                row["prompt_tokens_per_second"] = timings.get("prompt_per_second")
                row["completion_tokens_per_second"] = timings.get("predicted_per_second")
                latencies.append(elapsed)
                if isinstance(row["prompt_tokens_per_second"], (int, float)):
                    prompt_tps.append(float(row["prompt_tokens_per_second"]))
                if isinstance(row["completion_tokens_per_second"], (int, float)):
                    generation_tps.append(float(row["completion_tokens_per_second"]))
            except Exception as exc:
                row = {
                    "example_id": example.get("example_id"),
                    "task": example.get("task"),
                    "source": example.get("source"),
                    "actor_role": example.get("actor_role"),
                    "json_valid": False,
                    "parse_error": f"request_error:{type(exc).__name__}:{str(exc)[:300]}",
                    "required_fields_ok": False,
                    "exact_target_match": False,
                    "action_type_ok": False,
                    "role_action_ok": False,
                    "public_message_ok": False,
                    "prediction": "",
                }
            results.append(row)
            detail.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
            if index == 1 or index % args.progress_every == 0 or index == len(examples):
                print(
                    f"GGUF eval {index}/{len(examples)} "
                    f"json={sum(1 for r in results if r.get('json_valid')) / len(results):.3f} "
                    f"exact={sum(1 for r in results if r.get('exact_target_match')) / len(results):.3f}",
                    flush=True,
                )

    summary = helper.summarize_eval(results)
    summary["metadata"] = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server_url": args.server_url,
        "model_path": str(GGUF_PATH),
        "model_size_bytes": GGUF_PATH.stat().st_size if GGUF_PATH.exists() else None,
        "sha256": sha_text(),
        "sample_source": str(MERGED_DETAIL_PATH),
        "sample_limit": args.limit,
        "max_tokens": args.max_tokens,
        "request_timeout_seconds": args.timeout,
        "latency_seconds_mean": mean(latencies),
        "latency_seconds_median": statistics.median(latencies) if latencies else None,
        "prompt_tokens_per_second_mean": mean(prompt_tps),
        "completion_tokens_per_second_mean": mean(generation_tps),
    }
    output_json.write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the Mafia Gemma 4 GGUF through llama-server.")
    parser.add_argument("--server-url", default="http://127.0.0.1:8087")
    parser.add_argument("--limit", type=int, default=240)
    parser.add_argument("--max-tokens", type=int, default=384)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument(
        "--output-json",
        default=str(REPORT_DIR / "gguf_generation_eval.json"),
    )
    args = parser.parse_args()
    run_eval(args)


if __name__ == "__main__":
    main()
