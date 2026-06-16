from __future__ import annotations

from typing import Any

from mafia.engine.state import Event, GameState, Phase, Role


PUBLIC_EVENT_TYPES = {
    "game_created",
    "phase_started",
    "dawn_announced",
    "player_message",
    "moderator_cue",
    "claim_updated",
    "accusation_started",
    "vote_cast",
    "vote_tied",
    "vote_resolved",
    "player_eliminated",
    "game_over",
}


def player_public_dict(state: GameState, player_id: str) -> dict[str, Any]:
    player = state.players[player_id]
    return {
        "player_id": player.player_id,
        "name": player.display_name,
        "seat": player.seat,
        "is_human": player.is_human,
        "alive": player.alive,
        "status": player.public_status,
        "revealed_role": player.revealed_role.value if player.revealed_role else None,
        "claimed_role": (
            state.claims[player_id].claimed_role.value if state.claims[player_id].claimed_role else None
        ),
        "claim_confidence": state.claims[player_id].confidence,
        "last_vote": state.claims[player_id].last_vote,
    }


def public_view(state: GameState) -> dict[str, Any]:
    return {
        "game_id": state.game_id,
        "phase": state.phase.value,
        "day": state.day_number,
        "alive": state.alive_players(),
        "players": {pid: player_public_dict(state, pid) for pid in state.players},
        "claims": {
            pid: {
                "claimed_role": claim.claimed_role.value if claim.claimed_role else None,
                "confidence": claim.confidence,
                "counterclaimed_by": list(claim.counterclaimed_by),
                "key_quote": claim.key_quote,
                "night_story": claim.night_story,
                "last_vote": claim.last_vote,
            }
            for pid, claim in state.claims.items()
        },
        "votes": dict(state.votes),
        "locked_votes": sorted(state.locked_votes),
        "hot_seat_target": state.hot_seat_target,
        "dawn_message": state.dawn_message,
        "winner": state.winner.value if state.winner else None,
        "events": [
            public_event_dict(event)
            for event in state.events
            if event.type in PUBLIC_EVENT_TYPES
            and not _event_has_private_payload(event)
            and not _event_is_targeted_moderator_cue(event)
        ],
    }


def private_view(state: GameState, viewer_id: str) -> dict[str, Any]:
    if viewer_id not in state.players:
        raise KeyError(f"Unknown player {viewer_id}")
    player = state.players[viewer_id]
    view = public_view(state)
    view["you"] = {
        "player_id": player.player_id,
        "role": player.role.value,
        "team": player.team.value,
        "alive": player.alive,
        "persona": player.persona,
        "legal_actions": legal_actions_for(state, viewer_id),
    }
    private_info: dict[str, Any] = {}
    if player.role == Role.MAFIA:
        private_info["mafia_team"] = [
            pid for pid, other in state.players.items() if other.role == Role.MAFIA
        ]
    if player.role == Role.DETECTIVE:
        private_info["investigations"] = dict(player.private_memory.get("investigations", {}))
    if player.role == Role.DOCTOR:
        private_info["last_protect"] = player.private_memory.get("last_protect")
    view["private_info"] = private_info
    return view


def legal_actions_for(state: GameState, player_id: str) -> list[str]:
    if player_id not in state.players or not state.players[player_id].alive:
        return []
    role = state.players[player_id].role
    if state.phase == Phase.NIGHT:
        if role == Role.MAFIA:
            return ["kill"]
        if role == Role.DETECTIVE:
            return ["check"]
        if role == Role.DOCTOR:
            return ["protect"]
        return ["sleep"]
    if state.phase == Phase.DISCUSSION:
        return ["message", "claim", "accuse"]
    if state.phase == Phase.HOT_SEAT:
        return ["message", "claim"]
    if state.phase == Phase.VOTE:
        return ["vote"]
    return []


def public_event_dict(event: Event) -> dict[str, Any]:
    payload = dict(event.payload)
    if event.type == "doctor_save":
        payload = {"saved": True}
    return {
        "seq": event.seq,
        "type": event.type,
        "phase": event.phase.value,
        "day": event.day,
        "actor": event.actor,
        "payload": payload,
    }


def private_event_dict(state: GameState, event: Event, viewer_id: str) -> dict[str, Any] | None:
    if _event_is_targeted_moderator_cue(event):
        if event.payload.get("target") != viewer_id:
            return None
        payload = dict(event.payload)
        payload["private"] = True
        payload["source"] = payload.get("source", "ttt_floor_cue")
        return {
            "seq": event.seq,
            "type": "private_moderator_cue",
            "phase": event.phase.value,
            "day": event.day,
            "actor": "moderator",
            "payload": payload,
        }
    if event.type in PUBLIC_EVENT_TYPES and not _event_has_private_payload(event):
        return public_event_dict(event)
    if event.type == "night_action_submitted" and event.actor == viewer_id:
        return {
            "seq": event.seq,
            "type": event.type,
            "phase": event.phase.value,
            "day": event.day,
            "actor": event.actor,
            "payload": dict(event.payload),
        }
    if event.type == "investigation_result" and event.actor == viewer_id:
        return {
            "seq": event.seq,
            "type": event.type,
            "phase": event.phase.value,
            "day": event.day,
            "actor": event.actor,
            "payload": dict(event.payload),
        }
    if event.type == "private_moderator_cue" and event.payload.get("recipient") == viewer_id:
        return {
            "seq": event.seq,
            "type": event.type,
            "phase": event.phase.value,
            "day": event.day,
            "actor": "moderator",
            "payload": {
                "message": event.payload.get("message", ""),
                "recipient": viewer_id,
                "private": True,
                "source": event.payload.get("source", "moderator_private"),
            },
        }
    if event.type == "mafia_consensus" and state.players[viewer_id].role == Role.MAFIA:
        target = str(event.payload.get("target", ""))
        target_name = state.players[target].display_name if target in state.players else "the chosen target"
        return {
            "seq": event.seq,
            "type": event.type,
            "phase": event.phase.value,
            "day": event.day,
            "actor": "moderator",
            "payload": {
                "target": event.payload.get("target"),
                "message": f"Private Mafia consensus: {target_name} is the night target.",
                "private": True,
                "source": "mafia_consensus",
            },
        }
    return None


def _event_has_private_payload(event: Event) -> bool:
    return event.type == "investigation_result" or "is_mafia" in event.payload


def _event_is_targeted_moderator_cue(event: Event) -> bool:
    return (
        event.type == "moderator_cue"
        and event.actor == "moderator"
        and isinstance(event.payload.get("target"), str)
    )
