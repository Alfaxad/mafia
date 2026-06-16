# Holy Grail Architecture Benchmark

This is the final public report for the same-model architecture comparison. The finalized agent architecture is reported as **Holy Grail** throughout.

## Scope

- **Architectures compared:** Holy Grail, ReVAC, and GRAIL.
- **Models:** Mafia Gemma BF16, GPT-5-mini, and Claude Opus 4.8.
- **Game setting:** same 7-player Mafia setup with the explicit non-player Time-to-Talk moderator.
- **Purpose:** isolate architecture effects while keeping the model fixed within each comparison group.

## Same-Model Architecture Results

| model | architecture | games | good_win_rate | avg_good_vote_accuracy | avg_detective_hit_rate | avg_doctor_saves | avg_mafia_alive_final | avg_llm_calls |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mafia Gemma BF16 | Holy Grail | 3 | 1.000 | 0.678 | 0.389 | 2.33 | 0.000 | 38 |
| Mafia Gemma BF16 | ReVAC | 3 | 0.000 | 0.079 | 0.167 | 1.000 | 2 | 63.67 |
| Mafia Gemma BF16 | GRAIL | 3 | 0.000 | 0.116 | 0.278 | 1.000 | 2 | 39.67 |
| GPT-5-mini | Holy Grail | 3 | 0.667 | 0.557 | 0.556 | 1.67 | 0.667 | 35.67 |
| GPT-5-mini | ReVAC | 3 | 0.333 | 0.283 | 0.667 | 1.000 | 1.33 | 72 |
| GPT-5-mini | GRAIL | 3 | 0.000 | 0.485 | 0.333 | 1.000 | 1.33 | 47.67 |
| Claude Opus 4.8 | Holy Grail | 3 | 0.667 | 0.611 | 0.278 | 1.67 | 0.667 | 29.33 |
| Claude Opus 4.8 | ReVAC | 3 | 0.667 | 0.663 | 0.667 | 1.000 | 0.667 | 71.33 |
| Claude Opus 4.8 | GRAIL | 3 | 0.333 | 0.455 | 0.389 | 0.667 | 1.33 | 41.67 |

## Holy Grail Deltas Against Baselines

Positive `good_win_rate_delta`, `good_vote_accuracy_delta`, and `detective_hit_rate_delta` favor Holy Grail. Negative `mafia_alive_final_delta`, `llm_calls_delta`, and `elapsed_sec_delta` usually favor Holy Grail.

| model | comparison | good_win_rate_delta | good_vote_accuracy_delta | detective_hit_rate_delta | mafia_alive_final_delta | llm_calls_delta | elapsed_sec_delta |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Mafia Gemma BF16 | Holy Grail - ReVAC | 1.000 | 0.599 | 0.222 | -2 | -25.67 | -222.14 |
| Mafia Gemma BF16 | Holy Grail - GRAIL | 1.000 | 0.562 | 0.111 | -2 | -1.67 | 121.12 |
| GPT-5-mini | Holy Grail - ReVAC | 0.333 | 0.274 | -0.111 | -0.667 | -36.33 | -115.01 |
| GPT-5-mini | Holy Grail - GRAIL | 0.667 | 0.072 | 0.222 | -0.667 | -12 | -26.20 |
| Claude Opus 4.8 | Holy Grail - ReVAC | 0.000 | -0.052 | -0.389 | 0.000 | -42 | -171.12 |
| Claude Opus 4.8 | Holy Grail - GRAIL | 0.333 | 0.156 | -0.111 | -0.667 | -12.33 | -21.74 |

## Interpretation

Holy Grail was strongest where the base model needed explicit role discipline and public-evidence grounding. On Mafia Gemma BF16, Holy Grail beat both ReVAC and GRAIL across all three sampled games, raising Good win rate from 0.0 to 1.0 while sharply improving Good vote accuracy and reducing final Mafia survival.

Against stronger frontier models, the comparison is more nuanced. Holy Grail improved GPT-5-mini over both baselines and matched Claude Opus 4.8's Good win rate against ReVAC while using fewer LLM calls. This supports the design choice to make Holy Grail a hybrid: ReVAC-style objective/risk review, WOLF-style social/deception ledgers, GRAIL-style role-count constraints, and a role-adaptive policy layer.

## Included Artifacts

- `holy_grail_final_summary.csv`: cleaned architecture summary.
- `holy_grail_final_deltas.csv`: cleaned baseline deltas.
- `holy_grail_final_games.csv`: per-game metrics.
- `holy_grail_final_player_metrics.csv`: per-player metrics.
- `holy_grail_final_role_summary.csv`: role-level metrics.
- `holy_grail_final_combined.jsonl`: cleaned full raw game records.
- `raw/` and `raw_batches/`: cleaned archive copies of original reports and run batches.
