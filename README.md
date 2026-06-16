# Mafia

AI-native one-human plus six-AI Mafia game.

## Current Build

Implemented:

- Authoritative seven-player Mafia engine.
- Roles: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.
- Classic loop: Night -> Dawn -> Discussion -> Hot Seat -> Vote -> Resolution.
- Private/public view isolation.
- Event-sourced logs and replay summaries.
- Time-to-Talk style non-player `ModeratorAgent`.
- Product `holy_grail` player architecture, with `holy_grail_v4` compatibility alias.
- Online-only Modal model runtime for Mafia Gemma BF16 players and the base Gemma BF16 Time-to-Talk moderator.
- Phaser/Gradio Server game app with onboarding, avatar selection, status updates, discussions, action controls, role reveal, and endgame reveal.
- Modal staging entrypoint.

## Local Development

Use the Conda Python that has Gradio installed:

```bash
PYTHONPATH=src /Users/alfaxad/miniconda3/bin/python3 app.py
```

Then open:

```text
http://127.0.0.1:7860
```

## Tests

```bash
pytest -q
```

## Deterministic Engine Policy Playtests

```bash
PYTHONPATH=src /Users/alfaxad/miniconda3/bin/python3 -m mafia.simulation --games 20 --out-dir reports/playtests
```

## Modal Staging

```bash
modal deploy modal/gradio_app.py
```

Current deployed staging URL:

```text
https://nadhari--ai-native-mafia-gradio-web.modal.run
```

The staging app uses the deployed Modal inference app `mafia-gemma4-inference` through `src/mafia/models/modal_client.py`.
