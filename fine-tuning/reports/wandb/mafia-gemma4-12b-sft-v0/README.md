# W&B Run Snapshot: mafia-gemma4-12b-sft-v0

Source run: [alfaxad/mafia-gemma4-12b/7zhlpbt2](https://wandb.ai/alfaxad/mafia-gemma4-12b/runs/7zhlpbt2)

The live W&B API export was not available from this workstation because
`env.txt` does not currently contain `WANDB_API_KEY`, and there is no local W&B
login. To keep the repo artifact useful, this directory preserves the scalar
training history from the pulled Modal `trainer_state.json`. These are the same
Trainer metrics that were logged during the run:

- step loss
- eval loss
- learning rate
- gradient norm
- runtime and throughput
- final train loss

Files:

- `trainer_history.jsonl`: scalar log-history rows from `trainer_state.json`.
- `trainer_history.csv`: tabular version of the same rows.
- `trainer_history_summary.json`: run pointer, final step, row count, and final
  metric rows.

No API keys, local W&B cache files, checkpoints, or model weights are included.
