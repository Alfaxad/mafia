# Fine-Tuning Artifact Manifest

This directory is a repo-safe snapshot of the Modal fine-tuning pipeline used
for Mafia Gemma 4 12B.

## Included

- `configs/sft_v0.json`: final SFT configuration.
- `modal/mafia_gemma4_modal.py`: Modal training, merge, upload, and evaluation
  pipeline.
- `modal/mafia_modal_inference.py`: Modal inference runtime used for BF16/GGUF
  testing.
- `scripts/`: helper scripts for Modal secrets, artifact pulls, GGUF download,
  GGUF smoke/eval, and report reading.
- `reports/mafia_gemma4_sft_v0_final_report.md`: final SFT report.
- `reports/runbook.md`: runbook and acceptance checks.
- `reports/modal/`: pulled Modal metadata and final evaluation artifacts.
- `reports/wandb/mafia-gemma4-12b-sft-v0/`: W&B run pointer and exported
  Trainer scalar history.
- `gguf/gemma-4-12b-it.Q8_0.gguf.sha256`: checksum for the local/HF GGUF.
- `gguf/smoke_prompt.txt`: GGUF smoke-test prompt.

## Intentionally Excluded

- Model weights, adapters, checkpoints, and local GGUF binaries.
- Modal volumes and dataset caches.
- `env.txt`, API keys, W&B credentials, and local secret material.
- Python bytecode and cache folders.
- Research PDFs and downloaded notebooks that are references, not finalized
  pipeline artifacts.

The W&B API export could not be pulled on this machine because no
`WANDB_API_KEY` or local W&B login was configured. The same scalar training
history is preserved from `trainer_state.json`, and the canonical W&B run URL is
recorded in `reports/wandb/mafia-gemma4-12b-sft-v0/`.
