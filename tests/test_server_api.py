from fastapi.testclient import TestClient

from mafia.engine.reducers import create_game, submit_night_action
from mafia.engine.state import Role
from mafia.server.app import app
from mafia.server.app import view
from mafia.ui.session import GameSession


def test_ready_and_new_game_use_human_name(monkeypatch):
    from mafia.models.provider_types import GenerationResult

    monkeypatch.setattr(
        "mafia.models.modal_client.ModalModelClient.generate",
        lambda self, *args, **kwargs: GenerationResult(
            text='{"ready":true}',
            backend="test",
            model=self.model_label,
            latency_seconds=0.01,
        ),
    )
    client = TestClient(app)

    ready = client.post("/api/ready", json={"agent_mode": "Online"})
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    assert ready.json()["agentMode"] == "Online"

    game = client.post(
        "/api/game",
        json={
            "seed": 23,
            "human_name": "Asha",
            "human_role": "Random",
            "agent_mode": "Online",
            "human_avatar": "player_female_generated",
        },
    )
    assert game.status_code == 200
    payload = game.json()
    assert payload["human"]["name"] == "Asha"
    assert payload["players"][0]["name"] == "Asha"
    assert payload["humanAvatar"] == "player_female_generated"


def test_doctor_target_choices_are_legal_and_role_hidden():
    state = create_game(seed=33, human_name="Doc", human_role=Role.DOCTOR)
    session = GameSession(state=state)

    payload = view(session)
    choices = payload["targetChoices"]
    assert choices
    assert any(choice["id"] == state.human_player_id for choice in choices)
    assert all(role.value not in choice["label"] for role in Role for choice in choices)

    protected = choices[0]["id"]
    assert submit_night_action(state, state.human_player_id, "protect", protected)
    payload = view(session)
    assert protected not in {choice["id"] for choice in payload["targetChoices"]}
