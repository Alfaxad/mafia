from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any

from mafia.engine.replay import replay_summary
from mafia.engine.state import GameState


def game_metrics(state: GameState) -> dict[str, Any]:
    summary = replay_summary(state)
    message_lengths = [
        len(str(event.payload.get("message", "")).split())
        for event in state.events
        if event.type in {"player_message", "moderator_cue"}
    ]
    role_survival = Counter()
    for player in state.players.values():
        role_survival[f"{player.role.value}:alive={player.alive}"] += 1
    summary.update(
        {
            "avg_message_words": round(mean(message_lengths), 3) if message_lengths else 0.0,
            "role_survival": dict(role_survival),
            "model_calls": len(state.model_calls),
            "event_count": len(state.events),
        }
    )
    return summary
