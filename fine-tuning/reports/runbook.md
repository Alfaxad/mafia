# Mafia Gemma 4 Fine-Tuning Runbook

## Current Training Choice

Use Unsloth QLoRA on `unsloth/gemma-4-12b-it`.

Reasons:

- Gemma 4 support in the Unsloth notebook uses `FastModel`, 4-bit loading,
  response-only SFT, and native merged/GGUF export.
- vLLM's Gemma 4 recipe says the 12B dense model fits a single 40 GB GPU for
  inference; QLoRA training should fit an A100-80GB with margin.
- The training target is role-conditioned game behavior, not full model
  replacement, so LoRA is the right first pass.

## Stage Boundary

This run performs SFT over the unified task schema. It intentionally does not
run DPO or self-play RL until SFT validity is known, because poor JSON/action
formatting would poison preference or RL stages.

The dataset prep keeps `PREFERENCE_PAIR` examples in the prepared files so DPO
can be layered on after the SFT checkpoint has passed held-out evaluation.

## Acceptance Checks

- Modal smoke run reaches training, writes a checkpoint, and writes eval JSON.
- W&B run exists for the smoke run and the full run.
- Full run resumes from checkpoints if interrupted.
- Merged private model repo exists: `Alfaxad/mafia-gemma-4-12B-it`.
- Private GGUF repo exists: `Alfaxad/mafia-gemma-4-12B-it-gguf`.
- Evaluation reports compare base, LoRA/merged, and GGUF when available.
