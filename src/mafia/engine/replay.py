from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from mafia.engine.state import Event, GameState


def serialize_event(event: Event) -> dict[str, Any]:
    data = asdict(event)
    data["phase"] = event.phase.value
    return data


def export_events_jsonl(state: GameState, path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8") as fh:
        for event in state.events:
            fh.write(json.dumps(serialize_event(event), ensure_ascii=False) + "\n")


def replay_summary(state: GameState) -> dict[str, Any]:
    messages = [e for e in state.events if e.type in {"player_message", "moderator_cue"}]
    votes = [e for e in state.events if e.type == "vote_cast"]
    night_actions = [e for e in state.events if e.type == "night_action_submitted"]
    return {
        "game_id": state.game_id,
        "seed": state.seed,
        "winner": state.winner.value if state.winner else None,
        "days": state.day_number,
        "messages": len(messages),
        "votes": len(votes),
        "night_actions": len(night_actions),
        "invalid_actions": state.invalid_actions,
        "validator_repairs": state.validator_repairs,
        "moderator_turns": state.moderator_turns,
        "ai_turns": state.ai_turns,
        "eliminated_order": list(state.eliminated_order),
    }
