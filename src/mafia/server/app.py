from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from gradio import Server
from pydantic import BaseModel, Field

from mafia.engine.state import Phase, Role
from mafia.engine.views import legal_actions_for, private_event_dict, private_view, public_view
from mafia.metrics import game_metrics
from mafia.ui.session import (
    GameSession,
    advance_ai,
    human_floor_pending,
    human_accuse,
    human_claim,
    human_night_action,
    human_pass_floor,
    human_send_message,
    human_vote,
    new_session,
)


ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = ROOT / "frontend" / "dist"
PUBLIC_ASSETS = ROOT / "frontend" / "public" / "assets"

app = Server(title="Mafia", description="Online Mafia game server")
SESSIONS: dict[str, GameSession] = {}
READY_CACHE: dict[str, Any] = {}
SESSION_STORE: Any | None = None


class NewGameRequest(BaseModel):
    seed: int = Field(default=7, ge=1)
    human_name: str = Field(default="You", min_length=1, max_length=32)
    human_role: str = "Random"
    agent_mode: str = "Online"
    human_avatar: str = "player"


class TargetRequest(BaseModel):
    target: str


class MessageRequest(BaseModel):
    message: str = Field(default="", max_length=320)
    source: str = "human_typed"


class ClaimRequest(BaseModel):
    role: str


class AdvanceRequest(BaseModel):
    max_steps: int = Field(default=1, ge=1, le=24)


class SuggestionRequest(BaseModel):
    target: str | None = None


class SuggestionApprovalRequest(BaseModel):
    suggestion_id: str = Field(default="", max_length=64)
    message: str = Field(default="", max_length=320)


class ReadyRequest(BaseModel):
    agent_mode: str = "Online"


@app.get("/", include_in_schema=False, response_model=None)
def index():
    built = FRONTEND_DIST / "index.html"
    if built.exists():
        return FileResponse(
            built,
            headers={
                "Cache-Control": "no-store, max-age=0",
                "Pragma": "no-cache",
            },
        )
    return HTMLResponse(
        """
        <main style="font-family:system-ui;padding:32px;background:#090706;color:#f2dfbd;min-height:100vh">
          <h1>Mafia frontend not built yet.</h1>
          <p>Run <code>npm install</code> and <code>npm run build</code> in <code>frontend/</code>.</p>
        </main>
        """,
        status_code=503,
    )


@app.post("/api/game")
def create_game_api(payload: NewGameRequest) -> dict[str, Any]:
    session = new_session(
        seed=payload.seed,
        human_name=payload.human_name,
        human_role=payload.human_role,
    )
    session.human_avatar = payload.human_avatar
    advance_ai(session, max_steps=4)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/ready")
def ready_api(payload: ReadyRequest) -> dict[str, Any]:
    if READY_CACHE.get("ready"):
        return READY_CACHE["ready"]
    model_status: dict[str, Any] = {
        "agentMode": "Online",
        "moderator": "Time-to-Talk ModeratorAgent",
        "playerArchitecture": "holy_grail",
        "ready": True,
        "checks": [],
    }
    try:
        from mafia.models.modal_client import ModalModelClient

        player = ModalModelClient.mafia_bf16()
        moderator = ModalModelClient.base_moderator_bf16()
        model_status["checks"] = [
            _warm_model_check("player_model", player),
            _warm_model_check("moderator_model", moderator),
            {"name": "agent_architecture", "target": "holy_grail", "ready": True},
            {"name": "moderator_protocol", "target": "Time-to-Talk scheduler+generator", "ready": True},
        ]
    except Exception as exc:  # pragma: no cover - depends on local Modal installation.
        model_status["ready"] = False
        model_status["checks"] = [
            {"name": "modal_client", "ready": False, "error": type(exc).__name__}
        ]
    if model_status["ready"]:
        READY_CACHE["ready"] = model_status
    return model_status


@app.get("/api/game/{game_id}")
def get_game_api(game_id: str) -> dict[str, Any]:
    return view(_session(game_id))


@app.post("/api/game/{game_id}/advance")
def advance_game_api(game_id: str, payload: AdvanceRequest) -> dict[str, Any]:
    session = _session(game_id)
    advance_ai(session, max_steps=payload.max_steps)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/game/{game_id}/message")
def message_api(game_id: str, payload: MessageRequest) -> dict[str, Any]:
    session = _session(game_id)
    human_send_message(session, payload.message, source=payload.source)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/game/{game_id}/claim")
def claim_api(game_id: str, payload: ClaimRequest) -> dict[str, Any]:
    session = _session(game_id)
    human_claim(session, payload.role)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/game/{game_id}/accuse")
def accuse_api(game_id: str, payload: TargetRequest) -> dict[str, Any]:
    session = _session(game_id)
    human_accuse(session, payload.target)
    advance_ai(session, max_steps=2)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/game/{game_id}/start-vote")
def start_vote_api(game_id: str) -> dict[str, Any]:
    _session(game_id)
    raise HTTPException(status_code=403, detail="The moderator controls when voting begins.")


@app.post("/api/game/{game_id}/vote")
def vote_api(game_id: str, payload: TargetRequest) -> dict[str, Any]:
    session = _session(game_id)
    human_vote(session, payload.target)
    advance_ai(session, max_steps=4)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/game/{game_id}/night-action")
def night_action_api(game_id: str, payload: TargetRequest) -> dict[str, Any]:
    session = _session(game_id)
    human_night_action(session, payload.target)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/game/{game_id}/pass-floor")
def pass_floor_api(game_id: str) -> dict[str, Any]:
    session = _session(game_id)
    human_pass_floor(session)
    result = view(session)
    _store_session(session)
    return result


@app.post("/api/game/{game_id}/suggestions")
def suggestions_api(game_id: str, payload: SuggestionRequest) -> dict[str, Any]:
    session = _session(game_id)
    return {
        "suggestions": _suggestions_for(session, payload.target, refresh=True)
    }


@app.post("/api/game/{game_id}/approve-suggestion")
def approve_suggestion_api(game_id: str, payload: SuggestionApprovalRequest) -> dict[str, Any]:
    session = _session(game_id)
    human_send_message(
        session,
        payload.message,
        source=f"human_approved_suggestion:{payload.suggestion_id or 'unknown'}",
    )
    result = view(session)
    _store_session(session)
    return result


@app.api(name="advance_ai", description="Advance AI and moderator actions for a game session.")
def queued_advance_ai(game_id: str, max_steps: int = 1) -> dict[str, Any]:
    session = _session(game_id)
    advance_ai(session, max_steps=max(1, min(int(max_steps), 6)))
    result = view(session)
    _store_session(session)
    return result


def view(session: GameSession, *, refresh_suggestions: bool = False) -> dict[str, Any]:
    state = session.state
    human_id = state.human_player_id
    pv = private_view(state, human_id)
    public = public_view(state)
    human = state.players[human_id]
    events = [
        event_dict
        for event in state.events
        if (event_dict := private_event_dict(state, event, human_id)) is not None
    ]
    players = []
    for pid, player in sorted(state.players.items(), key=lambda item: item[1].seat):
        claim = state.claims[pid]
        role_for_view = None
        if pid == human_id or state.winner:
            role_for_view = player.role.value
        players.append(
            {
                "id": pid,
                "name": player.display_name,
                "seat": player.seat,
                "alive": player.alive,
                "isHuman": player.is_human,
                "persona": player.persona,
                "modelSpec": player.model_spec,
                "architecture": player.architecture,
                "team": player.team.value if pid == human_id or state.winner else None,
                "role": role_for_view,
                "claimedRole": claim.claimed_role.value if claim.claimed_role else None,
                "claimConfidence": claim.confidence,
                "keyQuote": claim.key_quote,
                "lastVote": claim.last_vote,
                "publicStatus": player.public_status,
                "avatar": getattr(session, "human_avatar", "player") if pid == human_id else None,
            }
        )
    partner_suggestion = _mafia_partner_suggested_target(session)
    target_choices = []
    for pid in _target_choices(session):
        label = f"{state.players[pid].seat}. {state.players[pid].display_name}"
        if pid == partner_suggestion:
            label += " (partner suggestion)"
        target_choices.append({"id": pid, "label": label})
    return {
        "gameId": state.game_id,
        "seed": state.seed,
        "mode": session.agent_mode,
        "phase": state.phase.value,
        "phaseLabel": state.phase.value.replace("_", " ").title(),
        "day": state.day_number,
        "winner": state.winner.value if state.winner else None,
        "aliveCount": len(state.alive_players()),
        "human": {
            "id": human_id,
            "name": human.display_name,
            "role": human.role.value,
            "team": human.team.value,
            "alive": human.alive,
            "legalActions": legal_actions_for(state, human_id),
            "privateInfo": pv.get("private_info", {}),
        },
        "players": players,
        "events": events,
        "scene": _scene_for(session),
        "suggestions": [],
        "pendingHumanFloor": human_floor_pending(state),
        "lastReceipt": _last_receipt(events, human_id),
        "public": public,
        "votes": dict(state.votes),
        "lockedVotes": sorted(state.locked_votes),
        "hotSeatTarget": state.hot_seat_target,
        "dawnMessage": state.dawn_message,
        "targetChoices": target_choices,
        "roleChoices": [role.value for role in Role],
        "metrics": _metrics(session),
        "humanAvatar": getattr(session, "human_avatar", "player"),
    }


def _suggestions_for(
    session: GameSession,
    target_id: str | None = None,
    *,
    refresh: bool = False,
) -> list[dict[str, str]]:
    state = session.state
    human_id = state.human_player_id
    human = state.players[human_id]
    if state.winner or not human.alive or state.phase not in {Phase.DISCUSSION, Phase.HOT_SEAT, Phase.VOTE}:
        return []
    key = _suggestion_cache_key(session, target_id)
    cache = getattr(session, "suggestion_cache", {})
    if not refresh and key in cache:
        return cache[key]
    if not refresh:
        return session.moderator._fallback_human_suggestions(state, human_id, target_id or "")
    suggestions = session.moderator.human_suggestions(state, human_id, target_id=target_id)
    session.suggestion_cache = {key: suggestions}
    return suggestions


def _suggestion_cache_key(session: GameSession, target_id: str | None) -> str:
    state = session.state
    alive = ",".join(state.alive_players())
    votes = ",".join(f"{actor}:{target}" for actor, target in sorted(state.votes.items()))
    locked = ",".join(sorted(state.locked_votes))
    claims = ",".join(
        f"{pid}:{claim.claimed_role.value if claim.claimed_role else ''}:{claim.confidence}"
        for pid, claim in sorted(state.claims.items())
    )
    return "|".join(
        [
            state.phase.value,
            str(state.day_number),
            state.hot_seat_target or "",
            target_id or "",
            alive,
            votes,
            locked,
            claims,
        ]
    )


def _session(game_id: str) -> GameSession:
    if game_id in SESSIONS:
        return SESSIONS[game_id]
    store = _modal_session_store()
    if store is not None:
        try:
            session = store[game_id]
        except KeyError:
            session = None
        if session is not None:
            if not hasattr(session, "suggestion_cache"):
                session.suggestion_cache = {}
            SESSIONS[game_id] = session
            return session
    raise HTTPException(status_code=404, detail=f"Unknown game: {game_id}")


def _store_session(session: GameSession) -> None:
    SESSIONS[session.state.game_id] = session
    store = _modal_session_store()
    if store is not None:
        store[session.state.game_id] = session


def _modal_session_store() -> Any | None:
    if os.getenv("MAFIA_SESSION_BACKEND") != "modal":
        return None
    global SESSION_STORE
    if SESSION_STORE is not None:
        return SESSION_STORE
    try:
        import modal

        SESSION_STORE = modal.Dict.from_name(
            os.getenv("MAFIA_SESSION_DICT", "ai-native-mafia-sessions"),
            create_if_missing=True,
        )
    except Exception:
        SESSION_STORE = None
    return SESSION_STORE


def _target_choices(session: GameSession) -> list[str]:
    state = session.state
    human = state.players[state.human_player_id]
    alive = state.alive_players()
    if state.phase == Phase.NIGHT:
        if human.role == Role.MAFIA:
            return [
                pid
                for pid in alive
                if pid != state.human_player_id and state.players[pid].role != Role.MAFIA
            ]
        if human.role == Role.DETECTIVE:
            return [pid for pid in alive if pid != state.human_player_id]
        if human.role == Role.DOCTOR:
            last_protect = human.private_memory.get("last_protect")
            return [pid for pid in alive if pid != last_protect]
        return []
    return [pid for pid in alive if pid != state.human_player_id]


def _mafia_partner_suggested_target(session: GameSession) -> str | None:
    state = session.state
    human = state.players[state.human_player_id]
    if state.phase != Phase.NIGHT or human.role != Role.MAFIA:
        return None
    return next(
        (
            vote
            for actor, vote in state.night_actions.mafia_votes.items()
            if actor != state.human_player_id and vote in state.players
        ),
        None,
    )


def _metrics(session: GameSession) -> dict[str, Any]:
    metrics = game_metrics(session.state)
    metrics["moderator"] = asdict(session.moderator.metrics)
    metrics["agent_mode"] = session.agent_mode
    if session.state.model_calls:
        metrics["last_model_call"] = session.state.model_calls[-1]
    return metrics


def _warm_model_check(name: str, client: Any) -> dict[str, Any]:
    result = client.generate(
        'Return exactly this JSON and nothing else: {"ready":true}',
        max_tokens=8,
        temperature=0.0,
        top_p=0.95,
        top_k=64,
    )
    return {
        "name": name,
        "target": client.model_label,
        "ready": True,
        "latencySeconds": result.latency_seconds,
        "backend": result.backend,
    }


def _scene_for(session: GameSession) -> dict[str, Any]:
    state = session.state
    human = state.players[state.human_player_id]
    if state.winner:
        return {
            "id": "endgame_reveal",
            "sceneKey": "endgame",
            "title": "The Truth Emerges" if state.winner.value == "town" else "The Shadows Prevail",
            "subtitle": "All roles are revealed.",
            "objective": "Review the turning points and prepare a rematch.",
            "soundCue": "victory" if state.winner.value == human.team.value else "defeat",
        }
    if state.phase == Phase.NIGHT:
        action = legal_actions_for(state, state.human_player_id)
        needs_action = human.alive and any(item in action for item in ("kill", "check", "protect"))
        return {
            "id": "night_action" if needs_action else "night_wait",
            "sceneKey": "night",
            "title": f"Night {state.day_number}",
            "subtitle": "The room darkens. Some players act in secret.",
            "objective": _night_objective(human.role.value, needs_action),
            "soundCue": "night_falls",
        }
    if state.phase == Phase.DAWN:
        return {
            "id": "dawn_report",
            "sceneKey": "table",
            "title": "Dawn Breaks",
            "subtitle": state.dawn_message or "The table waits for the report.",
            "objective": "Read the result, then reopen discussion.",
            "soundCue": "dawn_breaks",
        }
    if state.phase == Phase.HOT_SEAT:
        target = state.hot_seat_target
        target_name = state.players[target].display_name if target else "Unknown"
        return {
            "id": "hot_seat",
            "sceneKey": "vote",
            "title": "All Eyes Turn",
            "subtitle": f"{target_name} is on the hot seat.",
            "objective": "Press for one concrete answer before voting.",
            "soundCue": "accusation",
        }
    if state.phase == Phase.VOTE:
        return {
            "id": "vote_arena",
            "sceneKey": "vote",
            "title": "Voting Ends Soon",
            "subtitle": "Choose carefully. A wrong vote helps the Mafia.",
            "objective": "Lock your vote or state your hesitation.",
            "soundCue": "vote_countdown",
        }
    return {
        "id": "day_table",
        "sceneKey": "table",
        "title": f"Day {state.day_number} Discussion",
        "subtitle": "The table demands answers.",
        "objective": "Ask, accuse, defend, claim, or move the table toward a vote.",
        "soundCue": "discussion",
    }


def _night_objective(role: str, needs_action: bool) -> str:
    if not needs_action:
        return "Wait for the moderator to resolve the night."
    if role == "Mafia":
        return "Choose a non-Mafia player to eliminate."
    if role == "Detective":
        return "Choose one living player to investigate."
    if role == "Doctor":
        return "Choose one living player to protect."
    return "Sleep through the night."


def _last_receipt(events: list[dict[str, Any]], human_id: str) -> dict[str, Any] | None:
    receipt_types = {
        "player_message",
        "claim_updated",
        "accusation_started",
        "vote_cast",
        "night_action_submitted",
        "investigation_result",
        "player_eliminated",
        "dawn_announced",
    }
    for event in reversed(events):
        if event["type"] in receipt_types and event.get("actor") in {human_id, "moderator", None}:
            return event
    return None


if (FRONTEND_DIST / "app-assets").exists():
    app.mount("/app-assets", StaticFiles(directory=str(FRONTEND_DIST / "app-assets"), html=False), name="app-assets")

if PUBLIC_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(PUBLIC_ASSETS), html=False), name="assets")


def main() -> None:
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
        mcp_server=os.getenv("MAFIA_ENABLE_GRADIO_MCP", "1") != "0",
    )


if __name__ == "__main__":
    main()
