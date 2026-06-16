from __future__ import annotations

import json
from pathlib import Path

import modal


RUN = "mafia-gemma4-12b-sft-v0"
CHECKPOINT_ROOT = Path("/checkpoints")

volume = modal.Volume.from_name("mafia-gemma4-checkpoints")
image = modal.Image.debian_slim(python_version="3.11")
app = modal.App("mafia-gemma4-report-reader")


@app.function(image=image, volumes={str(CHECKPOINT_ROOT): volume}, timeout=600)
def read_reports() -> dict[str, object]:
    root = CHECKPOINT_ROOT / "experiments" / RUN
    files: dict[str, str] = {}
    names = [
        "reports/upload_summary.json",
        "reports/adapter_generation_eval.json",
        "reports/adapter_generation_eval.jsonl",
        "reports/merged_generation_eval.json",
        "reports/merged_generation_eval.jsonl",
        "reports/base_generation_eval.json",
        "reports/base_generation_eval.jsonl",
        "reports/prepared_manifest.json",
        "trainer_state.json",
        "config.resolved.json",
    ]
    for name in names:
        path = root / name
        if path.exists():
            files[name] = path.read_text()

    samples: dict[str, list[str]] = {}
    for detail in [
        "adapter_generation_eval.jsonl",
        "merged_generation_eval.jsonl",
        "base_generation_eval.jsonl",
    ]:
        path = root / "reports" / detail
        if not path.exists():
            continue
        rows: list[str] = []
        with path.open() as handle:
            for index, line in enumerate(handle):
                if index >= 12:
                    break
                rows.append(line.rstrip("\n"))
        samples[f"reports/{detail}"] = rows
    return {"files": files, "samples": samples}


@app.local_entrypoint()
def main(
    output_dir: str = "fine-tuning/reports/modal/mafia-gemma4-12b-sft-v0/reports_latest",
) -> None:
    result = read_reports.remote()
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    for name, text in result["files"].items():
        path = out_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    for name, rows in result["samples"].items():
        path = out_root / f"{name}.sample12"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(rows) + "\n")

    print(
        json.dumps(
            {
                "local_dir": str(out_root),
                "files": sorted(result["files"]),
                "samples": sorted(result["samples"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
