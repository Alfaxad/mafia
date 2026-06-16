# Codex Agent Trace

This folder contains the sanitized Codex agent trace for the social deduction
agent reasoning research and the development of the AI-native Mafia game.

The trace records the semi-autonomous Codex work that happened under developer
supervision and direction. It covers open-source background research, paper and
repository review, experiment harness development, Modal-based model evaluation,
Holy Grail agent design, OpenGame/OpenAgent supervision, production game
development, final reports, and repository launch preparation.

## Sanitization

The JSONL trace was sanitized before publication to remove infrastructure keys,
secrets, private tokens, and project references that were not intended for the
public repo. The original local trace was not edited in place; this exported
copy is the shareable artifact.

The trace remains large because it preserves the implementation history, tool
calls, experiment iteration, debugging, evaluation, and development context. It
is tracked with Git LFS.

## What This Trace Shows

- Codex reading and operationalizing social deduction research.
- Modal fine-tuning and inference setup for Mafia Gemma.
- Full-game evaluation across models and agent architectures.
- Design and iteration of the Holy Grail Mafia agent architecture.
- Use of OpenGame/OpenAgent to bootstrap visual game design.
- Productionization of the game backend, frontend, assets, and deployment docs.

This is not a polished tutorial transcript. It is a development trace: useful
for auditing how the work evolved, what tradeoffs were made, and how the final
Mafia game and agent stack were assembled.
