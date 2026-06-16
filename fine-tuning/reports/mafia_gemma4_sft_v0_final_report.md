# Mafia Gemma 4 12B SFT v0 Final Report

Run: `mafia-gemma4-12b-sft-v0`

Completed on Modal with `unsloth/gemma-4-12b-it`, LoRA r=32/alpha=64,
4096-token context, 60k sampled train rows, 2k validation rows, 2k test rows,
and 1000 optimizer steps.

## Training

- Final global step: 1000
- Train runtime: 20,352.4 seconds
- Final train loss: 0.04144
- Final step loss: 0.03355
- Final eval loss at step 1000: 0.57703
- Saved checkpoints: 100 through 1000
- Final adapter: `/checkpoints/experiments/mafia-gemma4-12b-sft-v0/final_adapter`

## Uploads

- Merged private HF repo: `build-small-hackathon/mafia-gemma-4-12B-it`
- GGUF private HF repo: `build-small-hackathon/mafia-gemma-4-12B-it-gguf`
- GGUF quantization: `Q8_0`
- Merged repo verification: private, has `model.safetensors`, config, tokenizer, and chat template files
- GGUF repo verification: private, has `gemma-4-12b-it.Q8_0.gguf` and `gemma-4-12b-it.BF16-mmproj.gguf`
- GGUF local download: complete at `fine-tuning/gguf/gemma-4-12b-it.Q8_0.gguf`
- GGUF SHA-256: `e1c320c43638bb0fde6986f669eada9850ac89d02acf7ba627efb87ea69e0572`
- GGUF runtime smoke: passed with the Gemma4-capable local `llama.cpp` build. Homebrew `llama-cli` was too old and failed with unknown architecture `gemma4`, so the local `tools/llama.cpp-diffusiongemma` build was used.

## Generation Eval

All variants were evaluated on 240 sampled held-out test examples.

| Variant | JSON valid | Required fields | Exact target | Action type | Role action | Public message |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Adapter | 1.000 | 1.000 | 0.2208 | 1.000 | 1.000 | 1.000 |
| Merged | 1.000 | 1.000 | 0.2250 | 1.000 | 1.000 | 1.000 |
| GGUF Q8_0 | 1.000 | 1.000 | 0.2458 | 1.000 | 1.000 | 1.000 |
| Base | 1.000 | 1.000 | 0.0000 | 0.9875 | 1.000 | 1.000 |

Task-level exact match:

| Variant | Night action | Public message | Vote decision |
| --- | ---: | ---: | ---: |
| Adapter | 0.2444 | 0.0071 | 0.7455 |
| Merged | 0.2889 | 0.0000 | 0.7455 |
| GGUF Q8_0 | 0.3556 | 0.0000 | 0.7818 |
| Base | 0.0000 | 0.0000 | 0.0000 |

## Quality Notes

The merged model is consistent with the adapter. The GGUF Q8_0 runtime is also
consistent with the merged model and slightly stronger on this held-out sample.
All fine-tuned variants return clean JSON-only outputs, preserve required
fields, and keep role/action constraints intact.
The base model often emits a `thought` prefix before JSON, while the fine-tuned
adapter, merged model, and GGUF runtime do not in the sampled rows.

Exact match is a strict metric and is naturally low for open-ended public
messages. The useful signal is that the fine-tuned model moved vote decisions
to 74.55 percent exact match and night actions to 28.89 percent after merge.
The local Q8_0 GGUF reached 78.18 percent vote exact match and 35.56 percent
night-action exact match while retaining 100 percent JSON validity and
required-field compliance. The small GGUF-over-merged lift is likely decoding
runtime variance rather than a different learned policy, but it is a good sign:
quantization did not damage the JSON/action behavior.

GGUF runtime speed on the local `llama-server` path averaged 233.2 prompt
tokens/sec, 23.8 generated tokens/sec, and 2.48 seconds/request over the
240-example eval.

## Local Artifacts

Pulled reports are under:

`fine-tuning/reports/modal/mafia-gemma4-12b-sft-v0/reports_latest`

Important files:

- `reports/upload_summary.json`
- `reports/adapter_generation_eval.json`
- `reports/merged_generation_eval.json`
- `reports/gguf_generation_eval.json`
- `reports/base_generation_eval.json`
- `reports/*.jsonl.sample12`
- `trainer_state.json`
- `config.resolved.json`

Additional GGUF local files:

- `fine-tuning/scripts/download_gguf.py`
- `fine-tuning/scripts/evaluate_gguf_server.py`
- `fine-tuning/gguf/gemma-4-12b-it.Q8_0.gguf`
- `fine-tuning/gguf/gemma-4-12b-it.Q8_0.gguf.sha256`

## Modal Cleanup

The deployed Modal app `mafia-gemma4-finetune` was stopped after merge/upload
and evaluations completed. Modal app list showed zero active tasks.
