# Mafia Evaluation Artifacts

This folder contains the finalized evaluation harnesses, Modal inference code, and public reports for the Mafia research and game system.

## Start Here

- [Holy Grail multi-model full-game benchmark](reports/holy_grail_multimodel/holy_grail_multimodel_final_report.md)
- [Holy Grail architecture benchmark](reports/holy_grail_vs_architectures/holy_grail_architecture_final_report.md)

## What Is Included

- `harnesses/run_seven_player_mafia.py`: full seven-player Mafia evaluation harness with classic win conditions, non-player Time-to-Talk moderation, provider routing, and architecture metrics.
- `modal/mafia_modal_inference.py`: Modal inference runtime used for Mafia Gemma BF16, base Gemma moderator, and GGUF evaluation endpoints.
- `scripts/`: analysis and scenario generation scripts used to produce the reports.
- `reports/holy_grail_multimodel/`: multi-model full-game results under the Holy Grail architecture.
- `reports/holy_grail_vs_architectures/`: same-model comparison between Holy Grail, ReVAC, and GRAIL.

## Reporting Convention

The finalized architecture is reported as **Holy Grail**. Older development file names and scenario IDs were normalized in this exported package so the public reports consistently use the final architecture name.

For the multi-model benchmark, BF16 and Q8 Mafia Gemma runs are combined into the public model family row **Mafia Gemma 4 12B**. Variant-level CSV/JSONL records are still archived under each report's `raw/` and `raw_batches/` folders for reproducibility.

## Reproducibility Notes

The reports are evaluation snapshots, not training artifacts. They intentionally exclude API keys, Hugging Face tokens, Modal secrets, W&B credentials, model weights, and generated cache folders.

Raw JSONL game records are included because they are the basis for the final tables and make the reported metrics auditable.
