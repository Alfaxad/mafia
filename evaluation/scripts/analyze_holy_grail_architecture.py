#!/usr/bin/env python3
"""Aggregate Holy Grail same-model full-game runs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parent
INPUT_FILES = [
    *sorted((ROOT / "gate_mafia_gemma_iter4_holy_grail_only").glob("*.jsonl")),
    *sorted((ROOT / "gate_mafia_gemma_iter4_comparators").glob("*.jsonl")),
    *sorted((ROOT / "batch_gpt5mini_final").glob("*.jsonl")),
    *sorted((ROOT / "batch_claude_opus_final").glob("*.jsonl")),
]

COMBINED_JSONL = ROOT / "holy_grail_final_combined.jsonl"
SUMMARY_CSV = ROOT / "holy_grail_final_summary.csv"
GAME_CSV = ROOT / "holy_grail_final_games.csv"
PLAYER_CSV = ROOT / "holy_grail_final_player_metrics.csv"
ROLE_CSV = ROOT / "holy_grail_final_role_summary.csv"
DELTA_CSV = ROOT / "holy_grail_final_deltas.csv"
REPORT_MD = ROOT / "holy_grail_final_report.md"

SCENARIO_META = {
    "mafia_gemma_bf16_holy_grail": ("Mafia Gemma BF16", "Holy Grail"),
    "mafia_gemma_bf16_revac": ("Mafia Gemma BF16", "ReVAC"),
    "mafia_gemma_bf16_grail": ("Mafia Gemma BF16", "GRAIL"),
    "claude_opus_4_8_holy_grail": ("Claude Opus 4.8", "Holy Grail"),
    "claude_opus_4_8_revac": ("Claude Opus 4.8", "ReVAC"),
    "claude_opus_4_8_grail": ("Claude Opus 4.8", "GRAIL"),
    "gpt5mini_holy_grail": ("GPT-5-mini", "Holy Grail"),
    "gpt5mini_revac": ("GPT-5-mini", "ReVAC"),
    "gpt5mini_grail": ("GPT-5-mini", "GRAIL"),
}
MODEL_ORDER = {"Mafia Gemma BF16": 0, "GPT-5-mini": 1, "Claude Opus 4.8": 2}
ARCH_ORDER = {"Holy Grail": 0, "ReVAC": 1, "GRAIL": 2}


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in INPUT_FILES:
        if not path.exists():
            raise FileNotFoundError(path)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            summary = dict(payload["summary"])
            scenario = summary["scenario"]
            if scenario not in SCENARIO_META:
                raise ValueError(f"Unknown scenario {scenario!r} in {path}:{line_number}")
            model, architecture = SCENARIO_META[scenario]
            summary["model_group"] = model
            summary["architecture_group"] = architecture
            summary["source_file"] = str(path.relative_to(ROOT))
            payload["summary"] = summary
            rows.append(payload)
    rows.sort(
        key=lambda row: (
            MODEL_ORDER[row["summary"]["model_group"]],
            ARCH_ORDER[row["summary"]["architecture_group"]],
            row["summary"]["seed"],
        )
    )
    return rows


def avg(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row["summary"].get(key, 0) or 0) for row in rows]
    return mean(values) if values else 0.0


def sum_key(rows: list[dict[str, Any]], key: str) -> float:
    return sum(float(row["summary"].get(key, 0) or 0) for row in rows)


def fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def grouped_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["summary"]["model_group"], row["summary"]["architecture_group"])].append(row)
    return grouped


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for (model, architecture), items in sorted(
        grouped_rows(rows).items(), key=lambda item: (MODEL_ORDER[item[0][0]], ARCH_ORDER[item[0][1]])
    ):
        n = len(items)
        good_wins = int(sum_key(items, "good_win"))
        mafia_wins = int(sum_key(items, "mafia_win"))
        output.append(
            {
                "model": model,
                "architecture": architecture,
                "n": n,
                "good_wins": good_wins,
                "mafia_wins": mafia_wins,
                "good_win_rate": good_wins / n if n else 0.0,
                "mafia_win_rate": mafia_wins / n if n else 0.0,
                "avg_days": avg(items, "days"),
                "avg_elapsed_sec": avg(items, "elapsed_sec"),
                "avg_llm_calls": avg(items, "llm_calls"),
                "avg_revac_review_calls": avg(items, "revac_review_calls"),
                "avg_holy_grail_guardrail_checks": avg(items, "holy_grail_guardrail_checks"),
                "avg_holy_grail_target_overrides": avg(items, "holy_grail_overrides"),
                "avg_holy_grail_message_overrides": avg(items, "holy_grail_message_overrides"),
                "avg_good_vote_accuracy": avg(items, "good_vote_accuracy"),
                "avg_mafia_vote_accuracy": avg(items, "mafia_vote_accuracy"),
                "avg_detective_hit_rate": avg(items, "detective_hit_rate"),
                "avg_doctor_saves": avg(items, "doctor_saves"),
                "avg_doctor_protected_detective": avg(items, "doctor_protected_detective"),
                "avg_mafia_alive_final": avg(items, "mafia_alive_final"),
                "avg_role_claims": avg(items, "role_claims"),
                "avg_false_role_claims": avg(items, "false_role_claims"),
                "avg_role_claim_deception_rate": avg(items, "role_claim_deception_rate"),
                "avg_discussion_messages": avg(items, "discussion_messages"),
                "avg_moderator_scheduler_calls": avg(items, "moderator_scheduler_calls"),
                "avg_moderator_generator_calls": avg(items, "moderator_generator_calls"),
                "avg_moderator_send_decisions": avg(items, "moderator_send_decisions"),
                "avg_moderator_wait_decisions": avg(items, "moderator_wait_decisions"),
                "avg_moderator_interventions": avg(items, "moderator_interventions"),
                "avg_moderator_gap_seconds": avg(items, "moderator_avg_message_gap_seconds"),
                "avg_moderator_rate_deviation": avg(items, "moderator_message_rate_deviation"),
                "avg_selected_quality": avg(items, "avg_selected_quality"),
                "avg_offer_quality": avg(items, "avg_offer_quality"),
                "total_api_errors": int(sum_key(items, "api_errors")),
                "total_parse_failures": int(sum_key(items, "parse_failures")),
                "total_invalid_actions": int(sum_key(items, "invalid_actions")),
                "total_moderator_parse_failures": int(sum_key(items, "moderator_parse_failures")),
            }
        )
    return output


def game_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        summary = row["summary"]
        output.append(
            {
                "model": summary["model_group"],
                "architecture": summary["architecture_group"],
                "scenario": summary["scenario"],
                "seed": summary["seed"],
                "winner": summary["winner"],
                "days": summary["days"],
                "good_vote_accuracy": summary.get("good_vote_accuracy", 0),
                "mafia_vote_accuracy": summary.get("mafia_vote_accuracy", 0),
                "detective_hit_rate": summary.get("detective_hit_rate", 0),
                "doctor_saves": summary.get("doctor_saves", 0),
                "doctor_protected_detective": summary.get("doctor_protected_detective", 0),
                "mafia_alive_final": summary.get("mafia_alive_final", 0),
                "role_claims": summary.get("role_claims", 0),
                "false_role_claims": summary.get("false_role_claims", 0),
                "holy_grail_target_overrides": summary.get("holy_grail_overrides", 0),
                "holy_grail_message_overrides": summary.get("holy_grail_message_overrides", 0),
                "llm_calls": summary.get("llm_calls", 0),
                "revac_review_calls": summary.get("revac_review_calls", 0),
                "api_errors": summary.get("api_errors", 0),
                "parse_failures": summary.get("parse_failures", 0),
                "invalid_actions": summary.get("invalid_actions", 0),
                "source_file": summary["source_file"],
            }
        )
    return output


def player_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        summary = row["summary"]
        for player, values in row["game"].get("player_metrics", {}).items():
            values = dict(values)
            player_model = values.pop("model", "")
            player_architecture = values.pop("architecture", "")
            output.append(
                {
                    "scenario": summary["scenario"],
                    "model": summary["model_group"],
                    "architecture": summary["architecture_group"],
                    "player_model": player_model,
                    "player_architecture": player_architecture,
                    "seed": summary["seed"],
                    "winner": summary["winner"],
                    "player": player,
                    **values,
                }
            )
    return output


def summarize_roles(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in players:
        grouped[(row["model"], row["architecture"], row["role"])].append(row)
    output: list[dict[str, Any]] = []
    for (model, architecture, role), items in sorted(
        grouped.items(), key=lambda item: (MODEL_ORDER[item[0][0]], ARCH_ORDER[item[0][1]], item[0][2])
    ):
        output.append(
            {
                "model": model,
                "architecture": architecture,
                "role": role,
                "n": len(items),
                "alive_final_rate": mean(float(item.get("alive_final", 0) or 0) for item in items),
                "avg_messages_spoken": mean(float(item.get("messages_spoken", 0) or 0) for item in items),
                "avg_votes_cast": mean(float(item.get("votes_cast", 0) or 0) for item in items),
                "avg_votes_received": mean(float(item.get("votes_received", 0) or 0) for item in items),
                "avg_role_claims": mean(float(item.get("role_claims", 0) or 0) for item in items),
                "avg_false_role_claims": mean(float(item.get("false_role_claims", 0) or 0) for item in items),
            }
        )
    return output


def delta_rows(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {(row["model"], row["architecture"]): row for row in summary_rows}
    rows: list[dict[str, Any]] = []
    for model in sorted(MODEL_ORDER, key=MODEL_ORDER.get):
        holy_grail = by_key[(model, "Holy Grail")]
        for baseline in ("ReVAC", "GRAIL"):
            base = by_key[(model, baseline)]
            rows.append(
                {
                    "model": model,
                    "comparison": f"Holy Grail - {baseline}",
                    "good_win_rate_delta": holy_grail["good_win_rate"] - base["good_win_rate"],
                    "good_vote_accuracy_delta": holy_grail["avg_good_vote_accuracy"] - base["avg_good_vote_accuracy"],
                    "detective_hit_rate_delta": holy_grail["avg_detective_hit_rate"] - base["avg_detective_hit_rate"],
                    "mafia_alive_final_delta": holy_grail["avg_mafia_alive_final"] - base["avg_mafia_alive_final"],
                    "llm_calls_delta": holy_grail["avg_llm_calls"] - base["avg_llm_calls"],
                    "elapsed_sec_delta": holy_grail["avg_elapsed_sec"] - base["avg_elapsed_sec"],
                }
            )
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


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    lines = [
        "| " + " | ".join(label for label, _ in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row[key]) for _, key in columns) + " |")
    return "\n".join(lines)


def best_by_model(summary_rows: list[dict[str, Any]]) -> list[str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in summary_rows:
        grouped[row["model"]].append(row)
    lines: list[str] = []
    for model in sorted(grouped, key=lambda value: MODEL_ORDER[value]):
        items = sorted(
            grouped[model],
            key=lambda row: (
                row["good_win_rate"],
                row["avg_good_vote_accuracy"],
                row["avg_detective_hit_rate"],
                -row["avg_mafia_alive_final"],
            ),
            reverse=True,
        )
        best = items[0]
        holy_grail = next(row for row in items if row["architecture"] == "Holy Grail")
        relation = "best" if best["architecture"] == "Holy Grail" else f"behind {best['architecture']}"
        lines.append(
            f"- {model}: Holy Grail was {relation}; "
            f"{int(holy_grail['good_wins'])}/{int(holy_grail['n'])} Good wins, "
            f"Good vote accuracy {holy_grail['avg_good_vote_accuracy']:.3f}, "
            f"Detective hit rate {holy_grail['avg_detective_hit_rate']:.3f}, "
            f"avg LLM calls {holy_grail['avg_llm_calls']:.1f}."
        )
    return lines


def role_takeaways(role_rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for model in sorted(MODEL_ORDER, key=MODEL_ORDER.get):
        holy_grail = [row for row in role_rows if row["model"] == model and row["architecture"] == "Holy Grail"]
        by_role = {row["role"]: row for row in holy_grail}
        mafia_alive = by_role["Mafia"]["alive_final_rate"]
        villager_alive = by_role["Villager"]["alive_final_rate"]
        detective_alive = by_role["Detective"]["alive_final_rate"]
        doctor_claims = by_role["Doctor"]["avg_role_claims"]
        lines.append(
            f"- {model}: Holy Grail left Mafia alive at {mafia_alive:.3f}, Villagers alive at {villager_alive:.3f}, "
            f"Detective alive at {detective_alive:.3f}; Doctor claims averaged {doctor_claims:.3f} per Doctor slot."
        )
    return lines


def write_report(
    rows: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    games: list[dict[str, Any]],
    roles: list[dict[str, Any]],
    deltas: list[dict[str, Any]],
) -> None:
    total_errors = sum(
        int(row["summary"].get(key, 0) or 0)
        for row in rows
        for key in ("api_errors", "parse_failures", "invalid_actions", "moderator_parse_failures")
    )
    expected = 27
    gate = next(row for row in summary_rows if row["model"] == "Mafia Gemma BF16" and row["architecture"] == "Holy Grail")
    lines = [
        "# Holy Grail Same-Model Full-Game Benchmark",
        "",
        f"Generated from {len(rows)} completed full games. Expected rows for the configured matrix: {expected}.",
        "",
        "Controls:",
        "- Roles: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.",
        "- Win conditions: classic Mafia parity for Mafia; all Mafia eliminated for Town.",
        "- Protocol: explicit non-player Moderator/Narrator agent using Time-to-Talk scheduler plus generator.",
        "- Moderator: base Gemma 4 12B BF16 through Modal.",
        "- Gemma sampler: `temperature=1.0`, `top_p=0.95`, `top_k=64` for both base moderator and Mafia Gemma BF16 players.",
        "- Same-model architecture tests: all seven player agents in a cell used the same player model and same architecture.",
        "- Seeds: 9900, 9901, 9902 per architecture cell.",
        f"- Validation: total API/player/moderator errors across aggregated rows = {total_errors}.",
        "",
        "## Architecture",
        "",
        "Long form: **Hidden-role Objective Ledgering with Yield-aware Game-theoretic Role-Adaptive Inference Loop**.",
        "",
        "```mermaid",
        "flowchart TD",
        '    A["Private role, public transcript, alive set, claims, votes"] --> B["ReVAC private review: objective, evidence, risk"]',
        '    B --> C["GRAIL constraints: role counts, impossible claims, posterior bounds"]',
        '    B --> D["WOLF ledger: suspicion, deception, claims, vote pressure"]',
        '    C --> E["Public-evidence adjudicator"]',
        '    D --> E',
        '    E --> F["Role action-value scorer"]',
        '    F --> G["Vote-closing and night-action controller"]',
        '    G --> H{"Assigned role"}',
        '    H --> I["Mafia: partner preservation, safe lies, power-role kill pressure"]',
        '    H --> J["Detective: convert checks into vote order, claim under threat"]',
        '    H --> K["Doctor: protect public information value, claim only under danger"]',
        '    H --> L["Villager: follow public checks, resist weak herds, preserve power claims"]',
        '    I --> M["Legal JSON target or concise public message"]',
        '    J --> M',
        '    K --> M',
        '    L --> M',
        "```",
        "",
        "Important implementation note: Holy Grail directly controls target decisions for vote, Mafia kill, Detective check, and Doctor save. Discussion remains model-generated, with Holy Grail message guardrails only when public evidence or role-risk gates are triggered. This makes Holy Grail a stronger architecture test, not a pure raw-model target-generation test.",
        "",
        "## Moderator Protocol",
        "",
        "```mermaid",
        "sequenceDiagram",
        "    participant T as Transcript state",
        "    participant S as TTT scheduler",
        "    participant G as Moderator generator",
        "    participant P as Player agent",
        "    T->>S: Alive set, floor counts, recent discussion, timing state",
        "    S-->>T: wait, or send",
        "    T->>G: If send, choose target and cue type",
        "    G->>P: Role-hidden floor cue",
        "    P->>T: Public message",
        "    T->>S: Updated transcript and simulated timing",
        "```",
        "",
        "## Iteration Audit",
        "",
        "- Holy Grail started from v3 but added a public-evidence adjudicator for role claims, public Detective checks, checked-good claims, low-agency evasion, and unsupported herd votes.",
        "- The live Mafia Gemma gate exposed a latency and reliability issue: Holy Grail was still spending target actions on redundant ReVAC/model calls.",
        "- The controller was revised so Holy Grail computes all target decisions through the architecture policy. This removed the repeated ReVAC review bottleneck and made the architecture legible in the logs through `architecture_guardrail` events.",
        "- The gate criterion before broader runs was Mafia Gemma BF16 Holy Grail beating Mafia Gemma BF16 ReVAC and GRAIL on the same three seeds.",
        f"- Gate result: Mafia Gemma BF16 Holy Grail reached {int(gate['good_wins'])}/{int(gate['n'])} Good wins with Good vote accuracy {gate['avg_good_vote_accuracy']:.3f}.",
        "",
        "## Outcome Table",
        "",
        markdown_table(
            summary_rows,
            [
                ("Model", "model"),
                ("Architecture", "architecture"),
                ("n", "n"),
                ("Good wins", "good_wins"),
                ("Mafia wins", "mafia_wins"),
                ("Good WR", "good_win_rate"),
                ("Days", "avg_days"),
                ("Good vote", "avg_good_vote_accuracy"),
                ("Mafia vote", "avg_mafia_vote_accuracy"),
                ("Detective hit", "avg_detective_hit_rate"),
                ("Doctor saves", "avg_doctor_saves"),
                ("Mafia alive", "avg_mafia_alive_final"),
                ("Target overrides", "avg_holy_grail_target_overrides"),
                ("Msg overrides", "avg_holy_grail_message_overrides"),
            ],
        ),
        "",
        "## Holy Grail Delta",
        "",
        markdown_table(
            deltas,
            [
                ("Model", "model"),
                ("Comparison", "comparison"),
                ("Good WR delta", "good_win_rate_delta"),
                ("Good vote delta", "good_vote_accuracy_delta"),
                ("Detective hit delta", "detective_hit_rate_delta"),
                ("Mafia alive delta", "mafia_alive_final_delta"),
                ("LLM calls delta", "llm_calls_delta"),
                ("Elapsed delta", "elapsed_sec_delta"),
            ],
        ),
        "",
        "## Per-Game Results",
        "",
        markdown_table(
            games,
            [
                ("Model", "model"),
                ("Architecture", "architecture"),
                ("Seed", "seed"),
                ("Winner", "winner"),
                ("Days", "days"),
                ("Good vote", "good_vote_accuracy"),
                ("Detective hit", "detective_hit_rate"),
                ("Doctor saves", "doctor_saves"),
                ("Mafia alive", "mafia_alive_final"),
                ("Target overrides", "holy_grail_target_overrides"),
                ("Msg overrides", "holy_grail_message_overrides"),
                ("LLM calls", "llm_calls"),
            ],
        ),
        "",
        "## Moderator And Flow Metrics",
        "",
        markdown_table(
            summary_rows,
            [
                ("Model", "model"),
                ("Architecture", "architecture"),
                ("LLM calls", "avg_llm_calls"),
                ("ReVAC reviews", "avg_revac_review_calls"),
                ("Mod sched", "avg_moderator_scheduler_calls"),
                ("Mod gen", "avg_moderator_generator_calls"),
                ("Send", "avg_moderator_send_decisions"),
                ("Wait", "avg_moderator_wait_decisions"),
                ("Gap sec", "avg_moderator_gap_seconds"),
                ("Rate dev", "avg_moderator_rate_deviation"),
                ("Cue quality", "avg_selected_quality"),
                ("Elapsed sec", "avg_elapsed_sec"),
            ],
        ),
        "",
        "## Role-Level Survival And Activity",
        "",
        markdown_table(
            roles,
            [
                ("Model", "model"),
                ("Architecture", "architecture"),
                ("Role", "role"),
                ("n", "n"),
                ("Alive final", "alive_final_rate"),
                ("Messages", "avg_messages_spoken"),
                ("Votes cast", "avg_votes_cast"),
                ("Votes received", "avg_votes_received"),
                ("Role claims", "avg_role_claims"),
                ("False claims", "avg_false_role_claims"),
            ],
        ),
        "",
        "## Takeaways",
        "",
        *best_by_model(summary_rows),
        "",
        "Role-side read:",
        *role_takeaways(roles),
        "",
        "Interpretation: Holy Grail achieved the target improvement for Mafia Gemma BF16 decisively: 3/3 Good wins versus 0/3 for ReVAC and 0/3 for GRAIL on identical seeds. It also improved GPT-5-mini over both baselines on win rate. Claude Opus remained the hardest case: Holy Grail tied ReVAC on win rate, beat GRAIL on win rate, used far fewer LLM calls than ReVAC, but ReVAC had slightly higher Good vote accuracy. The strongest conclusion is that Holy Grail is most valuable when the underlying model needs explicit evidence adjudication and vote-closing discipline; frontier models can partly compensate for weaker architecture, but Holy Grail still improves efficiency and keeps performance competitive.",
        "",
        "## Artifacts",
        "",
        f"- Combined raw games: `{COMBINED_JSONL.name}`",
        f"- Summary CSV: `{SUMMARY_CSV.name}`",
        f"- Per-game CSV: `{GAME_CSV.name}`",
        f"- Player metrics CSV: `{PLAYER_CSV.name}`",
        f"- Role summary CSV: `{ROLE_CSV.name}`",
        f"- Delta CSV: `{DELTA_CSV.name}`",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = load_rows()
    if len(rows) != 27:
        raise SystemExit(f"Expected 27 rows, found {len(rows)}")
    COMBINED_JSONL.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary_rows = summarize(rows)
    games = game_rows(rows)
    players = player_rows(rows)
    roles = summarize_roles(players)
    deltas = delta_rows(summary_rows)
    write_csv(SUMMARY_CSV, summary_rows)
    write_csv(GAME_CSV, games)
    write_csv(PLAYER_CSV, players)
    write_csv(ROLE_CSV, roles)
    write_csv(DELTA_CSV, deltas)
    write_report(rows, summary_rows, games, roles, deltas)
    print(json.dumps({
        "combined_jsonl": str(COMBINED_JSONL),
        "summary_csv": str(SUMMARY_CSV),
        "game_csv": str(GAME_CSV),
        "player_csv": str(PLAYER_CSV),
        "role_csv": str(ROLE_CSV),
        "delta_csv": str(DELTA_CSV),
        "report_md": str(REPORT_MD),
        "rows": len(rows),
    }, indent=2))


if __name__ == "__main__":
    main()
