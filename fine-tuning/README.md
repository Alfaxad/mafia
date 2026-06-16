# Mafia Gemma 4 12B Fine-Tuning

This folder contains the reproducible Modal pipeline for fine-tuning
`unsloth/gemma-4-12b-it` on `Alfaxad/mafia-dataset`.

The first implemented training pass is response-only SFT over the unified Mafia
task schema:

- legal JSON/action formatting
- role-conditioned policy decisions
- belief, claim, and deception labels
- scheduler and public-message behavior
- private review fields inspired by ReVAC/WOLF/GRAIL

DPO and self-play/distillation are treated as follow-on stages. The code keeps
preference examples and evaluation hooks separate so those stages can be added
without changing the SFT data contract.

## Modal Commands

Create or refresh the Modal secret from `env.txt`:

```bash
python3 fine-tuning/scripts/create_modal_secret.py
```

Run a short smoke test:

```bash
modal run fine-tuning/modal/mafia_gemma4_modal.py --stage smoke --config fine-tuning/configs/sft_v0.json --max-steps 5
```

Run full SFT:

```bash
modal run fine-tuning/modal/mafia_gemma4_modal.py --stage train --config fine-tuning/configs/sft_v0.json
```

Merge, upload, export GGUF, and evaluate:

```bash
modal run fine-tuning/modal/mafia_gemma4_modal.py --stage merge --config fine-tuning/configs/sft_v0.json
modal run fine-tuning/modal/mafia_gemma4_modal.py --stage eval --config fine-tuning/configs/sft_v0.json --variant merged
modal run fine-tuning/modal/mafia_gemma4_modal.py --stage eval --config fine-tuning/configs/sft_v0.json --variant base
```

Pull reports from Modal:

```bash
fine-tuning/scripts/pull_modal_artifacts.sh mafia-gemma4-12b-sft-v0
```

Stop Modal apps after completion:

```bash
modal app stop mafia-gemma4-finetune
```
