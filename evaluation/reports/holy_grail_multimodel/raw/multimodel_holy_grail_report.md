# Multi-Model Holy Grail Full-Game Benchmark

Date: 2026-06-13 JST.

This reruns the moderated flagship-style evaluation with every player agent using Holy Grail. Claude Fable 5 is intentionally excluded. The non-player Moderator/Narrator is fixed to base Gemma 4 12B BF16 with the Time-to-Talk scheduler plus generator pattern.

## Controls

- Roles: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.
- Win conditions: Mafia parity or all Mafia eliminated.
- Player architecture: `holy_grail` for every player model.
- Moderator: `modal_base_bf16/google/gemma-4-12B-it:baseline`.
- Gemma sampler for base moderator, Mafia Gemma BF16, and Mafia Gemma GGUF Q8: `temperature=1.0`, `top_p=0.95`, `top_k=64`.
- Models: Mafia Gemma BF16, Mafia Gemma GGUF Q8, GPT-5 medium, GPT-5-mini, Claude Opus 4.8, Claude Sonnet 4.6, Gemini 2.5 Pro OSV.
- Rows: 20 local-vs-frontier pairwise games plus 4 mixed all-star rotation games.
- Validation: total API/player/moderator errors across rows = 0.

## High-Level Outcome

Completed games: 24. Pairwise games: 20. All-star games: 4.

| winner | games |
|---|---:|
| good | 16 |
| mafia | 8 |

## Pairwise Local-vs-Frontier Matrix

`win` means the local Mafia Gemma side won that row. All rows use Holy Grail on both sides.

| opponent | BF16 as Mafia | BF16 as Good | GGUF Q8 as Mafia | GGUF Q8 as Good |
|---|---:|---:|---:|---:|
| GPT-5 medium | loss | loss | win | loss |
| GPT-5-mini | loss | win | win | win |
| Claude Opus 4.8 | loss | win | loss | win |
| Claude Sonnet 4.6 | win | win | win | win |
| Gemini 2.5 Pro OSV | loss | win | loss | loss |

## Local Side Win Counts

| local model | side | wins | games |
|---|---|---:|---:|
| Mafia Gemma BF16 | mafia | 1 | 5 |
| Mafia Gemma BF16 | good | 4 | 5 |
| Mafia Gemma GGUF Q8 | mafia | 3 | 5 |
| Mafia Gemma GGUF Q8 | good | 3 | 5 |

## Model Slot Scoreboard

This counts each player slot, so pairwise rows heavily weight the two local models and their current opponent. The all-star-only table is the cleaner mixed-table view but has just four games.

### All Games

| Model | Slots | Team WR | Alive | Messages | Votes | Votes received | Claims | False claims |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mafia Gemma BF16 | 39 | 0.641 | 0.538 | 1.436 | 2.077 | 1.923 | 0.231 | 0.000 |
| Mafia Gemma GGUF Q8 | 39 | 0.590 | 0.538 | 1.231 | 1.795 | 1.590 | 0.333 | 0.026 |
| GPT-5 medium | 18 | 0.611 | 0.722 | 1.167 | 1.778 | 1.222 | 0.222 | 0.056 |
| GPT-5-mini | 18 | 0.444 | 0.389 | 1.444 | 1.944 | 2.222 | 0.333 | 0.000 |
| Claude Opus 4.8 | 18 | 0.611 | 0.444 | 1.500 | 2.167 | 2.556 | 0.389 | 0.000 |
| Claude Sonnet 4.6 | 18 | 0.111 | 0.333 | 1.278 | 1.667 | 2.667 | 0.222 | 0.000 |
| Gemini 2.5 Pro OSV | 18 | 0.889 | 0.556 | 1.500 | 2.222 | 1.889 | 0.167 | 0.000 |

### All-Star Only

| Model | Slots | Team WR | Alive | Messages | Votes | Votes received |
| --- | --- | --- | --- | --- | --- | --- |
| Mafia Gemma BF16 | 4 | 0.750 | 0.750 | 1.500 | 2.000 | 1.000 |
| Mafia Gemma GGUF Q8 | 4 | 0.500 | 0.500 | 1.250 | 1.500 | 1.750 |
| GPT-5 medium | 4 | 0.500 | 0.500 | 1.750 | 2.000 | 1.500 |
| GPT-5-mini | 4 | 0.750 | 0.500 | 1.250 | 1.500 | 2.250 |
| Claude Opus 4.8 | 4 | 0.250 | 0.250 | 1.750 | 2.000 | 2.750 |
| Claude Sonnet 4.6 | 4 | 0.500 | 0.500 | 1.500 | 2.000 | 2.750 |
| Gemini 2.5 Pro OSV | 4 | 1.000 | 1.000 | 1.500 | 2.250 | 1.250 |

## Role-Level Summary

| Model | Role | Slots | Team WR | Alive | Vote acc | Votes | Messages | Votes received | Claims | False claims |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mafia Gemma BF16 | Mafia | 10 | 0.200 | 0.200 | 1.000 | 26 | 1.700 | 3.600 | 0.000 | 0.000 |
| Mafia Gemma BF16 | Detective | 5 | 0.800 | 0.600 | 0.625 | 8 | 0.800 | 1.600 | 0.600 | 0.000 |
| Mafia Gemma BF16 | Doctor | 8 | 0.750 | 0.750 | 0.706 | 17 | 1.375 | 2.375 | 0.750 | 0.000 |
| Mafia Gemma BF16 | Villager | 16 | 0.812 | 0.625 | 0.700 | 30 | 1.500 | 0.750 | 0.000 | 0.000 |
| Mafia Gemma GGUF Q8 | Mafia | 11 | 0.545 | 0.545 | 1.000 | 19 | 1.273 | 2.000 | 0.091 | 0.091 |
| Mafia Gemma GGUF Q8 | Detective | 5 | 0.600 | 0.400 | 0.556 | 9 | 1.400 | 2.200 | 1.200 | 0.000 |
| Mafia Gemma GGUF Q8 | Doctor | 6 | 0.667 | 0.500 | 0.692 | 13 | 1.333 | 1.500 | 1.000 | 0.000 |
| Mafia Gemma GGUF Q8 | Villager | 17 | 0.588 | 0.588 | 0.621 | 29 | 1.118 | 1.176 | 0.000 | 0.000 |
| GPT-5 medium | Mafia | 5 | 0.800 | 0.800 | 1.000 | 7 | 1.000 | 1.200 | 0.200 | 0.200 |
| GPT-5 medium | Detective | 2 | 0.500 | 0.500 | 1.000 | 3 | 1.000 | 1.000 | 1.000 | 0.000 |
| GPT-5 medium | Doctor | 2 | 0.500 | 0.500 | 0.667 | 3 | 0.500 | 3.000 | 0.500 | 0.000 |
| GPT-5 medium | Villager | 9 | 0.556 | 0.778 | 0.526 | 19 | 1.444 | 0.889 | 0.000 | 0.000 |
| GPT-5-mini | Mafia | 4 | 0.000 | 0.000 | 1.000 | 10 | 2.000 | 3.500 | 0.000 | 0.000 |
| GPT-5-mini | Detective | 3 | 0.667 | 0.333 | 0.750 | 4 | 1.000 | 1.667 | 1.000 | 0.000 |
| GPT-5-mini | Doctor | 2 | 0.500 | 0.500 | 0.600 | 5 | 2.000 | 3.500 | 1.500 | 0.000 |
| GPT-5-mini | Villager | 9 | 0.556 | 0.556 | 0.562 | 16 | 1.222 | 1.556 | 0.000 | 0.000 |
| Claude Opus 4.8 | Mafia | 6 | 0.000 | 0.000 | 1.000 | 13 | 1.500 | 4.167 | 0.000 | 0.000 |
| Claude Opus 4.8 | Detective | 3 | 0.667 | 0.333 | 0.600 | 5 | 1.000 | 2.000 | 1.000 | 0.000 |
| Claude Opus 4.8 | Doctor | 2 | 1.000 | 1.000 | 0.500 | 6 | 2.000 | 3.500 | 2.000 | 0.000 |
| Claude Opus 4.8 | Villager | 7 | 1.000 | 0.714 | 0.733 | 15 | 1.571 | 1.143 | 0.000 | 0.000 |
| Claude Sonnet 4.6 | Mafia | 7 | 0.143 | 0.143 | 1.000 | 12 | 1.286 | 3.857 | 0.000 | 0.000 |
| Claude Sonnet 4.6 | Detective | 3 | 0.333 | 0.333 | 0.500 | 4 | 0.667 | 1.000 | 0.667 | 0.000 |
| Claude Sonnet 4.6 | Doctor | 2 | 0.000 | 0.500 | 0.250 | 4 | 1.500 | 1.500 | 1.000 | 0.000 |
| Claude Sonnet 4.6 | Villager | 6 | 0.000 | 0.500 | 0.300 | 10 | 1.500 | 2.500 | 0.000 | 0.000 |
| Gemini 2.5 Pro OSV | Mafia | 5 | 0.600 | 0.600 | 1.000 | 13 | 2.200 | 2.600 | 0.000 | 0.000 |
| Gemini 2.5 Pro OSV | Detective | 3 | 1.000 | 0.333 | 0.833 | 6 | 1.333 | 2.333 | 0.667 | 0.000 |
| Gemini 2.5 Pro OSV | Doctor | 2 | 1.000 | 0.000 | 0.000 | 2 | 0.500 | 2.500 | 0.500 | 0.000 |
| Gemini 2.5 Pro OSV | Villager | 8 | 1.000 | 0.750 | 0.789 | 19 | 1.375 | 1.125 | 0.000 | 0.000 |

## Vote And Role-Action Diagnostics

### Vote Accuracy By Faction

| Model | Faction | Votes | Vote acc |
| --- | --- | --- | --- |
| Mafia Gemma BF16 | good | 55 | 0.691 |
| Mafia Gemma BF16 | mafia | 26 | 1.000 |
| Mafia Gemma GGUF Q8 | good | 51 | 0.627 |
| Mafia Gemma GGUF Q8 | mafia | 19 | 1.000 |
| GPT-5 medium | good | 25 | 0.600 |
| GPT-5 medium | mafia | 7 | 1.000 |
| GPT-5-mini | good | 25 | 0.600 |
| GPT-5-mini | mafia | 10 | 1.000 |
| Claude Opus 4.8 | good | 26 | 0.654 |
| Claude Opus 4.8 | mafia | 13 | 1.000 |
| Claude Sonnet 4.6 | good | 18 | 0.333 |
| Claude Sonnet 4.6 | mafia | 12 | 1.000 |
| Gemini 2.5 Pro OSV | good | 27 | 0.741 |
| Gemini 2.5 Pro OSV | mafia | 13 | 1.000 |

### Night / Power Action Quality

For Detective, success means a Mafia hit. For Doctor, success means covering the Mafia kill target. For Mafia kill votes, success means targeting a power role.

| Model | Action | Count | Success rate |
| --- | --- | --- | --- |
| Mafia Gemma BF16 | detective_check | 9 | 0.444 |
| Mafia Gemma BF16 | doctor_save | 17 | 0.647 |
| Mafia Gemma BF16 | mafia_kill_vote | 26 | 0.615 |
| Mafia Gemma GGUF Q8 | detective_check | 11 | 0.545 |
| Mafia Gemma GGUF Q8 | doctor_save | 13 | 0.769 |
| Mafia Gemma GGUF Q8 | mafia_kill_vote | 23 | 0.652 |
| GPT-5 medium | detective_check | 4 | 0.250 |
| GPT-5 medium | doctor_save | 3 | 1.000 |
| GPT-5 medium | mafia_kill_vote | 11 | 0.364 |
| GPT-5-mini | detective_check | 5 | 0.600 |
| GPT-5-mini | doctor_save | 5 | 0.800 |
| GPT-5-mini | mafia_kill_vote | 10 | 0.400 |
| Claude Opus 4.8 | detective_check | 6 | 0.333 |
| Claude Opus 4.8 | doctor_save | 6 | 0.833 |
| Claude Opus 4.8 | mafia_kill_vote | 13 | 0.385 |
| Claude Sonnet 4.6 | detective_check | 6 | 0.500 |
| Claude Sonnet 4.6 | doctor_save | 4 | 0.750 |
| Claude Sonnet 4.6 | mafia_kill_vote | 12 | 0.667 |
| Gemini 2.5 Pro OSV | detective_check | 8 | 0.750 |
| Gemini 2.5 Pro OSV | doctor_save | 2 | 1.000 |
| Gemini 2.5 Pro OSV | mafia_kill_vote | 13 | 0.538 |

## Low-Level Call Metrics

| Model | Calls | Avg latency sec | Max latency sec | Avg output chars | Failed calls |
| --- | --- | --- | --- | --- | --- |
| Mafia Gemma BF16 | 56 | 8.963 | 103.935 | 217.000 | 0 |
| Mafia Gemma GGUF Q8 | 48 | 2.383 | 20.068 | 219.604 | 0 |
| GPT-5 medium | 21 | 31.484 | 102.330 | 229.810 | 0 |
| GPT-5-mini | 26 | 5.888 | 20.425 | 225.308 | 0 |
| Claude Opus 4.8 | 27 | 3.228 | 6.578 | 249.741 | 0 |
| Claude Sonnet 4.6 | 23 | 2.835 | 3.746 | 240.609 | 0 |
| Gemini 2.5 Pro OSV | 27 | 19.449 | 138.644 | 143.741 | 0 |

## Interpretation

- Holy Grail changed the balance toward Town compared with the older corrected-moderator report: 16/24 total games were Good wins, and the pairwise matrix no longer shows a broad Mafia-side sweep.
- Mafia Gemma BF16 became strong as Good under Holy Grail, winning 4/5 local-good pairwise rows. Its Mafia side was much weaker in this sample, winning only against Claude Sonnet.
- Mafia Gemma GGUF Q8 was the more volatile local model: it beat GPT-5 medium and GPT-5-mini as Mafia, but lost both Opus and Gemini Mafia-side rows. As Good, it beat GPT-5-mini, Opus, and Sonnet, but lost to GPT-5 medium and Gemini.
- GPT-5 medium remained the toughest frontier opponent overall in pairwise side tests: it beat BF16 in both directions and split against GGUF, losing only when GGUF played Mafia.
- Claude Opus 4.8 was strongest against local Mafia but weaker when its own Mafia side faced local Good. That matches the same-model result where Opus did not need Holy Grail as much as smaller/local models but still benefited from efficient structure.
- Gemini 2.5 Pro OSV beat both local Mafia sides and beat GGUF Good when Gemini played Mafia; BF16 Good beat Gemini Mafia. Its all-games slot score was still the highest in this run, but the pairwise result is not a clean sweep.
- The all-star rows are too few for a ranking by themselves, but they are useful qualitatively: mixed tables did not collapse into automatic Mafia wins; Town won 3/4 all-star rotations.

## Artifacts

- Scenario config: `multimodel_holy_grail_scenarios.json`
- Combined raw games: `multimodel_holy_grail_combined.jsonl`
- Summary CSV: `multimodel_holy_grail_summary.csv`
- Pairwise matrix: `multimodel_holy_grail_pairwise_matrix.csv`
- Player metrics: `multimodel_holy_grail_player_metrics.csv`
- Model summary: `multimodel_holy_grail_model_summary.csv`
- Role summary: `multimodel_holy_grail_role_summary.csv`
- Vote summary: `multimodel_holy_grail_vote_summary.csv`
- Role action summary: `multimodel_holy_grail_role_action_summary.csv`
- Call summary: `multimodel_holy_grail_call_summary.csv`
