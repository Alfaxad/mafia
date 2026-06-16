from __future__ import annotations

from collections import Counter

from mafia.agents.base import AgentDecision
from mafia.agents.validators import validate_message
from mafia.engine.state import GameState, Phase, Role, Team


class HolyGrailAgent:
    """Role-adaptive Mafia policy used as the product `holy_grail` architecture."""

    def __init__(self, player_id: str, architecture: str = "holy_grail"):
        self.player_id = player_id
        self.architecture = "holy_grail" if architecture in {"holy_grail", "holy_grail_v4"} else architecture

    def decide(self, state: GameState) -> AgentDecision:
        player = state.players[self.player_id]
        if not player.alive:
            return AgentDecision(action="none")
        if state.phase == Phase.NIGHT:
            return self._night_decision(state)
        if state.phase == Phase.DISCUSSION:
            return self._discussion_decision(state)
        if state.phase == Phase.HOT_SEAT:
            return self._hot_seat_decision(state)
        if state.phase == Phase.VOTE:
            return self._vote_decision(state)
        return AgentDecision(action="none")

    def _night_decision(self, state: GameState) -> AgentDecision:
        player = state.players[self.player_id]
        alive = [pid for pid in state.alive_players() if pid != self.player_id]
        if player.role == Role.MAFIA:
            targets = [pid for pid in alive if state.players[pid].team == Team.TOWN]
            target = _power_role_claim_target(state, targets) or _lowest_suspicion_target(state, targets)
            return AgentDecision("kill", target=target, confidence=0.74, private_rationale_summary="remove town information value")
        if player.role == Role.DETECTIVE:
            unknown = [
                pid
                for pid in alive
                if pid not in player.private_memory.get("investigations", {})
            ]
            target = _most_suspicious_target(state, unknown or alive)
            return AgentDecision("check", target=target, confidence=0.72, private_rationale_summary="inspect highest pressure target")
        if player.role == Role.DOCTOR:
            last_protect = player.private_memory.get("last_protect")
            protectable = [pid for pid in state.alive_players() if pid != last_protect]
            target = _public_power_claim(state, protectable) or _least_suspicious_townish(state, protectable)
            return AgentDecision("protect", target=target, confidence=0.68, private_rationale_summary="protect public information value")
        return AgentDecision("sleep")

    def _discussion_decision(self, state: GameState) -> AgentDecision:
        player = state.players[self.player_id]
        if player.role == Role.DETECTIVE:
            checks = player.private_memory.get("investigations", {})
            mafia_hits = [pid for pid, is_mafia in checks.items() if is_mafia and state.players[pid].alive]
            if mafia_hits:
                target = mafia_hits[0]
                msg = f"I checked {state.players[target].display_name}; they are Mafia."
                return self._message(state, msg, "evidence", "pressing", target)
        target = _most_suspicious_target(
            state,
            [pid for pid in state.alive_players() if pid != self.player_id],
            actor=self.player_id,
        )
        if not target:
            return AgentDecision("none")
        msg = self._role_message(state, target)
        return self._message(state, msg, "accusation", "pressing", target)

    def _hot_seat_decision(self, state: GameState) -> AgentDecision:
        player = state.players[self.player_id]
        target = state.hot_seat_target
        if target == self.player_id:
            if player.role == Role.MAFIA:
                msg = "That case is too convenient. Name the contradiction, not just the suspicion."
            elif player.role == Role.DETECTIVE:
                if _has_public_claims(state):
                    msg = "My read has been consistent. Do not lock a vote without comparing claims."
                else:
                    msg = "My read has been consistent. Compare public messages before locking a vote."
            elif player.role == Role.DOCTOR:
                msg = "I am not the right elimination. Look at who pushed without evidence."
            else:
                msg = "I am town. My pressure has been based on public contradictions."
            return self._message(state, msg, "defense", "focused", self.player_id)
        if target:
            name = state.players[target].display_name
            if player.role == Role.MAFIA and state.players[target].role == Role.MAFIA:
                msg = f"{name} should answer, but this feels like a rushed wagon."
                return self._message(state, msg, "defense", "guarded", target)
            if _has_public_votes(state):
                msg = f"{name}, give one concrete reason your votes help town."
            else:
                msg = f"{name}, give one concrete reason your read helps town."
            return self._message(state, msg, "question", "pressing", target)
        return self._discussion_decision(state)

    def _vote_decision(self, state: GameState) -> AgentDecision:
        candidates = [pid for pid in state.alive_players() if pid != self.player_id]
        if state.hot_seat_target and state.hot_seat_target in candidates:
            target = state.hot_seat_target
        else:
            target = _most_suspicious_target(state, candidates, actor=self.player_id)
        return AgentDecision("vote", target=target, confidence=0.71, private_rationale_summary="close vote on best public target")

    def _message(
        self,
        state: GameState,
        message: str,
        speech_act: str,
        emotion: str,
        target: str | None,
    ) -> AgentDecision:
        result = validate_message(state, self.player_id, message, max_words=20)
        if not result.allow:
            state.validator_repairs += 1
            message = result.repaired_message or "That does not line up."
        return AgentDecision(
            "message",
            target=target,
            message=message,
            speech_act=speech_act,
            emotion=emotion,
            confidence=0.67,
            private_rationale_summary="public pressure based on ledger",
        )

    def _role_message(self, state: GameState, target: str) -> str:
        player = state.players[self.player_id]
        name = state.players[target].display_name
        if not _has_spoken_today(state, target):
            return f"{name}, give one clear read from the dawn result."
        if player.role == Role.MAFIA:
            if _has_public_votes(state):
                return f"{name}'s vote pattern is too convenient."
            return f"{name}'s read is too vague about who looks Mafia."
        if player.role == Role.DOCTOR:
            if _has_public_votes(state):
                return f"{name}, explain your vote before we lock."
            return f"{name}, give one grounded read from today's discussion."
        if player.role == Role.VILLAGER:
            if _has_public_claims(state):
                return f"{name} is avoiding the main claim conflict."
            return f"{name}'s read needs one concrete reason."
        return f"{name} is my strongest suspect."


def _has_public_votes(state: GameState) -> bool:
    return any(event.type == "vote_cast" for event in state.events)


def _has_public_claims(state: GameState) -> bool:
    return any(claim.claimed_role is not None for claim in state.claims.values()) or any(
        event.type == "claim_updated" for event in state.events
    )


def _has_spoken_today(state: GameState, player_id: str) -> bool:
    return any(
        event.day == state.day_number
        and event.type == "player_message"
        and event.actor == player_id
        for event in state.events
    )


def _public_power_claim(state: GameState, candidates: list[str] | None = None) -> str | None:
    allowed = set(candidates) if candidates is not None else None
    for pid, claim in state.claims.items():
        if allowed is not None and pid not in allowed:
            continue
        if state.players[pid].alive and claim.claimed_role in {Role.DETECTIVE, Role.DOCTOR}:
            return pid
    return None


def _power_role_claim_target(state: GameState, candidates: list[str]) -> str | None:
    for pid in candidates:
        if state.claims[pid].claimed_role in {Role.DETECTIVE, Role.DOCTOR}:
            return pid
    return None


def _most_suspicious_target(
    state: GameState,
    candidates: list[str],
    actor: str | None = None,
) -> str | None:
    if not candidates:
        return None
    pressure = Counter()
    for event in state.events:
        if event.type == "vote_cast":
            pressure[event.payload.get("target")] += 2
        if event.type == "player_message":
            text = str(event.payload.get("message", "")).lower()
            for pid in candidates:
                name = state.players[pid].display_name.lower()
                if name in text and any(word in text for word in ("mafia", "sus", "suspicious", "contradiction")):
                    pressure[pid] += 1
    if not any(pressure[pid] for pid in candidates):
        return _cyclic_nonhuman_target(state, candidates, actor)
    return sorted(candidates, key=lambda pid: (-pressure[pid], state.players[pid].seat))[0]


def _lowest_suspicion_target(state: GameState, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    if state.day_number == 1 and len(candidates) > 1:
        without_human = [pid for pid in candidates if pid != state.human_player_id]
        if without_human:
            candidates = without_human
    pressure = Counter(event.payload.get("target") for event in state.events if event.type == "vote_cast")
    return sorted(candidates, key=lambda pid: (pressure[pid], state.players[pid].seat))[0]


def _least_suspicious_townish(state: GameState, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    pressure = Counter(event.payload.get("target") for event in state.events if event.type == "vote_cast")
    return sorted(candidates, key=lambda pid: (pressure[pid], state.players[pid].seat))[0]


def _cyclic_nonhuman_target(state: GameState, candidates: list[str], actor: str | None) -> str | None:
    pool = candidates
    if len(pool) > 1:
        nonhuman = [pid for pid in pool if pid != state.human_player_id]
        if nonhuman:
            pool = nonhuman
    if actor and actor in state.players:
        actor_seat = state.players[actor].seat
        after_actor = [pid for pid in pool if state.players[pid].seat > actor_seat]
        if after_actor:
            return sorted(after_actor, key=lambda pid: state.players[pid].seat)[0]
    return sorted(pool, key=lambda pid: state.players[pid].seat)[0] if pool else None
