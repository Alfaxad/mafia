from mafia.engine.reducers import (
    cast_vote,
    create_game,
    resolve_night,
    start_discussion,
    start_vote,
    submit_night_action,
)
from mafia.engine.state import Phase, Role, Team
from mafia.ui.session import GameSession, advance_ai


def test_create_game_has_classic_role_counts():
    state = create_game(seed=42)
    counts = {}
    for player in state.players.values():
        counts[player.role] = counts.get(player.role, 0) + 1
    assert counts == {
        Role.MAFIA: 2,
        Role.DETECTIVE: 1,
        Role.DOCTOR: 1,
        Role.VILLAGER: 3,
    }
    assert len(state.players) == 7
    assert state.phase == Phase.NIGHT


def test_doctor_save_prevents_night_kill():
    state = create_game(seed=10)
    mafia = next(pid for pid, p in state.players.items() if p.role == Role.MAFIA)
    doctor = next(pid for pid, p in state.players.items() if p.role == Role.DOCTOR)
    target = next(pid for pid, p in state.players.items() if p.team == Team.TOWN and pid != doctor)
    assert submit_night_action(state, mafia, "kill", target)
    assert submit_night_action(state, doctor, "protect", target)
    resolve_night(state)
    assert state.players[target].alive
    assert state.phase == Phase.DAWN


def test_doctor_cannot_protect_same_target_twice_in_a_row():
    state = create_game(seed=10)
    doctor = next(pid for pid, p in state.players.items() if p.role == Role.DOCTOR)
    target = next(pid for pid, p in state.players.items() if p.team == Team.TOWN and pid != doctor)
    assert submit_night_action(state, doctor, "protect", target)
    state.night_actions.doctor_protects.clear()
    assert not submit_night_action(state, doctor, "protect", target)


def test_doctor_can_protect_self_but_not_twice_in_a_row():
    state = create_game(seed=10)
    doctor = next(pid for pid, p in state.players.items() if p.role == Role.DOCTOR)
    assert submit_night_action(state, doctor, "protect", doctor)
    state.night_actions.doctor_protects.clear()
    assert not submit_night_action(state, doctor, "protect", doctor)


def test_detective_gets_private_alignment_result():
    state = create_game(seed=14)
    detective = next(pid for pid, p in state.players.items() if p.role == Role.DETECTIVE)
    mafia = next(pid for pid, p in state.players.items() if p.role == Role.MAFIA)
    assert submit_night_action(state, detective, "check", mafia)
    resolve_night(state)
    assert state.players[detective].private_memory["investigations"][mafia] is True


def test_vote_eliminates_plurality_target():
    state = create_game(seed=3)
    resolve_night(state)
    start_discussion(state)
    state.phase = Phase.VOTE
    alive = state.alive_players()
    target = alive[-1]
    for voter in alive[:-1]:
        cast_vote(state, voter, target)
    assert not state.players[target].alive
    assert target in state.eliminated_order


def test_mafia_night_disagreement_still_resolves_team_kill():
    state = create_game(seed=42)
    mafia = [pid for pid, player in state.players.items() if player.role == Role.MAFIA]
    targets = [pid for pid, player in state.players.items() if player.team == Team.TOWN]
    assert len(mafia) == 2
    assert submit_night_action(state, mafia[0], "kill", targets[0])
    assert submit_night_action(state, mafia[1], "kill", targets[1])
    resolve_night(state)
    assert len([pid for pid in targets if not state.players[pid].alive]) == 1
    assert any(event.type == "mafia_consensus" for event in state.events)


def test_vote_phase_waits_for_living_human_vote_before_ai_votes():
    state = create_game(seed=33)
    resolve_night(state)
    start_discussion(state)
    start_vote(state)
    session = GameSession(state=state)

    advance_ai(session, max_steps=3)

    assert state.phase == Phase.VOTE
    assert state.human_player_id not in state.locked_votes
    assert not state.votes
