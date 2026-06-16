from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from mafia.agents.validators import validate_message
from mafia.engine.reducers import add_message
from mafia.engine.state import GameState, Phase, Role
from mafia.engine.views import private_view
from mafia.models.provider_types import TextProvider


@dataclass(slots=True)
class ModeratorMetrics:
    scheduler_calls: int = 0
    generator_calls: int = 0
    send_count: int = 0
    wait_count: int = 0
    repairs: int = 0


class ModeratorAgent:
    """Time-to-Talk style non-player moderator.

    The moderator has two separate jobs:
    - public floor control: scheduler chooses send/wait, generator gives one
      living player a neutral cue;
    - private human assistance: spoiler-safe message options the player may
      approve or ignore.
    """

    def __init__(
        self,
        model_name: str = "base-gemma-4-12b-bf16",
        max_words: int = 18,
        provider: TextProvider | None = None,
    ):
        self.model_name = model_name
        self.max_words = max_words
        self.provider = provider
        self.metrics = ModeratorMetrics()

    def maybe_cue(self, state: GameState) -> str | None:
        if state.phase not in {Phase.DISCUSSION, Phase.HOT_SEAT, Phase.VOTE}:
            self.metrics.wait_count += 1
            return None

        eligible = self._eligible_floor_targets(state)
        if not eligible:
            self.metrics.wait_count += 1
            return None

        floor = role_aware_floor(state)
        decision = self.schedule(state, floor, eligible)
        if decision == "wait" and _day_discussion_count(state) >= floor:
            self.metrics.wait_count += 1
            return None

        target, cue, message_type = self.generate_cue(
            state,
            floor,
            eligible,
            forced=decision == "wait",
        )
        result = validate_message(state, "moderator", cue, max_words=self.max_words)
        if not result.allow:
            self.metrics.repairs += 1
            state.validator_repairs += 1
            cue = result.repaired_message or f"{state.players[target].display_name}, give one concrete reason."

        state.moderator_turns += 1
        self.metrics.send_count += 1
        added = add_message(
            state,
            "moderator",
            cue,
            speech_act="floor_cue",
            emotion="neutral",
            source="ttt",
            metadata={"target": target, "message_type": message_type, "private": False},
        )
        return target if added else None

    def schedule(self, state: GameState, floor: int, eligible: list[str]) -> str:
        self.metrics.scheduler_calls += 1
        fallback = self._fallback_schedule(state, floor)
        if self.provider is None:
            return fallback

        prompt = json.dumps(
            {
                "task": "You are the non-player Moderator/Narrator Time-to-Talk scheduler. Return only <send> or <wait>.",
                "rules": [
                    "Choose <send> when useful public discussion is sparse or a player needs the floor.",
                    "Choose <wait> when the floor has been met and further talk is repetitive or low-value.",
                    "Never reveal hidden roles or private night actions.",
                ],
                "phase": state.phase.value,
                "day": state.day_number,
                "discussion_count_today": _day_discussion_count(state),
                "floor": floor,
                "eligible": [_player_label(state, pid) for pid in eligible],
                "message_rate": _message_rate_report(state),
                "recent_public_transcript": _recent_public_transcript(state, 10),
                "fallback": fallback,
            },
            ensure_ascii=False,
        )
        try:
            result = self.provider.generate(prompt, max_tokens=16, temperature=1.0, top_p=0.95, top_k=64)
            state.model_calls.append(_model_call_row("moderator_scheduler", result))
            text = result.text.strip().lower()
            if "<wait>" in text or re.search(r"\b(wait|stop|vote)\b", text):
                return "wait"
            if "<send>" in text or re.search(r"\b(send|speak|intervene)\b", text):
                return "send"
            self.metrics.repairs += 1
            state.validator_repairs += 1
        except Exception as exc:
            state.model_calls.append(_model_error_row("moderator_scheduler", self.provider, self.model_name, exc))
            self.metrics.repairs += 1
            state.validator_repairs += 1
        return fallback

    def generate_cue(
        self,
        state: GameState,
        floor: int,
        eligible: list[str],
        forced: bool = False,
    ) -> tuple[str, str, str]:
        self.metrics.generator_calls += 1
        fallback_target = _least_spoken_player(state, eligible)
        fallback_cue = self._fallback_cue(state, fallback_target)
        if self.provider is None:
            return fallback_target, fallback_cue, "pressure"

        prompt = json.dumps(
            {
                "task": "You are the non-player Mafia Moderator/Narrator generator. Generate one neutral public floor-control cue.",
                "constraints": [
                    "Do not reveal hidden roles or private night actions.",
                    f"Use at most {self.max_words} words.",
                    "Pick exactly one eligible living player.",
                    "The cue must start with the selected player's display name followed by a comma.",
                    "Ask for one concrete read, contradiction, defense, claim check, or hesitation.",
                    "Ask for vote reasons only if public_evidence.vote_count_total is above 0.",
                    "Ask for claim conflicts only if public_evidence.claim_count_total is above 0.",
                    "Return JSON only as {\"target\":\"player id or display name\",\"message_type\":\"evidence|claim_check|pressure|defense|vote_coordination\",\"cue\":\"...\"}.",
                ],
                "phase": state.phase.value,
                "day": state.day_number,
                "discussion_count_today": _day_discussion_count(state),
                "floor": floor,
                "forced": forced,
                "eligible": [_player_label(state, pid) for pid in eligible],
                "message_rate": _message_rate_report(state),
                "public_evidence": _public_evidence_summary(state),
                "recent_public_transcript": _recent_public_transcript(state, 10),
                "fallback": {"target": fallback_target, "cue": fallback_cue},
            },
            ensure_ascii=False,
        )
        try:
            result = self.provider.generate(prompt, max_tokens=96, temperature=1.0, top_p=0.95, top_k=64)
            state.model_calls.append(_model_call_row("moderator_generator", result))
            data = json.loads(_extract_json(result.text))
            target = _parse_target(state, str(data.get("target", "")), eligible) or fallback_target
            cue = " ".join(str(data.get("cue", "")).strip().split())
            message_type = str(data.get("message_type", "pressure")).strip()
            if cue:
                if not cue.startswith(f"{state.players[target].display_name},"):
                    cue = f"{state.players[target].display_name}, {cue}"
                if message_type not in {"evidence", "claim_check", "pressure", "defense", "vote_coordination"}:
                    message_type = "pressure"
                if _cue_uses_unsupported_public_evidence(state, cue):
                    self.metrics.repairs += 1
                    state.validator_repairs += 1
                    return fallback_target, fallback_cue, "pressure"
                return target, cue, message_type
            self.metrics.repairs += 1
            state.validator_repairs += 1
        except Exception as exc:
            state.model_calls.append(_model_error_row("moderator_generator", self.provider, self.model_name, exc))
            self.metrics.repairs += 1
            state.validator_repairs += 1
        return fallback_target, fallback_cue, "pressure"

    def should_open_vote(self, state: GameState) -> bool:
        if state.phase == Phase.HOT_SEAT and state.hot_seat_target:
            return any(
                event.type == "player_message"
                and event.actor == state.hot_seat_target
                and event.phase == Phase.HOT_SEAT
                for event in state.events
            )
        if state.phase != Phase.DISCUSSION:
            return False
        floor = role_aware_floor(state)
        if _day_discussion_count(state) < floor + 2:
            return False
        recent_claim_or_accusation = any(
            event.day == state.day_number and event.type in {"claim_updated", "accusation_started", "vote_cast"}
            for event in state.events
        )
        return recent_claim_or_accusation or _day_discussion_count(state) >= floor + 4

    def human_suggestions(
        self,
        state: GameState,
        viewer_id: str,
        target_id: str | None = None,
    ) -> list[dict[str, str]]:
        """Private, spoiler-safe message assists from the moderator.

        The options deliberately mix useful, risky, and neutral lines. The UI
        does not label them as correct or incorrect; the player still has to
        read the table and choose what to say.
        """

        if viewer_id not in state.players or not state.players[viewer_id].alive:
            return []
        target = target_id if target_id in state.players else _quietest_alive_player(state)
        if target == viewer_id:
            target = _quietest_alive_player(state)

        fallback = self._fallback_human_suggestions(state, viewer_id, target)
        if self.provider is None or state.phase not in {Phase.DISCUSSION, Phase.HOT_SEAT, Phase.VOTE}:
            return fallback

        player = state.players[viewer_id]
        prompt = json.dumps(
            {
                "task": "Generate private, spoiler-safe clickable Mafia table messages for the human player.",
                "rules": [
                    "Use the human player's private_view only; never reveal hidden roles beyond their private info.",
                    "Suggestions must reflect current phase, role, claims, votes, hot seat, and recent discussion.",
                    "Mix strong, cautious, and risky-but-legal options. Do not label them as correct.",
                    "Return JSON only as {\"suggestions\":[{\"id\":\"...\",\"intent\":\"ask|pressure|defend|claim|reveal|vote_reason|deflect\",\"tone\":\"...\",\"message\":\"...\"}]}",
                    "Messages are public if approved, so keep each under 28 words.",
                ],
                "phase": state.phase.value,
                "day": state.day_number,
                "human": {
                    "id": viewer_id,
                    "name": player.display_name,
                    "role": player.role.value,
                    "alive": player.alive,
                },
                "target": _player_label(state, target),
                "private_view": private_view(state, viewer_id),
                "recent_public_transcript": _recent_public_transcript(state, 12),
                "fallback": fallback,
            },
            ensure_ascii=False,
        )
        try:
            result = self.provider.generate(prompt, max_tokens=320, temperature=1.0, top_p=0.95, top_k=64)
            state.model_calls.append(_model_call_row("moderator_private_suggestions", result))
            data = json.loads(_extract_json(result.text))
            suggestions = [
                _normalize_suggestion(item, index)
                for index, item in enumerate(data.get("suggestions", []))
                if isinstance(item, dict)
            ]
            cleaned = [item for item in suggestions if item["message"]]
            if cleaned:
                return cleaned[:5]
            self.metrics.repairs += 1
            state.validator_repairs += 1
        except Exception as exc:
            state.model_calls.append(_model_error_row("moderator_private_suggestions", self.provider, self.model_name, exc))
            self.metrics.repairs += 1
            state.validator_repairs += 1
        return fallback

    def _fallback_human_suggestions(self, state: GameState, viewer_id: str, target: str) -> list[dict[str, str]]:
        target = _fallback_target_for_human(state, viewer_id, target)
        target_name = state.players[target].display_name
        player = state.players[viewer_id]
        hot_seat = state.hot_seat_target
        hot_seat_name = state.players[hot_seat].display_name if hot_seat in state.players else target_name
        has_votes = _has_public_votes(state)
        has_claims = _has_public_claims(state)
        suggestions: list[dict[str, str]] = [
            {
                "id": f"ask-trust-d{state.day_number}-{target}",
                "intent": "ask",
                "tone": "calm",
                "message": f"{target_name}, who do you trust most right now?",
            },
            {
                "id": f"pressure-reason-d{state.day_number}-{target}",
                "intent": "pressure",
                "tone": "suspicious",
                "message": f"{target_name}, give one concrete reason from public discussion.",
            },
            {
                "id": f"defend-wait-d{state.day_number}-{target}",
                "intent": "defend",
                "tone": "measured",
                "message": f"I want to hear {target_name} before the table locks in.",
            },
            {
                "id": f"risky-pressure-d{state.day_number}-{target}",
                "intent": "pressure",
                "tone": "bluffing",
                "message": f"I think {target_name} is not giving a concrete reason.",
            },
        ]
        if has_votes:
            suggestions.insert(
                0,
                {
                    "id": f"ask-vote-d{state.day_number}-{target}",
                    "intent": "ask",
                    "tone": "direct",
                    "message": f"{target_name}, explain your last vote in one concrete reason.",
                },
            )
        if has_votes and has_claims:
            suggestions.insert(
                0,
                {
                    "id": f"pressure-claim-d{state.day_number}-{target}",
                    "intent": "pressure",
                    "tone": "suspicious",
                    "message": f"{target_name}, your claim needs to match your votes.",
                },
            )
        if hot_seat and state.phase == Phase.HOT_SEAT:
            suggestions.insert(
                0,
                {
                    "id": f"hot-seat-question-d{state.day_number}-{hot_seat}",
                    "intent": "ask",
                    "tone": "pressing",
                    "message": f"{hot_seat_name}, answer the accusation with one concrete contradiction.",
                },
            )
        investigations = player.private_memory.get("investigations", {})
        if target in investigations:
            result = "Mafia" if investigations[target] else "not Mafia"
            suggestions.insert(
                0,
                {
                    "id": f"detective-result-d{state.day_number}-{target}",
                    "intent": "reveal",
                    "tone": "decisive",
                    "message": f"I checked {target_name}. They are {result}.",
                },
            )
        if player.role == Role.DETECTIVE:
            mafia_hits = [
                pid for pid, is_mafia in investigations.items() if is_mafia and state.players.get(pid) and state.players[pid].alive
            ]
            checked_good = [
                pid for pid, is_mafia in investigations.items() if not is_mafia and state.players.get(pid) and state.players[pid].alive
            ]
            if mafia_hits:
                hit = mafia_hits[0]
                suggestions.insert(
                    0,
                    {
                        "id": f"detective-mafia-hit-d{state.day_number}-{hit}",
                        "intent": "reveal",
                        "tone": "decisive",
                        "message": f"I checked {state.players[hit].display_name}. They are Mafia.",
                    },
                )
            if checked_good and state.phase == Phase.VOTE:
                good = checked_good[0]
                suggestions.insert(
                    0,
                    {
                        "id": f"detective-protect-good-d{state.day_number}-{good}",
                        "intent": "vote_reason",
                        "tone": "urgent",
                        "message": f"Do not vote {state.players[good].display_name}; I have a reason to trust them.",
                    },
                )
        if state.phase == Phase.HOT_SEAT and state.hot_seat_target == viewer_id:
            suggestions.insert(
                0,
                {
                    "id": f"hot-seat-defense-d{state.day_number}",
                    "intent": "defend",
                    "tone": "firm",
                    "message": "That case skips evidence. Ask me about one specific public message.",
                },
            )
        if state.phase == Phase.VOTE:
            suggestions.insert(
                0,
                {
                    "id": f"vote-reason-d{state.day_number}-{target}",
                    "intent": "vote_reason",
                    "tone": "measured",
                    "message": f"My vote should follow evidence, not momentum. I need one reason against {target_name}.",
                },
            )
        if player.role == Role.MAFIA:
            teammate = next(
                (
                    pid
                    for pid, other in state.players.items()
                    if pid != viewer_id and other.role == Role.MAFIA and other.alive
                ),
                None,
            )
            suggestions.append(
                {
                    "id": f"mafia-soft-deflect-d{state.day_number}-{target}",
                    "intent": "deflect",
                    "tone": "guarded",
                    "message": f"{target_name} may be town, but their timing is not clean.",
                }
            )
            if teammate and state.phase in {Phase.DISCUSSION, Phase.HOT_SEAT}:
                suggestions.insert(
                    0,
                    {
                        "id": f"mafia-partner-distance-d{state.day_number}-{teammate}",
                        "intent": "deflect",
                        "tone": "controlled",
                        "message": f"I want {state.players[teammate].display_name} to answer too, but this wagon feels too easy.",
                    },
                )
        if player.role == Role.DOCTOR:
            suggestions.insert(
                0,
                {
                    "id": f"doctor-low-exposure-d{state.day_number}-{target}",
                    "intent": "ask",
                    "tone": "careful",
                    "message": f"Before roles come out, compare who pushed {target_name} and who avoided giving reasons.",
                },
            )
        return suggestions[:6]

    def _fallback_schedule(self, state: GameState, floor: int) -> str:
        if state.phase == Phase.HOT_SEAT and state.hot_seat_target:
            return "send"
        if state.phase == Phase.VOTE:
            return "send" if any(pid not in state.locked_votes for pid in state.alive_players()) else "wait"
        return "send" if _day_discussion_count(state) < floor else "wait"

    def _fallback_cue(self, state: GameState, target: str | None = None) -> str:
        target = target or _quietest_alive_player(state)
        target_name = state.players[target].display_name
        if state.phase == Phase.HOT_SEAT and state.hot_seat_target:
            return f"{target_name}, answer the accusation with one concrete reason."
        if state.phase == Phase.VOTE:
            unlocked = [pid for pid in state.alive_players() if pid not in state.locked_votes]
            if unlocked:
                unlocked_name = state.players[unlocked[0]].display_name
                return f"{unlocked_name}, lock a vote or state your hesitation."
            return "Votes are locked. Resolving the table now."
        return f"{target_name}, give one read with evidence."

    def _eligible_floor_targets(self, state: GameState) -> list[str]:
        alive = state.alive_players()
        if state.phase == Phase.HOT_SEAT and state.hot_seat_target in alive:
            return [state.hot_seat_target]
        if state.phase == Phase.VOTE:
            return [pid for pid in alive if pid not in state.locked_votes]
        counts = _speaker_counts_today(state)
        last_speaker = next(
            (event.actor for event in reversed(state.events) if event.type == "player_message" and event.actor in alive),
            None,
        )
        eligible = [pid for pid in alive if counts[pid] < 2 and (pid != last_speaker or len(alive) == 1)]
        return eligible or alive


def _quietest_alive_player(state: GameState) -> str:
    counts = {pid: 0 for pid in state.alive_players()}
    for event in state.events:
        if event.type == "player_message" and event.actor in counts:
            counts[event.actor] += 1
    return sorted(counts, key=lambda pid: (counts[pid], state.players[pid].seat))[0]


def _fallback_target_for_human(state: GameState, viewer_id: str, current: str) -> str:
    alive = [pid for pid in state.alive_players() if pid != viewer_id]
    if not alive:
        return viewer_id
    if state.hot_seat_target in alive:
        return str(state.hot_seat_target)
    vote_counts = Counter(state.votes.values())
    pressured = [pid for pid in alive if vote_counts.get(pid, 0) > 0]
    if pressured:
        return sorted(pressured, key=lambda pid: (-vote_counts[pid], state.players[pid].seat))[0]
    player = state.players[viewer_id]
    investigations = player.private_memory.get("investigations", {})
    for pid, is_mafia in investigations.items():
        if is_mafia and pid in alive:
            return pid
    if current in alive:
        return current
    return _quietest_alive_player(state)


def _least_spoken_player(state: GameState, eligible: list[str]) -> str:
    counts = _speaker_counts_today(state)
    return sorted(eligible, key=lambda pid: (counts[pid], state.players[pid].seat))[0]


def role_aware_floor(state: GameState) -> int:
    alive_count = len(state.alive_players())
    return min(4, max(2, alive_count // 2 + 1))


def _day_discussion_count(state: GameState) -> int:
    return sum(
        1
        for event in state.events
        if event.day == state.day_number and event.type == "player_message"
    )


def _speaker_counts_today(state: GameState) -> Counter[str]:
    counts: Counter[str] = Counter({pid: 0 for pid in state.alive_players()})
    for event in state.events:
        if event.day == state.day_number and event.type == "player_message" and event.actor in counts:
            counts[str(event.actor)] += 1
    return counts


def _message_rate_report(state: GameState) -> list[dict[str, int | str]]:
    counts = _speaker_counts_today(state)
    return [
        {"id": pid, "name": state.players[pid].display_name, "messages_today": counts[pid]}
        for pid in state.alive_players()
    ]


def _public_evidence_summary(state: GameState) -> dict[str, object]:
    public_votes = [event for event in state.events if event.type == "vote_cast"]
    public_claims = [pid for pid, claim in state.claims.items() if claim.claimed_role is not None]
    accusations = [event for event in state.events if event.type == "accusation_started"]
    return {
        "day": state.day_number,
        "phase": state.phase.value,
        "vote_count_total": len(public_votes),
        "vote_count_today": sum(1 for event in public_votes if event.day == state.day_number),
        "claim_count_total": len(public_claims),
        "accusation_count_total": len(accusations),
    }


def _has_public_votes(state: GameState) -> bool:
    return any(event.type == "vote_cast" for event in state.events)


def _has_public_claims(state: GameState) -> bool:
    return any(claim.claimed_role is not None for claim in state.claims.values())


def _cue_uses_unsupported_public_evidence(state: GameState, cue: str) -> bool:
    text = cue.lower()
    has_votes = _has_public_votes(state)
    has_claims = _has_public_claims(state)
    vote_terms = ("vote pattern", "voting pattern", "last vote", "voted for", "your votes", "vote reason")
    claim_terms = ("claim conflict", "counterclaim", "your claim", "claimed")
    return (
        (not has_votes and any(term in text for term in vote_terms))
        or (not has_claims and any(term in text for term in claim_terms))
    )


def _recent_public_transcript(state: GameState, limit: int = 10) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in state.events:
        if event.type not in {"player_message", "moderator_cue", "claim_updated", "accusation_started", "vote_cast"}:
            continue
        actor = event.actor
        message = event.payload.get("message") or event.payload.get("quote")
        if event.type in {"vote_cast", "accusation_started"}:
            target = str(event.payload.get("target", ""))
            target_name = state.players[target].display_name if target in state.players else target
            verb = "voted for" if event.type == "vote_cast" else "accused"
            message = f"{verb} {target_name}"
        rows.append(
            {
                "seq": event.seq,
                "day": event.day,
                "phase": event.phase.value,
                "speaker": "Moderator" if actor == "moderator" else state.players[actor].display_name if actor in state.players else actor,
                "type": event.type,
                "message": message,
            }
        )
    return rows[-limit:]


def _player_label(state: GameState, player_id: str) -> dict[str, str | int]:
    player = state.players[player_id]
    return {"id": player_id, "name": player.display_name, "seat": player.seat}


def _parse_target(state: GameState, raw: str, eligible: list[str]) -> str | None:
    value = raw.strip().lower()
    for pid in eligible:
        player = state.players[pid]
        if value in {pid.lower(), player.display_name.lower(), str(player.seat)}:
            return pid
    for pid in eligible:
        if re.search(rf"\b{re.escape(state.players[pid].display_name)}\b", raw, flags=re.I):
            return pid
    return None


def _normalize_suggestion(item: dict, index: int) -> dict[str, str]:
    intent = str(item.get("intent", "ask")).strip().lower()[:32] or "ask"
    tone = str(item.get("tone", "private")).strip().lower()[:32] or "private"
    message = " ".join(str(item.get("message", "")).strip().split())
    return {
        "id": str(item.get("id") or f"moderator-private-{index}")[:64],
        "intent": intent,
        "tone": tone,
        "message": message,
    }


def _model_call_row(player_id: str, result: Any) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "provider": result.backend,
        "model": result.model,
        "latency_seconds": result.latency_seconds,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }


def _model_error_row(player_id: str, provider: TextProvider, model_name: str, exc: Exception) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "provider": getattr(provider, "app_name", "unknown"),
        "model": getattr(provider, "model_label", model_name),
        "latency_seconds": None,
        "error": type(exc).__name__,
    }


def _extract_json(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("No JSON object in moderator output")
