from __future__ import annotations

import html
import base64
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from mafia.engine.state import GameState, Phase, Role, Team
from mafia.metrics import game_metrics


SEAT_POSITIONS = {
    1: (50, 22),
    2: (76, 31),
    3: (82, 54),
    4: (64, 75),
    5: (36, 75),
    6: (18, 54),
    7: (24, 31),
}

ASSET_DIR = Path(__file__).resolve().parent / "assets"
PORTRAIT_ASSETS = {
    "p1": "portraits/p1-you.png",
    "p2": "portraits/p2-luna.png",
    "p3": "portraits/p3-rook.png",
    "p4": "portraits/p4-jett.png",
    "p5": "portraits/p5-vesper.png",
    "p6": "portraits/p6-dante.png",
    "p7": "portraits/p7-selene.png",
}

ROLE_ICON = {
    Role.MAFIA: "mask",
    Role.DETECTIVE: "eye",
    Role.DOCTOR: "cross",
    Role.VILLAGER: "star",
}


@dataclass(slots=True)
class RenderBundle:
    table: str
    left: str
    right: str
    replay: str
    status: str
    endgame: str


def render_bundle(state: GameState) -> RenderBundle:
    return RenderBundle(
        table=render_table(state),
        left=render_left_rail(state),
        right=render_right_rail(state),
        replay=render_replay(state),
        status=render_status(state),
        endgame=render_endgame(state),
    )


def render_status(state: GameState) -> str:
    human = state.players[state.human_player_id]
    winner = state.winner.value.upper() if state.winner else "IN PLAY"
    return (
        f"Day {state.day_number} · {state.phase.value.replace('_', ' ').title()} · "
        f"Alive {len(state.alive_players())}/7 · Your role: {human.role.value} · {winner}"
    )


def render_table(state: GameState) -> str:
    timer = _phase_timer_label(state)
    hot = state.hot_seat_target
    bg = "reference/table-room.png"
    if state.phase in {Phase.HOT_SEAT, Phase.VOTE}:
        bg = "reference/hot-seat-room.png"
    if state.winner:
        bg = "reference/endgame-room.png"
    center_label = ""
    if hot:
        center_label = f"ACCUSED: {html.escape(state.players[hot].display_name)}"
    elif state.winner:
        center_label = f"{state.winner.value.upper()} VICTORY"
    seats = []
    for pid, player in sorted(state.players.items(), key=lambda item: item[1].seat):
        x, y = SEAT_POSITIONS[player.seat]
        dead = " dead" if not player.alive else ""
        human = " human" if player.is_human else ""
        hot_class = " accused" if hot == pid else ""
        vote_count = sum(1 for target in state.votes.values() if target == pid)
        claim = state.claims[pid].claimed_role.value if state.claims[pid].claimed_role else "No claim"
        role_label = player.revealed_role.value if player.revealed_role else claim
        status = "Human" if player.is_human else "AI"
        if player.revealed_role:
            status = player.revealed_role.value
        portrait_uri = _asset_uri(PORTRAIT_ASSETS.get(pid, "portraits/p1-you.png"))
        reaction = _reaction_badge(state, pid)
        seats.append(
            f"""
            <div class="seat{dead}{human}{hot_class}" style="left:{x}%;top:{y}%;">
              <div class="reaction-chip">{reaction}</div>
              <div class="portrait"><img src="{portrait_uri}" alt="{html.escape(player.display_name)} portrait"></div>
              <div class="nameplate">
                <span class="seatnum">{player.seat}</span>
                <span class="pname">{html.escape(player.display_name)}</span>
                <span class="badge">{html.escape(status)}</span>
              </div>
              <div class="subline">{html.escape(role_label)}{f" · {vote_count} votes" if vote_count else ""}</div>
            </div>
            """
        )
    vote_arrows = ""
    if state.phase in {Phase.HOT_SEAT, Phase.VOTE}:
        vote_arrows = '<div class="pressure-ring">VOTES<br><strong>{}</strong></div>'.format(len(state.votes))
    dock = render_action_dock(state)
    coach = render_coach_panel(state)
    return f"""
    <section class="mafia-board" style="--board-bg: url('{_asset_uri(bg)}');">
      <div class="hud">
        <div class="phase-chip">{state.phase.value.replace('_', ' ').title()}</div>
        <div class="timer">{timer}</div>
        <div class="alive-chip">ALIVE<br><strong>{len(state.alive_players())}/7</strong></div>
      </div>
      <div class="table-ring">
        <div class="table-center">{f"<span>{center_label}</span>" if center_label else ""}</div>
        {vote_arrows}
        {''.join(seats)}
      </div>
      {dock}
      {coach}
    </section>
    """


def render_left_rail(state: GameState) -> str:
    claim_rows = []
    for pid, player in sorted(state.players.items(), key=lambda item: item[1].seat):
        claim = state.claims[pid]
        role = claim.claimed_role.value if claim.claimed_role else "No claim yet"
        quote = claim.key_quote or ("Eliminated" if not player.alive else "Watching the table")
        portrait_uri = _asset_uri(PORTRAIT_ASSETS.get(pid, "portraits/p1-you.png"))
        claim_rows.append(
            f"""
            <div class="ledger-row {'dead' if not player.alive else ''}">
              <div class="mini-avatar"><img src="{portrait_uri}" alt=""></div>
              <div>
                <strong>{html.escape(player.display_name)}</strong>
                <span>{html.escape(role)}</span>
                <small>{html.escape(quote)}</small>
              </div>
            </div>
            """
        )
    history = []
    for event in state.events:
        if event.type == "player_eliminated":
            player = state.players[event.actor]
            history.append(
                f"<li>Day {event.day}: {html.escape(player.display_name)} eliminated "
                f"({event.payload.get('revealed_role')})</li>"
            )
    if not history:
        history.append("<li>No one has been eliminated.</li>")
    return f"""
    <section class="side-panel">
      <h2>Claims</h2>
      <div class="ledger-list">{''.join(claim_rows)}</div>
      <h2>Vote History</h2>
      <ul class="history">{''.join(history[-5:])}</ul>
    </section>
    """


def render_right_rail(state: GameState) -> str:
    messages = [
        event for event in state.events if event.type in {"player_message", "moderator_cue"}
    ][-10:]
    rows = []
    for event in messages:
        actor = "Moderator" if event.actor == "moderator" else state.players[event.actor].display_name
        kind = event.payload.get("speech_act", "statement")
        rows.append(
            f"""
            <div class="chat-row {'mod' if event.actor == 'moderator' else ''}">
              <div class="chat-meta"><strong>{html.escape(actor)}</strong><span>{html.escape(kind)}</span></div>
              <p>{html.escape(str(event.payload.get('message', '')))}</p>
            </div>
            """
        )
    if not rows:
        rows.append('<div class="empty">The table is waiting.</div>')
    vote_rows = []
    for voter, target in sorted(state.votes.items(), key=lambda item: state.players[item[0]].seat):
        vote_rows.append(
            f"<li>{html.escape(state.players[voter].display_name)} -> "
            f"{html.escape(state.players[target].display_name)}</li>"
        )
    if not vote_rows:
        vote_rows.append("<li>No locked votes.</li>")
    assistant = render_assistant_panel(state)
    return f"""
    <section class="side-panel right-panel">
      <div class="rail-tabs"><span class="active">Chat</span><span>Game Log</span></div>
      <div class="chat-list">{''.join(rows)}</div>
      <h2>Votes</h2>
      <ul class="vote-list">{''.join(vote_rows)}</ul>
      <div class="reaction-bar">
        <span>👍</span><span>❤️</span><span>😂</span><span>😮</span><span>😡</span><span>👀</span>
      </div>
      {assistant}
    </section>
    """


def render_replay(state: GameState) -> str:
    items = []
    for event in state.events[-9:]:
        label = event.type.replace("_", " ").title()
        if event.type in {"player_message", "moderator_cue"}:
            label = "Message"
        if event.type == "night_action_submitted":
            label = "Night Action"
        items.append(
            f"""
            <div class="timeline-item">
              <span>{html.escape(label)}</span>
              <small>Day {event.day}</small>
            </div>
            """
        )
    return f"""
    <section class="replay-strip">
      <button class="play-dot" aria-label="Replay">▶</button>
      <div class="timeline">{''.join(items)}</div>
    </section>
    """


def render_endgame(state: GameState) -> str:
    if not state.winner:
        return ""
    metrics = game_metrics(state)
    cards = []
    for player in sorted(state.players.values(), key=lambda item: item.seat):
        outcome = "Survived" if player.alive else "Eliminated"
        portrait_uri = _asset_uri(PORTRAIT_ASSETS.get(player.player_id, "portraits/p1-you.png"))
        cards.append(
            f"""
            <div class="reveal-card {'dead' if not player.alive else ''}">
              <div class="portrait small"><img src="{portrait_uri}" alt=""></div>
              <strong>{html.escape(player.display_name)}</strong>
              <span>{player.role.value}</span>
              <small>{outcome}</small>
            </div>
            """
        )
    confession = _confession_text(state)
    return f"""
    <section class="endgame-panel" style="--endgame-bg: url('{_asset_uri('reference/endgame-room.png')}');">
      <h1>The Truth Emerges</h1>
      <p>{state.winner.value.title()} victory · {metrics['days']} days · {metrics['messages']} messages</p>
      <div class="reveal-grid">{''.join(cards)}</div>
      <div class="confession">
        <h2>Confession Booth</h2>
        <p>{html.escape(confession)}</p>
      </div>
    </section>
    """


def render_metrics_html(state: GameState) -> str:
    metrics = game_metrics(state)
    rows = "".join(
        f"<tr><th>{html.escape(str(key))}</th><td>{html.escape(str(value))}</td></tr>"
        for key, value in metrics.items()
        if key != "role_survival"
    )
    return f"<table class='metrics-table'>{rows}</table>"


def target_choices(state: GameState, include_self: bool = False) -> list[tuple[str, str]]:
    choices = []
    for pid, player in sorted(state.players.items(), key=lambda item: item[1].seat):
        if not player.alive:
            continue
        if not include_self and pid == state.human_player_id:
            continue
        choices.append((f"{player.seat}. {player.display_name}", pid))
    return choices


def role_choices() -> list[str]:
    return [role.value for role in Role]


def _phase_timer_label(state: GameState) -> str:
    if state.phase == Phase.NIGHT:
        return "NIGHT"
    if state.phase == Phase.HOT_SEAT:
        return "00:30"
    if state.phase == Phase.VOTE:
        return "00:12"
    if state.phase == Phase.GAME_OVER:
        return "DONE"
    return "01:24"


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def _confession_text(state: GameState) -> str:
    mafia_names = [p.display_name for p in state.players.values() if p.role == Role.MAFIA]
    if state.winner == Team.TOWN:
        return f"The town isolated the pressure chain and eliminated {', '.join(mafia_names)}."
    return f"The Mafia survived long enough to control the vote. {', '.join(mafia_names)} shaped the final table."


def render_action_dock(state: GameState) -> str:
    actions = [
        ("ask", "💬", "ASK", "Ask a player a question"),
        ("accuse", "⌖", "ACCUSE", "Accuse a player of being Mafia"),
        ("defend", "🛡", "DEFEND", "Defend yourself or others"),
        ("claim", "🎭", "CLAIM ROLE", "Reveal your role to the table"),
        ("vote", "🗳", "VOTE", "Place your vote to eliminate"),
    ]
    items = []
    for key, icon, label, sub in actions:
        active = " active" if (
            (key == "accuse" and state.phase == Phase.HOT_SEAT)
            or (key == "vote" and state.phase == Phase.VOTE)
        ) else ""
        items.append(
            f"""
            <div class="action-token{active}">
              <div class="action-icon">{icon}</div>
              <strong>{label}</strong>
              <span>{sub}</span>
            </div>
            """
        )
    return f"<div class='action-dock'>{''.join(items)}</div>"


def render_coach_panel(state: GameState) -> str:
    if state.day_number > 1 or state.winner:
        return ""
    human = state.players[state.human_player_id]
    role_note = {
        Role.MAFIA: "Blend in during the day. At night, coordinate the kill.",
        Role.DETECTIVE: "Gather checks quietly. Reveal only when it changes the vote.",
        Role.DOCTOR: "Protect likely information roles and survive suspicion.",
        Role.VILLAGER: "Track claims, pressure contradictions, and vote carefully.",
    }[human.role]
    return f"""
    <aside class="coach-panel">
      <h3>Your role: {human.role.value}</h3>
      <p>{role_note}</p>
      <small>Suggested first action: ask for one concrete read.</small>
    </aside>
    """


def render_assistant_panel(state: GameState) -> str:
    if state.winner:
        return ""
    hot = state.hot_seat_target
    pressure = "Pressure the accused" if hot else "Ask for evidence"
    target = state.players[hot].display_name if hot else "the quietest player"
    return f"""
    <aside class="assistant-panel">
      <h3>Assistant</h3>
      <p>Smart suggestions</p>
      <button>?</button><span>{pressure}</span>
      <button>🔥</button><span>Challenge {html.escape(target)}</span>
      <button>🛡</button><span>Defend a trusted player</span>
    </aside>
    """


def _reaction_badge(state: GameState, player_id: str) -> str:
    votes = sum(1 for target in state.votes.values() if target == player_id)
    if votes:
        return f"🔥 {votes}"
    player = state.players[player_id]
    if not player.alive:
        return "☠"
    if state.hot_seat_target == player_id:
        return "⚠"
    return {1: "👀", 2: "💚", 3: "🧠", 4: "😏", 5: "🤔", 6: "😡", 7: "❤️"}.get(
        player.seat, "..."
    )


@lru_cache(maxsize=64)
def _asset_uri(relative_path: str) -> str:
    path = ASSET_DIR / relative_path
    mime = "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"
