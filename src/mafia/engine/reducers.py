from __future__ import annotations

import random
import uuid
from collections import Counter
from copy import deepcopy
from typing import Iterable

from mafia.engine.state import (
    DEFAULT_NAMES,
    ROLE_LIST,
    ClaimState,
    GameState,
    Phase,
    PlayerState,
    Role,
    Team,
)


def normalize_architecture(name: str) -> str:
    normalized = name.strip().lower().replace("-", "_")
    aliases = {
        "holy_grail_v4": "holy_grail",
        "holygrail_v4": "holy_grail",
        "hgv4": "holy_grail",
        "hidden_role_objective_ledgering_v4": "holy_grail",
    }
    return aliases.get(normalized, normalized)


def create_game(
    seed: int = 1,
    human_name: str = "You",
    human_role: Role | None = None,
    names: Iterable[str] = DEFAULT_NAMES,
) -> GameState:
    rng = random.Random(seed)
    names_list = list(names)
    if len(names_list) != 7:
        raise ValueError("Classic AI-native Mafia requires exactly seven seats.")
    if names_list[0] != human_name:
        names_list[0] = human_name

    roles = list(ROLE_LIST)
    rng.shuffle(roles)
    if human_role is not None:
        if human_role not in roles:
            raise ValueError(f"Human role {human_role} is not in the role deck.")
        human_idx = roles.index(human_role)
        roles[human_idx], roles[0] = roles[0], roles[human_idx]

    players: dict[str, PlayerState] = {}
    personas = ["calm", "sharp", "nervy", "patient", "blunt", "warm", "theatrical"]
    for seat, (name, role) in enumerate(zip(names_list, roles, strict=True), start=1):
        player_id = f"p{seat}"
        players[player_id] = PlayerState(
            player_id=player_id,
            display_name=name,
            seat=seat,
            is_human=seat == 1,
            role=role,
            persona=personas[seat - 1],
            architecture=normalize_architecture("holy_grail"),
        )

    state = GameState(
        game_id=str(uuid.uuid4()),
        seed=seed,
        phase=Phase.NIGHT,
        day_number=1,
        players=players,
        human_player_id="p1",
        claims={pid: ClaimState() for pid in players},
    )
    state.append_event("game_created", payload={"seed": seed})
    state.append_event(
        "roles_assigned",
        payload={
            "role_counts": {
                Role.MAFIA.value: 2,
                Role.DETECTIVE.value: 1,
                Role.DOCTOR.value: 1,
                Role.VILLAGER.value: 3,
            }
        },
    )
    state.append_event("phase_started", payload={"phase": Phase.NIGHT.value})
    return state


def clone_state(state: GameState) -> GameState:
    return deepcopy(state)


def living_targets(state: GameState, exclude: str | None = None) -> list[str]:
    return [pid for pid in state.alive_players() if pid != exclude]


def ensure_alive(state: GameState, player_id: str) -> bool:
    return player_id in state.players and state.players[player_id].alive


def submit_night_action(state: GameState, actor: str, action: str, target: str) -> bool:
    if state.phase != Phase.NIGHT or not ensure_alive(state, actor) or not ensure_alive(state, target):
        state.invalid_actions += 1
        state.append_event(
            "invalid_action",
            actor=actor,
            payload={"action": action, "target": target, "reason": "illegal phase or target"},
        )
        return False

    role = state.players[actor].role
    action = action.lower()
    allowed = (
        (role == Role.MAFIA and action == "kill" and state.players[target].role != Role.MAFIA)
        or (role == Role.DETECTIVE and action == "check" and actor != target)
        or (role == Role.DOCTOR and action == "protect")
    )
    if role == Role.DOCTOR and action == "protect" and state.players[actor].private_memory.get("last_protect") == target:
        allowed = False
    if not allowed:
        state.invalid_actions += 1
        state.append_event(
            "invalid_action",
            actor=actor,
            payload={"action": action, "target": target, "role": role.value},
        )
        return False

    if action == "kill":
        state.night_actions.mafia_votes[actor] = target
    elif action == "check":
        state.night_actions.detective_checks[actor] = target
    elif action == "protect":
        state.night_actions.doctor_protects[actor] = target
        state.players[actor].private_memory["last_protect"] = target
    state.append_event("night_action_submitted", actor=actor, payload={"action": action, "target": target})
    return True


def _choose_plurality(votes: dict[str, str]) -> str | None:
    if not votes:
        return None
    counts = Counter(votes.values())
    if not counts:
        return None
    top_count = max(counts.values())
    top = sorted([target for target, count in counts.items() if count == top_count])
    return top[0] if len(top) == 1 else None


def _choose_night_kill_target(state: GameState) -> str | None:
    target = _choose_plurality(state.night_actions.mafia_votes)
    if target:
        return target
    if not state.night_actions.mafia_votes:
        return None
    counts = Counter(state.night_actions.mafia_votes.values())
    # Mafia is a team action. If model votes disagree, the moderator resolves
    # the team choice deterministically instead of treating disagreement as no kill.
    return sorted(
        counts,
        key=lambda pid: (-counts[pid], state.players[pid].seat),
    )[0]


def resolve_night(state: GameState) -> None:
    if state.phase != Phase.NIGHT:
        return
    protected = set(state.night_actions.doctor_protects.values())
    mafia_target = _choose_night_kill_target(state)
    killed: str | None = None
    if mafia_target and len(set(state.night_actions.mafia_votes.values())) > 1:
        state.append_event(
            "mafia_consensus",
            actor="moderator",
            payload={"target": mafia_target, "private": True},
        )
    if mafia_target and mafia_target not in protected:
        killed = mafia_target
        eliminate_player(state, killed, reveal=False, reason="night_kill")
        state.dawn_message = f"{state.players[killed].display_name} was eliminated during the night."
    elif mafia_target:
        state.dawn_message = "No one was eliminated during the night."
        state.append_event("doctor_save", payload={"target": mafia_target})
    else:
        state.dawn_message = "The night passed without a Mafia kill."

    for detective, target in state.night_actions.detective_checks.items():
        result = state.players[target].team == Team.MAFIA
        state.players[detective].private_memory.setdefault("investigations", {})[target] = result
        state.append_event(
            "investigation_result",
            actor=detective,
            payload={"target": target, "is_mafia": result},
        )
        alignment = "Mafia" if result else "Not Mafia"
        state.append_event(
            "private_moderator_cue",
            actor="moderator",
            payload={
                "recipient": detective,
                "message": f"Private result: {state.players[target].display_name} is {alignment}.",
                "private": True,
                "source": "detective_result",
            },
        )

    state.append_event("dawn_announced", payload={"message": state.dawn_message, "killed": killed})
    state.night_actions.mafia_votes.clear()
    state.night_actions.detective_checks.clear()
    state.night_actions.doctor_protects.clear()
    check_win_conditions(state)
    if state.winner is None:
        state.phase = Phase.DAWN
        state.append_event("phase_started", payload={"phase": Phase.DAWN.value})


def start_discussion(state: GameState) -> None:
    if state.phase not in {Phase.DAWN, Phase.RESOLUTION}:
        return
    state.phase = Phase.DISCUSSION
    state.votes.clear()
    state.locked_votes.clear()
    state.hot_seat_target = None
    state.append_event("phase_started", payload={"phase": Phase.DISCUSSION.value})


def add_message(
    state: GameState,
    actor: str,
    message: str,
    speech_act: str = "statement",
    emotion: str = "calm",
    source: str = "player",
    metadata: dict | None = None,
) -> bool:
    if state.phase not in {Phase.DISCUSSION, Phase.HOT_SEAT, Phase.VOTE, Phase.NIGHT}:
        return False
    if actor != "moderator" and not ensure_alive(state, actor):
        return False
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return False
    if actor != "moderator":
        state.ai_turns += 0 if state.players[actor].is_human else 1
    payload = {
        "message": cleaned,
        "speech_act": speech_act,
        "emotion": emotion,
        "source": source,
    }
    if metadata:
        payload.update(metadata)
    state.append_event(
        "player_message" if actor != "moderator" else "moderator_cue",
        actor=actor,
        payload=payload,
    )
    return True


def add_private_moderator_message(
    state: GameState,
    recipient: str,
    message: str,
    source: str = "moderator_private",
) -> bool:
    if recipient not in state.players:
        return False
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return False
    state.moderator_turns += 1
    state.append_event(
        "private_moderator_cue",
        actor="moderator",
        payload={
            "recipient": recipient,
            "message": cleaned,
            "private": True,
            "source": source,
        },
    )
    return True


def update_claim(
    state: GameState,
    actor: str,
    claimed_role: Role,
    quote: str = "",
    confidence: str = "claimed",
) -> bool:
    if not ensure_alive(state, actor):
        return False
    state.claims[actor].claimed_role = claimed_role
    state.claims[actor].confidence = confidence
    state.claims[actor].key_quote = quote[:160]
    for pid, claim in state.claims.items():
        if pid != actor and claim.claimed_role == claimed_role and actor not in claim.counterclaimed_by:
            claim.counterclaimed_by.append(actor)
    state.append_event(
        "claim_updated",
        actor=actor,
        payload={"claimed_role": claimed_role.value, "quote": quote[:160], "confidence": confidence},
    )
    return True


def accuse(state: GameState, actor: str, target: str) -> bool:
    if state.phase != Phase.DISCUSSION or not ensure_alive(state, actor) or not ensure_alive(state, target):
        return False
    state.hot_seat_target = target
    state.phase = Phase.HOT_SEAT
    state.append_event("accusation_started", actor=actor, payload={"target": target})
    state.append_event("phase_started", payload={"phase": Phase.HOT_SEAT.value})
    return True


def start_vote(state: GameState) -> None:
    if state.phase not in {Phase.DISCUSSION, Phase.HOT_SEAT}:
        return
    state.phase = Phase.VOTE
    state.append_event("phase_started", payload={"phase": Phase.VOTE.value})


def cast_vote(state: GameState, actor: str, target: str, lock: bool = True) -> bool:
    if state.phase != Phase.VOTE:
        return False
    if not ensure_alive(state, actor) or not ensure_alive(state, target) or actor == target:
        state.invalid_actions += 1
        state.append_event("invalid_action", actor=actor, payload={"action": "vote", "target": target})
        return False
    state.votes[actor] = target
    state.claims[actor].last_vote = target
    if lock:
        state.locked_votes.add(actor)
    state.append_event("vote_cast", actor=actor, payload={"target": target, "locked": lock})
    majority = len(state.alive_players()) // 2 + 1
    vote_counts = Counter(state.votes.values())
    if vote_counts[target] >= majority or all(pid in state.locked_votes for pid in state.alive_players()):
        resolve_vote(state)
    return True


def resolve_vote(state: GameState) -> None:
    if state.phase != Phase.VOTE:
        return
    state.phase = Phase.RESOLUTION
    target = _choose_plurality(state.votes)
    if target is None:
        state.append_event("vote_tied", payload={"votes": dict(state.votes)})
    else:
        eliminate_player(state, target, reveal=False, reason="vote")
        state.append_event("vote_resolved", payload={"eliminated": target, "votes": dict(state.votes)})
    check_win_conditions(state)
    if state.winner is None:
        state.day_number += 1
        state.phase = Phase.NIGHT
        state.votes.clear()
        state.locked_votes.clear()
        state.hot_seat_target = None
        state.append_event("phase_started", payload={"phase": Phase.NIGHT.value})


def eliminate_player(state: GameState, player_id: str, reveal: bool, reason: str) -> None:
    player = state.players[player_id]
    if not player.alive:
        return
    player.alive = False
    if reveal:
        player.revealed_role = player.role
    state.eliminated_order.append(player_id)
    state.append_event(
        "player_eliminated",
        actor=player_id,
        payload={"reason": reason},
    )


def check_win_conditions(state: GameState) -> Team | None:
    mafia = len(state.mafia_alive())
    town = len(state.town_alive())
    if mafia == 0:
        state.winner = Team.TOWN
    elif mafia >= town:
        state.winner = Team.MAFIA
    if state.winner is not None and state.phase != Phase.GAME_OVER:
        for player in state.players.values():
            player.revealed_role = player.role
        state.phase = Phase.GAME_OVER
        state.append_event("game_over", payload={"winner": state.winner.value})
    return state.winner
