from __future__ import annotations

import gradio as gr

from mafia.engine.state import Phase, Role
from mafia.metrics import game_metrics
from mafia.ui.components import (
    RenderBundle,
    render_bundle,
    render_metrics_html,
    role_choices,
    target_choices,
)
from mafia.ui.custom_components import (
    ClaimLedger,
    EndgameReveal,
    MafiaTable,
    MetricsPanel,
    ReplayTimeline,
    VoteChatRail,
)
from mafia.ui.session import (
    GameSession,
    advance_ai,
    human_accuse,
    human_claim,
    human_night_action,
    human_send_message,
    human_start_vote,
    human_vote,
    new_session,
)
from mafia.ui.styles import APP_CSS

APP_THEME = gr.themes.Base(
    primary_hue="red",
    secondary_hue="amber",
    neutral_hue="stone",
    font=["Inter", "ui-sans-serif", "system-ui"],
    font_mono=["JetBrains Mono", "monospace"],
)


def _bundle_outputs(session: GameSession):
    bundle = render_bundle(session.state)
    choices = target_choices(session.state, include_self=_human_can_target_self(session))
    default_target = choices[0][1] if choices else None
    status = f"{bundle.status} · Mode: {session.agent_mode}"
    metrics = render_metrics_html(session.state)
    return (
        session,
        bundle.table,
        bundle.left,
        bundle.right,
        bundle.replay,
        status,
        bundle.endgame,
        gr.update(choices=choices, value=default_target),
        metrics,
    )


def _new_game(seed, role_name):
    session = new_session(seed=int(seed or 1), human_role=role_name, agent_mode="Online")
    session = advance_ai(session)
    return _bundle_outputs(session)


def _continue(session: GameSession):
    if session is None:
        session = new_session(seed=7)
    return _bundle_outputs(advance_ai(session))


def _auto_tick(session: GameSession, autoplay: bool):
    if session is None:
        session = new_session(seed=7)
    if not autoplay:
        return _bundle_outputs(session)
    return _bundle_outputs(advance_ai(session, max_steps=1))


def _send(session: GameSession, message: str):
    session = human_send_message(session, message or "")
    session = advance_ai(session, max_steps=3)
    outputs = _bundle_outputs(session)
    return (*outputs, "")


def _claim(session: GameSession, role_name: str):
    session = human_claim(session, role_name)
    return _bundle_outputs(session)


def _accuse(session: GameSession, target: str):
    session = human_accuse(session, target)
    return _bundle_outputs(session)


def _start_vote(session: GameSession):
    session = human_start_vote(session)
    session = advance_ai(session, max_steps=3)
    return _bundle_outputs(session)


def _vote(session: GameSession, target: str):
    session = human_vote(session, target)
    session = advance_ai(session, max_steps=4)
    return _bundle_outputs(session)


def _night_action(session: GameSession, target: str):
    session = human_night_action(session, target)
    session = advance_ai(session)
    return _bundle_outputs(session)


def _human_can_target_self(session: GameSession) -> bool:
    state = session.state
    human = state.players[state.human_player_id]
    return state.phase == Phase.NIGHT and human.role == Role.DOCTOR


def _initial_outputs():
    session = new_session(seed=7)
    session = advance_ai(session)
    return _bundle_outputs(session)


with gr.Blocks(
    title="Mafia",
    fill_width=True,
) as demo:
    session_state = gr.State()
    with gr.Column(elem_id="mafia-root"):
        gr.HTML(
            """
            <div class="mafia-title">
              <strong>MAFIA</strong>
              <span class="status-line">Online social deduction · holy_grail agents · Time-to-Talk moderator</span>
            </div>
            """
        )
        status = gr.Markdown(elem_classes=["status-line"])
        with gr.Row():
            seed = gr.Number(value=7, label="Seed", precision=0, minimum=1)
            role = gr.Dropdown(["Random", *role_choices()], value="Random", label="Your role")
            gr.Textbox("Online", label="AI runtime", interactive=False)
            autoplay = gr.Checkbox(value=False, label="Autoplay AI turns")
            new_btn = gr.Button("New Game", variant="primary")
            continue_btn = gr.Button("Continue / Let AI Act")

        with gr.Row(elem_classes=["main-grid"]):
            left = ClaimLedger()
            table = MafiaTable()
            right = VoteChatRail()

        with gr.Row(elem_classes=["control-grid"]):
            message = gr.Textbox(
                label="Public message",
                placeholder="Make one short claim, question, accusation, or defense...",
                lines=2,
            )
            target = gr.Dropdown([], label="Target")
            claim_role = gr.Dropdown(role_choices(), value=Role.VILLAGER.value, label="Claim")

        with gr.Row():
            send_btn = gr.Button("Send Message")
            claim_btn = gr.Button("Claim Role")
            accuse_btn = gr.Button("Accuse")
            night_btn = gr.Button("Night Action")
            vote_btn = gr.Button("Vote")
            start_vote_btn = gr.Button("Start Vote")

        replay = ReplayTimeline()
        endgame = EndgameReveal()
        with gr.Accordion("Performance and audit metrics", open=False):
            metrics = MetricsPanel()

    outputs = [
        session_state,
        table,
        left,
        right,
        replay,
        status,
        endgame,
        target,
        metrics,
    ]
    auto_timer = gr.Timer(5, active=True)
    demo.load(_initial_outputs, outputs=outputs)
    new_btn.click(_new_game, inputs=[seed, role], outputs=outputs)
    continue_btn.click(_continue, inputs=[session_state], outputs=outputs)
    auto_timer.tick(_auto_tick, inputs=[session_state, autoplay], outputs=outputs, show_progress="hidden")
    send_btn.click(_send, inputs=[session_state, message], outputs=[*outputs, message])
    claim_btn.click(_claim, inputs=[session_state, claim_role], outputs=outputs)
    accuse_btn.click(_accuse, inputs=[session_state, target], outputs=outputs)
    night_btn.click(_night_action, inputs=[session_state, target], outputs=outputs)
    vote_btn.click(_vote, inputs=[session_state, target], outputs=outputs)
    start_vote_btn.click(_start_vote, inputs=[session_state], outputs=outputs)
    demo.queue(default_concurrency_limit=8)

demo.css = APP_CSS
demo.theme = APP_THEME


def main() -> None:
    demo.launch(css=APP_CSS, theme=APP_THEME)


if __name__ == "__main__":
    main()
