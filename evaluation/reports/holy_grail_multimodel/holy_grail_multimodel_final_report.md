# Holy Grail Multi-Model Full-Game Benchmark

This is the final public evaluation report for the full-game multi-model benchmark. The finalized agent architecture is reported as **Holy Grail** throughout.

## Scope

- **Game format:** 7-player Mafia, 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.
- **Flow:** full multi-day games with night actions, dawn reports, moderated discussion, public voting, and classic win conditions.
- **Moderator:** non-player Time-to-Talk moderator using scheduler + generator.
- **Player architecture:** Holy Grail agent architecture.
- **Local model reporting:** BF16 and Q8 Mafia Gemma runs are combined as **Mafia Gemma 4 12B**. Variant-level raw files remain archived under `raw/` and `raw_batches/` for reproducibility.

## Headline Results

- Completed games: **24** total: 20 local-vs-frontier pairwise games and 4 all-star mixed games.
- Overall winners: **Town/Good 16**, **Mafia 8**.
- The combined Mafia Gemma 4 12B result is competitive with frontier model slots under the same Holy Grail architecture: **0.615 team win rate** across 78 player slots.

## Model Slot Scoreboard

| model | player_slots | team_win_rate | alive_final_rate | avg_messages_spoken | avg_votes_cast | avg_votes_received | avg_role_claims | avg_false_role_claims |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mafia Gemma 4 12B | 78 | 0.615 | 0.538 | 1.33 | 1.94 | 1.76 | 0.282 | 0.013 |
| Claude Opus 4.8 | 18 | 0.611 | 0.444 | 1.50 | 2.17 | 2.56 | 0.389 | 0 |
| Claude Sonnet 4.6 | 18 | 0.111 | 0.333 | 1.28 | 1.67 | 2.67 | 0.222 | 0 |
| GPT-5 medium | 18 | 0.611 | 0.722 | 1.17 | 1.78 | 1.22 | 0.222 | 0.056 |
| GPT-5-mini | 18 | 0.444 | 0.389 | 1.44 | 1.94 | 2.22 | 0.333 | 0 |
| Gemini 2.5 Pro OSV | 18 | 0.889 | 0.556 | 1.50 | 2.22 | 1.89 | 0.167 | 0 |

## All-Star Mixed Games

| model | player_slots | team_win_rate | alive_final_rate | avg_messages_spoken | avg_votes_cast | avg_votes_received |
| --- | --- | --- | --- | --- | --- | --- |
| Mafia Gemma 4 12B | 8 | 0.625 | 0.625 | 1.38 | 1.75 | 1.38 |
| Claude Opus 4.8 | 4 | 0.250 | 0.250 | 1.75 | 2 | 2.75 |
| Claude Sonnet 4.6 | 4 | 0.500 | 0.500 | 1.50 | 2 | 2.75 |
| GPT-5 medium | 4 | 0.500 | 0.500 | 1.75 | 2 | 1.50 |
| GPT-5-mini | 4 | 0.750 | 0.500 | 1.25 | 1.50 | 2.25 |
| Gemini 2.5 Pro OSV | 4 | 1.000 | 1.000 | 1.50 | 2.25 | 1.25 |

## Mafia Gemma Role Breakdown

| role | player_slots | team_win_rate | alive_final_rate | vote_accuracy | votes | avg_messages_spoken | avg_votes_received | avg_role_claims | avg_false_role_claims |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mafia | 21 | 0.381 | 0.381 | 1 | 45 | 1.48 | 2.76 | 0.048 | 0.048 |
| Detective | 10 | 0.700 | 0.500 | 0.588 | 17 | 1.10 | 1.90 | 0.900 | 0 |
| Doctor | 14 | 0.714 | 0.643 | 0.700 | 30 | 1.36 | 2 | 0.857 | 0 |
| Villager | 33 | 0.697 | 0.606 | 0.661 | 59 | 1.30 | 0.970 | 0 | 0 |

## Provider Runtime Summary

| model | calls | avg_latency_sec | max_latency_sec | avg_output_chars | failed_calls |
| --- | --- | --- | --- | --- | --- |
| Mafia Gemma 4 12B | 104 | 5.93 | 103.94 | 218.20 | 0 |
| Claude Opus 4.8 | 27 | 3.23 | 6.58 | 249.74 | 0 |
| Claude Sonnet 4.6 | 23 | 2.84 | 3.75 | 240.61 | 0 |
| GPT-5 medium | 21 | 31.48 | 102.33 | 229.81 | 0 |
| GPT-5-mini | 26 | 5.89 | 20.43 | 225.31 | 0 |
| Gemini 2.5 Pro OSV | 27 | 19.45 | 138.64 | 143.74 | 0 |

## Interpretation

The combined Mafia Gemma 4 12B runs do not simply win because of isolated role luck: the local model family posts strong Town-side role performance while remaining viable in Mafia seats. Gemini 2.5 Pro OSV had the strongest aggregate team-slot win rate in this run, while Mafia Gemma 4 12B stayed close to GPT-5 medium and Claude Opus 4.8 despite running as the specialized local model family.

The most useful practical conclusion is architectural: once every model is placed under the same Holy Grail agent stack and moderated Time-to-Talk flow, small and local models can stay competitive in complete social-deduction games, especially when the architecture supplies role constraints, deception ledgers, private objective review, and floor-controlled communication.

## Included Artifacts

- `combined_model_summary.csv`: BF16/Q8 combined model-level summary.
- `combined_role_summary.csv`: BF16/Q8 combined role-level summary.
- `combined_vote_summary.csv`: BF16/Q8 combined vote summary.
- `combined_call_summary.csv`: BF16/Q8 combined runtime summary.
- `raw/`: cleaned copies of the original generated summaries.
- `raw_batches/`: cleaned raw JSONL game batches and batch summaries.
- `scenarios/`: cleaned scenario definitions.
