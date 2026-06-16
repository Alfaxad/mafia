from __future__ import annotations

from dataclasses import dataclass, field

from mafia.agents.base import AgentDecision
from mafia.agents.model_backed import ModelBackedHolyGrailAgent
from mafia.agents.moderator_ttt import ModeratorAgent
from mafia.engine.reducers import (
    accuse,
    add_private_moderator_message,
    add_message,
    cast_vote,
    create_game,
    resolve_night,
    start_discussion,
    start_vote,
    submit_night_action,
    update_claim,
)
from mafia.engine.state import GameState, Phase, Role
from mafia.models.provider_types import TextProvider


AgentMode = str


@dataclass
class GameSession:
    state: GameState
    moderator: ModeratorAgent = field(default_factory=ModeratorAgent)
    agent_mode: AgentMode = "Online"
    player_provider: TextProvider | None = None
    moderator_provider: TextProvider | None = None
    human_avatar: str = "player"
    speaker_cursor: int = 0
    agents: dict[str, ModelBackedHolyGrailAgent] = field(default_factory=dict)
    suggestion_cache: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    def agent_for(self, player_id: str) -> ModelBackedHolyGrailAgent:
        if self.player_provider is None:
            raise RuntimeError("Online Mafia sessions require a Modal player provider.")
        if player_id not in self.agents:
            self.agents[player_id] = ModelBackedHolyGrailAgent(player_id, self.player_provider)
        return self.agents[player_id]


def new_session(
    seed: int = 1,
    human_name: str = "You",
    human_role: str | None = None,
    agent_mode: AgentMode = "Online",
) -> GameSession:
    role = Role(human_role) if human_role and human_role != "Random" else None
    state = create_game(seed=seed, human_name=human_name.strip() or "You", human_role=role)
    from mafia.models.modal_client import ModalModelClient

    player_provider = ModalModelClient.mafia_bf16()
    moderator_provider = ModalModelClient.base_moderator_bf16()
    return GameSession(
        state=state,
        moderator=ModeratorAgent(provider=moderator_provider),
        agent_mode="Online",
        player_provider=player_provider,
        moderator_provider=moderator_provider,
    )


def advance_ai(session: GameSession, max_steps: int = 24) -> GameSession:
    state = session.state
    steps = 0
    while state.winner is None and steps < max_steps:
        steps += 1
        human = state.players[state.human_player_id]
        if human.alive and _pending_human_floor(state):
            break
        if state.phase == Phase.NIGHT:
            human_needs_action = human.alive and human.role in {Role.MAFIA, Role.DETECTIVE, Role.DOCTOR}
            for pid in state.alive_players():
                if pid == state.human_player_id:
                    continue
                if state.players[pid].role not in {Role.MAFIA, Role.DETECTIVE, Role.DOCTOR}:
                    continue
                if _night_action_submitted(state, pid):
                    continue
                decision = session.agent_for(pid).decide(state)
                if decision.action in {"kill", "check", "protect"} and decision.target:
                    submit_night_action(state, pid, decision.action, decision.target)
            if human_needs_action and human.role == Role.MAFIA and not _human_night_action_submitted(state):
                _maybe_add_mafia_partner_suggestion(session)
            if human_needs_action and not _human_night_action_submitted(state):
                break
            resolve_night(state)
        elif state.phase == Phase.DAWN:
            start_discussion(state)
        elif state.phase == Phase.DISCUSSION:
            if session.moderator.should_open_vote(state):
                start_vote(state)
                continue
            cued = session.moderator.maybe_cue(state)
            if cued is None:
                start_vote(state)
                continue
            if cued == state.human_player_id and human.alive:
                break
            speakers = [pid for pid in state.alive_players() if pid != state.human_player_id]
            speaker = cued if cued in speakers else _next_ai_speaker(session, speakers)
            if speaker:
                _apply_agent_decision(session, speaker, session.agent_for(speaker).decide(state))
            if state.phase == Phase.DISCUSSION and session.moderator.should_open_vote(state):
                start_vote(state)
        elif state.phase == Phase.HOT_SEAT:
            cued = session.moderator.maybe_cue(state)
            if cued == state.human_player_id and human.alive:
                break
            if state.hot_seat_target != state.human_player_id:
                target = state.hot_seat_target
                if target and state.players[target].alive:
                    _apply_agent_decision(session, target, session.agent_for(target).decide(state))
            if session.moderator.should_open_vote(state):
                start_vote(state)
        elif state.phase == Phase.VOTE:
            session.moderator.maybe_cue(state)
            if human.alive and state.human_player_id not in state.locked_votes:
                break
            for pid in list(state.alive_players()):
                if pid == state.human_player_id or pid in state.locked_votes:
                    continue
                decision = session.agent_for(pid).decide(state)
                if decision.action == "vote" and decision.target:
                    cast_vote(state, pid, decision.target)
        else:
            break
    return session


def _apply_agent_decision(session: GameSession, player_id: str, decision: AgentDecision) -> None:
    state = session.state
    if decision.action == "message":
        add_message(
            state,
            player_id,
            decision.message,
            speech_act=decision.speech_act,
            emotion=decision.emotion,
        )
    elif decision.action == "accuse" and decision.target:
        accuse(state, player_id, decision.target)
    elif decision.action == "claim":
        add_message(state, player_id, decision.message or "I have a role claim to make.", speech_act="claim", emotion="focused")


def _next_ai_speaker(session: GameSession, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    ordered = sorted(candidates, key=lambda pid: session.state.players[pid].seat)
    speaker = ordered[session.speaker_cursor % len(ordered)]
    session.speaker_cursor = (session.speaker_cursor + 1) % max(1, len(ordered))
    return speaker


def human_send_message(session: GameSession, message: str, source: str = "human_typed") -> GameSession:
    add_message(
        session.state,
        session.state.human_player_id,
        message,
        speech_act="statement",
        emotion="focused",
        source=source,
    )
    add_private_moderator_message(
        session.state,
        session.state.human_player_id,
        "Private: message accepted into the table discussion.",
        source="human_message_receipt",
    )
    return session


def human_claim(session: GameSession, role_name: str) -> GameSession:
    role = Role(role_name)
    update_claim(session.state, session.state.human_player_id, role, quote=f"I am the {role.value}.")
    add_message(
        session.state,
        session.state.human_player_id,
        f"I am the {role.value}.",
        speech_act="claim",
        emotion="steady",
    )
    return session


def human_accuse(session: GameSession, target: str) -> GameSession:
    accuse(session.state, session.state.human_player_id, target)
    return session


def human_start_vote(session: GameSession) -> GameSession:
    start_vote(session.state)
    return session


def human_vote(session: GameSession, target: str) -> GameSession:
    cast_vote(session.state, session.state.human_player_id, target)
    return session


def human_night_action(session: GameSession, target: str) -> GameSession:
    state = session.state
    human = state.players[state.human_player_id]
    action = {
        Role.MAFIA: "kill",
        Role.DETECTIVE: "check",
        Role.DOCTOR: "protect",
    }.get(human.role)
    if action:
        accepted = submit_night_action(state, human.player_id, action, target)
        if accepted and human.role == Role.MAFIA:
            for pid in state.mafia_alive():
                state.night_actions.mafia_votes[pid] = target
            add_private_moderator_message(
                state,
                human.player_id,
                f"Private: Mafia night target set to {state.players[target].display_name}.",
                source="mafia_team_kill_confirmed",
            )
    return advance_ai(session, max_steps=4)


def human_pass_floor(session: GameSession) -> GameSession:
    state = session.state
    human_id = state.human_player_id
    if state.players[human_id].alive and state.phase in {Phase.DISCUSSION, Phase.HOT_SEAT, Phase.VOTE}:
        state.append_event(
            "floor_passed",
            actor=human_id,
            payload={"source": "human_waited"},
        )
        add_private_moderator_message(
            state,
            human_id,
            "Private: you waited. The moderator is moving the floor.",
            source="human_floor_pass",
        )
    return advance_ai(session, max_steps=1)


def _human_night_action_submitted(state: GameState) -> bool:
    pid = state.human_player_id
    return _night_action_submitted(state, pid)


def _night_action_submitted(state: GameState, pid: str) -> bool:
    return (
        pid in state.night_actions.mafia_votes
        or pid in state.night_actions.detective_checks
        or pid in state.night_actions.doctor_protects
    )


def _pending_human_floor(state: GameState) -> bool:
    human_id = state.human_player_id
    last_cue_index = None
    for index in range(len(state.events) - 1, -1, -1):
        event = state.events[index]
        if event.type == "player_message" and event.actor == human_id and event.phase == state.phase:
            return False
        if event.type == "floor_passed" and event.actor == human_id and event.phase == state.phase:
            return False
        if (
            event.type == "moderator_cue"
            and event.phase == state.phase
            and event.payload.get("target") == human_id
        ):
            last_cue_index = index
            break
    return last_cue_index is not None


def human_floor_pending(state: GameState) -> bool:
    return _pending_human_floor(state)


def _maybe_add_mafia_partner_suggestion(session: GameSession) -> None:
    state = session.state
    human_id = state.human_player_id
    if state.players[human_id].role != Role.MAFIA:
        return
    target = next(
        (
            vote
            for actor, vote in state.night_actions.mafia_votes.items()
            if actor != human_id and vote in state.players
        ),
        None,
    )
    if not target:
        target = _fallback_mafia_target(state, human_id)
        partner = next(
            (
                pid
                for pid in state.mafia_alive()
                if pid != human_id and pid not in state.night_actions.mafia_votes
            ),
            None,
        )
        if partner and target:
            submit_night_action(state, partner, "kill", target)
        if not target:
            return
    already_sent = any(
        event.type == "private_moderator_cue"
        and event.day == state.day_number
        and event.payload.get("recipient") == human_id
        and event.payload.get("source") == "mafia_partner_suggestion"
        for event in state.events
    )
    if already_sent:
        return
    add_private_moderator_message(
        state,
        human_id,
        f"Private: your Mafia partner proposes eliminating {state.players[target].display_name}. Choose that target to agree, or choose another.",
        source="mafia_partner_suggestion",
    )


def _fallback_mafia_target(state: GameState, human_id: str) -> str | None:
    candidates = [
        pid
        for pid in state.alive_players()
        if pid != human_id and state.players[pid].role != Role.MAFIA
    ]
    if not candidates:
        return None

    # Prefer role claims and visible vote pressure, then fall back to seat order.
    vote_counts = {
        pid: sum(1 for target in state.votes.values() if target == pid)
        for pid in candidates
    }
    claim_weight = {
        pid: 1 if state.claims.get(pid) and state.claims[pid].claimed_role else 0
        for pid in candidates
    }
    return sorted(
        candidates,
        key=lambda pid: (-claim_weight[pid], -vote_counts[pid], state.players[pid].seat),
    )[0]
