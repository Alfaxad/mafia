from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mafia.engine.state import GameState


@dataclass(slots=True)
class AgentDecision:
    action: str
    target: str | None = None
    message: str = ""
    speech_act: str = "statement"
    emotion: str = "calm"
    confidence: float = 0.5
    private_rationale_summary: str = ""


class PlayerAgent(Protocol):
    player_id: str

    def decide(self, state: GameState) -> AgentDecision:
        ...
