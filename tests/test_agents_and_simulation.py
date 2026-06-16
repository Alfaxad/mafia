from mafia.agents.moderator_ttt import ModeratorAgent
from mafia.engine.reducers import create_game, resolve_night, start_discussion
from mafia.engine.state import Phase
from mafia.metrics import game_metrics
from mafia.models.provider_types import GenerationResult
from mafia.simulation import run_batch, run_policy_game


class BadVoteEvidenceCueProvider:
    app_name = "test"
    model_label = "test"

    def generate(self, prompt, max_tokens=192, temperature=1.0, top_p=0.95, top_k=64):
        return GenerationResult(
            text='{"target":"p2","message_type":"pressure","cue":"Nora, explain your vote reason."}',
            backend="test",
            model="test",
        )


def test_moderator_cues_discussion_floor():
    state = create_game(seed=5)
    resolve_night(state)
    start_discussion(state)
    moderator = ModeratorAgent()
    assert state.phase == Phase.DISCUSSION
    assert moderator.maybe_cue(state)
    assert state.events[-1].type == "moderator_cue"


def test_moderator_repairs_generated_vote_cue_before_votes_exist():
    state = create_game(seed=5)
    resolve_night(state)
    start_discussion(state)
    moderator = ModeratorAgent(provider=BadVoteEvidenceCueProvider())

    _target, cue, _message_type = moderator.generate_cue(state, 3, ["p2"])

    assert "vote reason" not in cue.lower()
    assert "vote pattern" not in cue.lower()


def test_policy_full_game_completes():
    state = run_policy_game(seed=8, max_days=6)
    metrics = game_metrics(state)
    assert metrics["winner"] in {"town", "mafia"}
    assert metrics["event_count"] > 0
    assert metrics["invalid_actions"] == 0


def test_twenty_policy_playtests_complete():
    rows = run_batch(20)
    assert len(rows) == 20
    assert all(row["winner"] in {"town", "mafia"} for row in rows)
    assert sum(row["invalid_actions"] for row in rows) == 0
