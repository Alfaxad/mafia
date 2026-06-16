import json

from mafia.engine.reducers import add_message, create_game, resolve_night, start_discussion, submit_night_action
from mafia.engine.state import Role, Team
from mafia.engine.views import legal_actions_for, private_event_dict, private_view, public_view


def test_public_view_does_not_leak_living_roles():
    state = create_game(seed=42)
    view = public_view(state)
    serialized = json.dumps(view)
    assert "mafia_team" not in serialized
    for pid, player in state.players.items():
        if player.alive:
            assert view["players"][pid]["revealed_role"] is None


def test_mafia_private_view_knows_only_mafia_team():
    state = create_game(seed=42)
    mafia = next(pid for pid, player in state.players.items() if player.role == Role.MAFIA)
    view = private_view(state, mafia)
    assert "mafia_team" in view["private_info"]
    assert len(view["private_info"]["mafia_team"]) == 2


def test_detective_result_is_private_not_public():
    state = create_game(seed=44)
    detective = next(pid for pid, player in state.players.items() if player.role == Role.DETECTIVE)
    mafia = next(pid for pid, player in state.players.items() if player.role == Role.MAFIA)
    submit_night_action(state, detective, "check", mafia)
    resolve_night(state)
    assert mafia in private_view(state, detective)["private_info"]["investigations"]
    assert "is_mafia" not in json.dumps(public_view(state))


def test_dead_roles_stay_hidden_until_game_over():
    state = create_game(seed=18)
    mafia = next(pid for pid, player in state.players.items() if player.role == Role.MAFIA)
    victim = next(pid for pid, player in state.players.items() if player.team == Team.TOWN)
    assert submit_night_action(state, mafia, "kill", victim)
    resolve_night(state)

    view = public_view(state)
    assert view["players"][victim]["alive"] is False
    assert view["players"][victim]["revealed_role"] is None
    assert state.players[victim].role.value not in json.dumps(view["events"])


def test_vote_start_is_moderator_owned():
    state = create_game(seed=20)
    resolve_night(state)
    start_discussion(state)
    for pid in state.alive_players():
        assert "start_vote" not in legal_actions_for(state, pid)


def test_mafia_consensus_event_is_private_to_mafia():
    state = create_game(seed=42)
    mafia = [pid for pid, player in state.players.items() if player.role == Role.MAFIA]
    town = [pid for pid, player in state.players.items() if player.team == Team.TOWN]
    submit_night_action(state, mafia[0], "kill", town[0])
    submit_night_action(state, mafia[1], "kill", town[1])
    resolve_night(state)
    event = next(event for event in state.events if event.type == "mafia_consensus")

    mafia_view = private_event_dict(state, event, mafia[0])
    town_view = private_event_dict(state, event, town[0])

    assert mafia_view is not None
    assert mafia_view["payload"]["private"] is True
    assert town_view is None


def test_targeted_moderator_cue_is_private_to_target_only():
    state = create_game(seed=42)
    target = "p2"
    other = "p3"
    add_message(
        state,
        "moderator",
        "Nora, give one concrete read.",
        speech_act="floor_cue",
        emotion="neutral",
        source="ttt",
        metadata={"target": target, "message_type": "evidence"},
    )
    event = state.events[-1]

    assert "Nora, give one concrete read." not in json.dumps(public_view(state))
    assert private_event_dict(state, event, other) is None

    target_event = private_event_dict(state, event, target)
    assert target_event is not None
    assert target_event["type"] == "private_moderator_cue"
    assert target_event["payload"]["private"] is True
