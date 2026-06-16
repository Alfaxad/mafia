from mafia.agents.base import AgentDecision
from mafia.agents.holy_grail import HolyGrailAgent
from mafia.agents.model_backed import _sanitize_model_message, _validate_decision
from mafia.engine.reducers import create_game
from mafia.engine.state import Phase, Role


def test_model_message_rewrites_raw_ids_and_self_possessive():
    state = create_game(seed=42)
    state.players["p7"].display_name = "Owen"

    message = _sanitize_model_message(
        state,
        "p7",
        "Peter, your silence on Owen's role is suspicious. Why did you vote p5 twice?",
    )

    assert "p5" not in message
    assert "Owen's role" not in message
    assert "Jules" in message
    assert "my role" in message


def test_model_message_with_unsupported_vote_evidence_falls_back_before_votes():
    state = create_game(seed=42)
    fallback = AgentDecision(
        action="message",
        target="p2",
        message="Nora is staying vague about who looks Mafia.",
        speech_act="accusation",
        emotion="pressing",
    )
    decision = AgentDecision(
        action="message",
        target="p2",
        message="Nora's voting pattern is suspicious.",
        speech_act="accusation",
        emotion="pressing",
    )

    repaired = _validate_decision(
        state,
        "p3",
        decision,
        fallback,
        ["message"],
        ["p2", "p4"],
    )

    assert repaired.message == fallback.message


def test_holy_grail_does_not_cite_votes_before_public_votes_exist():
    state = create_game(seed=42)
    state.phase = Phase.DISCUSSION
    mafia = next(pid for pid, player in state.players.items() if player.role == Role.MAFIA)

    decision = HolyGrailAgent(mafia).decide(state)

    assert "vote pattern" not in decision.message.lower()
    assert "voting pattern" not in decision.message.lower()


def test_holy_grail_does_not_cite_claims_before_public_claims_exist_on_hot_seat():
    state = create_game(seed=42)
    detective = next(pid for pid, player in state.players.items() if player.role == Role.DETECTIVE)
    state.phase = Phase.HOT_SEAT
    state.hot_seat_target = detective

    decision = HolyGrailAgent(detective).decide(state)

    assert "claim" not in decision.message.lower()


def test_holy_grail_asks_silent_target_for_read_instead_of_inventing_vagueness():
    state = create_game(seed=42)
    state.phase = Phase.DISCUSSION
    mafia = next(pid for pid, player in state.players.items() if player.role == Role.MAFIA)

    decision = HolyGrailAgent(mafia).decide(state)

    assert "give one clear read" in decision.message.lower()
    assert "staying vague" not in decision.message.lower()
