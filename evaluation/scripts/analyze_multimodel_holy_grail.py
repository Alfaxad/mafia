#!/usr/bin/env python3
"""Aggregate multi-model Holy Grail full-game benchmark rows."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parent
BATCHES = ["batch_bf16_pairwise", "batch_gguf_pairwise", "batch_allstar"]

COMBINED_JSONL = ROOT / "multimodel_holy_grail_combined.jsonl"
SUMMARY_CSV = ROOT / "multimodel_holy_grail_summary.csv"
PAIRWISE_CSV = ROOT / "multimodel_holy_grail_pairwise_matrix.csv"
PLAYER_CSV = ROOT / "multimodel_holy_grail_player_metrics.csv"
MODEL_CSV = ROOT / "multimodel_holy_grail_model_summary.csv"
ROLE_CSV = ROOT / "multimodel_holy_grail_role_summary.csv"
VOTE_CSV = ROOT / "multimodel_holy_grail_vote_summary.csv"
ACTION_CSV = ROOT / "multimodel_holy_grail_role_action_summary.csv"
CALL_CSV = ROOT / "multimodel_holy_grail_call_summary.csv"
ALLSTAR_CSV = ROOT / "multimodel_holy_grail_allstar_player_metrics.csv"
REPORT_MD = ROOT / "multimodel_holy_grail_report.md"

MODEL_LABELS = {
    ("modal_transformers", "Alfaxad/mafia-gemma-4-12B-it"): "Mafia Gemma BF16",
    ("modal_gguf", "Alfaxad/mafia-gemma-4-12B-it-gguf"): "Mafia Gemma GGUF Q8",
    ("openai", "gpt-5"): "GPT-5 medium",
    ("openai", "gpt-5-mini"): "GPT-5-mini",
    ("anthropic", "claude-opus-4-8"): "Claude Opus 4.8",
    ("anthropic", "claude-sonnet-4-6"): "Claude Sonnet 4.6",
    ("osv_gateway", "vertex_ai/gemini-2.5-pro"): "Gemini 2.5 Pro OSV",
    ("modal_base_bf16", "google/gemma-4-12B-it"): "Moderator Gemma 4 12B BF16",
}
LOCAL_ORDER = ["mafia_gemma_bf16", "mafia_gemma_gguf_q8"]
LOCAL_LABELS = {
    "mafia_gemma_bf16": "Mafia Gemma BF16",
    "mafia_gemma_gguf_q8": "Mafia Gemma GGUF Q8",
}
OPPONENT_ORDER = ["gpt5_medium", "gpt5mini", "claude_opus_4_8", "claude_sonnet_4_6", "gemini_2_5_pro_osv"]
OPPONENT_LABELS = {
    "gpt5_medium": "GPT-5 medium",
    "gpt5mini": "GPT-5-mini",
    "claude_opus_4_8": "Claude Opus 4.8",
    "claude_sonnet_4_6": "Claude Sonnet 4.6",
    "gemini_2_5_pro_osv": "Gemini 2.5 Pro OSV",
}
MODEL_ORDER = [
    "Mafia Gemma BF16",
    "Mafia Gemma GGUF Q8",
    "GPT-5 medium",
    "GPT-5-mini",
    "Claude Opus 4.8",
    "Claude Sonnet 4.6",
    "Gemini 2.5 Pro OSV",
]
ROLE_ORDER = {"Mafia": 0, "Detective": 1, "Doctor": 2, "Villager": 3}


def model_label(provider: str, model: str) -> str:
    return MODEL_LABELS.get((provider, model), f"{provider}/{model}")


def read_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch in BATCHES:
        for path in sorted((ROOT / batch).glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                row["_source_batch"] = batch
                row["_source_file"] = str(path.relative_to(ROOT))
                rows.append(row)
    rows.sort(key=lambda row: (row["_source_batch"], row["summary"]["scenario"], row["summary"]["seed"]))
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(key, "")) for _, key in columns) + " |")
    return "\n".join(lines)


def avg(values: list[float]) -> float:
    return mean(values) if values else 0.0


def pair_key(name: str) -> tuple[str, str, str] | None:
    pattern = r"^(mafia_gemma_(?:bf16|gguf_q8))_(mafia|good)_holy_grail_vs_(.+)_(good|mafia)_holy_grail_moderated_quality_ttt$"
    match = re.match(pattern, name)
    if not match:
        return None
    local, local_side, opponent, _opponent_side = match.groups()
    return local, opponent, local_side


def local_won(summary: dict[str, Any]) -> bool | None:
    parsed = pair_key(summary["scenario"])
    if not parsed:
        return None
    _local, _opponent, side = parsed
    return summary["winner"] == side


def flatten_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        s = row["summary"]
        out.append({"source_batch": row["_source_batch"], "source_file": row["_source_file"], **s})
    return out


def build_pairwise(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        s = row["summary"]
        key = pair_key(s["scenario"])
        if key:
            lookup[key] = s
    matrix: list[dict[str, Any]] = []
    for opponent in OPPONENT_ORDER:
        item = {"opponent": OPPONENT_LABELS[opponent]}
        for local in LOCAL_ORDER:
            for side in ("mafia", "good"):
                s = lookup.get((local, opponent, side))
                value = "missing"
                if s:
                    value = "win" if local_won(s) else "loss"
                    if s.get("api_errors", 0) or s.get("parse_failures", 0) or s.get("invalid_actions", 0):
                        value += "*"
                item[f"{local}_{side}"] = value
        matrix.append(item)
    return matrix


def player_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        s = row["summary"]
        is_allstar = s["scenario"].startswith("allstar_")
        for player, values in row["game"].get("player_metrics", {}).items():
            provider = values.get("provider", "")
            model = values.get("model", "")
            role = values.get("role", "")
            faction = values.get("faction", "")
            team_win = int((faction == "mafia" and s["winner"] == "mafia") or (faction == "good" and s["winner"] == "good"))
            out.append(
                {
                    "source_batch": row["_source_batch"],
                    "scenario": s["scenario"],
                    "seed": s["seed"],
                    "winner": s["winner"],
                    "is_allstar": int(is_allstar),
                    "player": player,
                    "model_label": model_label(provider, model),
                    "provider": provider,
                    "model": model,
                    "architecture": values.get("architecture", ""),
                    "role": role,
                    "faction": faction,
                    "team_win": team_win,
                    "alive_final": int(bool(values.get("alive_final"))),
                    "messages_spoken": values.get("messages_spoken", 0) or 0,
                    "votes_cast": values.get("votes_cast", 0) or 0,
                    "votes_received": values.get("votes_received", 0) or 0,
                    "role_claims": values.get("role_claims", 0) or 0,
                    "false_role_claims": values.get("false_role_claims", 0) or 0,
                }
            )
    return out


def vote_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        s = row["summary"]
        roles = row["game"]["roles"]
        player_info = row["game"].get("player_metrics", {})
        for event in row["game"].get("events", []):
            if event.get("type") != "vote":
                continue
            voter = str(event.get("voter"))
            target = str(event.get("target"))
            role = roles.get(voter, "")
            target_role = roles.get(target, "")
            faction = "mafia" if role == "Mafia" else "good"
            correct = int((faction == "good" and target_role == "Mafia") or (faction == "mafia" and target_role != "Mafia"))
            info = player_info.get(voter, {})
            out.append(
                {
                    "scenario": s["scenario"],
                    "seed": s["seed"],
                    "winner": s["winner"],
                    "is_allstar": int(s["scenario"].startswith("allstar_")),
                    "voter": voter,
                    "target": target,
                    "role": role,
                    "faction": faction,
                    "target_role": target_role,
                    "correct_vote": correct,
                    "model_label": model_label(info.get("provider", ""), info.get("model", "")),
                }
            )
    return out


def action_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        s = row["summary"]
        roles = row["game"]["roles"]
        info = row["game"].get("player_metrics", {})
        mafia_targets_by_night = {
            event.get("night"): event.get("target")
            for event in row["game"].get("events", [])
            if event.get("type") == "mafia_kill_vote"
        }
        no_death_by_night = {
            event.get("night"): "No one died" in str(event.get("message", ""))
            for event in row["game"].get("events", [])
            if event.get("type") == "night_result"
        }
        for event in row["game"].get("events", []):
            etype = event.get("type")
            if etype == "detective_check":
                player = str(event.get("detective"))
                target = str(event.get("target"))
                pinfo = info.get(player, {})
                out.append(
                    {
                        "scenario": s["scenario"],
                        "seed": s["seed"],
                        "winner": s["winner"],
                        "is_allstar": int(s["scenario"].startswith("allstar_")),
                        "model_label": model_label(pinfo.get("provider", ""), pinfo.get("model", "")),
                        "player": player,
                        "role": "Detective",
                        "action": "detective_check",
                        "target": target,
                        "target_role": roles.get(target, ""),
                        "success": int(event.get("result") == "Mafia"),
                    }
                )
            elif etype == "doctor_save":
                player = str(event.get("doctor"))
                target = str(event.get("target"))
                night = event.get("night")
                pinfo = info.get(player, {})
                covered = target == mafia_targets_by_night.get(night)
                out.append(
                    {
                        "scenario": s["scenario"],
                        "seed": s["seed"],
                        "winner": s["winner"],
                        "is_allstar": int(s["scenario"].startswith("allstar_")),
                        "model_label": model_label(pinfo.get("provider", ""), pinfo.get("model", "")),
                        "player": player,
                        "role": "Doctor",
                        "action": "doctor_save",
                        "target": target,
                        "target_role": roles.get(target, ""),
                        "success": int(covered and no_death_by_night.get(night, False)),
                    }
                )
            elif etype == "mafia_kill_vote":
                for player, target in (event.get("votes") or {}).items():
                    pinfo = info.get(player, {})
                    out.append(
                        {
                            "scenario": s["scenario"],
                            "seed": s["seed"],
                            "winner": s["winner"],
                            "is_allstar": int(s["scenario"].startswith("allstar_")),
                            "model_label": model_label(pinfo.get("provider", ""), pinfo.get("model", "")),
                            "player": player,
                            "role": "Mafia",
                            "action": "mafia_kill_vote",
                            "target": target,
                            "target_role": roles.get(str(target), ""),
                            "success": int(roles.get(str(target)) in {"Detective", "Doctor"}),
                        }
                    )
    return out


def summarize_model(players: list[dict[str, Any]], allstar_only: bool = False) -> list[dict[str, Any]]:
    source = [row for row in players if row["is_allstar"]] if allstar_only else players
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source:
        grouped[row["model_label"]].append(row)
    out: list[dict[str, Any]] = []
    for label in sorted(grouped, key=lambda value: MODEL_ORDER.index(value) if value in MODEL_ORDER else 999):
        items = grouped[label]
        out.append(
            {
                "model": label,
                "scope": "allstar_only" if allstar_only else "all_games",
                "player_slots": len(items),
                "team_win_rate": avg([float(item["team_win"]) for item in items]),
                "alive_final_rate": avg([float(item["alive_final"]) for item in items]),
                "avg_messages_spoken": avg([float(item["messages_spoken"]) for item in items]),
                "avg_votes_cast": avg([float(item["votes_cast"]) for item in items]),
                "avg_votes_received": avg([float(item["votes_received"]) for item in items]),
                "avg_role_claims": avg([float(item["role_claims"]) for item in items]),
                "avg_false_role_claims": avg([float(item["false_role_claims"]) for item in items]),
            }
        )
    return out


def summarize_roles(players: list[dict[str, Any]], votes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    vote_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in votes:
        vote_group[(row["model_label"], row["role"])].append(row)
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in players:
        grouped[(row["model_label"], row["role"])].append(row)
    out: list[dict[str, Any]] = []
    for (label, role), items in sorted(
        grouped.items(),
        key=lambda item: (
            MODEL_ORDER.index(item[0][0]) if item[0][0] in MODEL_ORDER else 999,
            ROLE_ORDER.get(item[0][1], 999),
        ),
    ):
        role_votes = vote_group.get((label, role), [])
        out.append(
            {
                "model": label,
                "role": role,
                "player_slots": len(items),
                "team_win_rate": avg([float(item["team_win"]) for item in items]),
                "alive_final_rate": avg([float(item["alive_final"]) for item in items]),
                "vote_accuracy": avg([float(item["correct_vote"]) for item in role_votes]) if role_votes else 0.0,
                "votes": len(role_votes),
                "avg_messages_spoken": avg([float(item["messages_spoken"]) for item in items]),
                "avg_votes_received": avg([float(item["votes_received"]) for item in items]),
                "avg_role_claims": avg([float(item["role_claims"]) for item in items]),
                "avg_false_role_claims": avg([float(item["false_role_claims"]) for item in items]),
            }
        )
    return out


def summarize_votes(votes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in votes:
        grouped[(row["model_label"], row["faction"])].append(row)
    out: list[dict[str, Any]] = []
    for (label, faction), items in sorted(grouped.items(), key=lambda item: (MODEL_ORDER.index(item[0][0]) if item[0][0] in MODEL_ORDER else 999, item[0][1])):
        out.append(
            {
                "model": label,
                "faction": faction,
                "votes": len(items),
                "vote_accuracy": avg([float(item["correct_vote"]) for item in items]),
            }
        )
    return out


def summarize_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in actions:
        grouped[(row["model_label"], row["action"])].append(row)
    out: list[dict[str, Any]] = []
    for (label, action), items in sorted(grouped.items(), key=lambda item: (MODEL_ORDER.index(item[0][0]) if item[0][0] in MODEL_ORDER else 999, item[0][1])):
        out.append(
            {
                "model": label,
                "action": action,
                "count": len(items),
                "success_rate": avg([float(item["success"]) for item in items]),
            }
        )
    return out


def summarize_calls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for record in row["game"].get("stats", {}).get("call_records", []):
            label = model_label(record.get("provider", ""), record.get("model", ""))
            if label.startswith("Moderator"):
                label = "Moderator Gemma 4 12B BF16"
            action = str(record.get("action", ""))
            is_moderator_actor = record.get("player") == "Moderator" or record.get("role") == "Moderator"
            action_group = "moderator" if is_moderator_actor else "player"
            grouped[(label, action_group)].append(record)
    out: list[dict[str, Any]] = []
    order = [*MODEL_ORDER, "Moderator Gemma 4 12B BF16"]
    for (label, action_group), items in sorted(grouped.items(), key=lambda item: (order.index(item[0][0]) if item[0][0] in order else 999, item[0][1])):
        latencies = [float(item.get("latency_sec", 0) or 0) for item in items]
        out.append(
            {
                "model": label,
                "action_group": action_group,
                "calls": len(items),
                "avg_latency_sec": avg(latencies),
                "max_latency_sec": max(latencies) if latencies else 0.0,
                "avg_output_chars": avg([float(item.get("output_chars", 0) or 0) for item in items]),
                "failed_calls": sum(0 if item.get("ok", True) else 1 for item in items),
            }
        )
    return out


def write_report(
    rows: list[dict[str, Any]],
    pairwise: list[dict[str, Any]],
    model_summary: list[dict[str, Any]],
    role_summary: list[dict[str, Any]],
    vote_summary: list[dict[str, Any]],
    action_summary: list[dict[str, Any]],
    call_summary: list[dict[str, Any]],
) -> None:
    summaries = [row["summary"] for row in rows]
    winners = Counter(item["winner"] for item in summaries)
    total_errors = sum(
        int(item.get(key, 0) or 0)
        for item in summaries
        for key in ("api_errors", "parse_failures", "invalid_actions", "moderator_parse_failures")
    )
    pairwise_summaries = [item for item in summaries if pair_key(item["scenario"])]
    allstar_summaries = [item for item in summaries if item["scenario"].startswith("allstar_")]
    local_counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for s in pairwise_summaries:
        local, _opponent, side = pair_key(s["scenario"]) or ("", "", "")
        local_counts[(LOCAL_LABELS[local], side)]["games"] += 1
        if local_won(s):
            local_counts[(LOCAL_LABELS[local], side)]["wins"] += 1

    all_games_model = [row for row in model_summary if row["scope"] == "all_games"]
    allstar_model = [row for row in model_summary if row["scope"] == "allstar_only"]
    player_calls = [row for row in call_summary if row["action_group"] == "player"]

    lines = [
        "# Multi-Model Holy Grail Full-Game Benchmark",
        "",
        "Date: 2026-06-13 JST.",
        "",
        "This reruns the moderated flagship-style evaluation with every player agent using Holy Grail. Claude Fable 5 is intentionally excluded. The non-player Moderator/Narrator is fixed to base Gemma 4 12B BF16 with the Time-to-Talk scheduler plus generator pattern.",
        "",
        "## Controls",
        "",
        "- Roles: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.",
        "- Win conditions: Mafia parity or all Mafia eliminated.",
        "- Player architecture: `holy_grail` for every player model.",
        "- Moderator: `modal_base_bf16/google/gemma-4-12B-it:baseline`.",
        "- Gemma sampler for base moderator, Mafia Gemma BF16, and Mafia Gemma GGUF Q8: `temperature=1.0`, `top_p=0.95`, `top_k=64`.",
        "- Models: Mafia Gemma BF16, Mafia Gemma GGUF Q8, GPT-5 medium, GPT-5-mini, Claude Opus 4.8, Claude Sonnet 4.6, Gemini 2.5 Pro OSV.",
        "- Rows: 20 local-vs-frontier pairwise games plus 4 mixed all-star rotation games.",
        f"- Validation: total API/player/moderator errors across rows = {total_errors}.",
        "",
        "## High-Level Outcome",
        "",
        f"Completed games: {len(rows)}. Pairwise games: {len(pairwise_summaries)}. All-star games: {len(allstar_summaries)}.",
        "",
        "| winner | games |",
        "|---|---:|",
    ]
    for winner, count in sorted(winners.items()):
        lines.append(f"| {winner} | {count} |")

    lines.extend(
        [
            "",
            "## Pairwise Local-vs-Frontier Matrix",
            "",
            "`win` means the local Mafia Gemma side won that row. All rows use Holy Grail on both sides.",
            "",
            "| opponent | BF16 as Mafia | BF16 as Good | GGUF Q8 as Mafia | GGUF Q8 as Good |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in pairwise:
        lines.append(
            f"| {row['opponent']} | {row['mafia_gemma_bf16_mafia']} | {row['mafia_gemma_bf16_good']} | "
            f"{row['mafia_gemma_gguf_q8_mafia']} | {row['mafia_gemma_gguf_q8_good']} |"
        )

    lines.extend(["", "## Local Side Win Counts", "", "| local model | side | wins | games |", "|---|---|---:|---:|"])
    for local in ("Mafia Gemma BF16", "Mafia Gemma GGUF Q8"):
        for side in ("mafia", "good"):
            counts = local_counts[(local, side)]
            lines.append(f"| {local} | {side} | {counts['wins']} | {counts['games']} |")

    lines.extend(
        [
            "",
            "## Model Slot Scoreboard",
            "",
            "This counts each player slot, so pairwise rows heavily weight the two local models and their current opponent. The all-star-only table is the cleaner mixed-table view but has just four games.",
            "",
            "### All Games",
            "",
            markdown_table(
                all_games_model,
                [
                    ("Model", "model"),
                    ("Slots", "player_slots"),
                    ("Team WR", "team_win_rate"),
                    ("Alive", "alive_final_rate"),
                    ("Messages", "avg_messages_spoken"),
                    ("Votes", "avg_votes_cast"),
                    ("Votes received", "avg_votes_received"),
                    ("Claims", "avg_role_claims"),
                    ("False claims", "avg_false_role_claims"),
                ],
            ),
            "",
            "### All-Star Only",
            "",
            markdown_table(
                allstar_model,
                [
                    ("Model", "model"),
                    ("Slots", "player_slots"),
                    ("Team WR", "team_win_rate"),
                    ("Alive", "alive_final_rate"),
                    ("Messages", "avg_messages_spoken"),
                    ("Votes", "avg_votes_cast"),
                    ("Votes received", "avg_votes_received"),
                ],
            ),
            "",
            "## Role-Level Summary",
            "",
            markdown_table(
                role_summary,
                [
                    ("Model", "model"),
                    ("Role", "role"),
                    ("Slots", "player_slots"),
                    ("Team WR", "team_win_rate"),
                    ("Alive", "alive_final_rate"),
                    ("Vote acc", "vote_accuracy"),
                    ("Votes", "votes"),
                    ("Messages", "avg_messages_spoken"),
                    ("Votes received", "avg_votes_received"),
                    ("Claims", "avg_role_claims"),
                    ("False claims", "avg_false_role_claims"),
                ],
            ),
            "",
            "## Vote And Role-Action Diagnostics",
            "",
            "### Vote Accuracy By Faction",
            "",
            markdown_table(vote_summary, [("Model", "model"), ("Faction", "faction"), ("Votes", "votes"), ("Vote acc", "vote_accuracy")]),
            "",
            "### Night / Power Action Quality",
            "",
            "For Detective, success means a Mafia hit. For Doctor, success means covering the Mafia kill target. For Mafia kill votes, success means targeting a power role.",
            "",
            markdown_table(action_summary, [("Model", "model"), ("Action", "action"), ("Count", "count"), ("Success rate", "success_rate")]),
            "",
            "## Low-Level Call Metrics",
            "",
            markdown_table(
                player_calls,
                [
                    ("Model", "model"),
                    ("Calls", "calls"),
                    ("Avg latency sec", "avg_latency_sec"),
                    ("Max latency sec", "max_latency_sec"),
                    ("Avg output chars", "avg_output_chars"),
                    ("Failed calls", "failed_calls"),
                ],
            ),
            "",
            "## Interpretation",
            "",
            "- Holy Grail changed the balance toward Town compared with the older corrected-moderator report: 16/24 total games were Good wins, and the pairwise matrix no longer shows a broad Mafia-side sweep.",
            "- Mafia Gemma BF16 became strong as Good under Holy Grail, winning 4/5 local-good pairwise rows. Its Mafia side was much weaker in this sample, winning only against Claude Sonnet.",
            "- Mafia Gemma GGUF Q8 was the more volatile local model: it beat GPT-5 medium and GPT-5-mini as Mafia, but lost both Opus and Gemini Mafia-side rows. As Good, it beat GPT-5-mini, Opus, and Sonnet, but lost to GPT-5 medium and Gemini.",
            "- GPT-5 medium remained the toughest frontier opponent overall in pairwise side tests: it beat BF16 in both directions and split against GGUF, losing only when GGUF played Mafia.",
            "- Claude Opus 4.8 was strongest against local Mafia but weaker when its own Mafia side faced local Good. That matches the same-model result where Opus did not need Holy Grail as much as smaller/local models but still benefited from efficient structure.",
            "- Gemini 2.5 Pro OSV beat both local Mafia sides and beat GGUF Good when Gemini played Mafia; BF16 Good beat Gemini Mafia. Its all-games slot score was still the highest in this run, but the pairwise result is not a clean sweep.",
            "- The all-star rows are too few for a ranking by themselves, but they are useful qualitatively: mixed tables did not collapse into automatic Mafia wins; Town won 3/4 all-star rotations.",
            "",
            "## Artifacts",
            "",
            f"- Scenario config: `{(ROOT / 'multimodel_holy_grail_scenarios.json').name}`",
            f"- Combined raw games: `{COMBINED_JSONL.name}`",
            f"- Summary CSV: `{SUMMARY_CSV.name}`",
            f"- Pairwise matrix: `{PAIRWISE_CSV.name}`",
            f"- Player metrics: `{PLAYER_CSV.name}`",
            f"- Model summary: `{MODEL_CSV.name}`",
            f"- Role summary: `{ROLE_CSV.name}`",
            f"- Vote summary: `{VOTE_CSV.name}`",
            f"- Role action summary: `{ACTION_CSV.name}`",
            f"- Call summary: `{CALL_CSV.name}`",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = read_rows()
    if len(rows) != 24:
        raise SystemExit(f"Expected 24 rows, found {len(rows)}")
    COMBINED_JSONL.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    summaries = flatten_summary(rows)
    pairwise = build_pairwise(rows)
    players = player_rows(rows)
    votes = vote_rows(rows)
    actions = action_rows(rows)
    model_summary = [*summarize_model(players, allstar_only=False), *summarize_model(players, allstar_only=True)]
    role_summary = summarize_roles(players, votes)
    vote_summary = summarize_votes(votes)
    action_summary = summarize_actions(actions)
    call_summary = summarize_calls(rows)
    allstar_players = [row for row in players if row["is_allstar"]]

    write_csv(SUMMARY_CSV, summaries)
    write_csv(PAIRWISE_CSV, pairwise)
    write_csv(PLAYER_CSV, players)
    write_csv(MODEL_CSV, model_summary)
    write_csv(ROLE_CSV, role_summary)
    write_csv(VOTE_CSV, vote_summary)
    write_csv(ACTION_CSV, action_summary)
    write_csv(CALL_CSV, call_summary)
    write_csv(ALLSTAR_CSV, allstar_players)
    write_report(rows, pairwise, model_summary, role_summary, vote_summary, action_summary, call_summary)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "combined": str(COMBINED_JSONL),
                "summary": str(SUMMARY_CSV),
                "pairwise": str(PAIRWISE_CSV),
                "players": str(PLAYER_CSV),
                "model_summary": str(MODEL_CSV),
                "role_summary": str(ROLE_CSV),
                "vote_summary": str(VOTE_CSV),
                "action_summary": str(ACTION_CSV),
                "call_summary": str(CALL_CSV),
                "report": str(REPORT_MD),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
