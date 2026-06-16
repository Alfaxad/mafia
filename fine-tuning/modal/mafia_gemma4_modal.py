from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import modal


APP_NAME = "mafia-gemma4-finetune"
SECRET_NAME = "mafia-finetune-secrets"

MODEL_CACHE = Path("/model_cache")
DATASET_CACHE = Path("/dataset_cache")
CHECKPOINT_ROOT = Path("/checkpoints")

model_cache_volume = modal.Volume.from_name("mafia-gemma4-model-cache", create_if_missing=True)
dataset_cache_volume = modal.Volume.from_name("mafia-gemma4-dataset", create_if_missing=True)
checkpoint_volume = modal.Volume.from_name("mafia-gemma4-checkpoints", create_if_missing=True)

train_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "git-lfs", "curl", "build-essential", "cmake", "pkg-config")
    .run_commands(
        "pip install --upgrade pip uv",
        "uv pip install --system "
        "'torch>=2.8.0' 'triton>=3.4.0' torchvision bitsandbytes accelerate "
        "'datasets==4.3.0' 'huggingface_hub>=0.34.0' hf_transfer "
        "sentencepiece protobuf peft 'trl==0.29.1' timm torchcodec wandb "
        "safetensors pandas numpy scikit-learn",
        "uv pip install --system "
        "'unsloth[base] @ git+https://github.com/unslothai/unsloth' "
        "'unsloth_zoo[base] @ git+https://github.com/unslothai/unsloth-zoo'",
        "uv pip install --system --no-deps "
        "'transformers==5.11.0' 'tokenizers>=0.22.0,<=0.23.0' 'trl==0.29.1'",
    )
    .env(
        {
            "HF_HOME": str(MODEL_CACHE),
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "HF_XET_HIGH_PERFORMANCE": "1",
            "TORCHDYNAMO_CACHE_SIZE_LIMIT": "2048",
            "UNSLOTH_COMPILE_DISABLE": "1",
            "UNSLOTH_COMPILE_MAXIMUM": "0",
            "PYTHONUNBUFFERED": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
)

app = modal.App(APP_NAME)


QUALITY_ORDER = {"bronze": 0, "silver": 1, "gold": 2}
TASK_REQUIRED_FIELDS = {
    "ACTION_JSON": ["action_type"],
    "SCHEDULER": ["speak", "urgency", "message_type"],
    "PUBLIC_MESSAGE": ["message", "message_type"],
    "BELIEF_UPDATE": ["belief_update"],
    "CLAIM_CHECK": ["claim_check"],
    "DECEPTION_LABEL": ["deception_label"],
    "VOTE_DECISION": ["action_type", "target_player"],
    "NIGHT_ACTION": ["action_type", "target_player"],
    "PRIVATE_REVIEW": ["private_review"],
    "PREFERENCE_PAIR": ["chosen", "rejected"],
}
ALLOWED_ACTION_TYPES = {"message", "vote", "kill", "protect", "investigate", "speak_wait"}
NIGHT_ACTION_BY_ROLE = {"Mafia": "kill", "Doctor": "protect", "Detective": "investigate"}


def default_config() -> dict[str, Any]:
    return {
        "run_name": "mafia-gemma4-12b-sft-v0",
        "base_model_id": "unsloth/gemma-4-12b-it",
        "hf_dataset_repo": "build-small-hackathon/mafia-dataset",
        "hf_dataset_file": "data/examples/training_examples.full.jsonl",
        "target_model_repo": "build-small-hackathon/mafia-gemma-4-12B-it",
        "target_gguf_repo": "build-small-hackathon/mafia-gemma-4-12B-it-gguf",
        "seed": 3407,
        "max_seq_length": 4096,
        "target_train_rows": 60000,
        "target_eval_rows": 2000,
        "target_test_rows": 2000,
        "min_message_quality": 1,
        "min_quality_by_task": {"PRIVATE_REVIEW": "bronze"},
        "source_weights": {"bayesian_avalon_grail": 3.5},
        "always_include_train_sources": ["bayesian_avalon_grail", "llmafia", "local_7p_harness"],
        "task_weights": {},
        "tier_weights": {"gold": 3.0, "silver": 1.6, "bronze": 0.35},
        "role_weights": {},
        "max_transcript_events": 5,
        "max_text_chars": 420,
        "max_json_chars": 5600,
        "lora_r": 32,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 16,
        "learning_rate": 1e-4,
        "weight_decay": 0.001,
        "warmup_ratio": 0.03,
        "lr_scheduler_type": "cosine",
        "max_steps": 1000,
        "logging_steps": 25,
        "save_steps": 100,
        "eval_steps": 250,
        "preprocess_num_proc": 8,
        "packing": True,
        "resume": True,
        "enable_wandb": True,
        "wandb_project": "mafia-gemma4-12b",
        "eval_generation_limit": 240,
        "eval_max_new_tokens": 384,
        "upload_merged": True,
        "upload_gguf": True,
        "gguf_quantization": "Q8_0",
    }


def load_config(config_json: str | None = None, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    config = default_config()
    if config_json:
        loaded = json.loads(config_json)
        deep_update(config, loaded)
    if overrides:
        deep_update(config, overrides)
    return config


def deep_update(target: dict[str, Any], incoming: dict[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_update(target[key], value)
        else:
            target[key] = value


def configure_torch_dynamo(torch_module: Any) -> None:
    """Relax TorchDynamo limits for Unsloth's compiled Gemma 4 modules."""
    dynamo = getattr(torch_module, "_dynamo", None)
    if dynamo is None:
        return
    config = getattr(dynamo, "config", None)
    if config is None:
        return
    for name, value in {
        "cache_size_limit": 2048,
        "accumulated_cache_size_limit": 4096,
        "recompile_limit": 2048,
        "accumulated_recompile_limit": 4096,
    }.items():
        try:
            if hasattr(config, name):
                setattr(config, name, value)
        except Exception:
            pass
    try:
        if hasattr(config, "suppress_errors"):
            config.suppress_errors = True
    except Exception:
        pass
    visible = {}
    for name in ("cache_size_limit", "accumulated_cache_size_limit", "recompile_limit"):
        if hasattr(config, name):
            visible[name] = getattr(config, name)
    print(f"TorchDynamo config: {visible}")


def run_dir(config: dict[str, Any]) -> Path:
    return CHECKPOINT_ROOT / "experiments" / config["run_name"]


def prepared_dir(config: dict[str, Any]) -> Path:
    return DATASET_CACHE / "prepared" / config["run_name"]


def raw_dataset_path(config: dict[str, Any]) -> Path:
    safe_name = config["hf_dataset_file"].replace("/", "__")
    return DATASET_CACHE / "raw" / config["hf_dataset_repo"].replace("/", "__") / safe_name


def stable_float(value: str, seed: int = 0) -> float:
    digest = hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16) / float(16**16)


def stable_key(row: dict[str, Any]) -> str:
    return str(row.get("example_id") or row.get("source_ref", {}).get("event_id") or json.dumps(row, sort_keys=True)[:200])


def compact_text(value: str, max_chars: int) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 3].rstrip() + "..."


def compact_value(value: Any, max_text_chars: int, max_transcript_events: int) -> Any:
    if isinstance(value, str):
        return compact_text(value, max_text_chars)
    if isinstance(value, list):
        items = value[-max_transcript_events:] if len(value) > max_transcript_events else value
        return [compact_value(item, max_text_chars, max_transcript_events) for item in items]
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, inner in value.items():
            if key in {"raw_text", "raw", "source_file", "file"}:
                continue
            compacted[key] = compact_value(inner, max_text_chars, max_transcript_events)
        return compacted
    return value


def truncate_jsonable(obj: Any, max_chars: int) -> Any:
    text = json.dumps(obj, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    if len(text) <= max_chars:
        return obj
    if isinstance(obj, dict):
        reduced = copy.deepcopy(obj)
        public_state = reduced.get("public_state")
        if isinstance(public_state, dict) and isinstance(public_state.get("public_transcript_window"), list):
            public_state["public_transcript_window"] = public_state["public_transcript_window"][-3:]
        text = json.dumps(reduced, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if len(text) <= max_chars:
            return reduced
    return {"truncated_context_json": text[: max_chars - 20] + "..."}


def tier_allowed(row: dict[str, Any], config: dict[str, Any]) -> bool:
    task = row.get("task", "ACTION_JSON")
    min_tier = config.get("min_quality_by_task", {}).get(task, "bronze")
    return QUALITY_ORDER.get(row.get("quality_tier", "bronze"), -1) >= QUALITY_ORDER.get(min_tier, 0)


def row_is_eligible(row: dict[str, Any], config: dict[str, Any]) -> bool:
    labels = row.get("quality_labels") or {}
    if not labels.get("valid_schema", False):
        return False
    if not labels.get("no_future_leakage", False):
        return False
    if not labels.get("no_private_info_leakage", False):
        return False
    if row.get("task") in {"ACTION_JSON", "VOTE_DECISION", "NIGHT_ACTION"} and not labels.get("legal_action", False):
        return False
    if row.get("task") in {"VOTE_DECISION", "NIGHT_ACTION"} and not labels.get("role_consistent", False):
        return False
    if row.get("task") == "PUBLIC_MESSAGE" and labels.get("message_quality", 0) < config.get("min_message_quality", 0):
        return False
    if not tier_allowed(row, config):
        return False
    if not isinstance(row.get("target"), dict):
        return False
    return True


def group_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        row.get("source", "unknown"),
        row.get("task", "unknown"),
        row.get("quality_tier", "bronze"),
        (row.get("actor") or {}).get("role", "Unknown"),
    )


def row_weight(group: tuple[str, str, str, str], config: dict[str, Any]) -> float:
    source, task, tier, role = group
    source_weight = config.get("source_weights", {}).get(source, config.get("source_weights", {}).get("unknown", 0.5))
    task_weight = config.get("task_weights", {}).get(task, 1.0)
    tier_weight = config.get("tier_weights", {}).get(tier, 1.0)
    role_weight = config.get("role_weights", {}).get(role, 1.0)
    return max(0.0, float(source_weight) * float(task_weight) * float(tier_weight) * float(role_weight))


def solve_sample_scale(group_counts: Counter[tuple[str, str, str, str]], target_rows: int, config: dict[str, Any]) -> float:
    if target_rows <= 0 or not group_counts:
        return 0.0

    def expected(scale: float) -> float:
        total = 0.0
        for group, count in group_counts.items():
            total += count * min(1.0, row_weight(group, config) * scale)
        return total

    lo, hi = 0.0, 1.0
    while expected(hi) < target_rows and hi < 1e6:
        hi *= 2.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        if expected(mid) < target_rows:
            lo = mid
        else:
            hi = mid
    return hi


def build_prompt(row: dict[str, Any], config: dict[str, Any]) -> str:
    task = row.get("task", "ACTION_JSON")
    actor = row.get("actor", {})
    prompt = {
        "instruction": "You are a role-adaptive Mafia game agent. Return only valid JSON for the target task. Do not reveal private role information in public-message tasks unless a legal claim is explicitly required by the task.",
        "task": task,
        "required_target_fields": TASK_REQUIRED_FIELDS.get(task, []),
        "actor": {
            "id": actor.get("id"),
            "role": actor.get("role"),
            "team": actor.get("team"),
            "alive": actor.get("alive"),
        },
        "game": row.get("game"),
        "private_info": row.get("private_info"),
        "public_state": row.get("public_state"),
        "structured_memory": row.get("structured_memory"),
        "candidate_actions": (row.get("input") or {}).get("candidate_actions", []),
        "constraints": (row.get("input") or {}).get("constraints", []),
        "source_training_note": {
            "source": row.get("source"),
            "quality_tier": row.get("quality_tier"),
            "label_source": (row.get("quality_labels") or {}).get("label_source"),
        },
    }
    prompt = compact_value(prompt, config["max_text_chars"], config["max_transcript_events"])
    prompt = truncate_jsonable(prompt, config["max_json_chars"])
    return (
        "MAFIA_AGENT_TRAINING_TASK\n"
        "Output policy: return exactly one JSON object and no markdown.\n"
        "Training item:\n"
        + json.dumps(prompt, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    )


def build_conversation(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    target = json.dumps(row["target"], ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return {
        "example_id": row.get("example_id"),
        "split": row.get("split"),
        "source": row.get("source"),
        "task": row.get("task"),
        "quality_tier": row.get("quality_tier"),
        "actor_role": (row.get("actor") or {}).get("role"),
        "target": target,
        "conversations": [
            {"role": "user", "content": [{"type": "text", "text": build_prompt(row, config)}]},
            {"role": "assistant", "content": [{"type": "text", "text": target}]},
        ],
    }


def scan_eligible_counts(raw_path: Path, config: dict[str, Any]) -> tuple[Counter[tuple[str, str, str, str]], Counter[str], Counter[str]]:
    train_groups: Counter[tuple[str, str, str, str]] = Counter()
    split_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    with raw_path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not row_is_eligible(row, config):
                continue
            split = row.get("split", "train")
            split_counts[split] += 1
            source_counts[row.get("source", "unknown")] += 1
            if split == "train":
                train_groups[group_key(row)] += 1
    return train_groups, split_counts, source_counts


def write_prepared_files(raw_path: Path, config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    train_groups, split_counts, source_counts = scan_eligible_counts(raw_path, config)
    train_scale = solve_sample_scale(train_groups, int(config["target_train_rows"]), config)

    counts: Counter[str] = Counter()
    by_task: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    by_role: Counter[str] = Counter()
    dpo_pairs = 0

    paths = {
        "train": output_dir / "train.messages.jsonl",
        "validation": output_dir / "eval.messages.jsonl",
        "test": output_dir / "test.messages.jsonl",
        "dpo": output_dir / "dpo_pairs.jsonl",
        "sample": output_dir / "samples.jsonl",
    }

    handles = {name: path.open("w") for name, path in paths.items()}
    try:
        with raw_path.open() as raw:
            for line in raw:
                if not line.strip():
                    continue
                row = json.loads(line)
                if not row_is_eligible(row, config):
                    continue
                split = row.get("split", "train")
                key = stable_key(row)
                if split == "train":
                    source = row.get("source", "unknown")
                    always_include = source in set(config.get("always_include_train_sources", []))
                    if not always_include:
                        probability = min(1.0, row_weight(group_key(row), config) * train_scale)
                        if stable_float(key, config["seed"]) >= probability:
                            continue
                        if counts["train"] >= int(config["target_train_rows"]):
                            continue
                    out_name = "train"
                elif split == "validation":
                    if counts["validation"] >= int(config["target_eval_rows"]):
                        continue
                    if stable_float(key, config["seed"] + 17) > 0.5:
                        continue
                    out_name = "validation"
                elif split == "test":
                    if counts["test"] >= int(config["target_test_rows"]):
                        continue
                    if stable_float(key, config["seed"] + 23) > 0.5:
                        continue
                    out_name = "test"
                else:
                    continue

                prepared = build_conversation(row, config)
                handles[out_name].write(json.dumps(prepared, ensure_ascii=True, separators=(",", ":")) + "\n")
                counts[out_name] += 1
                by_task[row.get("task", "unknown")] += 1
                by_source[row.get("source", "unknown")] += 1
                by_role[(row.get("actor") or {}).get("role", "Unknown")] += 1

                if row.get("task") == "PREFERENCE_PAIR":
                    handles["dpo"].write(json.dumps(prepared, ensure_ascii=True, separators=(",", ":")) + "\n")
                    dpo_pairs += 1
                if counts["sample"] < 100:
                    handles["sample"].write(json.dumps(prepared, ensure_ascii=True, separators=(",", ":")) + "\n")
                    counts["sample"] += 1
    finally:
        for handle in handles.values():
            handle.close()

    manifest = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "config": config,
        "raw_path": str(raw_path),
        "eligible_split_counts": dict(split_counts),
        "eligible_source_counts": dict(source_counts),
        "train_group_count": len(train_groups),
        "train_sample_scale": train_scale,
        "prepared_counts": dict(counts),
        "prepared_by_task": dict(by_task),
        "prepared_by_source": dict(by_source),
        "prepared_by_role": dict(by_role),
        "dpo_pairs": dpo_pairs,
        "paths": {name: str(path) for name, path in paths.items()},
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def ensure_raw_dataset(config: dict[str, Any]) -> Path:
    from huggingface_hub import hf_hub_download

    raw_path = raw_dataset_path(config)
    if raw_path.exists() and raw_path.stat().st_size > 0:
        return raw_path
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    token = os.environ["HF_API_KEY"]
    downloaded = hf_hub_download(
        repo_id=config["hf_dataset_repo"],
        filename=config["hf_dataset_file"],
        repo_type="dataset",
        token=token,
        local_dir=raw_path.parent,
    )
    downloaded_path = Path(downloaded)
    if downloaded_path != raw_path:
        raw_path.write_bytes(downloaded_path.read_bytes())
    return raw_path


def ensure_prepared(config: dict[str, Any], force: bool = False) -> dict[str, Any]:
    out = prepared_dir(config)
    manifest_path = out / "manifest.json"
    if manifest_path.exists() and not force:
        return json.loads(manifest_path.read_text())
    raw_path = ensure_raw_dataset(config)
    return write_prepared_files(raw_path, config, out)


def load_text_dataset(path: Path, tokenizer: Any, num_proc: int):
    from datasets import load_dataset

    dataset = load_dataset("json", data_files=str(path), split="train")

    def format_batch(examples: dict[str, list[Any]]) -> dict[str, list[str]]:
        texts = []
        for conversation in examples["conversations"]:
            text = tokenizer.apply_chat_template(
                conversation,
                tokenize=False,
                add_generation_prompt=False,
            ).removeprefix("<bos>")
            texts.append(text)
        return {"text": texts}

    remove_columns = dataset.column_names
    return dataset.map(
        format_batch,
        batched=True,
        remove_columns=remove_columns,
        num_proc=max(1, int(num_proc)),
        desc=f"Formatting {path.name}",
    )


def find_latest_checkpoint(path: Path) -> str | None:
    if not path.exists():
        return None
    checkpoints = []
    for child in path.iterdir():
        if child.is_dir() and child.name.startswith("checkpoint-"):
            try:
                checkpoints.append((int(child.name.split("-")[-1]), child))
            except ValueError:
                continue
    if not checkpoints:
        return None
    return str(sorted(checkpoints)[-1][1])


def normalize_json_for_compare(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def extract_json_object(text: str) -> tuple[dict[str, Any] | None, str | None]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    decoder = json.JSONDecoder()
    for idx, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj, None
    return None, "no_json_object"


def evaluate_prediction(example: dict[str, Any], prediction_text: str) -> dict[str, Any]:
    target_raw = example.get("target") or {}
    if isinstance(target_raw, str):
        try:
            target = json.loads(target_raw)
        except json.JSONDecodeError:
            target = {}
    else:
        target = target_raw
    task = example.get("task")
    parsed, parse_error = extract_json_object(prediction_text)
    result = {
        "example_id": example.get("example_id"),
        "task": task,
        "source": example.get("source"),
        "actor_role": example.get("actor_role"),
        "json_valid": parsed is not None,
        "parse_error": parse_error,
        "required_fields_ok": False,
        "exact_target_match": False,
        "action_type_ok": False,
        "role_action_ok": True,
        "public_message_ok": True,
    }
    if parsed is None:
        return result
    required = TASK_REQUIRED_FIELDS.get(task, [])
    result["required_fields_ok"] = all(field in parsed for field in required)
    result["exact_target_match"] = normalize_json_for_compare(parsed) == normalize_json_for_compare(target)
    action_type = parsed.get("action_type")
    result["action_type_ok"] = action_type in ALLOWED_ACTION_TYPES if action_type is not None else task not in {"ACTION_JSON", "VOTE_DECISION", "NIGHT_ACTION"}
    if task == "NIGHT_ACTION":
        expected = NIGHT_ACTION_BY_ROLE.get(example.get("actor_role"))
        result["role_action_ok"] = bool(expected and action_type == expected)
    if task == "PUBLIC_MESSAGE":
        message = str(parsed.get("message", ""))
        lower = message.lower()
        result["public_message_ok"] = bool(message.strip()) and not any(
            phrase in lower
            for phrase in [
                "my private_info",
                "private info",
                "mafia_partners",
                "investigation_results",
                "structured_memory",
            ]
        )
    return result


def summarize_eval(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"count": 0}
    metrics = [
        "json_valid",
        "required_fields_ok",
        "exact_target_match",
        "action_type_ok",
        "role_action_ok",
        "public_message_ok",
    ]
    summary: dict[str, Any] = {"count": len(rows)}
    for metric in metrics:
        summary[metric] = sum(1 for row in rows if row.get(metric)) / len(rows)
    by_task: dict[str, dict[str, Any]] = {}
    tasks = sorted({str(row.get("task")) for row in rows})
    for task in tasks:
        task_rows = [row for row in rows if row.get("task") == task]
        by_task[task] = {"count": len(task_rows)}
        for metric in metrics:
            by_task[task][metric] = sum(1 for row in task_rows if row.get(metric)) / len(task_rows)
    summary["by_task"] = by_task
    return summary


def sample_eval_examples(path: Path, limit: int, seed: int) -> list[dict[str, Any]]:
    rows: list[tuple[float, dict[str, Any]]] = []
    with path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            key = row.get("example_id") or line[:100]
            rows.append((stable_float(str(key), seed), row))
    rows.sort(key=lambda item: item[0])
    return [row for _, row in rows[:limit]]


def run_generation_eval(
    model: Any,
    tokenizer: Any,
    examples: list[dict[str, Any]],
    config: dict[str, Any],
    report_path: Path,
) -> dict[str, Any]:
    import torch

    report_path.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    detail_path = report_path.with_suffix(".jsonl")
    with detail_path.open("w") as detail:
        for index, example in enumerate(examples, 1):
            conversation = example["conversations"][:1]
            inputs = tokenizer.apply_chat_template(
                conversation,
                add_generation_prompt=True,
                tokenize=True,
                return_tensors="pt",
                return_dict=True,
            ).to("cuda")
            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=int(config["eval_max_new_tokens"]),
                    do_sample=False,
                    use_cache=True,
                )
            input_tokens = inputs["input_ids"].shape[-1]
            decoded = tokenizer.decode(output[0][input_tokens:], skip_special_tokens=True)
            row = evaluate_prediction(example, decoded)
            row["prediction"] = decoded[:2000]
            results.append(row)
            detail.write(json.dumps(row, ensure_ascii=True, separators=(",", ":")) + "\n")
            if index % 25 == 0:
                print(f"Evaluated {index}/{len(examples)} examples")
    summary = summarize_eval(results)
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


@app.function(
    image=train_image,
    volumes={
        str(MODEL_CACHE): model_cache_volume,
        str(DATASET_CACHE): dataset_cache_volume,
        str(CHECKPOINT_ROOT): checkpoint_volume,
    },
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=6 * 60 * 60,
)
def prepare_dataset(config_json: str | None = None, force: bool = False) -> dict[str, Any]:
    config = load_config(config_json)
    manifest = ensure_prepared(config, force=force)
    dataset_cache_volume.commit()
    return manifest


@app.function(
    image=train_image,
    gpu=["A100-80GB", "H100", "A100-40GB"],
    volumes={
        str(MODEL_CACHE): model_cache_volume,
        str(DATASET_CACHE): dataset_cache_volume,
        str(CHECKPOINT_ROOT): checkpoint_volume,
    },
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=24 * 60 * 60,
    retries=modal.Retries(initial_delay=0.0, max_retries=2),
    single_use_containers=True,
)
def train_sft(config_json: str | None = None, force_prepare: bool = False) -> dict[str, Any]:
    import unsloth  # noqa: F401
    import torch
    import wandb
    from unsloth import FastModel
    from unsloth.chat_templates import get_chat_template, train_on_responses_only
    from transformers import set_seed
    from trl import SFTConfig, SFTTrainer

    configure_torch_dynamo(torch)
    config = load_config(config_json)
    set_seed(int(config["seed"]))

    manifest = ensure_prepared(config, force=force_prepare)
    paths = {
        "run": run_dir(config),
        "prepared": prepared_dir(config),
    }
    reports_dir = paths["run"] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    paths["run"].mkdir(parents=True, exist_ok=True)
    (paths["run"] / "config.resolved.json").write_text(json.dumps(config, indent=2, sort_keys=True))
    (reports_dir / "prepared_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))

    if config.get("enable_wandb", True):
        wandb.init(
            project=config.get("wandb_project", "mafia-gemma4-12b"),
            name=config["run_name"],
            config=config,
        )

    print(f"Loading model {config['base_model_id']}")
    model, tokenizer = FastModel.from_pretrained(
        model_name=config["base_model_id"],
        dtype=None,
        max_seq_length=int(config["max_seq_length"]),
        load_in_4bit=True,
        full_finetuning=False,
        token=os.environ["HF_API_KEY"],
    )
    tokenizer = get_chat_template(tokenizer, chat_template="gemma-4")

    model = FastModel.get_peft_model(
        model,
        finetune_vision_layers=False,
        finetune_language_layers=True,
        finetune_attention_modules=True,
        finetune_mlp_modules=True,
        r=int(config["lora_r"]),
        lora_alpha=int(config["lora_alpha"]),
        lora_dropout=float(config["lora_dropout"]),
        bias="none",
        random_state=int(config["seed"]),
    )

    train_dataset = load_text_dataset(paths["prepared"] / "train.messages.jsonl", tokenizer, int(config["preprocess_num_proc"]))
    eval_dataset = load_text_dataset(paths["prepared"] / "eval.messages.jsonl", tokenizer, max(1, min(4, int(config["preprocess_num_proc"]))))

    training_args = SFTConfig(
        dataset_text_field="text",
        per_device_train_batch_size=int(config["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(config["gradient_accumulation_steps"]),
        warmup_ratio=float(config["warmup_ratio"]),
        max_steps=int(config["max_steps"]),
        learning_rate=float(config["learning_rate"]),
        logging_steps=int(config["logging_steps"]),
        save_strategy="steps",
        save_steps=int(config["save_steps"]),
        eval_strategy="steps",
        eval_steps=int(config["eval_steps"]),
        optim="adamw_8bit",
        weight_decay=float(config["weight_decay"]),
        lr_scheduler_type=str(config["lr_scheduler_type"]),
        seed=int(config["seed"]),
        output_dir=str(paths["run"]),
        report_to="wandb" if config.get("enable_wandb", True) else "none",
        run_name=config["run_name"],
        packing=bool(config["packing"]),
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=training_args,
    )
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|turn>user\n",
        response_part="<|turn>model\n",
    )

    resume_from = find_latest_checkpoint(paths["run"]) if config.get("resume", True) else None
    if resume_from:
        print(f"Resuming from checkpoint: {resume_from}")
        trainer.train(resume_from_checkpoint=resume_from)
    else:
        print("Starting SFT from scratch")
        trainer.train()

    final_adapter = paths["run"] / "final_adapter"
    model.save_pretrained(final_adapter)
    tokenizer.save_pretrained(final_adapter)
    trainer.save_state()

    examples = sample_eval_examples(paths["prepared"] / "test.messages.jsonl", int(config["eval_generation_limit"]), int(config["seed"]) + 101)
    summary = run_generation_eval(model, tokenizer, examples, config, reports_dir / "adapter_generation_eval.json")

    if config.get("enable_wandb", True):
        wandb.log({f"generation_eval/{key}": value for key, value in summary.items() if isinstance(value, (int, float))})
        wandb.finish()

    checkpoint_volume.commit()
    dataset_cache_volume.commit()
    model_cache_volume.commit()

    return {
        "run_name": config["run_name"],
        "final_adapter": str(final_adapter),
        "eval_summary": summary,
        "prepared_counts": manifest.get("prepared_counts"),
    }


@app.function(
    image=train_image,
    gpu=["A100-80GB", "H100", "A100-40GB"],
    volumes={
        str(MODEL_CACHE): model_cache_volume,
        str(DATASET_CACHE): dataset_cache_volume,
        str(CHECKPOINT_ROOT): checkpoint_volume,
    },
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=18 * 60 * 60,
    retries=modal.Retries(initial_delay=0.0, max_retries=1),
    single_use_containers=True,
)
def evaluate_model(config_json: str | None = None, variant: str = "adapter", limit: int | None = None) -> dict[str, Any]:
    import unsloth  # noqa: F401
    import torch
    from unsloth import FastModel
    from unsloth.chat_templates import get_chat_template

    configure_torch_dynamo(torch)
    config = load_config(config_json)
    ensure_prepared(config, force=False)
    run_path = run_dir(config)
    reports_dir = run_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    if variant == "base":
        model_name = config["base_model_id"]
    elif variant == "adapter":
        model_name = str(run_path / "final_adapter")
    elif variant == "merged":
        model_name = str(run_path / "merged_16bit")
    else:
        raise ValueError(f"Unknown variant: {variant}")

    model, tokenizer = FastModel.from_pretrained(
        model_name=model_name,
        dtype=None,
        max_seq_length=int(config["max_seq_length"]),
        load_in_4bit=True,
        full_finetuning=False,
        token=os.environ["HF_API_KEY"],
    )
    tokenizer = get_chat_template(tokenizer, chat_template="gemma-4")

    eval_limit = int(limit or config["eval_generation_limit"])
    examples = sample_eval_examples(prepared_dir(config) / "test.messages.jsonl", eval_limit, int(config["seed"]) + 211)
    summary = run_generation_eval(
        model,
        tokenizer,
        examples,
        config,
        reports_dir / f"{variant}_generation_eval.json",
    )
    checkpoint_volume.commit()
    return {"variant": variant, "summary": summary}


@app.function(
    image=train_image,
    gpu=["A100-80GB", "H100"],
    volumes={
        str(MODEL_CACHE): model_cache_volume,
        str(DATASET_CACHE): dataset_cache_volume,
        str(CHECKPOINT_ROOT): checkpoint_volume,
    },
    secrets=[modal.Secret.from_name(SECRET_NAME)],
    timeout=24 * 60 * 60,
    retries=modal.Retries(initial_delay=0.0, max_retries=1),
    single_use_containers=True,
)
def merge_upload_export(config_json: str | None = None) -> dict[str, Any]:
    import unsloth  # noqa: F401
    import torch
    from huggingface_hub import HfApi
    from unsloth import FastModel
    from unsloth.chat_templates import get_chat_template

    configure_torch_dynamo(torch)
    config = load_config(config_json)
    token = os.environ["HF_API_KEY"]
    run_path = run_dir(config)
    adapter_path = run_path / "final_adapter"
    if not adapter_path.exists():
        raise FileNotFoundError(f"Missing final adapter: {adapter_path}")

    api = HfApi(token=token)
    api.create_repo(config["target_model_repo"], repo_type="model", private=True, exist_ok=True)
    api.create_repo(config["target_gguf_repo"], repo_type="model", private=True, exist_ok=True)

    model, tokenizer = FastModel.from_pretrained(
        model_name=str(adapter_path),
        dtype=None,
        max_seq_length=int(config["max_seq_length"]),
        load_in_4bit=True,
        full_finetuning=False,
        token=token,
    )
    tokenizer = get_chat_template(tokenizer, chat_template="gemma-4")

    merged_path = run_path / "merged_16bit"
    print(f"Saving merged model to {merged_path}")
    model.save_pretrained_merged(str(merged_path), tokenizer, save_method="merged_16bit")

    uploaded: dict[str, Any] = {"merged_path": str(merged_path)}
    if config.get("upload_merged", True):
        print(f"Uploading merged model to {config['target_model_repo']}")
        model.push_to_hub_merged(
            config["target_model_repo"],
            tokenizer,
            save_method="merged_16bit",
            token=token,
        )
        uploaded["merged_repo"] = config["target_model_repo"]

    if config.get("upload_gguf", True):
        gguf_quant = str(config.get("gguf_quantization", "Q8_0"))
        print(f"Uploading GGUF to {config['target_gguf_repo']} with quantization {gguf_quant}")
        try:
            model.push_to_hub_gguf(
                config["target_gguf_repo"],
                tokenizer,
                quantization_method=gguf_quant,
                token=token,
            )
            uploaded["gguf_repo"] = config["target_gguf_repo"]
            uploaded["gguf_quantization"] = gguf_quant
        except Exception as exc:
            fallback = gguf_quant.lower()
            if fallback == gguf_quant:
                raise
            print(f"GGUF upload failed with {gguf_quant}: {exc}. Retrying with {fallback}")
            model.push_to_hub_gguf(
                config["target_gguf_repo"],
                tokenizer,
                quantization_method=fallback,
                token=token,
            )
            uploaded["gguf_repo"] = config["target_gguf_repo"]
            uploaded["gguf_quantization"] = fallback

    (run_path / "reports").mkdir(parents=True, exist_ok=True)
    (run_path / "reports" / "upload_summary.json").write_text(json.dumps(uploaded, indent=2, sort_keys=True))
    checkpoint_volume.commit()
    model_cache_volume.commit()
    return uploaded


@app.local_entrypoint()
def main(
    stage: str = "smoke",
    config: str = "fine-tuning/configs/sft_v0.json",
    max_steps: int = 0,
    variant: str = "adapter",
    force_prepare: bool = False,
) -> None:
    config_path = Path(config)
    config_json = config_path.read_text() if config_path.exists() else None
    resolved = load_config(config_json)

    if stage == "smoke":
        smoke = copy.deepcopy(resolved)
        smoke["run_name"] = f"{resolved['run_name']}-smoke"
        smoke["target_train_rows"] = 768
        smoke["target_eval_rows"] = 128
        smoke["target_test_rows"] = 128
        smoke["always_include_train_sources"] = ["bayesian_avalon_grail"]
        smoke["max_steps"] = max_steps or 5
        smoke["save_steps"] = max(1, min(5, smoke["max_steps"]))
        smoke["eval_steps"] = max(1, min(5, smoke["max_steps"]))
        smoke["logging_steps"] = 1
        smoke["eval_generation_limit"] = 16
        smoke["enable_wandb"] = bool(resolved.get("enable_wandb", True))
        smoke_json = json.dumps(smoke)
        print(json.dumps(prepare_dataset.remote(smoke_json, force=True), indent=2, sort_keys=True))
        print(json.dumps(train_sft.remote(smoke_json, force_prepare=False), indent=2, sort_keys=True))
        return

    if max_steps > 0:
        resolved["max_steps"] = max_steps
    config_json = json.dumps(resolved)

    if stage == "prepare":
        print(json.dumps(prepare_dataset.remote(config_json, force=force_prepare), indent=2, sort_keys=True))
    elif stage == "train":
        print(json.dumps(train_sft.remote(config_json, force_prepare=force_prepare), indent=2, sort_keys=True))
    elif stage == "spawn_train":
        call = train_sft.spawn(config_json, force_prepare=force_prepare)
        launched = {
            "run_name": resolved["run_name"],
            "max_steps": resolved["max_steps"],
            "function_call": getattr(call, "object_id", str(call)),
            "note": "Training was submitted with train_sft.spawn; use modal app list/logs to monitor the ephemeral app.",
        }
        local_report = Path("fine-tuning/reports/modal/last_spawn_train.json")
        local_report.parent.mkdir(parents=True, exist_ok=True)
        local_report.write_text(json.dumps(launched, indent=2, sort_keys=True))
        print(json.dumps(launched, indent=2, sort_keys=True))
    elif stage == "eval":
        print(json.dumps(evaluate_model.remote(config_json, variant=variant), indent=2, sort_keys=True))
    elif stage == "merge":
        print(json.dumps(merge_upload_export.remote(config_json), indent=2, sort_keys=True))
    elif stage == "all":
        print(json.dumps(prepare_dataset.remote(config_json, force=force_prepare), indent=2, sort_keys=True))
        print(json.dumps(train_sft.remote(config_json, force_prepare=False), indent=2, sort_keys=True))
        print(json.dumps(merge_upload_export.remote(config_json), indent=2, sort_keys=True))
        print(json.dumps(evaluate_model.remote(config_json, variant="merged"), indent=2, sort_keys=True))
        print(json.dumps(evaluate_model.remote(config_json, variant="base"), indent=2, sort_keys=True))
    else:
        raise SystemExit(f"Unknown stage: {stage}")
