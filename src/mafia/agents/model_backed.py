from __future__ import annotations

import json
import re

from mafia.agents.base import AgentDecision
from mafia.agents.holy_grail import HolyGrailAgent
from mafia.agents.validators import validate_message
from mafia.engine.state import GameState
from mafia.engine.views import legal_actions_for, private_view
from mafia.models.provider_types import TextProvider


class ModelBackedHolyGrailAgent(HolyGrailAgent):
    """Optional model-backed agent wrapper.

    The deterministic Holy Grail policy remains the fallback. Model output must
    satisfy the same JSON contract; otherwise the architecture policy handles it.
    """

    def __init__(self, player_id: str, provider: TextProvider):
        super().__init__(player_id)
        self.provider = provider

    def decide(self, state: GameState) -> AgentDecision:
        fallback = super().decide(state)
        legal_actions = legal_actions_for(state, self.player_id)
        fallback = _fallback_for_legal(state, self.player_id, fallback, legal_actions)
        if not legal_actions or legal_actions == ["sleep"] or fallback.action in {"none", "sleep"}:
            return fallback
        legal_targets = _legal_targets(state, self.player_id, legal_actions)
        fallback = _repair_target_for_legal(fallback, legal_targets)
        prompt = json.dumps(
            {
                "task": "Choose one legal Mafia game action as strict JSON.",
                "json_schema": {
                    "action": legal_actions,
                    "target": legal_targets,
                    "message": "short public message if action is message",
                    "speech_act": "statement|question|accusation|defense|evidence|claim",
                    "emotion": "calm|focused|pressing|nervy|guarded",
                },
                "rules": [
                    f"You are {state.players[self.player_id].display_name}. Your player_id is {self.player_id}.",
                    "Speak only as yourself. Do not write dialogue for another player.",
                    "Use display names from player_name_map. Never mention raw IDs like p1, p2, or p5.",
                    "If referring to your own role, say 'my role' or 'I am...', not '<your name> role'.",
                    "Pick only an action from legal_actions.",
                    "Pick target only from legal_targets.",
                    "Only cite public evidence that appears in public_evidence.",
                    "Do not mention votes, voting patterns, or last votes unless public_evidence.vote_count_total is above 0.",
                    "Do not mention claim conflicts unless public_evidence.claim_count_total is above 0.",
                    "Never reveal private information unless it is your deliberate public claim.",
                    "For public speech, use at most 20 words and stay in-character.",
                    "In hot-seat phase, answer the accusation with a defense or concrete question. Do not vote until phase is vote.",
                    "Use HOLY GRAIL: role-count constraints, evidence ledger, deception-risk review, and WOLF-style suspicion/claim tracking.",
                    "Return JSON only. No markdown.",
                ],
                "legal_actions": legal_actions,
                "legal_targets": legal_targets,
                "actor_identity": _actor_identity(state, self.player_id),
                "player_name_map": _player_name_map(state),
                "public_evidence": _public_evidence_summary(state),
                "private_view": private_view(state, self.player_id),
                "fallback_policy": {
                    "action": fallback.action,
                    "target": fallback.target,
                    "message": fallback.message,
                    "speech_act": fallback.speech_act,
                },
            },
            ensure_ascii=False,
        )
        try:
            result = self.provider.generate(prompt, max_tokens=192, temperature=1.0, top_p=0.95, top_k=64)
            state.model_calls.append(
                {
                    "player_id": self.player_id,
                    "provider": result.backend,
                    "model": result.model,
                    "latency_seconds": result.latency_seconds,
                    "prompt_tokens": result.prompt_tokens,
                    "completion_tokens": result.completion_tokens,
                }
            )
            data = json.loads(_extract_json(result.text))
            raw_message = str(data.get("message", fallback.message))
            decision = AgentDecision(
                action=str(data.get("action", fallback.action)),
                target=data.get("target", fallback.target),
                message=_sanitize_model_message(state, self.player_id, raw_message),
                speech_act=str(data.get("speech_act", fallback.speech_act)),
                emotion=str(data.get("emotion", fallback.emotion)),
                confidence=float(data.get("confidence", fallback.confidence)),
                private_rationale_summary="model-backed holy_grail decision",
            )
            return _validate_decision(state, self.player_id, decision, fallback, legal_actions, legal_targets)
        except Exception as exc:
            state.model_calls.append(
                {
                    "player_id": self.player_id,
                    "provider": getattr(self.provider, "app_name", "unknown"),
                    "model": getattr(self.provider, "model_label", "unknown"),
                    "latency_seconds": None,
                    "error": type(exc).__name__,
                }
            )
            state.validator_repairs += 1
            return fallback


def _fallback_for_legal(
    state: GameState,
    player_id: str,
    fallback: AgentDecision,
    legal_actions: list[str],
) -> AgentDecision:
    if fallback.action in legal_actions:
        return fallback
    if "message" in legal_actions:
        if state.hot_seat_target == player_id:
            message = "I reject that case. Point to one concrete public reason before voting me."
            return AgentDecision("message", message=message, speech_act="defense", emotion="focused")
        target = state.hot_seat_target or next((pid for pid in state.alive_players() if pid != player_id), None)
        target_name = state.players[target].display_name if target else "someone"
        return AgentDecision(
            "message",
            target=target,
            message=f"{target_name}, give one concrete reason for your read.",
            speech_act="question",
            emotion="focused",
        )
    return fallback


def _extract_json(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("No JSON object in model output")


def _legal_targets(state: GameState, player_id: str, legal_actions: list[str]) -> list[str]:
    if not legal_actions:
        return []
    if "kill" in legal_actions:
        return [
            pid
            for pid in state.alive_players()
            if pid != player_id and state.players[pid].team != state.players[player_id].team
        ]
    if "check" in legal_actions:
        return [pid for pid in state.alive_players() if pid != player_id]
    if "protect" in legal_actions:
        last_protect = state.players[player_id].private_memory.get("last_protect")
        return [
            pid
            for pid in state.alive_players()
            if pid != last_protect
        ]
    if "vote" in legal_actions or "accuse" in legal_actions:
        return [pid for pid in state.alive_players() if pid != player_id]
    return []


def _repair_target_for_legal(fallback: AgentDecision, legal_targets: list[str]) -> AgentDecision:
    if fallback.action in {"kill", "check", "protect", "vote", "accuse"} and fallback.target not in legal_targets:
        return AgentDecision(
            action=fallback.action,
            target=legal_targets[0] if legal_targets else None,
            message=fallback.message,
            speech_act=fallback.speech_act,
            emotion=fallback.emotion,
            confidence=fallback.confidence,
            private_rationale_summary=fallback.private_rationale_summary,
        )
    return fallback


def _actor_identity(state: GameState, player_id: str) -> dict[str, object]:
    player = state.players[player_id]
    return {
        "player_id": player_id,
        "display_name": player.display_name,
        "seat": player.seat,
        "role": player.role.value,
        "team": player.team.value,
        "persona": player.persona,
    }


def _player_name_map(state: GameState) -> dict[str, str]:
    return {pid: player.display_name for pid, player in state.players.items()}


def _public_evidence_summary(state: GameState) -> dict[str, object]:
    public_votes = [event for event in state.events if event.type == "vote_cast"]
    public_claims = [pid for pid, claim in state.claims.items() if claim.claimed_role is not None]
    accusations = [event for event in state.events if event.type == "accusation_started"]
    dawns = [event for event in state.events if event.type == "dawn_announced"]
    return {
        "day": state.day_number,
        "phase": state.phase.value,
        "vote_count_total": len(public_votes),
        "vote_count_today": sum(1 for event in public_votes if event.day == state.day_number),
        "claim_count_total": len(public_claims),
        "accusation_count_total": len(accusations),
        "night_deaths_announced": [
            str(event.payload.get("message", "")) for event in dawns[-3:]
        ],
    }


def _sanitize_model_message(state: GameState, player_id: str, message: str) -> str:
    cleaned = " ".join(str(message or "").split())
    for pid, player in state.players.items():
        cleaned = re.sub(rf"\b{re.escape(pid)}\b", player.display_name, cleaned, flags=re.IGNORECASE)
    own_name = state.players[player_id].display_name
    cleaned = re.sub(rf"\b{re.escape(own_name)}'s role\b", "my role", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"\b{re.escape(own_name)}'s\b", "my", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(rf"^{re.escape(own_name)}\s*,\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def _uses_unsupported_public_evidence(state: GameState, message: str) -> bool:
    text = message.lower()
    has_votes = any(event.type == "vote_cast" for event in state.events)
    has_claims = any(claim.claimed_role is not None for claim in state.claims.values())
    vote_terms = ("vote pattern", "voting pattern", "last vote", "vote reason", "voted", "your vote", "votes")
    claim_terms = ("claim conflict", "counterclaim", "your claim", "claimed")
    return (
        (not has_votes and any(term in text for term in vote_terms))
        or (not has_claims and any(term in text for term in claim_terms))
    )


def _validate_decision(
    state: GameState,
    player_id: str,
    decision: AgentDecision,
    fallback: AgentDecision,
    legal_actions: list[str],
    legal_targets: list[str],
) -> AgentDecision:
    if decision.action not in legal_actions:
        state.validator_repairs += 1
        return fallback
    if decision.action in {"kill", "check", "protect", "vote", "accuse"} and decision.target not in legal_targets:
        state.validator_repairs += 1
        return fallback
    if decision.action == "message":
        decision.message = _sanitize_model_message(state, player_id, decision.message)
        if _uses_unsupported_public_evidence(state, decision.message):
            state.validator_repairs += 1
            return fallback
        result = validate_message(state, player_id, decision.message, max_words=20)
        if not result.allow:
            state.validator_repairs += 1
            return AgentDecision(
                action="message",
                target=decision.target if decision.target in legal_targets else fallback.target,
                message=result.repaired_message or fallback.message,
                speech_act=decision.speech_act,
                emotion=decision.emotion,
                confidence=decision.confidence,
                private_rationale_summary="model-backed holy_grail decision repaired",
            )
    return decision
