from __future__ import annotations

from typing import Any

import gradio as gr

from gradio.events import Dependency

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
    from typing import Callable, Literal, Sequence, Any, TYPE_CHECKING
    from gradio.blocks import Block
    if TYPE_CHECKING:
        from gradio.components import Timer
        from gradio.components.base import Component


class MafiaTable(MafiaHTML):
    component_name = "MafiaTable"
    from typing import Callable, Literal, Sequence, Any, TYPE_CHECKING
    from gradio.blocks import Block
    if TYPE_CHECKING:
        from gradio.components import Timer
        from gradio.components.base import Component


class ClaimLedger(MafiaHTML):
    component_name = "ClaimLedger"
    from typing import Callable, Literal, Sequence, Any, TYPE_CHECKING
    from gradio.blocks import Block
    if TYPE_CHECKING:
        from gradio.components import Timer
        from gradio.components.base import Component


class VoteChatRail(MafiaHTML):
    component_name = "VoteChatRail"
    from typing import Callable, Literal, Sequence, Any, TYPE_CHECKING
    from gradio.blocks import Block
    if TYPE_CHECKING:
        from gradio.components import Timer
        from gradio.components.base import Component


class ReplayTimeline(MafiaHTML):
    component_name = "ReplayTimeline"
    from typing import Callable, Literal, Sequence, Any, TYPE_CHECKING
    from gradio.blocks import Block
    if TYPE_CHECKING:
        from gradio.components import Timer
        from gradio.components.base import Component


class EndgameReveal(MafiaHTML):
    component_name = "EndgameReveal"
    from typing import Callable, Literal, Sequence, Any, TYPE_CHECKING
    from gradio.blocks import Block
    if TYPE_CHECKING:
        from gradio.components import Timer
        from gradio.components.base import Component


class MetricsPanel(MafiaHTML):
    component_name = "MetricsPanel"
    from typing import Callable, Literal, Sequence, Any, TYPE_CHECKING
    from gradio.blocks import Block
    if TYPE_CHECKING:
        from gradio.components import Timer
        from gradio.components.base import Component
