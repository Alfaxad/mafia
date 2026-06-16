# Gradio Component Plan

The first playable build uses Python `gr.HTML` subclasses in `src/mafia/ui/custom_components.py`.
Those classes define stable component boundaries for:

- `MafiaTable`
- `ClaimLedger`
- `VoteChatRail`
- `ReplayTimeline`
- `EndgameReveal`
- `MetricsPanel`

Once the engine and interaction loop are stable, each class can be replaced with a packaged
Svelte Gradio custom component without changing the session controller.
