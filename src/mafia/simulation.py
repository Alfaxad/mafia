from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from mafia.agents.holy_grail import HolyGrailAgent
from mafia.agents.moderator_ttt import ModeratorAgent
from mafia.engine.reducers import (
    accuse,
    add_message,
    cast_vote,
    create_game,
    resolve_night,
    start_discussion,
    start_vote,
    submit_night_action,
)
from mafia.engine.state import GameState, Phase, Role
from mafia.metrics import game_metrics


def run_policy_game(seed: int = 1, human_role: Role | None = None, max_days: int = 5) -> GameState:
    state = create_game(seed=seed, human_role=human_role)
    agents = {pid: HolyGrailAgent(pid) for pid, player in state.players.items() if not player.is_human}
    agents[state.human_player_id] = HolyGrailAgent(state.human_player_id)
    moderator = ModeratorAgent()
    while state.winner is None and state.day_number <= max_days:
        if state.phase == Phase.NIGHT:
            for pid in state.alive_players():
                decision = agents[pid].decide(state)
                if decision.action in {"kill", "check", "protect"} and decision.target:
                    submit_night_action(state, pid, decision.action, decision.target)
            resolve_night(state)
        elif state.phase == Phase.DAWN:
            start_discussion(state)
        elif state.phase == Phase.DISCUSSION:
            moderator.maybe_cue(state)
            for pid in state.alive_players():
                decision = agents[pid].decide(state)
                if decision.action == "message":
                    add_message(
                        state,
                        pid,
                        decision.message,
                        speech_act=decision.speech_act,
                        emotion=decision.emotion,
                    )
            alive = state.alive_players()
            if len(alive) > 2:
                accuser = alive[0]
                target = agents[accuser].decide(state).target or alive[-1]
                if target == accuser:
                    target = alive[-1]
                accuse(state, accuser, target)
            else:
                start_vote(state)
        elif state.phase == Phase.HOT_SEAT:
            moderator.maybe_cue(state)
            start_vote(state)
        elif state.phase == Phase.VOTE:
            moderator.maybe_cue(state)
            for pid in list(state.alive_players()):
                if pid in state.locked_votes:
                    continue
                decision = agents[pid].decide(state)
                if decision.target:
                    cast_vote(state, pid, decision.target, lock=True)
            if state.phase == Phase.VOTE:
                # Safety fallback for impossible loops.
                start_vote(state)
        else:
            break
    return state


def run_batch(n: int, out_dir: str | Path | None = None) -> list[dict]:
    rows = []
    for seed in range(1, n + 1):
        state = run_policy_game(seed=seed)
        rows.append(game_metrics(state))
    if out_dir:
        path = Path(out_dir)
        path.mkdir(parents=True, exist_ok=True)
        with (path / "policy_batch_metrics.jsonl").open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        aggregate = {
            "n": len(rows),
            "winners": dict(Counter(row["winner"] for row in rows)),
            "avg_days": sum(row["days"] for row in rows) / len(rows),
            "avg_messages": sum(row["messages"] for row in rows) / len(rows),
            "invalid_actions": sum(row["invalid_actions"] for row in rows),
            "validator_repairs": sum(row["validator_repairs"] for row in rows),
        }
        (path / "policy_batch_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--out-dir", default="reports/playtests")
    args = parser.parse_args()
    rows = run_batch(args.games, args.out_dir)
    print(json.dumps({"games": len(rows), "winners": dict(Counter(row["winner"] for row in rows))}, indent=2))


run_engine_policy_game = run_policy_game


if __name__ == "__main__":
    main()
