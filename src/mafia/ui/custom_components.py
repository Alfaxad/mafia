from __future__ import annotations

from typing import Any

import gradio as gr


class MafiaHTML(gr.HTML):
    """Small reusable Gradio HTML component base for the Mafia UI.

    These are product-facing custom components in Python first. The API boundary
    stays stable so each class can later be replaced by a packaged Svelte Gradio
    component without rewriting the session logic.
    """

    component_name = "MafiaHTML"

    def __init__(self, value: str | None = None, **kwargs: Any):
        super().__init__(value=value or "", container=False, padding=False, **kwargs)

    def api_info(self) -> dict[str, str]:
        return {"type": "string", "description": f"Rendered HTML for {self.component_name}."}


class MafiaTable(MafiaHTML):
    component_name = "MafiaTable"


class ClaimLedger(MafiaHTML):
    component_name = "ClaimLedger"


class VoteChatRail(MafiaHTML):
    component_name = "VoteChatRail"


class ReplayTimeline(MafiaHTML):
    component_name = "ReplayTimeline"


class EndgameReveal(MafiaHTML):
    component_name = "EndgameReveal"


class MetricsPanel(MafiaHTML):
    component_name = "MetricsPanel"
