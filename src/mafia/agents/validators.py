from __future__ import annotations

from dataclasses import dataclass, field

from mafia.engine.state import GameState, Phase
from mafia.engine.views import legal_actions_for


@dataclass(slots=True)
class ValidationResult:
    allow: bool
    reasons: list[str] = field(default_factory=list)
    repaired_message: str | None = None


FORBIDDEN_PRIVATE_PHRASES = (
    "system prompt",
    "hidden prompt",
    "private_info",
    "mafia_team",
    "role assignment seed",
)


def validate_message(state: GameState, actor: str, message: str, max_words: int = 24) -> ValidationResult:
    reasons: list[str] = []
    words = message.split()
    if len(words) > max_words:
        reasons.append("message exceeds word budget")
    lowered = message.lower()
    if any(phrase in lowered for phrase in FORBIDDEN_PRIVATE_PHRASES):
        reasons.append("message references private/system information")
    if actor != "moderator" and actor not in state.players:
        reasons.append("unknown actor")
    if state.phase not in {Phase.DISCUSSION, Phase.HOT_SEAT, Phase.VOTE, Phase.NIGHT}:
        reasons.append("message not legal in current phase")
    if reasons:
        repaired = " ".join(words[:max_words])
        return ValidationResult(False, reasons, repaired_message=repaired)
    return ValidationResult(True)


def validate_action(state: GameState, actor: str, action: str, target: str | None) -> ValidationResult:
    legal = legal_actions_for(state, actor)
    if action not in legal:
        return ValidationResult(False, [f"{action} is not legal for current role/phase"])
    if target is not None and target not in state.players:
        return ValidationResult(False, ["target does not exist"])
    if target is not None and not state.players[target].alive:
        return ValidationResult(False, ["target is not alive"])
    return ValidationResult(True)
