#!/usr/bin/env python3
"""Run 7-player Mafia games with model/architecture/protocol controls.

Roles:
- 2 Mafia
- 1 Detective
- 1 Doctor
- 3 Villagers

This harness is intentionally independent from the original Mini-Mafia game
classes because it needs full multi-night play, doctor saves, two mafia, and a
Time-to-Talk-style communication protocol.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


PLAYER_NAMES = ["Ariel", "Blake", "Casey", "Devon", "Emery", "Finley", "Gray"]
ROLE_LIST = ["Mafia", "Mafia", "Detective", "Doctor", "Villager", "Villager", "Villager"]
GOOD_ROLES = {"Detective", "Doctor", "Villager"}
MODAL_INFERENCE_APP = "mafia-gemma4-inference"
MODERATOR_NAME = "Moderator"
MODERATED_PROTOCOLS = {
    "moderated_time_to_talk",
    "moderated_candidate_time_to_talk",
    "moderated_quality_time_to_talk",
}
ARCHITECTURE_ALIASES = {
    "vanilla": "baseline",
    "baseline": "baseline",
    "grail_lite": "grail",
    "grail": "grail",
    "revac_lite": "revac",
    "revac": "revac",
    "wolf_ledger": "wolf",
    "wolf": "wolf",
    "hybrid": "grail_wolf",
    "grail_deception": "grail_wolf",
    "grail_wolf": "grail_wolf",
    "verified_grail_wolf": "grail_wolf_verified",
    "grail_wolf_verified": "grail_wolf_verified",
    "wolf_revac_grail": "wolf_revac_grail",
    "mafia_hybrid": "wolf_revac_grail",
    "role_adaptive_hybrid": "role_adaptive_hybrid",
    "any_role_hybrid": "role_adaptive_hybrid",
    "holy_grail": "holy_grail",
    "holygrail": "holy_grail",
    "h_o_l_y_g_r_a_i_l": "holy_grail",
    "hidden_role_objective_ledgering": "holy_grail",
    "holy_grail_v2": "holy_grail_v2",
    "holygrail_v2": "holy_grail_v2",
    "hgv2": "holy_grail_v2",
    "hidden_role_objective_ledgering_v2": "holy_grail_v2",
    "holy_grail_v3": "holy_grail_v3",
    "holygrail_v3": "holy_grail_v3",
    "hgv3": "holy_grail_v3",
    "hidden_role_objective_ledgering_v3": "holy_grail_v3",
    "holy_grail": "holy_grail",
    "holygrail_v4": "holy_grail",
    "holy_grail": "holy_grail",
    "hidden_role_objective_ledgering_v4": "holy_grail",
}
_MODAL_INSTANCE_CACHE: dict[str, Any] = {}


@dataclass
class AgentSpec:
    provider: str
    model: str
    architecture: str = "baseline"
    reasoning_effort: str | None = None
    temperature: float = 0.2
    top_p: float | None = None
    top_k: int | None = None

    @property
    def label(self) -> str:
        prefix = self.provider if self.provider != "ollama" else "ollama"
        return f"{prefix}/{self.model}:{self.architecture}"


@dataclass
class Player:
    name: str
    role: str
    spec: AgentSpec
    alive: bool = True
    investigations: dict[str, str] = field(default_factory=dict)
    last_protected: str | None = None


@dataclass
class Moderator:
    name: str
    role: str
    spec: AgentSpec


@dataclass
class GameStats:
    parse_failures: int = 0
    invalid_actions: int = 0
    api_errors: int = 0
    llm_calls: int = 0
    discussion_messages: int = 0
    waits: int = 0
    scheduler_calls: int = 0
    scheduler_rounds: int = 0
    candidate_messages: int = 0
    deferred_messages: int = 0
    doctor_saves: int = 0
    mafia_kill_votes: int = 0
    tie_no_eliminations: int = 0
    revac_review_calls: int = 0
    moderator_scheduler_calls: int = 0
    moderator_generator_calls: int = 0
    moderator_send_decisions: int = 0
    moderator_wait_decisions: int = 0
    moderator_interventions: int = 0
    moderator_forced_interventions: int = 0
    moderator_parse_failures: int = 0
    moderator_sim_wait_seconds: float = 0.0
    moderator_sim_typing_seconds: float = 0.0
    moderator_avg_message_gap_seconds: float = 0.0
    moderator_message_rate_deviation: float = 0.0
    holy_grail_v2_guardrail_checks: int = 0
    holy_grail_v2_overrides: int = 0
    holy_grail_v3_guardrail_checks: int = 0
    holy_grail_v3_overrides: int = 0
    holy_grail_v3_message_overrides: int = 0
    holy_grail_guardrail_checks: int = 0
    holy_grail_overrides: int = 0
    holy_grail_message_overrides: int = 0
    elapsed_sec: float = 0.0
    error_messages: list[str] = field(default_factory=list)
    call_records: list[dict[str, Any]] = field(default_factory=list)


def load_env_file(workspace_root: Path) -> None:
    env_path = workspace_root / "env.txt"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
    if os.environ.get("OPEN_AI_KEY") and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPEN_AI_KEY"]
    if os.environ.get("ANTHROPIC_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_KEY"]


def normalize_architecture(architecture: str | None) -> str:
    if not architecture:
        return "baseline"
    return ARCHITECTURE_ALIASES.get(architecture.strip().lower(), architecture.strip().lower())


def parse_model_spec(
    spec: str,
    architecture: str,
    reasoning_effort: str | None,
    temperature: float,
    top_p: float | None = None,
    top_k: int | None = None,
) -> AgentSpec:
    if "/" in spec:
        provider, model = spec.split("/", 1)
    elif spec.startswith("gemma") or ":" in spec:
        provider, model = "ollama", spec
    else:
        provider, model = "ollama", spec
    return AgentSpec(
        provider=provider,
        model=model,
        architecture=normalize_architecture(architecture),
        reasoning_effort=reasoning_effort,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
    )


def agent_spec_from_config(config: Any, default_architecture: str = "baseline", default_reasoning_effort: str | None = None, default_temperature: float = 0.2) -> AgentSpec:
    if isinstance(config, str):
        return parse_model_spec(config, default_architecture, default_reasoning_effort, default_temperature)
    if not isinstance(config, dict):
        raise ValueError(f"Invalid agent spec: {config!r}")
    provider = config.get("provider")
    model = config.get("model")
    if not model:
        raise ValueError(f"Agent spec missing model: {config!r}")
    architecture = normalize_architecture(config.get("architecture", default_architecture))
    reasoning_effort = config.get("reasoning_effort", default_reasoning_effort)
    temperature = float(config.get("temperature", default_temperature))
    top_p = config.get("top_p")
    top_k = config.get("top_k")
    parsed_top_p = float(top_p) if top_p is not None else None
    parsed_top_k = int(top_k) if top_k is not None else None
    if provider:
        return AgentSpec(
            provider=provider,
            model=model,
            architecture=architecture,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            top_p=parsed_top_p,
            top_k=parsed_top_k,
        )
    return parse_model_spec(model, architecture, reasoning_effort, temperature, parsed_top_p, parsed_top_k)


def architecture_text(architecture: str) -> str:
    architecture = normalize_architecture(architecture)
    common = (
        "Do all reasoning privately. Return only the requested JSON. "
        "Never reveal private reasoning unless asked for a public message.\n"
    )
    if architecture == "baseline":
        return common
    if architecture == "grail":
        return (
            common
            + "Architecture: GRAIL. Maintain a private hidden-role belief table with exact counts: "
            "2 Mafia, 1 Detective, 1 Doctor, 3 Villagers. Treat those counts as hard constraints, "
            "subtract publicly revealed dead roles, and keep alive-player beliefs normalized to the remaining slots. "
            "Use public claims, votes, timing, night outcomes, and contradictions as evidence, but never let evidence "
            "violate the counts. Prefer actions that improve posterior separation between plausible role assignments.\n"
        )
    if architecture == "revac":
        return (
            common
            + "Architecture: ReVAC. Run a private review cycle before every action: objective, evidence, "
            "player profiles, social alignments, contradictions, risks if wrong, likely lies, available moves, "
            "communication tone, and expected faction win impact. Prefer the action whose downside is controlled "
            "if your read is wrong. Then output only JSON.\n"
        )
    if architecture == "wolf":
        return (
            common
            + "Architecture: WOLF. Maintain a private deception ledger: role claims, suspicious incentives, "
            "self-serving wording, omissions, distortions, fabrications, misdirection, partner-defense patterns, "
            "vote pressure, and shifts after new evidence. As Mafia, manage deception without overclaiming. "
            "As good, identify inconsistencies and pressure them.\n"
        )
    if architecture == "grail_wolf":
        return (
            architecture_text("grail")
            + "Advanced layer: combine GRAIL's hard hidden-role counts with WOLF deception measurement and "
            "Revac risk review. Use deception signals to adjust beliefs inside the count constraints, then choose "
            "the action with the best risk-adjusted faction value.\n"
        )
    if architecture == "grail_wolf_verified":
        return (
            architecture_text("grail")
            + "Verified GRAIL-WOLF layer. Treat hard role counts as constraints, then verify public claims against "
            "revealed roles, remaining role slots, vote history, night outcomes, and deception flags. For good-team "
            "play, protect credible Detective or Doctor information, coordinate around verified checks, and punish "
            "claims that are count-impossible or strategically timed for Mafia. For Mafia play, anticipate how good "
            "agents will verify claims and avoid contradictions that fail role-count or vote-ledger checks.\n"
        )
    if architecture == "wolf_revac_grail":
        return (
            common
            + "Architecture: WOLF + ReVAC core with GRAIL constraints. Maintain a private deception/vote ledger "
            "covering claims, suspicion shifts, omissions, distortions, fabrications, misdirection, partner-defense "
            "or distancing patterns, pressure targets, and likely lies. Before acting, run a ReVAC review: objective, "
            "evidence, player profiles, social alignments, risk if wrong, safest lie or truth, tone, and expected "
            "faction value. Use GRAIL hard role-count constraints to avoid impossible claims and exploit public "
            "role-count mistakes. As Mafia, manage deception, steer votes, and keep partner exposure controlled. "
            "As good, use the same ledger to find inconsistent incentives and overfit claims.\n"
        )
    if architecture == "role_adaptive_hybrid":
        return (
            common
            + "Architecture: role-adaptive hybrid for any Mafia role. First identify your current role and faction, "
            "then select the right operating mode: Mafia deception/risk management, Detective evidence protection "
            "and reveal timing, Doctor exposure control and save logic, or Villager pressure/vote coordination. "
            "Use WOLF's claim/suspicion/deception ledger, ReVAC's memory/review/tone/action loop, and GRAIL's hard "
            "role-count constraints. For Time-to-Talk, speak when the message adds concrete evidence, pressure, "
            "defense, claim checking, or vote coordination; stay quiet when the message would only add noise.\n"
        )
    if architecture == "holy_grail":
        return (
            common
            + "Architecture: Holy Grail, Hidden-role Objective Ledgering with Yield-aware Game-theoretic "
            "Role-Adaptive Action Inference Loop. This is one unified any-role architecture, not separate "
            "Mafia and Town agents. Route every decision through: (1) role kernel selection, (2) GRAIL hard "
            "role-count and belief constraints, (3) WOLF deception/claim/vote ledger, (4) ReVAC memory, risk, "
            "tone, and action review, (5) legal action output. Use the strongest specialized policy for your "
            "current assigned role while sharing the same public evidence ledger across all roles.\n"
        )
    if architecture == "holy_grail_v2":
        return (
            common
            + "Architecture: Holy Grail v2, Hidden-role Objective Ledgering with Yield-aware Game-theoretic "
            "Role-Adaptive Inference Loop. This is a role-weighted any-role controller. It first builds a "
            "deterministic game state, then routes through a role-specific module order: Mafia uses WOLF -> "
            "ReVAC -> GRAIL; Detective uses GRAIL -> ReVAC -> WOLF; Doctor uses ReVAC -> GRAIL -> WOLF; "
            "Villager uses GRAIL -> WOLF -> ReVAC. Endgame/parity checks and legal JSON validation come last. "
            "Town votes must be belief-constrained; raw suspicion alone is not enough.\n"
        )
    if architecture == "holy_grail_v3":
        return (
            common
            + "Architecture: Holy Grail v3, Hidden-role Objective Ledgering with Yield-aware Game-theoretic "
            "Role-Adaptive Inference Loop. This version uses ReVAC as the top-level controller for every role: "
            "objective -> evidence -> risks -> alternatives -> final legal action. GRAIL is the constrained "
            "belief engine, WOLF is the deception/claim/vote signal engine, and a role-specific action-value "
            "scorer arbitrates the final move. Do not stack the modules equally: ReVAC decides the decision "
            "process, GRAIL constrains what is possible, WOLF supplies social evidence, and the role policy "
            "decides what matters for the assigned role. Town votes require posterior evidence, public case "
            "strength, coalition feasibility, and low power-role risk; Mafia actions require plausible pressure, "
            "partner exposure control, and legal claims under role counts.\n"
        )
    if architecture == "holy_grail":
        return (
            common
            + "Architecture: Holy Grail, Hidden-role Objective Ledgering with Yield-aware Game-theoretic "
            "Role-Adaptive Inference Loop. This version keeps the v3 ReVAC -> GRAIL -> WOLF -> role-value "
            "controller, then adds a public-evidence adjudicator and vote-closing layer. Treat public Detective "
            "checks, checked-good statements, uncontested power claims, counterclaims, role-count impossibilities, "
            "same-day vote herds, and low-agency echo messages as structured state. Town agents must convert "
            "credible public Mafia checks into coordinated votes and must not eliminate credible Detectives, "
            "Doctors, or checked-good players without a counterclaim. Mafia agents may exploit the same public "
            "state, but should avoid brittle claims that fail the adjudicator.\n"
        )
    return common


def role_objective(role: str) -> str:
    if role == "Mafia":
        return "You are Mafia. Your team wins when Mafia are at least as numerous as non-Mafia. Deceive and survive."
    if role == "Detective":
        return "You are the Detective. Each night you learn whether one player is Mafia. Help the good team eliminate Mafia."
    if role == "Doctor":
        return "You are the Doctor. Each night you protect one alive player from the Mafia kill. Help the good team."
    return "You are a Villager. You have no night power. Use discussion and voting to eliminate Mafia."


def holy_grail_role_kernel(player: Player, action: str, protocol: str) -> str:
    architecture = normalize_architecture(player.spec.architecture)
    if architecture not in {"holy_grail", "holy_grail_v2", "holy_grail_v3", "holy_grail"}:
        return ""
    if architecture == "holy_grail":
        header = (
            "Holy Grail controller. Apply this silently before returning JSON. "
            "Use private role information only in private reasoning; public messages must cite public evidence unless a reveal gate is triggered.\n"
        )
        shared = (
            "- Controller order: ReVAC objective/evidence/risk -> GRAIL constrained posterior -> WOLF social/deception signals -> public-evidence adjudicator -> role action-value scorer -> vote-closing plan -> legal JSON.\n"
            "- Public-evidence adjudicator: hard-track claimed Detective/Doctor, claimed check results, checked-good players, counterclaims, impossible claims, no-kill implications, and same-day vote herds.\n"
            "- Vote-closing plan: before voting, identify must_not_vote, best_vote, acceptable_votes, dangerous_votes, and the public reason. Do not split Town votes away from a credible Mafia check.\n"
            "- Low-agency WOLF signal: repeated generic shock, vague unease, or copied prompts without a target/reason is evasion evidence, especially after another player already said it.\n"
            "- Moderator cue filter: answer the cue, but redirect weak silence pressure toward concrete claims, contradictions, vote shifts, or night evidence.\n"
        )
        if player.role == "Mafia":
            return header + shared + (
                "- Mafia policy: preserve partners first. Use WOLF/ReVAC to decide whether to attack the Detective claim, counterclaim, or push a checked-good only when the public adjudicator leaves room. "
                "Night kills prioritize credible Detective, checked-good coordinators, Doctor claims, and accurate Mafia voters. Avoid partner votes unless survival or counterclaim math forces it.\n"
            )
        if player.role == "Detective":
            return header + shared + (
                "- Detective policy: investigate for vote conversion. Reveal any live Mafia result with a specific vote order. If a checked-good is endangered, reveal to block the vote. "
                "If under pressure, claim cleanly with night, target, result, and a fallback plan. Do not allow Town to spend the day on no-evidence herds.\n"
            )
        if player.role == "Doctor":
            return header + shared + (
                "- Doctor policy: protect public information value. Default to credible Detective or checked-good coordinator when exposed; otherwise protect the best Town vote leader. "
                "Claim only when the vote threatens you or when a no-kill/save explanation changes today's vote. Push Town to follow credible checks.\n"
            )
        return header + shared + (
            "- Villager policy: act as public-evidence enforcer. Follow credible Detective Mafia checks, protect checked-good and uncontested power claims, punish impossible/counterclaimed roles, "
            "and resist Day 1 herds based only on silence. When evidence is thin, vote the strongest low-agency echo or contradiction rather than the current herd target.\n"
        )
    if architecture == "holy_grail_v3":
        header = (
            "Holy Grail v3 controller. Apply this silently before returning JSON. "
            "Use private role information only in private reasoning; public messages must be explainable from public evidence unless a reveal gate is triggered.\n"
        )
        shared = (
            "- Controller order: ReVAC objective/evidence/risk -> GRAIL constrained posterior -> WOLF deception/claim/vote signals -> role action-value scorer -> legal JSON.\n"
            "- Vote discipline: do not vote from raw suspicion alone. Prefer candidates with high constrained posterior, public case strength, coalition feasibility, and low risk of being Detective/Doctor/checked-good.\n"
            "- Moderator cue filter: answer the cue, but do not let it override role objective, private evidence, or vote discipline. Redirect if the cue would cause exposure or a weak vote.\n"
            "- Public message discipline: name one concrete reason, one candidate or claim conflict, and one next action. Avoid table noise and unsupported certainty.\n"
        )
        if player.role == "Mafia":
            return header + shared + (
                "- Mafia policy: use WOLF first for pressure/deception opportunities, but let ReVAC reject brittle lies. "
                "Never vote a partner unless forced by survival. Push non-Mafia targets with existing public pressure, "
                "power-role exposure, or coalition feasibility. Night kills should remove credible Detective/Doctor, "
                "checked-good coordinators, or accurate Mafia voters while avoiding targets likely to be protected.\n"
            )
        if player.role == "Detective":
            return header + shared + (
                "- Detective policy: choose investigations by expected vote value, not curiosity. Prioritize high-posterior unresolved targets, "
                "claim conflicts, vote leaders, and players whose alignment would settle today's coalition. A Mafia result should anchor "
                "today's vote. A checked-good result should protect the target from elimination. Reveal when it changes the vote, prevents "
                "a checked-good elimination, resolves a claim conflict, or parity risk is high.\n"
            )
        if player.role == "Doctor":
            return header + shared + (
                "- Doctor policy: maximize expected save value. Protect public or likely information holders, credible vote coordinators, "
                "players who pushed revealed Mafia, or yourself when exposed. Avoid saving high-posterior Mafia suspects. Claim only to "
                "prevent your own elimination, resolve a decisive Doctor conflict, or explain a no-kill/save that changes the vote.\n"
            )
        return header + shared + (
            "- Villager policy: act as the vote-quality controller. Build two Mafia hypotheses, ask for claim/vote contradictions, "
            "and coordinate around the strongest constrained case. Penalize opportunistic vote shifts, impossible claims, and pressure "
            "without evidence. Protect credible power claims unless they are count-impossible or contradicted.\n"
        )
    if architecture == "holy_grail_v2":
        header = (
            "Holy Grail v2 role-weighted kernel. Apply this silently before returning JSON. "
            "Use private role information only in private reasoning; public messages must be explainable from public evidence unless a reveal gate is triggered.\n"
        )
        shared = (
            "- Shared controller: deterministic state -> role-specific module order -> endgame/parity solver -> TTT cue response -> legal JSON validator.\n"
            "- Calibrated WOLF: distinguish deception_likelihood from mafia_likelihood_delta. Detective/Doctor withholding can look deceptive but should not automatically become a Mafia read.\n"
            "- GRAIL belief constraints: exact role counts dominate Town votes, claim checks, and Detective investigation choices.\n"
            "- ReVAC discipline: state objective, evidence, risk if wrong, tone, and action. Prefer actions with clear faction value and bounded downside.\n"
        )
        if player.role == "Mafia":
            return header + shared + (
                "- Mafia order: WOLF -> ReVAC -> GRAIL -> Endgame. Track partner exposure, exploit Town claim/count mistakes, "
                "and push high-agency Town without obvious coordination. Prefer omission and misdirection over brittle fabrication. "
                "At parity or near-parity, prioritize a coordinated vote on a non-Mafia target.\n"
            )
        if player.role == "Detective":
            return header + shared + (
                "- Detective order: GRAIL -> ReVAC -> WOLF -> Reveal Policy. Investigate high-posterior unresolved targets, "
                "vote-leverage players, claim conflicts, or suspicious defenders. Reveal a Mafia check when it can drive today's vote, "
                "reveal a checked-good when they are vote-endangered, and reveal in parity-risk states. Otherwise steer with public evidence.\n"
            )
        if player.role == "Doctor":
            return header + shared + (
                "- Doctor order: ReVAC -> GRAIL -> WOLF -> Protection Policy. Protect information value: claimed/likely Detective, "
                "checked-good coordinators, or players correctly pressuring Mafia. Self-protect only when exposure or kill risk is high. "
                "Claim only to prevent your elimination, resolve a decisive Doctor conflict, or explain a no-kill that changes the vote.\n"
            )
        return header + shared + (
            "- Villager order: GRAIL -> WOLF -> ReVAC -> Vote Plan. Maintain two live Mafia hypotheses, ask one concrete question, "
            "and propose a vote with a contingency. In endgame force role claim, vote reason, and partner theory. Do not over-trust raw suspicion.\n"
        )
    header = (
        "Holy Grail role kernel. Apply this role-specific policy silently before returning JSON. "
        "Use public evidence only in public messages; use private role information only when strategically justified.\n"
    )
    shared = (
        "- Shared constraints: obey exact role counts, avoid impossible claims, track claim conflicts, "
        "separate public facts from private knowledge, and choose actions with high faction value and controlled downside.\n"
        "- Communication timing: answer moderator cues directly; speak when you add concrete evidence, defense, "
        "claim checking, or vote coordination; avoid generic agreement.\n"
    )
    if player.role == "Mafia":
        return header + shared + (
            "- Mafia kernel: use WOLF+ReVAC+GRAIL as the primary operating mode. Maintain deception that is plausible "
            "under role counts; prefer omission or misdirection over fragile fabrication; avoid exposing your partner. "
            "Pressure high-value Town roles, exploit bad claims, and coordinate votes toward Detective/Doctor or credible "
            "Town leaders without making the partnership obvious. Night kills should remove confirmed or high-agency Town, "
            "especially Detective claims, protected-vote coordinators, or players correctly suspecting Mafia.\n"
        )
    if player.role == "Detective":
        return header + shared + (
            "- Detective kernel: maximize information value and survival. Investigate players with high public suspicion, "
            "vote leverage, or unresolved claim conflicts rather than obvious night-kill targets. Treat a Mafia result as "
            "high-priority evidence, but reveal it when it can change the vote, prevent a checked-good elimination, or "
            "counter a false claim. When revealing, be specific: name the night, target, result, and vote plan. When not "
            "revealing, steer votes using public reasons that do not expose the investigation trail.\n"
        )
    if player.role == "Doctor":
        return header + shared + (
            "- Doctor kernel: protect information and vote power while minimizing exposure. Prioritize claimed or likely "
            "Detective, credible vote coordinators, yourself when under night-kill risk, and players attacked by Mafia-led "
            "pressure. Do not claim Doctor casually; claim only to prevent your elimination, resolve a decisive claim "
            "conflict, or explain a no-kill/save that changes the vote. Never imply a protected player knows they were "
            "protected unless the public transcript establishes it.\n"
        )
    return header + shared + (
        "- Villager kernel: act as the Town coordination layer. Build a public case from votes, claims, contradictions, "
        "night outcomes, and WOLF suspicion signals. Ask one concrete question or propose one vote plan, not vague reads. "
        "Protect credible Detective/Doctor claims without blindly trusting them; punish count-impossible claims and "
        "opportunistic vote shifts. In endgame, force each player to commit to a claim, vote reason, and partner theory.\n"
    )


def alive_players(players: dict[str, Player]) -> list[str]:
    return [name for name in PLAYER_NAMES if players[name].alive]


def alive_mafia(players: dict[str, Player]) -> list[str]:
    return [name for name in alive_players(players) if players[name].role == "Mafia"]


def check_winner(players: dict[str, Player]) -> str | None:
    mafia = len(alive_mafia(players))
    good = len([name for name in alive_players(players) if players[name].role in GOOD_ROLES])
    if mafia == 0:
        return "good"
    if mafia >= good:
        return "mafia"
    return None


def compact_transcript(events: list[dict[str, Any]], max_events: int = 36) -> str:
    lines = []
    visible_events = [
        event for event in events
        if event.get("type") in {"night_result", "discussion", "vote", "elimination", "no_elimination", "system"}
    ]
    for event in visible_events[-max_events:]:
        kind = event.get("type")
        if kind == "night_result":
            lines.append(f"Night {event['night']}: {event['message']}")
        elif kind == "discussion":
            lines.append(f"Day {event['day']} {event['speaker']}: {event['message']}")
        elif kind == "vote":
            lines.append(f"Day {event['day']} vote: {event['voter']} voted for {event['target']}")
        elif kind == "elimination":
            lines.append(f"Day {event['day']}: {event['message']}")
        elif kind == "no_elimination":
            lines.append(f"Day {event['day']}: {event['message']}")
        elif kind == "system":
            lines.append(event["message"])
    return "\n".join(lines) if lines else "No public events yet."


def private_context(player: Player, players: dict[str, Player]) -> str:
    if player.role == "Mafia":
        team = [name for name, other in players.items() if other.role == "Mafia" and name != player.name]
        return f"Your Mafia teammate(s): {', '.join(team) if team else 'none alive/known'}."
    if player.role == "Detective":
        if not player.investigations:
            return "Detective investigations so far: none."
        items = [f"{name} is {result}" for name, result in sorted(player.investigations.items())]
        return "Detective investigations so far: " + "; ".join(items) + "."
    if player.role == "Doctor":
        return f"Last protected player: {player.last_protected or 'none'}."
    return "No private role information."


def public_role_claims(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    explicit = re.compile(
        r"\b(?:hard claim:?\s*)?(?:i\s*(?:am|['’]m|was)|i claim(?:ed)?(?: to be)?|claiming(?: to be)?)\s+(?:a\s+|the\s+)?"
        r"(detective|doctor|villager|mafia)\b",
        flags=re.I,
    )
    detective_hint = re.compile(r"\b(?:i|my)\s+(?:investigated|checked|scanned|got a result on)\b", flags=re.I)
    doctor_hint = re.compile(r"\b(?:i|my)\s+(?:protected|saved|healed|guarded)\b", flags=re.I)
    for event in events:
        if event.get("type") != "discussion":
            continue
        message = str(event.get("message", ""))
        speaker = event.get("speaker", "?")
        for match in explicit.finditer(message):
            claims.append({
                "day": event.get("day"),
                "speaker": speaker,
                "role": match.group(1).title(),
                "evidence": trim_message(message, 18),
                "kind": "explicit",
            })
        if detective_hint.search(message):
            claims.append({
                "day": event.get("day"),
                "speaker": speaker,
                "role": "Detective",
                "evidence": trim_message(message, 18),
                "kind": "power_hint",
            })
        if doctor_hint.search(message):
            claims.append({
                "day": event.get("day"),
                "speaker": speaker,
                "role": "Doctor",
                "evidence": trim_message(message, 18),
                "kind": "power_hint",
            })
    return claims


def format_claim_ledger(events: list[dict[str, Any]], max_items: int = 12) -> str:
    claims = public_role_claims(events)
    if not claims:
        return "No public role or power claims yet."
    lines = []
    for claim in claims[-max_items:]:
        lines.append(
            f"Day {claim['day']}: {claim['speaker']} claimed {claim['role']} "
            f"({claim['kind']}: \"{claim['evidence']}\")."
        )
    return "\n".join(lines)


def format_vote_ledger(events: list[dict[str, Any]], max_days: int = 3) -> str:
    votes_by_day: dict[int, list[dict[str, Any]]] = defaultdict(list)
    eliminations: dict[int, dict[str, Any]] = {}
    for event in events:
        if event.get("type") == "vote":
            votes_by_day[int(event["day"])].append(event)
        elif event.get("type") == "elimination":
            eliminations[int(event["day"])] = event
        elif event.get("type") == "no_elimination":
            eliminations[int(event["day"])] = event
    if not votes_by_day and not eliminations:
        return "No votes yet."
    days = sorted(set(votes_by_day) | set(eliminations))[-max_days:]
    lines = []
    for day in days:
        votes = votes_by_day.get(day, [])
        if votes:
            counts = Counter(vote["target"] for vote in votes)
            count_text = ", ".join(f"{target}:{count}" for target, count in counts.most_common())
            voter_text = "; ".join(f"{vote['voter']}->{vote['target']}" for vote in votes)
            lines.append(f"Day {day} votes: {count_text}. Ballots: {voter_text}.")
        if day in eliminations:
            elim = eliminations[day]
            if elim.get("type") == "no_elimination":
                lines.append(f"Day {day} result: {elim['message']}")
            else:
                lines.append(f"Day {day} reveal: {elim['target']} was {elim['role']}.")
    return "\n".join(lines)


def revealed_role_counts(events: list[dict[str, Any]]) -> str:
    counts = Counter(event.get("role") for event in events if event.get("type") == "elimination")
    if not counts:
        return "No publicly revealed vote-elimination roles yet."
    remaining = Counter({"Mafia": 2, "Detective": 1, "Doctor": 1, "Villager": 3})
    for role, count in counts.items():
        if role:
            remaining[role] -= count
    parts = [f"{role}: revealed {counts.get(role, 0)}, remaining slots {max(remaining.get(role, 0), 0)}" for role in ["Mafia", "Detective", "Doctor", "Villager"]]
    return "; ".join(parts) + "."


def format_deception_flags(events: list[dict[str, Any]]) -> str:
    claims = public_role_claims(events)
    flags: list[str] = []
    by_speaker: dict[str, set[str]] = defaultdict(set)
    by_role: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        by_speaker[str(claim["speaker"])].add(str(claim["role"]))
        by_role[str(claim["role"])].add(str(claim["speaker"]))
    for speaker, roles in sorted(by_speaker.items()):
        if len(roles) > 1:
            flags.append(f"{speaker} has made multiple role/power claims: {', '.join(sorted(roles))}.")
    for role in ["Detective", "Doctor"]:
        claimers = by_role.get(role, set())
        if len(claimers) > 1:
            flags.append(f"Multiple {role} claimers: {', '.join(sorted(claimers))}.")
    vote_swings: dict[str, list[str]] = defaultdict(list)
    for event in events:
        if event.get("type") == "vote":
            vote_swings[str(event["voter"])].append(str(event["target"]))
    for voter, targets in sorted(vote_swings.items()):
        if len(set(targets[-3:])) >= 3:
            flags.append(f"{voter} has spread recent votes across many targets: {', '.join(targets[-3:])}.")
    return "\n".join(flags[-8:]) if flags else "No public deception flags yet."


def public_suspicion_table(events: list[dict[str, Any]], alive: list[str]) -> str:
    scores = {name: 0.0 for name in alive}
    reasons: dict[str, list[str]] = {name: [] for name in alive}
    claims = public_role_claims(events)
    by_role: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        speaker = str(claim["speaker"])
        role = str(claim["role"])
        by_role[role].add(speaker)
        if speaker in scores and role == "Mafia":
            scores[speaker] += 2.0
            reasons[speaker].append("public Mafia claim")
        elif speaker in scores and claim.get("kind") == "power_hint":
            scores[speaker] += 0.4
            reasons[speaker].append(f"{role} power hint")
    for role, claimers in by_role.items():
        if role in {"Detective", "Doctor"} and len(claimers) > 1:
            for speaker in claimers:
                if speaker in scores:
                    scores[speaker] += 1.2
                    reasons[speaker].append(f"contested {role} claim")
    recent_votes = [event for event in events if event.get("type") == "vote"][-21:]
    vote_targets = Counter(str(event.get("target")) for event in recent_votes)
    for target, count in vote_targets.items():
        if target in scores:
            scores[target] += min(1.5, 0.35 * count)
            reasons[target].append(f"{count} recent vote(s) received")
    voter_targets: dict[str, list[str]] = defaultdict(list)
    for event in recent_votes:
        voter_targets[str(event.get("voter"))].append(str(event.get("target")))
    for voter, targets in voter_targets.items():
        if voter in scores and len(set(targets[-3:])) >= 3:
            scores[voter] += 0.7
            reasons[voter].append("scattered vote pressure")
    lines = []
    for name in alive:
        normalized = min(1.0, scores[name] / 4.0)
        why = "; ".join(reasons[name][-3:]) if reasons[name] else "no public flags"
        lines.append(f"{name}: suspicion {normalized:.2f} ({why})")
    return "\n".join(lines)


def public_belief_table(events: list[dict[str, Any]], alive: list[str]) -> str:
    revealed = Counter(event.get("role") for event in events if event.get("type") == "elimination")
    remaining = Counter({"Mafia": 2, "Detective": 1, "Doctor": 1, "Villager": 3})
    for role, count in revealed.items():
        if role:
            remaining[role] -= count
    mafia_slots = max(remaining["Mafia"], 0)
    alive_count = max(len(alive), 1)
    base_mafia = mafia_slots / alive_count
    suspicion = {}
    for line in public_suspicion_table(events, alive).splitlines():
        match = re.match(r"([^:]+): suspicion ([0-9.]+)", line)
        if match:
            suspicion[match.group(1)] = float(match.group(2))
    raw = {name: max(0.01, base_mafia + (suspicion.get(name, 0.0) - 0.25) * 0.35) for name in alive}
    total_raw = sum(raw.values()) or 1.0
    scale = mafia_slots / total_raw if mafia_slots else 0.0
    lines = [
        "Approximate public GRAIL-style role table. These are not private truth; they are public-evidence priors constrained by remaining role slots.",
        f"Remaining slots: Mafia={max(remaining['Mafia'], 0)}, Detective={max(remaining['Detective'], 0)}, Doctor={max(remaining['Doctor'], 0)}, Villager={max(remaining['Villager'], 0)}.",
    ]
    for name in alive:
        mafia_prob = min(0.99, max(0.0, raw[name] * scale))
        non_mafia = max(0.0, 1.0 - mafia_prob)
        lines.append(f"{name}: P(Mafia)~{mafia_prob:.2f}, P(non-Mafia)~{non_mafia:.2f}")
    return "\n".join(lines)


def remaining_role_slots(events: list[dict[str, Any]]) -> Counter[str]:
    remaining = Counter({"Mafia": 2, "Detective": 1, "Doctor": 1, "Villager": 3})
    for event in events:
        if event.get("type") == "elimination" and event.get("role"):
            remaining[str(event["role"])] -= 1
    for role in ["Mafia", "Detective", "Doctor", "Villager"]:
        remaining[role] = max(remaining[role], 0)
    return remaining


def hg_v2_claim_state(events: list[dict[str, Any]]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, set[str]]]:
    by_player: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_role: dict[str, set[str]] = defaultdict(set)
    for claim in public_role_claims(events):
        speaker = str(claim.get("speaker", ""))
        role = str(claim.get("role", ""))
        if speaker and role:
            by_player[speaker].append(claim)
            by_role[role].add(speaker)
    return by_player, by_role


def hg_v2_vote_signal(events: list[dict[str, Any]], alive: list[str]) -> tuple[dict[str, float], dict[str, list[str]]]:
    scores = {name: 0.0 for name in alive}
    reasons: dict[str, list[str]] = {name: [] for name in alive}
    votes_by_day: dict[int, list[dict[str, Any]]] = defaultdict(list)
    eliminations: dict[int, dict[str, Any]] = {}
    for event in events:
        if event.get("type") == "vote":
            votes_by_day[int(event["day"])].append(event)
        elif event.get("type") == "elimination":
            eliminations[int(event["day"])] = event

    for day, elimination in sorted(eliminations.items()):
        target = str(elimination.get("target", ""))
        role = str(elimination.get("role", ""))
        for vote in votes_by_day.get(day, []):
            voter = str(vote.get("voter", ""))
            voted = str(vote.get("target", ""))
            if voter not in scores:
                continue
            if role == "Mafia":
                if voted == target:
                    scores[voter] -= 0.65
                    reasons[voter].append(f"voted out Mafia {target} on Day {day}")
                else:
                    scores[voter] += 0.45
                    reasons[voter].append(f"avoided Mafia vote Day {day}")
            elif role in GOOD_ROLES and voted == target:
                vote_count = len(votes_by_day.get(day, [])) or 1
                target_vote_count = sum(1 for item in votes_by_day.get(day, []) if item.get("target") == target)
                consensus_discount = 0.35 if target_vote_count / vote_count >= 0.6 else 1.0
                penalty = 0.65 if role in {"Detective", "Doctor"} else 0.35
                penalty *= consensus_discount
                scores[voter] += penalty
                reasons[voter].append(f"voted out {role} {target} on Day {day}")

    recent_votes = [event for event in events if event.get("type") == "vote"][-14:]
    received = Counter(str(event.get("target")) for event in recent_votes)
    for target, count in received.items():
        if target in scores and count >= 2:
            scores[target] += min(0.45, 0.12 * count)
            reasons[target].append(f"received {count} recent votes")
    return scores, reasons


def hg_v2_social_alignment(events: list[dict[str, Any]], max_items: int = 10) -> str:
    relations: list[str] = []
    names = "|".join(re.escape(name) for name in PLAYER_NAMES)
    accuse_re = re.compile(rf"\b(?:suspect|accuse|vote|pressure|push|eliminate|lynch)\s+({names})\b", re.I)
    defend_re = re.compile(rf"\b(?:trust|defend|support|clear|agree with)\s+({names})\b", re.I)
    for event in events:
        if event.get("type") != "discussion":
            continue
        speaker = str(event.get("speaker", ""))
        message = str(event.get("message", ""))
        day = event.get("day")
        for target in accuse_re.findall(message):
            if target != speaker:
                relations.append(f"Day {day}: {speaker} accuses/pressures {target}")
        for target in defend_re.findall(message):
            if target != speaker:
                relations.append(f"Day {day}: {speaker} defends/supports {target}")
    return "\n".join(relations[-max_items:]) if relations else "No explicit accusation/defense relations extracted yet."


def hg_v2_endgame_state(players: dict[str, Player], events: list[dict[str, Any]]) -> dict[str, Any]:
    alive = alive_players(players)
    remaining = remaining_role_slots(events)
    alive_count = len(alive)
    max_public_mafia = min(remaining["Mafia"], alive_count)
    min_public_good = max(0, alive_count - max_public_mafia)
    possible_parity_now = max_public_mafia >= min_public_good if alive_count else False
    good_after_possible_miselim = max(0, alive_count - 1 - max_public_mafia)
    must_vote_mafia_today = max_public_mafia >= max(1, good_after_possible_miselim)
    state = "normal"
    if must_vote_mafia_today:
        state = "parity_risk"
    if alive_count <= 4:
        state = "lylo_or_terminal"
    return {
        "alive_count": alive_count,
        "public_max_mafia": max_public_mafia,
        "public_min_good": min_public_good,
        "state": state,
        "possible_parity_now": possible_parity_now,
        "must_vote_mafia_today": must_vote_mafia_today,
    }


def hg_v2_posterior(player: Player, players: dict[str, Player], events: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, list[str]]]:
    alive = alive_players(players)
    remaining = remaining_role_slots(events)
    mafia_slots = max(remaining["Mafia"], 0)
    base = mafia_slots / max(len(alive), 1)
    claim_by_player, claim_by_role = hg_v2_claim_state(events)
    vote_scores, vote_reasons = hg_v2_vote_signal(events, alive)
    suspicion_scores: dict[str, float] = {}
    for line in public_suspicion_table(events, alive).splitlines():
        match = re.match(r"([^:]+): suspicion ([0-9.]+)", line)
        if match:
            suspicion_scores[match.group(1)] = float(match.group(2))

    raw: dict[str, float] = {}
    reasons: dict[str, list[str]] = {name: [] for name in alive}
    for name in alive:
        score = 0.0
        if player.role == "Detective" and name in player.investigations:
            if player.investigations[name] == "Mafia":
                raw[name] = 4.0
                reasons[name].append("private Detective result: Mafia")
                continue
            raw[name] = 0.01
            reasons[name].append("private Detective result: not Mafia")
            continue
        if player.role == "Mafia" and players[name].role == "Mafia":
            raw[name] = 3.5
            reasons[name].append("private Mafia teammate")
            continue

        score += vote_scores.get(name, 0.0)
        reasons[name].extend(vote_reasons.get(name, [])[-2:])

        suspicion = suspicion_scores.get(name, 0.0)
        score += (suspicion - 0.25) * 0.75
        if suspicion >= 0.45:
            reasons[name].append(f"public calibrated suspicion {suspicion:.2f}")

        claims = claim_by_player.get(name, [])
        roles = {str(claim.get("role")) for claim in claims}
        if "Mafia" in roles:
            score += 2.0
            reasons[name].append("public Mafia claim")
        for role in roles:
            if role in {"Detective", "Doctor"}:
                contested = len(claim_by_role.get(role, set())) > 1
                exhausted = remaining.get(role, 0) <= 0
                if contested or exhausted:
                    score += 1.25
                    reasons[name].append(f"contested/impossible {role} claim")
                else:
                    score -= 0.15
                    reasons[name].append(f"uncontested {role} claim; do not over-penalize withholding")

        raw[name] = max(0.01, base + score * 0.18)
        if not reasons[name]:
            reasons[name].append("near base public role-count prior")

    total_raw = sum(raw.values()) or 1.0
    scale = mafia_slots / total_raw if mafia_slots else 0.0
    posterior = {name: min(0.99, max(0.0, raw[name] * scale)) for name in alive}
    return posterior, reasons


def format_hg_v2_state_context(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> str:
    if normalize_architecture(player.spec.architecture) != "holy_grail_v2":
        return ""
    alive = alive_players(players)
    remaining = remaining_role_slots(events)
    posterior, reasons = hg_v2_posterior(player, players, events)
    ranked = sorted(alive, key=lambda name: posterior.get(name, 0.0), reverse=True)
    belief_lines = []
    for name in ranked:
        why = "; ".join(reasons.get(name, [])[-3:])
        belief_lines.append(f"{name}: P(Mafia)={posterior.get(name, 0.0):.2f}; evidence={why}")
    endgame = hg_v2_endgame_state(players, events)
    claim_by_player, claim_by_role = hg_v2_claim_state(events)
    claim_lines = []
    for name in alive:
        claims = claim_by_player.get(name, [])
        if claims:
            roles = ", ".join(sorted({str(claim.get("role")) for claim in claims}))
            claim_lines.append(f"{name}: {roles}")
    for role in ["Detective", "Doctor"]:
        claimers = sorted(claim_by_role.get(role, set()))
        if len(claimers) > 1:
            claim_lines.append(f"Conflict: multiple {role} claimers: {', '.join(claimers)}")
    candidate_line = f"Current action candidates: {candidates}" if candidates else "Current action candidates: none"
    return (
        "Holy Grail v2 deterministic state snapshot:\n"
        f"- Day/night index: {day}; action: {action}; {candidate_line}\n"
        f"- Remaining public role slots: Mafia={remaining['Mafia']}, Detective={remaining['Detective']}, Doctor={remaining['Doctor']}, Villager={remaining['Villager']}.\n"
        f"- Endgame state: {endgame['state']}; must_vote_mafia_today={endgame['must_vote_mafia_today']}; public_max_mafia={endgame['public_max_mafia']}.\n"
        "- Structured GRAIL posterior:\n" + "\n".join(belief_lines) + "\n"
        "- Public claim state:\n" + ("\n".join(claim_lines) if claim_lines else "No public role claims/hints yet.") + "\n"
        "- ReVAC social alignment graph excerpt:\n" + hg_v2_social_alignment(events) + "\n"
    )


def hg_v3_public_pressure(events: list[dict[str, Any]], candidates: list[str], day: int) -> tuple[dict[str, float], dict[str, float], dict[str, list[str]]]:
    case_strength = {candidate: 0.0 for candidate in candidates}
    coalition = {candidate: 0.0 for candidate in candidates}
    reasons: dict[str, list[str]] = {candidate: [] for candidate in candidates}
    pressure_words = r"suspect|accuse|vote|pressure|push|eliminate|lynch|contradict|claim|case|evidence"
    defend_words = r"trust|defend|clear|support|protect|believe"
    supporters: dict[str, set[str]] = defaultdict(set)
    defenders: dict[str, set[str]] = defaultdict(set)
    weak_pressure_words = r"quiet|silence|silent|initial|opening|no claims|no strong|weak signal|neutral|early read"
    hard_evidence_words = r"checked|result|claim conflict|contradict|lied|fabricat|vote shift|revealed|saved|counterclaim|impossible"
    for event in events:
        if event.get("type") != "discussion" or int(event.get("day", -1)) != day:
            continue
        speaker = str(event.get("speaker", ""))
        text = str(event.get("message", ""))
        lowered = text.lower()
        for candidate in candidates:
            if not re.search(rf"\b{re.escape(candidate)}\b", text):
                continue
            if re.search(rf"\b({pressure_words})\b", lowered):
                weak_pressure = bool(re.search(rf"\b({weak_pressure_words})\b", lowered)) and not re.search(rf"\b({hard_evidence_words})\b", lowered)
                if weak_pressure:
                    case_strength[candidate] -= 0.35
                    coalition[candidate] -= 0.18
                    reasons[candidate].append(f"weak silence/early-read pressure from {speaker}; discount")
                    if speaker in case_strength and speaker != candidate:
                        reasons[speaker].append(f"initiated weak pressure on {candidate}")
                else:
                    supporters[candidate].add(speaker)
                    case_strength[candidate] += 0.35
                    if re.search(r"\b(because|evidence|vote|claim|contradict|result|checked|lied|shift)\b", lowered):
                        case_strength[candidate] += 0.25
                    reasons[candidate].append(f"public pressure from {speaker}")
            if re.search(rf"\b({defend_words})\b", lowered):
                defenders[candidate].add(speaker)
                case_strength[candidate] -= 0.25
                reasons[candidate].append(f"public defense from {speaker}")
    for candidate in candidates:
        coalition[candidate] = min(1.0, 0.32 * len(supporters[candidate]) - 0.22 * len(defenders[candidate]))
        case_strength[candidate] = max(-1.0, min(2.0, case_strength[candidate]))
        if supporters[candidate]:
            reasons[candidate].append(f"{len(supporters[candidate])} pressure speaker(s)")
        if defenders[candidate]:
            reasons[candidate].append(f"{len(defenders[candidate])} defense speaker(s)")
    return case_strength, coalition, reasons


def hg_v3_current_day_vote_pressure(events: list[dict[str, Any]], candidates: list[str], day: int) -> dict[str, float]:
    votes = [
        event for event in events
        if event.get("type") == "vote" and int(event.get("day", -1)) == day
    ]
    counts = Counter(str(event.get("target")) for event in votes)
    return {candidate: min(1.0, 0.28 * counts.get(candidate, 0)) for candidate in candidates}


def hg_v3_claim_features(events: list[dict[str, Any]], candidates: list[str]) -> tuple[dict[str, float], dict[str, float], dict[str, list[str]]]:
    remaining = remaining_role_slots(events)
    claim_by_player, claim_by_role = hg_v2_claim_state(events)
    power_risk = {candidate: 0.0 for candidate in candidates}
    claim_conflict = {candidate: 0.0 for candidate in candidates}
    reasons: dict[str, list[str]] = {candidate: [] for candidate in candidates}
    for candidate in candidates:
        roles = {str(claim.get("role")) for claim in claim_by_player.get(candidate, [])}
        for role in roles:
            if role in {"Detective", "Doctor"}:
                contested = len(claim_by_role.get(role, set())) > 1
                exhausted = remaining.get(role, 0) <= 0
                if contested or exhausted:
                    claim_conflict[candidate] += 1.0
                    reasons[candidate].append(f"contested/impossible {role} claim")
                else:
                    power_risk[candidate] += 1.0
                    reasons[candidate].append(f"uncontested {role} claim")
            elif role == "Mafia":
                claim_conflict[candidate] += 2.0
                reasons[candidate].append("public Mafia claim")
    return power_risk, claim_conflict, reasons


def hg_v3_action_values(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    if not candidates:
        return [], {}
    posterior, posterior_reasons = hg_v2_posterior(player, players, events)
    public_case, coalition, pressure_reasons = hg_v3_public_pressure(events, candidates, day)
    power_risk, claim_conflict, claim_reasons = hg_v3_claim_features(events, candidates)
    voted_mafia = hg_v2_voted_revealed_mafia_score(events, candidates)
    vote_pressure = hg_v2_recent_vote_pressure(events, candidates)
    same_day_vote_pressure = hg_v3_current_day_vote_pressure(events, candidates, day)
    endgame = hg_v2_endgame_state(players, events)

    values: list[dict[str, Any]] = []
    reasons: dict[str, list[str]] = {candidate: [] for candidate in candidates}
    for candidate in candidates:
        p_mafia = posterior.get(candidate, 0.0)
        components: dict[str, float] = {
            "posterior": p_mafia,
            "public_case": public_case.get(candidate, 0.0),
            "coalition": coalition.get(candidate, 0.0),
            "power_role_risk": power_risk.get(candidate, 0.0),
            "claim_conflict": claim_conflict.get(candidate, 0.0),
            "town_credit": voted_mafia.get(candidate, 0.0),
            "vote_pressure": vote_pressure.get(candidate, 0.0),
            "current_vote_support": same_day_vote_pressure.get(candidate, 0.0),
            "herd_risk": same_day_vote_pressure.get(candidate, 0.0) if public_case.get(candidate, 0.0) <= 0.1 and claim_conflict.get(candidate, 0.0) <= 0.0 else 0.0,
        }
        candidate_reasons = (
            posterior_reasons.get(candidate, [])[-2:]
            + pressure_reasons.get(candidate, [])[-2:]
            + claim_reasons.get(candidate, [])[-2:]
        )

        private_mafia_hit = player.role == "Detective" and player.investigations.get(candidate) == "Mafia"
        private_not_mafia = player.role == "Detective" and player.investigations.get(candidate) == "not Mafia"
        mafia_teammate = player.role == "Mafia" and players[candidate].role == "Mafia"

        if action == "vote":
            if player.role == "Mafia":
                score = (
                    1.0 * components["posterior"]
                    + 0.85 * components["public_case"]
                    + 0.75 * components["coalition"]
                    + 0.35 * components["power_role_risk"]
                    + 0.25 * components["vote_pressure"]
                    - 1.4 * components["town_credit"]
                    - (6.0 if mafia_teammate else 0.0)
                )
                if mafia_teammate:
                    candidate_reasons.append("private Mafia teammate; avoid unless forced")
            else:
                score = (
                    3.2 * components["posterior"]
                    + 0.8 * components["public_case"]
                    + 0.55 * components["coalition"]
                    + (0.85 * components["current_vote_support"] if (components["public_case"] >= 0.45 or components["claim_conflict"] > 0 or private_mafia_hit) else 0.0)
                    + 1.05 * components["claim_conflict"]
                    + (0.35 if endgame["must_vote_mafia_today"] else 0.0) * components["posterior"]
                    - 1.7 * components["power_role_risk"]
                    - 1.2 * components["town_credit"]
                    - 1.5 * components["herd_risk"]
                    - (4.0 if private_not_mafia else 0.0)
                    + (6.0 if private_mafia_hit else 0.0)
                )
                if private_mafia_hit:
                    candidate_reasons.append("private Detective result: Mafia")
                if private_not_mafia:
                    candidate_reasons.append("private Detective result: not Mafia")
        elif action == "detective_check":
            already_checked = candidate in player.investigations
            score = (
                2.5 * components["posterior"]
                + 0.75 * components["public_case"]
                + 0.7 * components["claim_conflict"]
                + 0.45 * components["coalition"]
                + 0.2 * components["vote_pressure"]
                - (3.0 if already_checked else 0.0)
            )
            if already_checked:
                candidate_reasons.append("already investigated")
        elif action == "doctor_save":
            self_exposure = 1.0 if candidate == player.name and (day > 1 or components["vote_pressure"] >= 0.2) else 0.0
            score = (
                2.2 * components["power_role_risk"]
                + 1.3 * components["town_credit"]
                + 0.65 * max(components["coalition"], 0.0)
                + 0.45 * max(components["public_case"], 0.0)
                + self_exposure
                - 1.6 * components["posterior"]
            )
            if self_exposure:
                candidate_reasons.append("self exposure/save value")
        elif action == "mafia_kill":
            score = (
                2.2 * components["power_role_risk"]
                + 1.4 * components["town_credit"]
                + 0.8 * max(components["coalition"], 0.0)
                + 0.45 * max(components["public_case"], 0.0)
                + 0.25 * components["vote_pressure"]
                - 0.8 * components["posterior"]
            )
        else:
            score = components["posterior"]

        values.append({
            "candidate": candidate,
            "score": round(score, 4),
            "components": {key: round(value, 4) for key, value in components.items()},
        })
        reasons[candidate] = candidate_reasons or ["low-signal action-value estimate"]

    values.sort(key=lambda row: (float(row["score"]), row["candidate"]), reverse=True)
    return values, reasons


def format_hg_v3_state_context(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> str:
    if normalize_architecture(player.spec.architecture) != "holy_grail_v3":
        return ""
    alive = alive_players(players)
    remaining = remaining_role_slots(events)
    posterior, posterior_reasons = hg_v2_posterior(player, players, events)
    ranked = sorted(alive, key=lambda name: posterior.get(name, 0.0), reverse=True)
    belief_lines = []
    for name in ranked:
        why = "; ".join(posterior_reasons.get(name, [])[-3:])
        belief_lines.append(f"{name}: P(Mafia)={posterior.get(name, 0.0):.2f}; evidence={why}")
    values, value_reasons = hg_v3_action_values(player, players, events, action, candidates, day)
    value_lines = []
    for row in values[:7]:
        candidate = str(row["candidate"])
        components = row["components"]
        why = "; ".join(value_reasons.get(candidate, [])[-3:])
        value_lines.append(
            f"{candidate}: value={row['score']:.2f}; posterior={components['posterior']:.2f}; "
            f"case={components['public_case']:.2f}; coalition={components['coalition']:.2f}; "
            f"power_risk={components['power_role_risk']:.2f}; claim_conflict={components['claim_conflict']:.2f}; "
            f"vote_support={components.get('current_vote_support', 0.0):.2f}; herd_risk={components.get('herd_risk', 0.0):.2f}; why={why}"
        )
    endgame = hg_v2_endgame_state(players, events)
    return (
        "Holy Grail v3 controller snapshot:\n"
        f"- Day/night index: {day}; action: {action}; candidates: {candidates if candidates else 'none'}.\n"
        f"- Remaining public role slots: Mafia={remaining['Mafia']}, Detective={remaining['Detective']}, Doctor={remaining['Doctor']}, Villager={remaining['Villager']}.\n"
        f"- Endgame state: {endgame['state']}; must_vote_mafia_today={endgame['must_vote_mafia_today']}; public_max_mafia={endgame['public_max_mafia']}.\n"
        "- GRAIL constrained posterior:\n" + "\n".join(belief_lines) + "\n"
        "- Role action-value table:\n" + ("\n".join(value_lines) if value_lines else "No target action values for this step.") + "\n"
        "- WOLF social alignment excerpt:\n" + hg_v2_social_alignment(events) + "\n"
    )


def holy_grail_public_investigation_claims(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = "|".join(re.escape(name) for name in PLAYER_NAMES)
    check_re = re.compile(
        rf"\b(?:night\s*(?P<night>\d+)\s*)?(?:i\s*)?(?:checked|investigated|scanned)\s+"
        rf"(?P<target>{names})\s+(?:as|and\s+(?:got|found)|result(?:ed)?\s*(?:as|was)?|is)?\s*"
        r"(?P<result>not\s+mafia|non[-\s]?mafia|town|good|mafia)\b",
        flags=re.I,
    )
    checked_good_re = re.compile(
        rf"\b(?P<target>{names})\s+(?:is|was)\s+(?:my\s+)?checked[-\s]?good\b",
        flags=re.I,
    )
    claims: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "discussion":
            continue
        message = str(event.get("message", ""))
        speaker = str(event.get("speaker", ""))
        for match in check_re.finditer(message):
            raw_result = match.group("result").lower().replace("-", " ")
            result = "Mafia" if raw_result == "mafia" else "not Mafia"
            night_raw = match.groupdict().get("night")
            claims.append({
                "day": event.get("day"),
                "speaker": speaker,
                "target": match.group("target"),
                "result": result,
                "night": int(night_raw) if night_raw else None,
                "evidence": trim_message(message, 22),
            })
        for match in checked_good_re.finditer(message):
            claims.append({
                "day": event.get("day"),
                "speaker": speaker,
                "target": match.group("target"),
                "result": "not Mafia",
                "night": None,
                "evidence": trim_message(message, 22),
            })
    return claims


def holy_grail_claim_adjudication(
    players: dict[str, Player],
    events: list[dict[str, Any]],
    candidates: list[str],
) -> dict[str, Any]:
    alive = set(alive_players(players))
    claim_by_player, claim_by_role = hg_v2_claim_state(events)
    detective_claimers = {name for name in claim_by_role.get("Detective", set()) if name in alive}
    doctor_claimers = {name for name in claim_by_role.get("Doctor", set()) if name in alive}
    detective_contested = len(detective_claimers) > 1
    doctor_contested = len(doctor_claimers) > 1
    credible_detectives = set() if detective_contested else set(detective_claimers)
    credible_doctors = set() if doctor_contested else set(doctor_claimers)

    public_mafia_hits: dict[str, list[str]] = defaultdict(list)
    public_checked_good: dict[str, list[str]] = defaultdict(list)
    public_results = holy_grail_public_investigation_claims(events)
    for claim in public_results:
        speaker = str(claim.get("speaker", ""))
        target = str(claim.get("target", ""))
        if target not in candidates and target not in alive:
            continue
        speaker_roles = {str(item.get("role")) for item in claim_by_player.get(speaker, [])}
        speaker_is_detective_like = speaker in credible_detectives or "Detective" in speaker_roles
        if not speaker_is_detective_like or detective_contested:
            continue
        if claim.get("result") == "Mafia":
            public_mafia_hits[target].append(speaker)
        else:
            public_checked_good[target].append(speaker)

    dangerous_vote: dict[str, list[str]] = defaultdict(list)
    for name in candidates:
        if name in credible_detectives:
            dangerous_vote[name].append("uncontested public Detective claim")
        if name in credible_doctors:
            dangerous_vote[name].append("uncontested public Doctor claim")
        if name in public_checked_good:
            dangerous_vote[name].append(f"public checked-good from {', '.join(sorted(set(public_checked_good[name])))}")

    lines: list[str] = []
    if detective_contested:
        lines.append(f"Detective counterclaim conflict: {', '.join(sorted(detective_claimers))}.")
    elif credible_detectives:
        lines.append(f"Credible public Detective claim: {', '.join(sorted(credible_detectives))}.")
    if doctor_contested:
        lines.append(f"Doctor counterclaim conflict: {', '.join(sorted(doctor_claimers))}.")
    elif credible_doctors:
        lines.append(f"Credible public Doctor claim: {', '.join(sorted(credible_doctors))}.")
    for target, speakers in sorted(public_mafia_hits.items()):
        lines.append(f"Public Mafia check: {', '.join(sorted(set(speakers)))} -> {target}.")
    for target, speakers in sorted(public_checked_good.items()):
        lines.append(f"Public checked-good: {', '.join(sorted(set(speakers)))} -> {target}.")
    return {
        "credible_detectives": credible_detectives,
        "credible_doctors": credible_doctors,
        "detective_contested": detective_contested,
        "doctor_contested": doctor_contested,
        "public_mafia_hits": public_mafia_hits,
        "public_checked_good": public_checked_good,
        "dangerous_vote": dangerous_vote,
        "lines": lines or ["No decisive public power-role adjudication yet."],
    }


def holy_grail_discussion_quality_signals(
    events: list[dict[str, Any]],
    candidates: list[str],
    day: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, list[str]]]:
    evasion = {candidate: 0.0 for candidate in candidates}
    leadership = {candidate: 0.0 for candidate in candidates}
    reasons: dict[str, list[str]] = {candidate: [] for candidate in candidates}
    prior_generic_phrases: Counter[str] = Counter()
    names_re = "|".join(re.escape(name) for name in PLAYER_NAMES)
    for event in events:
        if event.get("type") != "discussion" or int(event.get("day", -1)) != day:
            continue
        speaker = str(event.get("speaker", ""))
        if speaker not in evasion:
            continue
        message = str(event.get("message", ""))
        lowered = message.lower()
        named_other = bool(re.search(rf"\b({names_re})\b", message) and not re.fullmatch(rf".*\b{re.escape(speaker)}\b.*", message))
        concrete = bool(re.search(r"\b(because|vote|claim|checked|result|contradict|lied|saved|counterclaim|impossible|specific|evidence)\b", lowered))
        generic = bool(re.search(r"\b(shocked|share|observations|feelings? of unease|initial thoughts|early suspicions|who has information|quiet|silence)\b", lowered))
        if generic and not concrete and not named_other:
            evasion[speaker] += 0.28
            reasons[speaker].append("generic low-agency message without target or reason")
        phrase_keys = []
        for phrase in (
            "shocked by",
            "share any night",
            "feelings of unease",
            "who has information",
            "initial thoughts",
            "early suspicions",
        ):
            if phrase in lowered:
                phrase_keys.append(phrase)
        repeated = sum(prior_generic_phrases[key] for key in phrase_keys)
        if repeated:
            evasion[speaker] += min(0.55, 0.18 * repeated)
            reasons[speaker].append("echoed prior generic phrasing")
        if concrete and (named_other or re.search(r"\b(vote|claim|checked|result|contradict|counterclaim)\b", lowered)):
            leadership[speaker] += 0.35
            reasons[speaker].append("concrete public evidence or vote leadership")
        for key in phrase_keys:
            prior_generic_phrases[key] += 1
    return evasion, leadership, reasons


def holy_grail_action_values(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    values, reasons = hg_v3_action_values(player, players, events, action, candidates, day)
    adjudication = holy_grail_claim_adjudication(players, events, candidates)
    evasion, leadership, quality_reasons = holy_grail_discussion_quality_signals(events, candidates, day)
    current_vote_pressure = hg_v3_current_day_vote_pressure(events, candidates, day)
    value_by_candidate = {str(row["candidate"]): row for row in values}

    for candidate in candidates:
        row = value_by_candidate.get(candidate)
        if not row:
            continue
        score = float(row["score"])
        components = dict(row.get("components", {}))
        components["public_mafia_check"] = 1.0 if candidate in adjudication["public_mafia_hits"] else 0.0
        components["public_checked_good"] = 1.0 if candidate in adjudication["public_checked_good"] else 0.0
        components["credible_power_claim"] = 1.0 if candidate in adjudication["credible_detectives"] or candidate in adjudication["credible_doctors"] else 0.0
        components["low_agency_evasion"] = evasion.get(candidate, 0.0)
        components["public_leadership"] = leadership.get(candidate, 0.0)
        components["herd_vote_without_case"] = current_vote_pressure.get(candidate, 0.0) if (
            float(components.get("public_case", 0.0)) <= 0.1
            and float(components.get("claim_conflict", 0.0)) <= 0.0
            and candidate not in adjudication["public_mafia_hits"]
        ) else 0.0

        if action == "vote":
            if player.role == "Mafia":
                score += 0.85 * components["credible_power_claim"]
                score += 0.65 * components["public_checked_good"]
                score += 0.35 * components["public_leadership"]
                if candidate in adjudication["public_mafia_hits"] and players[candidate].role == "Mafia":
                    score -= 2.8
                    reasons[candidate].append("public Mafia check points at teammate; avoid unless forced")
            else:
                score += 7.5 * components["public_mafia_check"]
                score += 1.25 * components["low_agency_evasion"]
                score -= 4.2 * components["public_checked_good"]
                score -= 3.8 * components["credible_power_claim"]
                score -= 1.4 * components["public_leadership"]
                score -= 2.2 * components["herd_vote_without_case"]
        elif action == "detective_check":
            score += 0.85 * components["low_agency_evasion"]
            score += 0.5 * components["public_leadership"]
            score -= 2.5 * components["public_checked_good"]
            score -= 1.8 * components["credible_power_claim"]
        elif action == "doctor_save":
            score += 4.0 * (1.0 if candidate in adjudication["credible_detectives"] else 0.0)
            score += 2.1 * components["public_checked_good"]
            score += 0.8 * components["public_leadership"]
            score -= 1.6 * components["public_mafia_check"]
        elif action == "mafia_kill":
            score += 4.2 * (1.0 if candidate in adjudication["credible_detectives"] else 0.0)
            score += 2.2 * components["public_checked_good"]
            score += 1.2 * components["public_leadership"]
            score -= 1.3 * components["public_mafia_check"]

        if candidate in adjudication["public_mafia_hits"]:
            speakers = ", ".join(sorted(set(adjudication["public_mafia_hits"][candidate])))
            reasons[candidate].append(f"credible public Mafia check from {speakers}")
        if candidate in adjudication["dangerous_vote"]:
            reasons[candidate].extend(adjudication["dangerous_vote"][candidate][-2:])
        reasons[candidate].extend(quality_reasons.get(candidate, [])[-2:])
        row["score"] = round(score, 4)
        row["components"] = {key: round(float(value), 4) for key, value in components.items()}

    values.sort(key=lambda row: (float(row["score"]), str(row["candidate"])), reverse=True)
    return values, reasons, adjudication


def holy_grail_vote_plan(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    candidates: list[str],
    day: int,
) -> dict[str, Any]:
    values, reasons, adjudication = holy_grail_action_values(player, players, events, "vote", candidates, day)
    if not candidates or not values:
        return {
            "best_vote": None,
            "must_not_vote": [],
            "dangerous_votes": [],
            "acceptable_votes": [],
            "reason": "No vote candidates.",
            "action_values": [],
            "adjudication": adjudication,
        }
    must_vote = sorted(name for name in candidates if name in adjudication["public_mafia_hits"])
    dangerous = sorted(name for name in candidates if adjudication["dangerous_vote"].get(name))
    if player.role == "Detective":
        dangerous.extend(sorted(name for name in candidates if player.investigations.get(name) == "not Mafia"))
        for name in candidates:
            if player.investigations.get(name) == "Mafia" and name not in must_vote:
                must_vote.append(name)
    dangerous = sorted(set(dangerous))

    if player.role == "Mafia":
        non_partner_values = [row for row in values if players[str(row["candidate"])].role != "Mafia"]
        best_vote = str((non_partner_values or values)[0]["candidate"])
    elif must_vote:
        ranked_must = sorted(must_vote, key=lambda name: float(next((row["score"] for row in values if row["candidate"] == name), 0.0)), reverse=True)
        best_vote = ranked_must[0]
    else:
        safe_values = [row for row in values if str(row["candidate"]) not in dangerous]
        best_vote = str((safe_values or values)[0]["candidate"])
    acceptable = [str(row["candidate"]) for row in values[:3] if str(row["candidate"]) not in dangerous or str(row["candidate"]) == best_vote]
    reason = "; ".join(reasons.get(best_vote, [])[-4:]) if best_vote else "No recommended vote."
    return {
        "best_vote": best_vote,
        "must_not_vote": dangerous,
        "dangerous_votes": dangerous,
        "acceptable_votes": acceptable,
        "reason": reason,
        "action_values": values[:7],
        "adjudication": adjudication,
    }


def format_holy_grail_state_context(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> str:
    if normalize_architecture(player.spec.architecture) != "holy_grail":
        return ""
    alive = alive_players(players)
    remaining = remaining_role_slots(events)
    posterior, posterior_reasons = hg_v2_posterior(player, players, events)
    ranked = sorted(alive, key=lambda name: posterior.get(name, 0.0), reverse=True)
    belief_lines = [
        f"{name}: P(Mafia)={posterior.get(name, 0.0):.2f}; evidence={'; '.join(posterior_reasons.get(name, [])[-3:])}"
        for name in ranked
    ]
    values, value_reasons, adjudication = holy_grail_action_values(player, players, events, action, candidates, day)
    value_lines = []
    for row in values[:7]:
        candidate = str(row["candidate"])
        components = row["components"]
        why = "; ".join(value_reasons.get(candidate, [])[-4:])
        value_lines.append(
            f"{candidate}: value={row['score']:.2f}; posterior={components.get('posterior', 0.0):.2f}; "
            f"case={components.get('public_case', 0.0):.2f}; check={components.get('public_mafia_check', 0.0):.0f}; "
            f"checked_good={components.get('public_checked_good', 0.0):.0f}; power={components.get('credible_power_claim', 0.0):.0f}; "
            f"evasion={components.get('low_agency_evasion', 0.0):.2f}; herd={components.get('herd_vote_without_case', 0.0):.2f}; why={why}"
        )
    vote_plan = holy_grail_vote_plan(player, players, events, candidates, day) if action == "vote" else None
    vote_plan_text = ""
    if vote_plan:
        vote_plan_text = (
            "- Vote-closing plan:\n"
            f"best_vote={vote_plan['best_vote']}; must_not_vote={vote_plan['must_not_vote']}; "
            f"acceptable_votes={vote_plan['acceptable_votes']}; reason={vote_plan['reason']}\n"
        )
    endgame = hg_v2_endgame_state(players, events)
    return (
        "Holy Grail public-evidence controller snapshot:\n"
        f"- Day/night index: {day}; action: {action}; candidates: {candidates if candidates else 'none'}.\n"
        f"- Remaining public role slots: Mafia={remaining['Mafia']}, Detective={remaining['Detective']}, Doctor={remaining['Doctor']}, Villager={remaining['Villager']}.\n"
        f"- Endgame state: {endgame['state']}; must_vote_mafia_today={endgame['must_vote_mafia_today']}; public_max_mafia={endgame['public_max_mafia']}.\n"
        "- Public claim/check adjudication:\n" + "\n".join(adjudication["lines"]) + "\n"
        "- GRAIL constrained posterior:\n" + "\n".join(belief_lines) + "\n"
        "- Role action-value table:\n" + ("\n".join(value_lines) if value_lines else "No target action values for this step.") + "\n"
        + vote_plan_text
        + "- WOLF social alignment excerpt:\n" + hg_v2_social_alignment(events) + "\n"
    )


def architecture_context(player: Player, events: list[dict[str, Any]]) -> str:
    architecture = normalize_architecture(player.spec.architecture)
    if architecture == "baseline":
        return ""
    alive = [name for name in PLAYER_NAMES if not any(
        (event.get("type") == "elimination" and event.get("target") == name)
        or (event.get("type") == "night_result" and str(event.get("message", "")).startswith(f"{name} was killed"))
        for event in events
    )]
    sections = [
        "Public role-count status: " + revealed_role_counts(events),
        "Public GRAIL belief table:\n" + public_belief_table(events, alive),
        "Public claim ledger:\n" + format_claim_ledger(events),
        "Public vote ledger:\n" + format_vote_ledger(events),
    ]
    if architecture in {"wolf", "grail_wolf", "revac", "grail_wolf_verified", "wolf_revac_grail", "role_adaptive_hybrid", "holy_grail", "holy_grail_v2", "holy_grail_v3", "holy_grail"}:
        sections.append("Public deception flags:\n" + format_deception_flags(events))
        sections.append("Public WOLF suspicion table:\n" + public_suspicion_table(events, alive))
    if architecture in {"revac", "grail_wolf", "grail_wolf_verified", "wolf_revac_grail", "role_adaptive_hybrid", "holy_grail", "holy_grail_v2", "holy_grail_v3", "holy_grail"}:
        sections.append(
            "Private ReVAC review memory: track player profiles, social alignments, contradictions, current objective, "
            "strongest evidence, uncertainty, downside if wrong, best tone for the next public move, final action."
        )
    return "\n\n".join(sections) + "\n"


def build_prompt(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
    protocol: str,
    candidate_message: str | None = None,
    moderator_cue: str | None = None,
    review_context: str | None = None,
) -> str:
    alive = alive_players(players)
    public = compact_transcript(events)
    private = private_context(player, players)
    base = f"""You are {player.name} in a 7-player Mafia game.
Role: {player.role}
{role_objective(player.role)}

Alive players: {', '.join(alive)}
Original role counts: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.
{private}

Public transcript:
{public}

{architecture_text(player.spec.architecture)}
{architecture_context(player, events)}
{holy_grail_role_kernel(player, action, protocol)}
{format_hg_v2_state_context(player, players, events, action, candidates, day)}
{format_hg_v3_state_context(player, players, events, action, candidates, day)}
{format_holy_grail_state_context(player, players, events, action, candidates, day)}
"""
    if review_context:
        base += f"""
Private ReVAC review summary for this action. Use it silently; do not reveal it verbatim:
{review_context}
"""
    if action == "discussion":
        if protocol == "time_to_talk":
            return base + f"""
Day {day} discussion. You must say one concise public message that helps your faction.

Return JSON exactly:
{{"message": "public message, 28 words or fewer"}}
"""
        return base + f"""
Day {day} discussion. You must say one concise public message that helps your faction.

Return JSON exactly:
{{"message": "public message, 28 words or fewer"}}
"""
    if action == "time_to_talk_offer":
        return base + f"""
Day {day} game-level Time-to-Talk scheduler.
The scheduler is collecting speaking offers from all alive players and will select the most useful next public message.
You may speak more than once today if the public transcript has changed, but do not repeat yourself.

Decide if speaking now helps your faction more than waiting.
Urgency scale:
0 = no useful contribution
1 = minor or redundant comment
2 = useful clarification
3 = useful pressure, defense, or question
4 = important evidence, role-claim response, or vote coordination
5 = urgent correction, decisive claim, or endgame vote-critical message

Return JSON exactly:
{{"speak": true/false, "urgency": 0-5, "message": "public message, 28 words or fewer"}}
"""
    if action == "role_aware_time_to_talk_offer":
        return base + f"""
Day {day} role-aware, floor-constrained Time-to-Talk scheduler.
The scheduler must collect enough useful public discussion before voting, then stop when additional speech is low-value.
Offer to speak only when your next message adds new pressure, verified evidence, claim analysis, defense, or vote coordination.
If today's public discussion is still sparse, a concrete first contribution is usually better than waiting.
Waiting is appropriate only when your message would be redundant, self-damaging, or tactically mistimed.

Role-aware guidance:
- Detective: high urgency for a Mafia result, a claim conflict, or a vote that risks eliminating a checked good player.
- Doctor: avoid unnecessary exposure; speak when you can defend a critical vote, challenge a dangerous claim, or coordinate without outing yourself.
- Villager: ask concrete questions, pressure contradictions, and coordinate around credible claims or vote evidence.
- Mafia: shape suspicion plausibly, avoid impossible claims under role counts, manage partner defense/distancing, and do not overexplain.

Message types: evidence, claim_check, pressure, defense, vote_coordination, deception, wait.
Urgency scale:
0 = wait
1 = minor or redundant comment
2 = useful clarification
3 = useful pressure, defense, or question
4 = important evidence, role-claim response, or vote coordination
5 = urgent correction, decisive claim, or endgame vote-critical message

Return JSON exactly:
{{"speak": true/false, "urgency": 0-5, "message_type": "one message type", "message": "public message, 28 words or fewer"}}
"""
    if action == "role_aware_quality_time_to_talk_offer":
        return base + f"""
Day {day} role-aware, quality-filtered Time-to-Talk scheduler.
The scheduler must collect enough useful public discussion before voting, then stop when additional speech is low-value.
Offer to speak only if your next message is new, role-appropriate, tactically useful, and not redundant with the transcript.
If today's public discussion is still sparse, a concrete first contribution is usually better than waiting.
Waiting is appropriate when your message repeats prior content, creates unnecessary exposure, or gives the opposing faction a cleaner target.

Role-aware quality guidance:
- Detective: speak for a Mafia result, a claim conflict, or a vote that risks eliminating a checked good player; avoid vague unsupported pressure.
- Doctor: avoid unnecessary exposure; do not assume protected targets know they were protected unless the public transcript says so.
- Villager: ask concrete questions, pressure contradictions, and coordinate votes around credible claims or vote evidence.
- Mafia: shape suspicion plausibly, avoid impossible claims under role counts, manage partner defense/distancing, and do not overexplain.

Quality score:
0 = harmful or redundant
1 = generic table noise
2 = minor clarification
3 = useful concrete pressure, defense, or question
4 = strong evidence, claim check, or vote coordination
5 = decisive, timely, role-aware, and low-risk

Redundancy risk:
0 = new information or new tactical synthesis
5 = repeats the transcript without adding value

Message types: evidence, claim_check, pressure, defense, vote_coordination, deception, wait.
Urgency scale:
0 = wait
1 = minor or redundant comment
2 = useful clarification
3 = useful pressure, defense, or question
4 = important evidence, role-claim response, or vote coordination
5 = urgent correction, decisive claim, or endgame vote-critical message

Return JSON exactly:
{{"speak": true/false, "urgency": 0-5, "quality": 0-5, "redundancy_risk": 0-5, "message_type": "one message type", "message": "public message, 28 words or fewer"}}
"""
    if action == "forced_role_aware_message":
        return base + f"""
Day {day} role-aware Time-to-Talk floor.
The game has not reached enough useful public discussion for a vote, so you must speak now.
Give one concise, role-appropriate public message that advances your faction without repeating the transcript.

Useful options: a concrete suspicion with evidence, a claim-count check, a vote-coordination proposal, a defense against a bad push, or a plausible Mafia deception.
Do not reveal private reasoning. Only make a hard power-role claim if it is strategically necessary.

Return JSON exactly:
{{"message_type": "evidence/claim_check/pressure/defense/vote_coordination/deception", "message": "public message, 28 words or fewer"}}
"""
    if action == "moderator_cued_message":
        cue = moderator_cue or "The moderator has given you the floor. Add a useful, concise public message."
        return base + f"""
Day {day} moderated asynchronous Time-to-Talk.
The neutral moderator has given you the floor with this cue:
"{trim_message(cue, 40)}"

Respond as a player, not as the moderator. Add one concise public message that advances your faction,
answers the moderator's cue, and does not repeat the transcript.
Do not reveal private reasoning. Only make a hard power-role claim if it is strategically necessary.

Return JSON exactly:
{{"message_type": "evidence/claim_check/pressure/defense/vote_coordination/deception", "message": "public message, 32 words or fewer"}}
"""
    if action == "candidate_message":
        return base + f"""
Day {day} candidate-generation step. Draft the public message you would send if asked to speak now.
Make it useful to your faction and socially plausible. Do not decide timing yet.

Return JSON exactly:
{{"message": "candidate public message, 28 words or fewer"}}
"""
    if action == "schedule_candidate":
        proposed = candidate_message or ""
        return base + f"""
Day {day} candidate-first Time-to-Talk scheduler.
Candidate message:
"{trim_message(proposed, 36)}"

Decide whether this is the right time to send the candidate message. The game-level scheduler will compare
offers from all alive players and choose the most useful next public message.
Send it if it adds new evidence, pressure, defense, coordination, or useful deception.
Wait if it is redundant, mistimed, or strategically harmful.
If sending, you may lightly edit the candidate for tone but keep the same strategic content.
Urgency scale:
0 = no useful contribution
1 = minor or redundant comment
2 = useful clarification
3 = useful pressure, defense, or question
4 = important evidence, role-claim response, or vote coordination
5 = urgent correction, decisive claim, or endgame vote-critical message

Return JSON exactly:
{{"speak": true/false, "urgency": 0-5, "message": "public message, 28 words or fewer"}}
"""
    if action == "vote":
        return base + f"""
Day {day} vote. Vote to eliminate exactly one player from this candidate list:
{candidates}

Return JSON exactly:
{{"target": "one exact candidate name"}}
"""
    if action == "mafia_kill":
        return base + f"""
Night {day}. The Mafia must choose exactly one non-Mafia player to kill from:
{candidates}

Return JSON exactly:
{{"target": "one exact candidate name"}}
"""
    if action == "detective_check":
        return base + f"""
Night {day}. Choose exactly one player to investigate from:
{candidates}

Return JSON exactly:
{{"target": "one exact candidate name"}}
"""
    if action == "doctor_save":
        return base + f"""
Night {day}. Choose exactly one alive player to protect from:
{candidates}

Return JSON exactly:
{{"target": "one exact candidate name"}}
"""
    raise ValueError(action)


def extract_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def parse_target(response: str, candidates: list[str]) -> tuple[str | None, bool]:
    parsed = extract_json(response)
    raw_values = []
    if parsed:
        for key in ("target", "vote", "vote_out", "player", "name"):
            if key in parsed:
                raw_values.append(str(parsed[key]))
    raw_values.append(response.splitlines()[0] if response.splitlines() else response)
    raw_values.append(response)
    for value in raw_values:
        for candidate in candidates:
            if value.strip().lower() == candidate.lower():
                return candidate, False
    for value in raw_values:
        for candidate in candidates:
            if re.search(rf"\b{re.escape(candidate)}\b", value, flags=re.I):
                return candidate, False
    return None, True


def parse_discussion(response: str, protocol: str) -> tuple[bool, str | None, bool]:
    parsed = extract_json(response)
    if parsed:
        speak = parsed.get("speak", True)
        if isinstance(speak, str):
            speak = speak.strip().lower() not in {"false", "no", "wait", "pass"}
        message = parsed.get("message", "")
        if not speak:
            return False, None, False
        if isinstance(message, str) and message.strip():
            return True, trim_message(message), False
    if protocol in {"time_to_talk", "candidate_time_to_talk", "role_aware_time_to_talk", "role_aware_quality_time_to_talk", *MODERATED_PROTOCOLS} and re.search(r"\b(wait|pass|silent)\b", response, flags=re.I):
        return False, None, False
    match = re.search(r'"([^"]{1,220})"', response)
    if match:
        return True, trim_message(match.group(1)), False
    first = response.strip().splitlines()[0] if response.strip() else ""
    if first:
        return True, trim_message(first), True
    return False, None, True


def holy_grail_v3_message_guardrail(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    day: int,
    speak: bool,
    message: str | None,
    stats: GameStats,
) -> tuple[bool, str | None, bool, str]:
    if normalize_architecture(player.spec.architecture) != "holy_grail_v3":
        return speak, message, False, ""
    if action not in {"moderator_cued_message", "forced_role_aware_message", "discussion"}:
        return speak, message, False, ""

    def under_public_pressure(name: str) -> bool:
        pressure_terms = r"suspect|suspicious|pressure|push|nominate|vote|lynch|eliminate|quiet|silence|lack of input|noted your|mentioned your|inactive"
        for event in events:
            if int(event.get("day", -1)) != day:
                continue
            if event.get("type") == "discussion":
                text = str(event.get("message", ""))
            elif event.get("type") == "moderator_prompt":
                text = str(event.get("cue", ""))
            else:
                continue
            if (event.get("target") == name or re.search(rf"\b{re.escape(name)}\b", text)) and re.search(rf"\b({pressure_terms})\b", text, flags=re.I):
                return True
        return False

    if player.role == "Detective":
        checks = [
            event for event in events
            if event.get("type") == "detective_check" and event.get("detective") == player.name
        ]
        mafia_hits = [
            event for event in checks
            if event.get("result") == "Mafia"
            and str(event.get("target", "")) in players
            and players[str(event.get("target"))].alive
        ]
        if mafia_hits:
            hit = mafia_hits[-1]
            target = str(hit["target"])
            night = int(hit.get("night", day))
            guarded = f"I claim Detective: Night {night} I checked {target} as Mafia. Vote {target} today; Doctor protect me if alive."
            stats.holy_grail_v3_message_overrides += 1
            events.append({
                "type": "architecture_message_guardrail",
                "architecture": "holy_grail_v3",
                "player": player.name,
                "role": player.role,
                "action": action,
                "day": day,
                "reason": "Detective Mafia result reveal gate",
                "selected_message": guarded,
            })
            return True, trim_message(guarded, 32), True, "evidence"
        if checks and under_public_pressure(player.name):
            check = checks[-1]
            target = str(check["target"])
            result = str(check["result"])
            night = int(check.get("night", day))
            guarded = f"I claim Detective under pressure: Night {night} I checked {target} as {result}. Do not eliminate me on weak pressure."
            stats.holy_grail_v3_message_overrides += 1
            events.append({
                "type": "architecture_message_guardrail",
                "architecture": "holy_grail_v3",
                "player": player.name,
                "role": player.role,
                "action": action,
                "day": day,
                "reason": "Detective pressure-claim gate",
                "selected_message": guarded,
            })
            return True, trim_message(guarded, 32), True, "evidence"

    if player.role == "Doctor" and under_public_pressure(player.name):
        guarded = "I claim Doctor under pressure. Do not eliminate me on weak silence pressure; ask for counterclaims and vote a concrete case."
        stats.holy_grail_v3_message_overrides += 1
        events.append({
            "type": "architecture_message_guardrail",
            "architecture": "holy_grail_v3",
            "player": player.name,
            "role": player.role,
            "action": action,
            "day": day,
            "reason": "Doctor pressure-claim gate",
            "selected_message": guarded,
        })
        return True, trim_message(guarded, 32), True, "claim_check"

    text = message or ""
    weak_silence_case = (
        player.role in GOOD_ROLES
        and bool(re.search(r"\b(quiet|silence|silent|not spoken|hasn't spoken|early read|initial read)\b", text, flags=re.I))
        and not re.search(r"\b(checked|result|claim conflict|counterclaim|lied|contradict|revealed|saved|impossible)\b", text, flags=re.I)
    )
    if weak_silence_case:
        guarded = (
            "I will not vote on quietness alone. Give concrete contradictions, claims, vote shifts, or night evidence before we choose a target."
        )
        stats.holy_grail_v3_message_overrides += 1
        events.append({
            "type": "architecture_message_guardrail",
            "architecture": "holy_grail_v3",
            "player": player.name,
            "role": player.role,
            "action": action,
            "day": day,
            "reason": "Good-role weak silence pressure filter",
            "proposed_message": trim_message(text, 32),
            "selected_message": guarded,
        })
        return True, trim_message(guarded, 32), True, "defense"

    if player.role == "Detective":
        current_votes = [
            event for event in events
            if event.get("type") == "vote" and int(event.get("day", -1)) == day
        ]
        vote_pressure = Counter(str(event.get("target")) for event in current_votes)
        for target, result in player.investigations.items():
            if result == "not Mafia" and target in players and players[target].alive and vote_pressure.get(target, 0) >= 1:
                guarded = f"I claim Detective: {target} is my checked-good. Do not vote {target}; move to a stronger public case."
                stats.holy_grail_v3_message_overrides += 1
                events.append({
                    "type": "architecture_message_guardrail",
                    "architecture": "holy_grail_v3",
                    "player": player.name,
                    "role": player.role,
                    "action": action,
                    "day": day,
                    "reason": "Detective checked-good protection gate",
                    "selected_message": guarded,
                })
                return True, trim_message(guarded, 32), True, "evidence"

    return speak, message, False, ""


def holy_grail_message_guardrail(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    day: int,
    speak: bool,
    message: str | None,
    stats: GameStats,
) -> tuple[bool, str | None, bool, str]:
    if normalize_architecture(player.spec.architecture) != "holy_grail":
        return speak, message, False, ""
    if action not in {"moderator_cued_message", "forced_role_aware_message", "discussion"}:
        return speak, message, False, ""

    def record(reason: str, guarded: str, message_type: str, proposed: str | None = None) -> tuple[bool, str | None, bool, str]:
        stats.holy_grail_message_overrides += 1
        payload = {
            "type": "architecture_message_guardrail",
            "architecture": "holy_grail",
            "player": player.name,
            "role": player.role,
            "action": action,
            "day": day,
            "reason": reason,
            "selected_message": guarded,
        }
        if proposed:
            payload["proposed_message"] = trim_message(proposed, 32)
        events.append(payload)
        return True, trim_message(guarded, 32), True, message_type

    def under_public_pressure(name: str) -> bool:
        pressure_terms = r"suspect|suspicious|pressure|push|nominate|vote|lynch|eliminate|quiet|silence|lack of input|noted your|mentioned your|inactive"
        for event in events:
            if int(event.get("day", -1)) != day:
                continue
            if event.get("type") == "discussion":
                text = str(event.get("message", ""))
            elif event.get("type") == "moderator_prompt":
                text = str(event.get("cue", ""))
            else:
                continue
            if (event.get("target") == name or re.search(rf"\b{re.escape(name)}\b", text)) and re.search(rf"\b({pressure_terms})\b", text, flags=re.I):
                return True
        return False

    alive = alive_players(players)
    adjudication = holy_grail_claim_adjudication(players, events, alive)
    public_hits = sorted(
        name for name in alive
        if name in adjudication["public_mafia_hits"] and players[name].alive
    )
    if player.role in GOOD_ROLES and public_hits:
        target = public_hits[0]
        speakers = ", ".join(sorted(set(adjudication["public_mafia_hits"][target])))
        guarded = f"Vote {target}. {speakers}'s public Detective check says {target} is Mafia; do not split onto claimants or quiet players."
        return record("Public Mafia check vote-coordination gate", guarded, "vote_coordination", message)

    if player.role == "Detective":
        checks = [
            event for event in events
            if event.get("type") == "detective_check" and event.get("detective") == player.name
        ]
        mafia_hits = [
            event for event in checks
            if event.get("result") == "Mafia"
            and str(event.get("target", "")) in players
            and players[str(event.get("target"))].alive
        ]
        if mafia_hits:
            hit = mafia_hits[-1]
            target = str(hit["target"])
            night = int(hit.get("night", day))
            guarded = f"I claim Detective. Night {night}: {target} is Mafia. Vote {target} now; if I die, keep pressure on my voters."
            return record("Detective Mafia result reveal gate", guarded, "evidence", message)
        if checks and under_public_pressure(player.name):
            check = checks[-1]
            target = str(check["target"])
            result = str(check["result"])
            night = int(check.get("night", day))
            guarded = f"I claim Detective under pressure. Night {night}: {target} is {result}. Do not eliminate me on weak pressure."
            return record("Detective pressure-claim gate", guarded, "evidence", message)

    if player.role == "Doctor" and under_public_pressure(player.name):
        guarded = "I claim Doctor under pressure. Do not vote me on weak pressure; follow public checks or demand concrete contradictions."
        return record("Doctor pressure-claim gate", guarded, "claim_check", message)

    text = message or ""
    weak_silence_case = (
        player.role in GOOD_ROLES
        and bool(re.search(r"\b(quiet|silence|silent|not spoken|hasn't spoken|early read|initial read)\b", text, flags=re.I))
        and not re.search(r"\b(checked|result|claim conflict|counterclaim|lied|contradict|revealed|saved|impossible)\b", text, flags=re.I)
    )
    if weak_silence_case:
        guarded = "Quietness alone is not enough. Compare claims, vote shifts, contradictions, and repeated low-detail answers before choosing a vote."
        return record("Good-role weak silence pressure filter", guarded, "defense", text)

    low_agency_good_message = (
        player.role in GOOD_ROLES
        and bool(re.search(r"\b(shocked|share any|feelings? of unease|who has information|initial thoughts)\b", text, flags=re.I))
        and not re.search(r"\b(vote|claim|checked|result|because|contradict|counterclaim|specific|evidence)\b", text, flags=re.I)
    )
    if low_agency_good_message:
        guarded = "I do not have hard evidence yet. Avoid a herd vote; compare low-detail echo answers and require a concrete vote reason."
        return record("Good-role low-agency echo filter", guarded, "vote_coordination", text)

    if player.role == "Detective":
        current_votes = [
            event for event in events
            if event.get("type") == "vote" and int(event.get("day", -1)) == day
        ]
        vote_pressure = Counter(str(event.get("target")) for event in current_votes)
        for target, result in player.investigations.items():
            if result == "not Mafia" and target in players and players[target].alive and vote_pressure.get(target, 0) >= 1:
                guarded = f"I claim Detective: {target} is my checked-good. Do not vote {target}; move to a stronger public case."
                return record("Detective checked-good protection gate", guarded, "evidence", message)

    return speak, message, False, ""


def parse_speech_offer(response: str) -> tuple[bool, str | None, int, bool]:
    parsed = extract_json(response)
    if parsed:
        speak = parsed.get("speak", True)
        if isinstance(speak, str):
            speak = speak.strip().lower() not in {"false", "no", "wait", "pass", "silent"}
        urgency_raw = parsed.get("urgency", 3 if speak else 0)
        try:
            urgency = int(float(urgency_raw))
        except (TypeError, ValueError):
            urgency = 3 if speak else 0
        urgency = max(0, min(5, urgency))
        message = parsed.get("message", "")
        if not speak:
            return False, None, urgency, False
        if isinstance(message, str) and message.strip():
            return True, trim_message(message), urgency, False
    if re.search(r"\b(wait|pass|silent)\b", response, flags=re.I):
        return False, None, 0, False
    match = re.search(r'"([^"]{1,220})"', response)
    if match:
        return True, trim_message(match.group(1)), 3, False
    first = response.strip().splitlines()[0] if response.strip() else ""
    if first:
        return True, trim_message(first), 2, True
    return False, None, 0, True


def trim_message(message: str, max_words: int = 28) -> str:
    message = re.sub(r"\s+", " ", message.strip())
    words = message.split()
    if len(words) <= max_words:
        return message
    return " ".join(words[:max_words])


def complete_with_agent(spec: AgentSpec, prompt: str, max_tokens: int) -> str:
    if spec.provider == "stub":
        return stub_complete(spec, prompt, max_tokens)
    if spec.provider == "ollama":
        return ollama_complete(spec, prompt, max_tokens)
    if spec.provider == "llama_diffusion":
        return llama_diffusion_complete(spec, prompt, max_tokens)
    if spec.provider == "openai":
        return openai_complete(spec, prompt, max_tokens)
    if spec.provider == "anthropic":
        return anthropic_complete(spec, prompt, max_tokens)
    if spec.provider in {"osv_gateway", "osvapi"}:
        return osv_gateway_complete(spec, prompt, max_tokens)
    if spec.provider in {"modal_transformers", "modal_hf", "modal_bf16"}:
        return modal_complete(spec, prompt, max_tokens, "MergedBF16Model")
    if spec.provider in {"modal_base_bf16", "modal_base", "modal_gemma_base"}:
        return modal_complete(spec, prompt, max_tokens, "BaseBF16Model")
    if spec.provider in {"modal_gguf", "modal_q8"}:
        return modal_complete(spec, prompt, max_tokens, "GGUFQ8Model")
    raise ValueError(f"Unsupported provider: {spec.provider}")


def stub_complete(spec: AgentSpec, prompt: str, max_tokens: int) -> str:
    names = [name for name in PLAYER_NAMES if re.search(rf"\b{re.escape(name)}\b", prompt)]
    eligible_match = re.search(r"eligible list:\s*(\[[^\]]*\])", prompt, flags=re.I)
    candidates_match = re.search(r"\[(.*?)\]", prompt, flags=re.S)
    candidates = []
    if eligible_match:
        try:
            parsed_candidates = json.loads(eligible_match.group(1).replace("'", '"'))
            candidates = [name for name in parsed_candidates if name in PLAYER_NAMES]
        except Exception:
            candidates = []
    if not candidates and candidates_match:
        candidates = [part.strip().strip("'\"") for part in candidates_match.group(1).split(",")]
        candidates = [name for name in candidates if name in PLAYER_NAMES]
    if "Return only <send> or <wait>" in prompt:
        if "has not reached the discussion floor" in prompt or "Current public discussion count: 0" in prompt:
            return "<send>"
        return "<wait>"
    if "Moderator generator" in prompt:
        target = candidates[0] if candidates else (names[0] if names else PLAYER_NAMES[0])
        return json.dumps({"target": target, "cue": f"{target}, give a concrete read and one vote reason.", "message_type": "pressure"})
    if '"target"' in prompt:
        target = candidates[0] if candidates else (names[0] if names else PLAYER_NAMES[0])
        return json.dumps({"target": target})
    if '"message"' in prompt:
        return json.dumps({"message_type": "pressure", "message": "I want concrete evidence and a clear vote reason before we decide."})
    return json.dumps({"ok": True})


def modal_complete(spec: AgentSpec, prompt: str, max_tokens: int, class_name: str) -> str:
    try:
        import modal
    except ImportError as exc:
        raise RuntimeError("modal package is not installed") from exc
    cache_key = f"{MODAL_INFERENCE_APP}:{class_name}"
    model = _MODAL_INSTANCE_CACHE.get(cache_key)
    if model is None:
        remote_cls = modal.Cls.from_name(MODAL_INFERENCE_APP, class_name)
        model = remote_cls()
        _MODAL_INSTANCE_CACHE[cache_key] = model
    result = model.generate.remote(prompt, max_tokens, spec.temperature, spec.top_p, spec.top_k)
    if isinstance(result, dict):
        content = str(result.get("text") or "").strip()
    else:
        content = str(result or "").strip()
    if not content:
        raise RuntimeError(f"Modal {class_name} returned empty content")
    return content


def ollama_complete(spec: AgentSpec, prompt: str, max_tokens: int) -> str:
    options: dict[str, Any] = {
        "temperature": spec.temperature,
        "num_ctx": 4096,
        "num_predict": max_tokens,
    }
    if spec.top_p is not None:
        options["top_p"] = spec.top_p
    if spec.top_k is not None:
        options["top_k"] = spec.top_k
    payload = {
        "model": spec.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": options,
    }
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc
    content = (parsed.get("message", {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("Ollama returned empty visible content")
    return content


def llama_diffusion_complete(spec: AgentSpec, prompt: str, max_tokens: int) -> str:
    workspace_root = Path(__file__).resolve().parents[3]
    binary = workspace_root / "tools" / "llama.cpp-diffusiongemma" / "build" / "bin" / "llama-diffusion-cli"
    model_path = Path(spec.model)
    if not model_path.is_absolute():
        model_path = workspace_root / model_path
    if not binary.exists():
        raise RuntimeError(f"llama-diffusion-cli not found: {binary}")
    if not model_path.exists():
        raise RuntimeError(f"DiffusionGemma model file not found: {model_path}")
    cmd = [
        str(binary),
        "-m", str(model_path),
        "-p", prompt,
        "-n", str(max(max_tokens, 384)),
        "--temp", str(spec.temperature),
        "-c", "4096",
        "-ngl", "all",
        "--verbosity", "1",
        "--diffusion-gpu-sampling", "off",
    ]
    completed = subprocess.run(cmd, text=True, capture_output=True, timeout=360, check=False)
    raw = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    if completed.returncode != 0:
        raise RuntimeError(f"llama-diffusion-cli failed with code {completed.returncode}: {raw[-1000:]}")
    content = clean_llama_diffusion_output(raw)
    if not content:
        raise RuntimeError("llama-diffusion-cli returned no visible content")
    return content


def clean_llama_diffusion_output(raw: str) -> str:
    text = raw.strip()
    if "<channel|>" in text:
        text = text.rsplit("<channel|>", 1)[1]
    text = re.split(r"\ntotal time:", text, maxsplit=1)[0]
    text = re.sub(r"(?m)^\d+\.\d+\.\d+\s+[EWI]\s+.*$", "", text)
    text = re.sub(r"<\|[^>]+>", "", text)
    text = text.strip()
    if extract_json(text):
        return text
    matches = list(re.finditer(r"\{.*?\}", text, flags=re.S))
    for match in reversed(matches):
        candidate = match.group(0).strip()
        if extract_json(candidate):
            return candidate
    return text


def openai_complete(spec: AgentSpec, prompt: str, max_tokens: int) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is not installed") from exc
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), timeout=180.0)
    if spec.model.startswith("gpt-5"):
        if spec.model == "gpt-5" or spec.reasoning_effort == "medium":
            output_budget = max(max_tokens, 2048)
        else:
            output_budget = max(max_tokens, 1024)
        response = client.responses.create(
            model=spec.model,
            input=prompt,
            max_output_tokens=output_budget,
            reasoning={"effort": spec.reasoning_effort or "low"},
            text={"verbosity": "low"},
        )
        content = getattr(response, "output_text", "")
        if content and content.strip():
            return content.strip()
        chunks = []
        for item in getattr(response, "output", []) or []:
            for block in getattr(item, "content", []) or []:
                text = getattr(block, "text", None)
                if text:
                    chunks.append(text)
        content = "\n".join(chunks).strip()
        if content:
            return content
        status = getattr(response, "status", None)
        incomplete = getattr(response, "incomplete_details", None)
        raise RuntimeError(f"OpenAI Responses API returned empty output_text status={status} incomplete={incomplete}")
    response = client.chat.completions.create(
        model=spec.model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=spec.temperature,
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError("OpenAI returned empty content")
    return content.strip()


def osv_gateway_complete(spec: AgentSpec, prompt: str, max_tokens: int) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is not installed") from exc
    client = OpenAI(
        api_key=os.environ.get("OSV_API_KEY"),
        base_url="https://developer.osv.engineering/inference/v1",
        timeout=240.0,
    )
    response = client.chat.completions.create(
        model=spec.model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max(max_tokens, 1024 if "gemini" in spec.model.lower() else 512),
        temperature=spec.temperature,
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError("OSV gateway returned empty content")
    return content.strip()


def anthropic_complete(spec: AgentSpec, prompt: str, max_tokens: int) -> str:
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("anthropic package is not installed") from exc
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"), timeout=180.0)
    kwargs: dict[str, Any] = {
        "model": spec.model,
        "max_tokens": max(max_tokens, 1024 if spec.model.startswith(("claude-fable", "claude-opus-4-8")) else 512),
        "messages": [{"role": "user", "content": prompt}],
    }
    if not (spec.model.startswith("claude-fable") or spec.model.startswith("claude-opus-4-8")):
        kwargs["temperature"] = spec.temperature
    response = client.messages.create(**kwargs)
    texts = []
    for block in response.content:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            texts.append(block.text)
    content = "\n".join(texts).strip()
    if not content:
        raise RuntimeError("Anthropic returned no visible text content")
    return content


def stop_ollama_model(model: str) -> None:
    subprocess.run(["ollama", "stop", model], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def assign_roles(seed: int) -> dict[str, str]:
    rng = random.Random(seed)
    roles = ROLE_LIST[:]
    rng.shuffle(roles)
    return dict(zip(PLAYER_NAMES, roles))


def build_players(role_assignment: dict[str, str], lineup: dict[str, AgentSpec]) -> dict[str, Player]:
    players = {}
    for name in PLAYER_NAMES:
        role = role_assignment[name]
        faction_key = "mafia" if role == "Mafia" else "good"
        spec = (
            lineup.get(name.lower())
            or lineup.get(role.lower())
            or lineup.get(faction_key)
            or lineup["default"]
        )
        players[name] = Player(name=name, role=role, spec=spec)
    return players


def make_lineup_from_assignments(assignments: dict[str, Any], args: argparse.Namespace) -> dict[str, AgentSpec]:
    if "default" not in assignments:
        raise ValueError("Scenario assignments must include a 'default' agent spec")
    lineup: dict[str, AgentSpec] = {}
    for key, config in assignments.items():
        lineup[key.lower()] = agent_spec_from_config(
            config,
            default_architecture=getattr(args, "architecture", "baseline"),
            default_reasoning_effort=getattr(args, "reasoning_effort", None),
            default_temperature=getattr(args, "temperature", 0.2),
        )
    return lineup


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        scenarios = raw.get("scenarios")
    else:
        scenarios = raw
    if not isinstance(scenarios, list):
        raise ValueError("Scenario file must be a list or an object with a 'scenarios' list")
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            raise ValueError(f"Scenario {index} is not an object")
        if "name" not in scenario:
            scenario["name"] = f"scenario_{index}"
        if "assignments" not in scenario:
            raise ValueError(f"Scenario {scenario['name']} missing assignments")
    return scenarios


def lineup_digest(lineup: dict[str, AgentSpec]) -> str:
    labels = {key: spec.label for key, spec in sorted(lineup.items())}
    return hashlib.sha1(json.dumps(labels, sort_keys=True).encode("utf-8")).hexdigest()[:10]


def stop_lineup_models(lineup: dict[str, AgentSpec]) -> None:
    stopped: set[str] = set()
    for spec in lineup.values():
        if spec.provider == "ollama" and spec.model not in stopped:
            stop_ollama_model(spec.model)
            stopped.add(spec.model)


def safe_call(player: Player, prompt: str, stats: GameStats, max_tokens: int, action: str = "unknown") -> str:
    stats.llm_calls += 1
    started = time.perf_counter()
    attempts = 0
    last_message = ""
    for attempt in range(1, 4):
        attempts = attempt
        try:
            content = complete_with_agent(player.spec, prompt, max_tokens=max_tokens)
            stats.call_records.append({
                "player": player.name,
                "role": player.role,
                "provider": player.spec.provider,
                "model": player.spec.model,
                "architecture": player.spec.architecture,
                "action": action,
                "max_tokens": max_tokens,
                "attempts": attempts,
                "latency_sec": round(time.perf_counter() - started, 3),
                "output_chars": len(content),
                "ok": True,
            })
            return content
        except Exception as exc:
            last_message = f"{type(exc).__name__}: {exc}"
            if attempt < 3:
                time.sleep(1.5 * attempt)
    stats.api_errors += 1
    if len(stats.error_messages) < 20:
        stats.error_messages.append(last_message[:500])
    stats.call_records.append({
        "player": player.name,
        "role": player.role,
        "provider": player.spec.provider,
        "model": player.spec.model,
        "architecture": player.spec.architecture,
        "action": action,
        "max_tokens": max_tokens,
        "attempts": attempts,
        "latency_sec": round(time.perf_counter() - started, 3),
        "output_chars": 0,
        "ok": False,
        "error": last_message[:500],
    })
    return json.dumps({"error": last_message})


def uses_revac_review(architecture: str) -> bool:
    return normalize_architecture(architecture) in {
        "revac",
        "grail_wolf",
        "grail_wolf_verified",
        "wolf_revac_grail",
        "role_adaptive_hybrid",
        "holy_grail",
        "holy_grail_v2",
        "holy_grail_v3",
        "holy_grail",
    }


def build_revac_review_prompt(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
    protocol: str,
    moderator_cue: str | None = None,
) -> str:
    alive = alive_players(players)
    cue = f"\nModerator cue: {moderator_cue}" if moderator_cue else ""
    return f"""You are the private ReVAC reviewer module for {player.name} in a 7-player Mafia game.
Role: {player.role}
{role_objective(player.role)}

Current phase/action: {action}
Day/night number: {day}
Protocol: {protocol}
Alive players: {', '.join(alive)}
Candidates if applicable: {candidates}
Private role context: {private_context(player, players)}{cue}

Public transcript:
{compact_transcript(events)}

Public memory:
{architecture_context(player, events)}

Review the observation state using the ReVAC pattern: memory, objective, evidence, risk, alternatives,
communication tone, and final action guidance. Do not reveal private role information in public guidance.

Return JSON exactly:
{{"objective": "short", "evidence": "short", "risk": "short", "tone": "short", "action_hint": "short"}}
"""


def maybe_revac_review(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
    protocol: str,
    stats: GameStats,
    moderator_cue: str | None = None,
) -> str | None:
    if not uses_revac_review(player.spec.architecture):
        return None
    if normalize_architecture(player.spec.architecture) == "holy_grail" and action in {
        "vote",
        "moderator_cued_message",
        "forced_role_aware_message",
    }:
        return None
    if action in {"time_to_talk_offer", "role_aware_time_to_talk_offer", "role_aware_quality_time_to_talk_offer", "schedule_candidate"}:
        return None
    stats.revac_review_calls += 1
    prompt = build_revac_review_prompt(player, players, events, action, candidates, day, protocol, moderator_cue=moderator_cue)
    raw = safe_call(player, prompt, stats, max_tokens=220, action=f"revac_review:{action}")
    parsed = extract_json(raw)
    if parsed:
        parts = []
        for key in ("objective", "evidence", "risk", "tone", "action_hint"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{key}: {trim_message(value, 28)}")
        if parts:
            return "\n".join(parts)
    return trim_message(raw, 80)


def hg_v2_recent_vote_pressure(events: list[dict[str, Any]], candidates: list[str]) -> dict[str, float]:
    recent = [event for event in events if event.get("type") == "vote"][-14:]
    counts = Counter(str(event.get("target")) for event in recent)
    return {candidate: min(1.0, 0.2 * counts.get(candidate, 0)) for candidate in candidates}


def hg_v2_public_power_claim_score(events: list[dict[str, Any]], candidates: list[str], role: str) -> dict[str, float]:
    scores = {candidate: 0.0 for candidate in candidates}
    for claim in public_role_claims(events):
        speaker = str(claim.get("speaker", ""))
        claimed_role = str(claim.get("role", ""))
        if speaker in scores and claimed_role == role:
            scores[speaker] += 1.0 if claim.get("kind") == "explicit" else 0.7
    return scores


def hg_v2_voted_revealed_mafia_score(events: list[dict[str, Any]], candidates: list[str]) -> dict[str, float]:
    scores = {candidate: 0.0 for candidate in candidates}
    votes_by_day: dict[int, list[dict[str, Any]]] = defaultdict(list)
    eliminations: dict[int, dict[str, Any]] = {}
    for event in events:
        if event.get("type") == "vote":
            votes_by_day[int(event["day"])].append(event)
        elif event.get("type") == "elimination":
            eliminations[int(event["day"])] = event
    for day, elimination in eliminations.items():
        if elimination.get("role") != "Mafia":
            continue
        mafia_target = str(elimination.get("target"))
        for vote in votes_by_day.get(day, []):
            voter = str(vote.get("voter"))
            if voter in scores and vote.get("target") == mafia_target:
                scores[voter] += 1.0
    return scores


def holy_grail_v2_recommended_target(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> tuple[str | None, str, float]:
    if normalize_architecture(player.spec.architecture) != "holy_grail_v2" or not candidates:
        return None, "", 0.0

    posterior, reasons = hg_v2_posterior(player, players, events)
    vote_pressure = hg_v2_recent_vote_pressure(events, candidates)
    detective_claims = hg_v2_public_power_claim_score(events, candidates, "Detective")
    doctor_claims = hg_v2_public_power_claim_score(events, candidates, "Doctor")
    voted_mafia = hg_v2_voted_revealed_mafia_score(events, candidates)
    endgame = hg_v2_endgame_state(players, events)

    if action == "vote":
        if player.role == "Mafia":
            non_teammates = [candidate for candidate in candidates if players[candidate].role != "Mafia"]
            pool = non_teammates or candidates
            def mafia_vote_score(name: str) -> float:
                return (
                    posterior.get(name, 0.0)
                    + vote_pressure.get(name, 0.0)
                    + 0.6 * detective_claims.get(name, 0.0)
                    + 0.3 * doctor_claims.get(name, 0.0)
                    - 0.8 * voted_mafia.get(name, 0.0)
                )
            ranked = sorted(pool, key=mafia_vote_score, reverse=True)
            target = ranked[0]
            runner_up = ranked[1] if len(ranked) > 1 else target
            confidence = mafia_vote_score(target) - mafia_vote_score(runner_up)
            return target, "Mafia vote guardrail: prefer plausible non-teammate miselimination with existing pressure.", confidence

        for target, result in player.investigations.items():
            if target in candidates and result == "Mafia":
                return target, f"Town vote guardrail: private Detective Mafia check on {target}.", 1.0

        pool = [
            candidate for candidate in candidates
            if not (player.role == "Detective" and player.investigations.get(candidate) == "not Mafia")
        ] or candidates
        ranked = sorted(pool, key=lambda name: (posterior.get(name, 0.0), vote_pressure.get(name, 0.0)), reverse=True)
        target = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else target
        confidence = posterior.get(target, 0.0) - posterior.get(runner_up, 0.0)
        reason = "; ".join(reasons.get(target, [])[-2:])
        if endgame["must_vote_mafia_today"]:
            return target, f"Town parity guardrail: vote top GRAIL posterior candidate {target}; {reason}", confidence
        return target, f"Town vote guardrail: top GRAIL posterior candidate {target}; {reason}", confidence

    if action == "detective_check":
        pool = [candidate for candidate in candidates if candidate not in player.investigations] or candidates
        def check_score(name: str) -> float:
            return (
                posterior.get(name, 0.0)
                + 0.25 * vote_pressure.get(name, 0.0)
                + 0.3 * detective_claims.get(name, 0.0)
                + 0.2 * doctor_claims.get(name, 0.0)
            )
        ranked = sorted(pool, key=check_score, reverse=True)
        target = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else target
        confidence = check_score(target) - check_score(runner_up)
        return target, "Detective guardrail: investigate high-posterior unresolved or claim-relevant target.", confidence

    if action == "doctor_save":
        self_pressure = vote_pressure.get(player.name, 0.0)
        def protect_score(name: str) -> float:
            return (
                2.5 * detective_claims.get(name, 0.0)
                + 1.2 * voted_mafia.get(name, 0.0)
                + 0.7 * doctor_claims.get(name, 0.0)
                + (0.9 if name == player.name and (day <= 1 or self_pressure > 0.2) else 0.0)
                - 0.6 * posterior.get(name, 0.0)
            )
        ranked = sorted(candidates, key=protect_score, reverse=True)
        target = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else target
        confidence = protect_score(target) - protect_score(runner_up)
        return target, "Doctor guardrail: protect information value, credible Town pressure, or exposed self.", confidence

    if action == "mafia_kill":
        def kill_score(name: str) -> float:
            return (
                3.0 * detective_claims.get(name, 0.0)
                + 1.5 * doctor_claims.get(name, 0.0)
                + 1.5 * voted_mafia.get(name, 0.0)
                - 0.4 * posterior.get(name, 0.0)
                + 0.2 * vote_pressure.get(name, 0.0)
            )
        ranked = sorted(candidates, key=kill_score, reverse=True)
        target = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else target
        confidence = kill_score(target) - kill_score(runner_up)
        return target, "Mafia kill guardrail: remove public power claim, accurate voter, or high-agency Town.", confidence

    return None, "", 0.0


def apply_holy_grail_v2_target_guardrail(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
    proposed: str,
    stats: GameStats,
) -> str:
    if normalize_architecture(player.spec.architecture) != "holy_grail_v2":
        return proposed
    stats.holy_grail_v2_guardrail_checks += 1
    recommended, reason, confidence = holy_grail_v2_recommended_target(player, players, events, action, candidates, day)
    if not recommended or recommended not in candidates:
        return proposed
    posterior, _ = hg_v2_posterior(player, players, events)
    override = recommended != proposed
    if action == "vote" and player.role in GOOD_ROLES and proposed in candidates:
        private_bad = player.role == "Detective" and player.investigations.get(proposed) == "not Mafia"
        private_hit = player.role == "Detective" and player.investigations.get(recommended) == "Mafia"
        endgame = hg_v2_endgame_state(players, events)
        margin = posterior.get(recommended, 0.0) - posterior.get(proposed, 0.0)
        override = recommended != proposed and (
            private_bad
            or private_hit
            or (endgame["must_vote_mafia_today"] and margin >= 0.18)
            or margin >= 0.22
        )
    elif action == "vote" and player.role == "Mafia":
        proposed_partner = players[proposed].role == "Mafia"
        override = recommended != proposed and (proposed_partner or confidence >= 0.10)
    elif action == "detective_check":
        has_public_signal = bool(public_role_claims(events)) or any(
            event.get("type") in {"discussion", "vote", "elimination", "no_elimination"} for event in events
        )
        override = recommended != proposed and has_public_signal and confidence >= 0.12
    elif action == "doctor_save":
        override = recommended != proposed and confidence >= 0.75
    elif action == "mafia_kill":
        override = recommended != proposed and confidence >= 0.50

    if not override:
        return proposed
    stats.holy_grail_v2_overrides += 1
    events.append({
        "type": "architecture_guardrail",
        "architecture": "holy_grail_v2",
        "player": player.name,
        "role": player.role,
        "action": action,
        "day": day,
        "proposed": proposed,
        "selected": recommended,
        "reason": reason,
    })
    return recommended


def holy_grail_v3_recommended_target(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> tuple[str | None, str, float, list[dict[str, Any]]]:
    if normalize_architecture(player.spec.architecture) != "holy_grail_v3" or not candidates:
        return None, "", 0.0, []
    values, reasons = hg_v3_action_values(player, players, events, action, candidates, day)
    if not values:
        return None, "", 0.0, []
    target = str(values[0]["candidate"])
    target_score = float(values[0]["score"])
    runner_up_score = float(values[1]["score"]) if len(values) > 1 else target_score
    confidence = target_score - runner_up_score
    reason = "; ".join(reasons.get(target, [])[-3:])
    return target, reason, confidence, values[:5]


def apply_holy_grail_v3_target_guardrail(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
    proposed: str,
    stats: GameStats,
) -> str:
    if normalize_architecture(player.spec.architecture) != "holy_grail_v3":
        return proposed
    stats.holy_grail_v3_guardrail_checks += 1
    recommended, reason, confidence, action_values = holy_grail_v3_recommended_target(player, players, events, action, candidates, day)
    if not recommended or recommended not in candidates:
        return proposed
    if recommended == proposed:
        return proposed

    value_by_name = {str(row["candidate"]): float(row["score"]) for row in action_values}
    proposed_score = value_by_name.get(proposed, -9.0)
    recommended_score = value_by_name.get(recommended, proposed_score + confidence)
    score_margin = recommended_score - proposed_score
    endgame = hg_v2_endgame_state(players, events)
    power_risk, claim_conflict, _ = hg_v3_claim_features(events, candidates)
    public_case, coalition, _ = hg_v3_public_pressure(events, candidates, day)

    override = False
    if action == "vote":
        if player.role == "Mafia":
            proposed_partner = proposed in players and players[proposed].role == "Mafia"
            override = proposed_partner or (score_margin >= 0.45 and (public_case.get(recommended, 0.0) >= 0.45 or coalition.get(recommended, 0.0) > 0))
        else:
            private_hit = player.role == "Detective" and player.investigations.get(recommended) == "Mafia"
            private_bad = player.role == "Detective" and player.investigations.get(proposed) == "not Mafia"
            proposed_power = power_risk.get(proposed, 0.0) >= 1.0 and claim_conflict.get(proposed, 0.0) <= 0.0
            recommended_has_case = (
                public_case.get(recommended, 0.0) >= 0.45
                or coalition.get(recommended, 0.0) > 0
                or claim_conflict.get(recommended, 0.0) > 0
                or private_hit
            )
            override = (
                private_hit
                or private_bad
                or (proposed_power and score_margin >= 0.15)
                or (endgame["must_vote_mafia_today"] and score_margin >= 0.08)
                or (recommended_has_case and score_margin >= 0.16)
                or (recommended_has_case and recommended_score >= 0.95 and score_margin >= 0.10)
            )
    elif action == "detective_check":
        signal = (
            public_case.get(recommended, 0.0) > 0
            or claim_conflict.get(recommended, 0.0) > 0
            or coalition.get(recommended, 0.0) > 0
        )
        override = signal and score_margin >= 0.14
    elif action == "doctor_save":
        override = score_margin >= 0.35 and recommended_score > 0.2
    elif action == "mafia_kill":
        override = score_margin >= 0.45 and recommended_score > 0.4

    if not override:
        return proposed
    stats.holy_grail_v3_overrides += 1
    events.append({
        "type": "architecture_guardrail",
        "architecture": "holy_grail_v3",
        "player": player.name,
        "role": player.role,
        "action": action,
        "day": day,
        "proposed": proposed,
        "selected": recommended,
        "confidence": round(confidence, 4),
        "score_margin": round(score_margin, 4),
        "reason": reason,
        "action_values": action_values,
    })
    return recommended


def holy_grail_recommended_target(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
) -> tuple[str | None, str, float, list[dict[str, Any]], dict[str, Any]]:
    if normalize_architecture(player.spec.architecture) != "holy_grail" or not candidates:
        return None, "", 0.0, [], {}
    if action == "vote":
        plan = holy_grail_vote_plan(player, players, events, candidates, day)
        target = plan.get("best_vote")
        values = list(plan.get("action_values", []))
        if not target or target not in candidates:
            return None, "", 0.0, values, plan
        value_by_name = {str(row["candidate"]): float(row["score"]) for row in values}
        target_score = value_by_name.get(str(target), 0.0)
        runner_up_score = max([score for name, score in value_by_name.items() if name != target] or [target_score])
        confidence = target_score - runner_up_score
        return str(target), str(plan.get("reason", "")), confidence, values[:5], plan
    values, reasons, adjudication = holy_grail_action_values(player, players, events, action, candidates, day)
    if not values:
        return None, "", 0.0, [], {"adjudication": adjudication}
    target = str(values[0]["candidate"])
    target_score = float(values[0]["score"])
    runner_up_score = float(values[1]["score"]) if len(values) > 1 else target_score
    confidence = target_score - runner_up_score
    reason = "; ".join(reasons.get(target, [])[-4:])
    return target, reason, confidence, values[:5], {"adjudication": adjudication}


def apply_holy_grail_target_guardrail(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
    proposed: str,
    stats: GameStats,
) -> str:
    if normalize_architecture(player.spec.architecture) != "holy_grail":
        return proposed
    stats.holy_grail_guardrail_checks += 1
    recommended, reason, confidence, action_values, plan = holy_grail_recommended_target(player, players, events, action, candidates, day)
    if not recommended or recommended not in candidates or recommended == proposed:
        return proposed

    adjudication = plan.get("adjudication") or holy_grail_claim_adjudication(players, events, candidates)
    value_by_name = {str(row["candidate"]): float(row["score"]) for row in action_values}
    proposed_score = value_by_name.get(proposed, -9.0)
    recommended_score = value_by_name.get(recommended, proposed_score + confidence)
    score_margin = recommended_score - proposed_score
    public_case, coalition, _ = hg_v3_public_pressure(events, candidates, day)
    current_vote_pressure = hg_v3_current_day_vote_pressure(events, candidates, day)
    evasion, _, _ = holy_grail_discussion_quality_signals(events, candidates, day)

    override = False
    override_reason = reason
    if action == "vote":
        if player.role == "Mafia":
            proposed_partner = proposed in players and players[proposed].role == "Mafia"
            recommended_not_partner = recommended in players and players[recommended].role != "Mafia"
            has_public_cover = (
                public_case.get(recommended, 0.0) >= 0.25
                or coalition.get(recommended, 0.0) > 0
                or recommended in adjudication.get("dangerous_vote", {})
                or evasion.get(recommended, 0.0) >= 0.25
            )
            override = proposed_partner or (recommended_not_partner and has_public_cover and score_margin >= 0.20)
        else:
            public_hit = recommended in adjudication.get("public_mafia_hits", {})
            private_hit = player.role == "Detective" and player.investigations.get(recommended) == "Mafia"
            private_bad = player.role == "Detective" and player.investigations.get(proposed) == "not Mafia"
            proposed_dangerous = proposed in adjudication.get("dangerous_vote", {})
            proposed_no_case_herd = (
                current_vote_pressure.get(proposed, 0.0) > 0
                and public_case.get(proposed, 0.0) <= 0.1
                and proposed not in adjudication.get("public_mafia_hits", {})
            )
            recommended_has_public_reason = (
                public_hit
                or private_hit
                or evasion.get(recommended, 0.0) >= 0.25
                or public_case.get(recommended, 0.0) >= 0.25
                or coalition.get(recommended, 0.0) > 0
            )
            override = (
                public_hit
                or private_hit
                or private_bad
                or proposed_dangerous
                or (proposed_no_case_herd and recommended_has_public_reason and score_margin >= -0.05)
                or (recommended_has_public_reason and score_margin >= 0.12)
                or score_margin >= 0.35
            )
            if public_hit:
                override_reason = f"Holy Grail vote-closing: public Mafia check requires vote on {recommended}; {reason}"
            elif proposed_dangerous:
                override_reason = f"Holy Grail must-not-vote protection: {proposed} is protected by public adjudication; {reason}"
            elif proposed_no_case_herd:
                override_reason = f"Holy Grail anti-herd: {proposed} has vote pressure without a case; {reason}"
    elif action == "detective_check":
        already_checked_bad = proposed in player.investigations
        override = already_checked_bad or score_margin >= 0.12
    elif action == "doctor_save":
        credible_detective_target = recommended in adjudication.get("credible_detectives", set())
        override = credible_detective_target or (score_margin >= 0.25 and recommended_score > 0.15)
    elif action == "mafia_kill":
        credible_detective_target = recommended in adjudication.get("credible_detectives", set())
        override = credible_detective_target or (score_margin >= 0.35 and recommended_score > 0.25)

    if not override:
        return proposed
    stats.holy_grail_overrides += 1
    events.append({
        "type": "architecture_guardrail",
        "architecture": "holy_grail",
        "player": player.name,
        "role": player.role,
        "action": action,
        "day": day,
        "proposed": proposed,
        "selected": recommended,
        "confidence": round(confidence, 4),
        "score_margin": round(score_margin, 4),
        "reason": override_reason,
        "action_values": action_values,
        "vote_plan": {
            key: value for key, value in plan.items()
            if key not in {"action_values", "adjudication"}
        } if action == "vote" else {},
    })
    return recommended


def choose_target(
    player: Player,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    action: str,
    candidates: list[str],
    day: int,
    protocol: str,
    stats: GameStats,
    rng: random.Random,
) -> str:
    if normalize_architecture(player.spec.architecture) == "holy_grail":
        stats.holy_grail_guardrail_checks += 1
        recommended, reason, confidence, action_values, plan = holy_grail_recommended_target(
            player, players, events, action, candidates, day
        )
        if recommended and recommended in candidates:
            stats.holy_grail_overrides += 1
            events.append({
                "type": "architecture_guardrail",
                "architecture": "holy_grail",
                "player": player.name,
                "role": player.role,
                "action": action,
                "day": day,
                "proposed": f"direct_{action}_plan",
                "selected": recommended,
                "confidence": round(confidence, 4),
                "score_margin": round(confidence, 4),
                "reason": f"Holy Grail direct {action} plan: {reason}",
                "action_values": action_values,
                "vote_plan": {
                    key: value for key, value in plan.items()
                    if key not in {"action_values", "adjudication"}
                },
            })
            return recommended

    review_context = maybe_revac_review(player, players, events, action, candidates, day, protocol, stats)
    prompt = build_prompt(player, players, events, action, candidates, day, protocol, review_context=review_context)
    raw = safe_call(player, prompt, stats, max_tokens=96, action=action)
    target, failed = parse_target(raw, candidates)
    if failed or target is None:
        stats.parse_failures += 1
        stats.invalid_actions += 1
        target = rng.choice(candidates)
    target = apply_holy_grail_target_guardrail(player, players, events, action, candidates, day, target, stats)
    target = apply_holy_grail_v3_target_guardrail(player, players, events, action, candidates, day, target, stats)
    target = apply_holy_grail_v2_target_guardrail(player, players, events, action, candidates, day, target, stats)
    return target


def choose_mafia_kill(
    players: dict[str, Player],
    events: list[dict[str, Any]],
    day: int,
    protocol: str,
    stats: GameStats,
    rng: random.Random,
) -> str | None:
    mafia_names = alive_mafia(players)
    if not mafia_names:
        return None
    kill_candidates = [name for name in alive_players(players) if players[name].role != "Mafia"]
    if not kill_candidates:
        return None
    ballots: dict[str, str] = {}
    for name in mafia_names:
        target = choose_target(players[name], players, events, "mafia_kill", kill_candidates, day, protocol, stats, rng)
        ballots[name] = target
    stats.mafia_kill_votes += len(ballots)
    counts = Counter(ballots.values())
    max_votes = max(counts.values())
    tied = sorted([name for name, count in counts.items() if count == max_votes])
    target = rng.choice(tied)
    events.append({
        "type": "mafia_kill_vote",
        "night": day,
        "votes": ballots,
        "target": target,
        "tie": len(tied) > 1,
    })
    return target


def day_discussion_count(events: list[dict[str, Any]], day: int) -> int:
    return sum(1 for event in events if event.get("type") == "discussion" and event.get("day") == day)


def role_aware_floor(players: dict[str, Player]) -> int:
    alive_count = len(alive_players(players))
    return min(4, max(2, alive_count // 2 + 1))


def pick_floor_speaker(eligible: list[str], speaker_counts: Counter[str], rng: random.Random) -> str:
    min_count = min(speaker_counts[name] for name in eligible)
    least_used = sorted(name for name in eligible if speaker_counts[name] == min_count)
    return rng.choice(least_used)


def emit_forced_role_aware_message(
    players: dict[str, Player],
    events: list[dict[str, Any]],
    day: int,
    protocol: str,
    stats: GameStats,
    rng: random.Random,
    eligible: list[str],
    speaker_counts: Counter[str],
    scheduler_round: int,
) -> str | None:
    if not eligible:
        return None
    speaker = pick_floor_speaker(eligible, speaker_counts, rng)
    player = players[speaker]
    review_context = maybe_revac_review(player, players, events, "forced_role_aware_message", [], day, protocol, stats)
    prompt = build_prompt(player, players, events, "forced_role_aware_message", [], day, protocol, review_context=review_context)
    raw = safe_call(player, prompt, stats, max_tokens=160, action="forced_role_aware_message")
    speak, message, failed = parse_discussion(raw, protocol)
    if failed:
        stats.parse_failures += 1
    parsed = extract_json(raw) or {}
    message_type = str(parsed.get("message_type", "forced") or "forced")
    events.append({
        "type": "scheduler_forced_floor",
        "day": day,
        "scheduler_round": scheduler_round,
        "speaker": speaker,
        "protocol": protocol,
        "message_type": message_type,
        "message": message or trim_message(raw, 28),
        "parse_failed": bool(failed),
    })
    if not speak or not message:
        stats.waits += 1
        return None
    speaker_counts[speaker] += 1
    stats.discussion_messages += 1
    events.append({
        "type": "discussion",
        "day": day,
        "speaker": speaker,
        "message": message,
        "protocol": protocol,
        "scheduler_round": scheduler_round,
        "urgency": 2,
        "message_type": message_type,
        "forced_floor": True,
        "selected_from": 0,
    })
    return speaker


def format_clock(seconds: float) -> str:
    seconds_i = max(0, int(round(seconds)))
    return f"{seconds_i // 60:02d}:{seconds_i % 60:02d}"


def timed_transcript(events: list[dict[str, Any]], max_events: int = 40) -> str:
    visible = [
        event for event in events
        if event.get("type") in {
            "system", "night_result", "moderator_prompt", "discussion", "vote", "elimination", "no_elimination"
        }
    ]
    lines = []
    for idx, event in enumerate(visible[-max_events:]):
        stamp = format_clock(float(event.get("sim_time_sec", idx * 3)))
        kind = event.get("type")
        if kind == "moderator_prompt":
            lines.append(f"[{stamp}] Moderator to {event.get('target', 'table')}: {event.get('cue', '')}")
        elif kind == "discussion":
            lines.append(f"[{stamp}] {event.get('speaker')}: {event.get('message')}")
        elif kind == "night_result":
            lines.append(f"[{stamp}] Game: Night {event.get('night')}: {event.get('message')}")
        elif kind == "vote":
            lines.append(f"[{stamp}] Game: {event.get('voter')} voted for {event.get('target')}")
        elif kind == "elimination":
            lines.append(f"[{stamp}] Game: {event.get('message')}")
        elif kind == "no_elimination":
            lines.append(f"[{stamp}] Game: {event.get('message')}")
        elif kind == "system":
            lines.append(f"[{stamp}] Game: {event.get('message')}")
    return "\n".join(lines) if lines else "No public chat yet."


def day_speaker_counts(events: list[dict[str, Any]], day: int) -> Counter[str]:
    counts: Counter[str] = Counter()
    for event in events:
        if event.get("type") == "discussion" and event.get("day") == day:
            counts[str(event.get("speaker"))] += 1
    return counts


def format_message_rate_report(players: dict[str, Player], events: list[dict[str, Any]], day: int) -> str:
    alive = alive_players(players)
    counts = day_speaker_counts(events, day)
    total = sum(counts.values())
    if not alive:
        return "No alive players."
    ideal = 1 / len(alive)
    lines = [f"Alive players: {', '.join(alive)}.", f"Discussion messages today: {total}. Ideal share per alive player: {ideal:.2f}."]
    for name in alive:
        share = counts[name] / total if total else 0.0
        mode = "talkative" if total == 0 or share < ideal else "listening"
        lines.append(f"{name}: messages={counts[name]}, share={share:.2f}, suggested scheduler stance={mode}.")
    return "\n".join(lines)


def parse_send_wait(raw: str) -> tuple[str, bool]:
    text = (raw or "").strip().lower()
    if "<send>" in text or re.search(r"\bsend\b|\bspeak\b|\bintervene\b", text):
        return "send", False
    if "<wait>" in text or re.search(r"\bwait\b|\bpass\b|\bstop\b|\bvote\b", text):
        return "wait", False
    return "send", True


def build_moderator_scheduler_prompt(
    moderator: Moderator,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    day: int,
    floor: int,
    scheduler_round: int,
    sim_time_sec: float,
    protocol: str = "moderated_time_to_talk",
    candidate_cue: str | None = None,
) -> str:
    discussion_count = day_discussion_count(events, day)
    floor_state = "has not reached the discussion floor" if discussion_count < floor else "has reached the discussion floor"
    candidate = f"\nCandidate moderator cue under consideration:\n\"{trim_message(candidate_cue, 48)}\"\n" if candidate_cue else ""
    quality_line = ""
    if protocol == "moderated_quality_time_to_talk":
        quality_line = "\n- In quality-filtered mode, choose <send> only when the next cue can elicit concrete, non-redundant evidence, defense, claim analysis, or vote reasoning."
    return f"""You are the neutral Moderator/Narrator in a 7-player Mafia game.
You are not a player and you do not try to help either faction. Your job is to manage an asynchronous day discussion fairly.

Time-to-Talk scheduler module:
- Decide whether the moderator should send a short neutral cue now or wait/end discussion.
- Use only the public transcript and message timing.
- If useful discussion is sparse, choose <send>.
- If the discussion floor is met and further talk is repetitive or low-value, choose <wait>.
- Never reveal hidden roles or private night actions beyond public announcements.
- Return only the tag. Do not include JSON, markdown, thoughts, or explanation.
{quality_line}

Current time: [{format_clock(sim_time_sec)}]
Day: {day}
Scheduler round: {scheduler_round}
Current public discussion count: {discussion_count}; floor: {floor}; the game {floor_state}.

Message-rate state:
{format_message_rate_report(players, events, day)}

Timed public transcript:
{timed_transcript(events)}
{candidate}
Return only <send> or <wait>.
"""


def build_moderator_generator_prompt(
    moderator: Moderator,
    players: dict[str, Player],
    events: list[dict[str, Any]],
    day: int,
    floor: int,
    scheduler_round: int,
    sim_time_sec: float,
    eligible: list[str],
    protocol: str = "moderated_time_to_talk",
    forced: bool = False,
) -> str:
    quality_line = ""
    if protocol == "moderated_quality_time_to_talk":
        quality_line = "\n- In quality-filtered mode, prefer a cue that asks for one specific read, contradiction, claim check, defense, or vote reason that has not already been covered."
    return f"""You are the neutral Moderator/Narrator in a 7-player Mafia game.
Moderator generator module.
The scheduler chose <send>. Generate the moderator's next short neutral cue.

Rules:
- Pick exactly one alive player to receive the floor from this eligible list: {eligible}
- The cue must start with the exact selected player name followed by a comma.
- Address only that one selected player. Do not address the whole table or list multiple players as addressees.
- Do not reveal hidden roles, night choices, private investigations, or private protections.
- Do not suggest a player may be Detective, Doctor, or Mafia unless that claim is already public in the transcript.
- Do not ask for private night findings unless the selected player has publicly claimed an investigative role.
- Ask for concrete evidence, claim analysis, defense, pressure, or vote reasoning.
- Keep the cue neutral. Do not accuse on behalf of the moderator.
- If discussion is sparse or forced={forced}, invite a low-participation player to give a concrete read.
- Return only JSON. Do not include markdown, thoughts, or explanation.
{quality_line}

Current time: [{format_clock(sim_time_sec)}]
Day: {day}
Discussion floor: {floor}
Scheduler round: {scheduler_round}

Message-rate state:
{format_message_rate_report(players, events, day)}

Timed public transcript:
{timed_transcript(events)}

Return JSON exactly:
{{"target": "one exact eligible player name", "message_type": "evidence/claim_check/pressure/defense/vote_coordination", "cue": "moderator cue, 24 words or fewer"}}
"""


def parse_moderator_generation(raw: str, eligible: list[str], rng: random.Random, speaker_counts: Counter[str]) -> tuple[str, str, str, bool]:
    parsed = extract_json(raw) or {}
    target = ""
    for key in ("target", "player", "speaker", "name", "floor_to"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            target = value.strip()
            break
    cue = ""
    for key in ("cue", "message", "prompt", "moderator_cue"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            cue = value.strip()
            break
    message_type = str(parsed.get("message_type", "pressure") or "pressure").strip()
    failed = False
    if target not in eligible:
        for candidate in eligible:
            if re.search(rf"\b{re.escape(candidate)}\b", raw, flags=re.I):
                target = candidate
                break
    if target not in eligible:
        failed = True
        target = pick_floor_speaker(eligible, speaker_counts, rng)
    if not cue:
        cue_match = re.search(r"(?:cue|prompt|message)\s*[:=-]\s*[\"']?(.{12,220})", raw, flags=re.I | re.S)
        if cue_match:
            cue = cue_match.group(1).strip().strip("\"'`")
        else:
            quoted = re.search(r"[\"']([^\"']{12,220})[\"']", raw)
            if quoted:
                cue = quoted.group(1).strip()
    if not cue:
        failed = True
        cue = f"{target}, give one concrete read and one vote reason."
    if message_type not in {"evidence", "claim_check", "pressure", "defense", "vote_coordination"}:
        message_type = "pressure"
    return target, trim_message(cue, 24), message_type, failed


def moderator_cue_quality(cue: str, target: str, events: list[dict[str, Any]], day: int) -> tuple[int, int]:
    text = cue.strip()
    lowered = text.lower()
    words = text.split()
    score = 0
    if text.startswith(f"{target},"):
        score += 1
    if 7 <= len(words) <= 26:
        score += 1
    if re.search(r"\b(concrete|specific|evidence|read|reason|vote|claim|defend|explain|pressure|contradiction)\b", lowered):
        score += 2
    if "?" in text or re.search(r"\b(give|share|explain|defend|name)\b", lowered):
        score += 1
    redundancy = 0
    if len(words) < 6 or len(words) > 32:
        redundancy += 1
    named_players = [name for name in PLAYER_NAMES if re.search(rf"\b{re.escape(name)}\b", text)]
    if len(set(named_players) - {target}) >= 2:
        redundancy += 2
    recent_cues = [
        str(event.get("cue", "")).lower()
        for event in events
        if event.get("type") == "moderator_prompt" and event.get("day") == day
    ][-3:]
    cue_terms = set(re.findall(r"\b[a-z]{4,}\b", lowered))
    for prior in recent_cues:
        prior_terms = set(re.findall(r"\b[a-z]{4,}\b", prior))
        if cue_terms and len(cue_terms & prior_terms) / max(len(cue_terms), 1) > 0.65:
            redundancy += 1
            break
    return min(5, score), min(5, redundancy)


def run_moderated_time_to_talk_discussion(
    players: dict[str, Player],
    events: list[dict[str, Any]],
    day: int,
    protocol: str,
    stats: GameStats,
    rng: random.Random,
    moderator_spec: AgentSpec,
) -> None:
    moderator = Moderator(name=MODERATOR_NAME, role="Moderator", spec=moderator_spec)
    floor = role_aware_floor(players)
    max_turns = max(floor + 1, min(10, len(alive_players(players)) * 2))
    speaker_counts: Counter[str] = Counter()
    sim_time_sec = 0.0
    message_times: list[float] = []
    last_speaker: str | None = None
    consecutive_waits = 0

    for scheduler_round in range(1, max_turns + 1):
        alive = alive_players(players)
        eligible = [
            name for name in alive
            if speaker_counts[name] < 2 and (name != last_speaker or len(alive) == 1)
        ]
        if not eligible:
            break
        stats.scheduler_rounds += 1
        stats.scheduler_calls += 1
        stats.moderator_scheduler_calls += 1

        candidate_cue = None
        candidate_target = None
        candidate_message_type = "pressure"
        if protocol == "moderated_candidate_time_to_talk":
            candidate_prompt = build_moderator_generator_prompt(
                moderator, players, events, day, floor, scheduler_round, sim_time_sec, eligible, protocol=protocol, forced=False
            )
            stats.moderator_generator_calls += 1
            candidate_raw = safe_call(moderator, candidate_prompt, stats, max_tokens=160, action="moderator_candidate_generator")
            candidate_target, candidate_cue, candidate_message_type, candidate_failed = parse_moderator_generation(candidate_raw, eligible, rng, speaker_counts)
            stats.candidate_messages += 1
            if candidate_failed:
                stats.moderator_parse_failures += 1

        scheduler_prompt = build_moderator_scheduler_prompt(
            moderator, players, events, day, floor, scheduler_round, sim_time_sec, protocol=protocol, candidate_cue=candidate_cue
        )
        scheduler_raw = safe_call(moderator, scheduler_prompt, stats, max_tokens=16, action="moderator_scheduler")
        decision, failed = parse_send_wait(scheduler_raw)
        if failed:
            stats.moderator_parse_failures += 1
        events.append({
            "type": "moderator_scheduler_decision",
            "day": day,
            "scheduler_round": scheduler_round,
            "protocol": protocol,
            "decision": decision,
            "raw": scheduler_raw[:200],
            "discussion_count": day_discussion_count(events, day),
            "floor": floor,
            "parse_failed": failed,
            "sim_time_sec": sim_time_sec,
        })

        forced = False
        if decision == "wait":
            stats.waits += 1
            stats.moderator_wait_decisions += 1
            consecutive_waits += 1
            sim_time_sec += 3
            stats.moderator_sim_wait_seconds += 3
            if day_discussion_count(events, day) >= floor:
                break
            if consecutive_waits < 2:
                continue
            forced = True
            stats.moderator_forced_interventions += 1
        else:
            stats.moderator_send_decisions += 1
            consecutive_waits = 0

        generator_raw = ""
        if candidate_cue and protocol == "moderated_candidate_time_to_talk" and not forced:
            target, cue, message_type, generation_failed = parse_moderator_generation(
                json.dumps({"target": candidate_target, "cue": candidate_cue, "message_type": candidate_message_type}),
                eligible,
                rng,
                speaker_counts,
            )
            generator_raw = json.dumps({"target": candidate_target, "cue": candidate_cue, "message_type": candidate_message_type})
        else:
            generator_prompt = build_moderator_generator_prompt(
                moderator, players, events, day, floor, scheduler_round, sim_time_sec, eligible, protocol=protocol, forced=forced
            )
            stats.moderator_generator_calls += 1
            generator_raw = safe_call(moderator, generator_prompt, stats, max_tokens=160, action="moderator_generator")
            target, cue, message_type, generation_failed = parse_moderator_generation(generator_raw, eligible, rng, speaker_counts)
        if generation_failed:
            stats.moderator_parse_failures += 1

        quality_score = None
        redundancy_risk = None
        quality_rejected = False
        if protocol == "moderated_quality_time_to_talk":
            quality_score, redundancy_risk = moderator_cue_quality(cue, target, events, day)
            floor_met = day_discussion_count(events, day) >= floor
            if floor_met and quality_score < 3:
                quality_rejected = True
                stats.deferred_messages += 1
                stats.waits += 1
                events.append({
                    "type": "moderator_rejected_cue",
                    "day": day,
                    "scheduler_round": scheduler_round,
                    "target": target,
                    "cue": cue,
                    "quality_score": quality_score,
                    "redundancy_risk": redundancy_risk,
                    "protocol": protocol,
                    "sim_time_sec": sim_time_sec,
                })
                sim_time_sec += 3
                stats.moderator_sim_wait_seconds += 3
                continue

        stats.moderator_interventions += 1
        cue_words = len(cue.split())
        cue_typing = min(10, max(1, cue_words // 3 if cue_words else 1))
        sim_time_sec += cue_typing
        stats.moderator_sim_typing_seconds += cue_typing
        events.append({
            "type": "moderator_prompt",
            "day": day,
            "scheduler_round": scheduler_round,
            "speaker": MODERATOR_NAME,
            "target": target,
            "cue": cue,
            "message_type": message_type,
            "protocol": protocol,
            "forced": forced,
            "sim_time_sec": sim_time_sec,
            "generator_raw": generator_raw[:300],
            "parse_failed": bool(generation_failed),
            "quality_score": quality_score,
            "redundancy_risk": redundancy_risk,
            "quality_rejected": quality_rejected,
        })

        player = players[target]
        review_context = maybe_revac_review(
            player, players, events, "moderator_cued_message", [], day, protocol, stats, moderator_cue=cue
        )
        player_prompt = build_prompt(
            player,
            players,
            events,
            "moderator_cued_message",
            [],
            day,
            protocol,
            moderator_cue=cue,
            review_context=review_context,
        )
        raw = safe_call(player, player_prompt, stats, max_tokens=192, action="moderator_cued_message")
        speak, message, player_failed = parse_discussion(raw, protocol)
        speak, message, message_guarded, guarded_message_type = holy_grail_message_guardrail(
            player, players, events, "moderator_cued_message", day, speak, message, stats
        )
        if not message_guarded:
            speak, message, message_guarded, guarded_message_type = holy_grail_v3_message_guardrail(
                player, players, events, "moderator_cued_message", day, speak, message, stats
            )
        if message_guarded:
            player_failed = False
        if player_failed:
            stats.parse_failures += 1
        if speak and message:
            speaker_counts[target] += 1
            last_speaker = target
            stats.discussion_messages += 1
            message_words = len(message.split())
            message_typing = min(12, max(1, message_words // 3 if message_words else 1))
            sim_time_sec += message_typing
            stats.moderator_sim_typing_seconds += message_typing
            message_times.append(sim_time_sec)
            events.append({
                "type": "discussion",
                "day": day,
                "speaker": target,
                "message": message,
                "protocol": protocol,
                "scheduler_round": scheduler_round,
                "moderator_cue": cue,
                "message_type": guarded_message_type or message_type,
                "forced_floor": forced,
                "architecture_message_guarded": message_guarded,
                "sim_time_sec": sim_time_sec,
            })
        else:
            stats.waits += 1
            sim_time_sec += 3
            stats.moderator_sim_wait_seconds += 3

        if day_discussion_count(events, day) >= floor and scheduler_round >= floor:
            # Let the scheduler get one more chance only if the last message created a major new public claim.
            recent_claims = public_role_claims([event for event in events if event.get("day") == day])
            if not recent_claims:
                continue

    if len(message_times) >= 2:
        gaps = [b - a for a, b in zip(message_times, message_times[1:])]
        stats.moderator_avg_message_gap_seconds = sum(gaps) / len(gaps)
    counts = day_speaker_counts(events, day)
    total = sum(counts.values())
    if total:
        alive = alive_players(players)
        ideal = 1 / len(alive) if alive else 0.0
        stats.moderator_message_rate_deviation = sum(abs((counts[name] / total) - ideal) for name in alive) / len(alive)


def run_dynamic_time_to_talk_discussion(
    players: dict[str, Player],
    events: list[dict[str, Any]],
    day: int,
    protocol: str,
    stats: GameStats,
    rng: random.Random,
) -> None:
    speaker_counts: Counter[str] = Counter()
    role_aware = protocol in {"role_aware_time_to_talk", "role_aware_quality_time_to_talk"}
    quality_filtered = protocol == "role_aware_quality_time_to_talk"
    floor = role_aware_floor(players) if role_aware else 0
    if quality_filtered:
        max_turns = floor
        speaker_cap = 1
    elif role_aware:
        max_turns = floor
        speaker_cap = 1
    else:
        max_turns = max(4, len(alive_players(players)))
        speaker_cap = 2
    last_speaker: str | None = None

    for scheduler_round in range(1, max_turns + 1):
        alive = alive_players(players)
        eligible = [
            name for name in alive
            if speaker_counts[name] < speaker_cap and (name != last_speaker or len(alive) == 1)
        ]
        if not eligible:
            break
        stats.scheduler_rounds += 1
        offers: list[dict[str, Any]] = []
        for name in eligible:
            player = players[name]
            if protocol == "candidate_time_to_talk":
                review_context = maybe_revac_review(player, players, events, "candidate_message", [], day, protocol, stats)
                candidate_prompt = build_prompt(player, players, events, "candidate_message", [], day, protocol, review_context=review_context)
                candidate_raw = safe_call(player, candidate_prompt, stats, max_tokens=128, action="candidate_message")
                _, candidate_message, candidate_failed = parse_discussion(candidate_raw, "round_robin")
                stats.candidate_messages += 1
                if candidate_failed:
                    stats.parse_failures += 1
                candidate_message = candidate_message or trim_message(candidate_raw, 28)
                events.append({
                    "type": "scheduler_candidate",
                    "day": day,
                    "scheduler_round": scheduler_round,
                    "speaker": name,
                    "protocol": protocol,
                    "message": candidate_message,
                })
                prompt = build_prompt(
                    player,
                    players,
                    events,
                    "schedule_candidate",
                    [],
                    day,
                    protocol,
                    candidate_message=candidate_message,
                )
            elif quality_filtered:
                prompt = build_prompt(player, players, events, "role_aware_quality_time_to_talk_offer", [], day, protocol)
            elif role_aware:
                prompt = build_prompt(player, players, events, "role_aware_time_to_talk_offer", [], day, protocol)
            else:
                prompt = build_prompt(player, players, events, "time_to_talk_offer", [], day, protocol)
            stats.scheduler_calls += 1
            raw = safe_call(player, prompt, stats, max_tokens=160, action="time_to_talk_offer")
            speak, message, urgency, failed = parse_speech_offer(raw)
            if failed:
                stats.parse_failures += 1
            parsed_offer = extract_json(raw) or {}
            message_type = str(parsed_offer.get("message_type", "") or "")
            quality_score = None
            redundancy_risk = None
            selection_score = int(urgency)
            if quality_filtered:
                try:
                    quality_score = max(0, min(5, int(float(parsed_offer.get("quality", urgency)))))
                except (TypeError, ValueError):
                    quality_score = int(urgency)
                try:
                    redundancy_risk = max(0, min(5, int(float(parsed_offer.get("redundancy_risk", 0)))))
                except (TypeError, ValueError):
                    redundancy_risk = 0
                selection_score = max(0, int(urgency) * 2 + quality_score - redundancy_risk)
                if quality_score < 2 or redundancy_risk >= 5:
                    speak = False
                    message = None
            events.append({
                "type": "scheduler_offer",
                "day": day,
                "scheduler_round": scheduler_round,
                "speaker": name,
                "protocol": protocol,
                "speak": bool(speak),
                "urgency": int(urgency),
                "message_type": message_type,
                "message": message or "",
                "quality_score": quality_score,
                "redundancy_risk": redundancy_risk,
                "selection_score": selection_score,
                "parse_failed": bool(failed),
            })
            if speak and message:
                offers.append({
                    "speaker": name,
                    "message": message,
                    "urgency": urgency,
                    "quality_score": quality_score,
                    "redundancy_risk": redundancy_risk,
                    "selection_score": selection_score,
                    "message_type": message_type,
                    "raw": raw,
                })
            else:
                stats.waits += 1
        if not offers:
            if role_aware and day_discussion_count(events, day) < floor:
                forced_speaker = emit_forced_role_aware_message(
                    players,
                    events,
                    day,
                    protocol,
                    stats,
                    rng,
                    eligible,
                    speaker_counts,
                    scheduler_round,
                )
                if forced_speaker:
                    last_speaker = forced_speaker
                    continue
            break
        best_urgency = max(int(offer["urgency"]) for offer in offers)
        floor_met = not role_aware or day_discussion_count(events, day) >= floor
        if quality_filtered:
            qualified = [
                offer for offer in offers
                if int(offer.get("quality_score") if offer.get("quality_score") is not None else offer["urgency"]) >= 3
                or not floor_met
            ]
            if qualified:
                offers = qualified
            elif stats.discussion_messages > 0 and floor_met:
                stats.deferred_messages += len(offers)
                break
            best_urgency = max(int(offer["urgency"]) for offer in offers)
        if best_urgency < 2 and stats.discussion_messages > 0 and floor_met:
            stats.deferred_messages += len(offers)
            break
        if quality_filtered:
            best_score = max(int(offer.get("selection_score", offer["urgency"])) for offer in offers)
            best_offers = [offer for offer in offers if int(offer.get("selection_score", offer["urgency"])) == best_score]
        else:
            best_offers = [offer for offer in offers if int(offer["urgency"]) == best_urgency]
        selected = rng.choice(best_offers)
        stats.deferred_messages += len(offers) - 1
        speaker = str(selected["speaker"])
        speaker_counts[speaker] += 1
        last_speaker = speaker
        stats.discussion_messages += 1
        events.append({
            "type": "discussion",
            "day": day,
            "speaker": speaker,
            "message": selected["message"],
            "protocol": protocol,
            "scheduler_round": scheduler_round,
            "urgency": int(selected["urgency"]),
            "message_type": selected.get("message_type", ""),
            "quality_score": selected.get("quality_score"),
            "redundancy_risk": selected.get("redundancy_risk"),
            "selection_score": selected.get("selection_score"),
            "forced_floor": role_aware and not floor_met and best_urgency < 2,
            "selected_from": len(offers),
        })


def run_discussion(
    players: dict[str, Player],
    events: list[dict[str, Any]],
    day: int,
    protocol: str,
    stats: GameStats,
    rng: random.Random,
    moderator_spec: AgentSpec | None = None,
) -> None:
    if protocol in MODERATED_PROTOCOLS:
        if moderator_spec is None:
            moderator_spec = AgentSpec(provider="stub", model="moderator_stub", architecture="baseline", temperature=0.0)
        run_moderated_time_to_talk_discussion(players, events, day, protocol, stats, rng, moderator_spec)
        return
    if protocol in {"time_to_talk", "candidate_time_to_talk", "role_aware_time_to_talk", "role_aware_quality_time_to_talk"}:
        run_dynamic_time_to_talk_discussion(players, events, day, protocol, stats, rng)
        return

    for name in alive_players(players):
        player = players[name]
        review_context = maybe_revac_review(player, players, events, "discussion", [], day, protocol, stats)
        prompt = build_prompt(player, players, events, "discussion", [], day, protocol, review_context=review_context)
        raw = safe_call(player, prompt, stats, max_tokens=128, action="discussion")
        speak, message, failed = parse_discussion(raw, protocol)
        if failed:
            stats.parse_failures += 1
        if speak and message:
            stats.discussion_messages += 1
            events.append({"type": "discussion", "day": day, "speaker": name, "message": message})
        else:
            stats.waits += 1


def post_game_metrics(events: list[dict[str, Any]], roles: dict[str, str], final_alive: list[str]) -> dict[str, Any]:
    claims = public_role_claims(events)
    false_claims = 0
    true_claims = 0
    mafia_false_claims = 0
    good_false_claims = 0
    for claim in claims:
        speaker = str(claim["speaker"])
        claimed_role = str(claim["role"])
        actual_role = roles.get(speaker)
        if actual_role == claimed_role:
            true_claims += 1
        else:
            false_claims += 1
            if actual_role == "Mafia":
                mafia_false_claims += 1
            else:
                good_false_claims += 1
    first_mafia_eliminated_day = None
    eliminated_roles = []
    for event in events:
        if event.get("type") == "elimination":
            eliminated_roles.append(event.get("role"))
            if event.get("role") == "Mafia" and first_mafia_eliminated_day is None:
                first_mafia_eliminated_day = event.get("day")
    role_claims = len(claims)
    good_votes_total = 0
    good_votes_on_mafia = 0
    mafia_votes_total = 0
    mafia_votes_on_good = 0
    vote_targets_by_day: dict[int, Counter[str]] = defaultdict(Counter)
    for event in events:
        if event.get("type") != "vote":
            continue
        voter = str(event.get("voter"))
        target = str(event.get("target"))
        day = int(event.get("day", 0) or 0)
        vote_targets_by_day[day][target] += 1
        if roles.get(voter) == "Mafia":
            mafia_votes_total += 1
            if roles.get(target) != "Mafia":
                mafia_votes_on_good += 1
        else:
            good_votes_total += 1
            if roles.get(target) == "Mafia":
                good_votes_on_mafia += 1
    day_vote_majorities = 0
    for counts in vote_targets_by_day.values():
        if not counts:
            continue
        top = counts.most_common(1)[0][1]
        total = sum(counts.values())
        if top > total / 2:
            day_vote_majorities += 1
    detective_checks = [event for event in events if event.get("type") == "detective_check"]
    doctor_protects = [event for event in events if event.get("type") == "doctor_save"]
    detective_hits = sum(1 for event in detective_checks if event.get("result") == "Mafia")
    doctor_self_protects = sum(1 for event in doctor_protects if event.get("target") == event.get("doctor"))
    doctor_protected_detective = sum(1 for event in doctor_protects if roles.get(str(event.get("target"))) == "Detective")
    forced_floor_messages = sum(1 for event in events if event.get("type") == "discussion" and event.get("forced_floor"))
    forced_floor_attempts = sum(1 for event in events if event.get("type") == "scheduler_forced_floor")
    quality_offers = [
        event for event in events
        if event.get("quality_score") is not None
        and event.get("type") in {"scheduler_offer", "moderator_prompt", "moderator_rejected_cue"}
    ]
    selected_quality_messages = [
        event for event in events
        if event.get("quality_score") is not None
        and event.get("type") in {"discussion", "moderator_prompt"}
        and not event.get("quality_rejected")
    ]
    def avg_quality(items: list[dict[str, Any]], key: str) -> float:
        values = [float(item[key]) for item in items if item.get(key) is not None]
        return sum(values) / len(values) if values else 0.0
    return {
        "role_claims": role_claims,
        "true_role_claims": true_claims,
        "false_role_claims": false_claims,
        "role_claim_deception_rate": false_claims / role_claims if role_claims else 0.0,
        "mafia_false_claims": mafia_false_claims,
        "good_false_claims": good_false_claims,
        "first_mafia_eliminated_day": first_mafia_eliminated_day,
        "mafia_eliminated_count": sum(1 for role in eliminated_roles if role == "Mafia"),
        "detective_alive_final": int(any(roles[name] == "Detective" for name in final_alive)),
        "doctor_alive_final": int(any(roles[name] == "Doctor" for name in final_alive)),
        "mafia_alive_final": sum(1 for name in final_alive if roles[name] == "Mafia"),
        "good_votes_total": good_votes_total,
        "good_votes_on_mafia": good_votes_on_mafia,
        "good_vote_accuracy": good_votes_on_mafia / good_votes_total if good_votes_total else 0.0,
        "mafia_votes_total": mafia_votes_total,
        "mafia_votes_on_good": mafia_votes_on_good,
        "mafia_vote_accuracy": mafia_votes_on_good / mafia_votes_total if mafia_votes_total else 0.0,
        "day_vote_majorities": day_vote_majorities,
        "detective_checks": len(detective_checks),
        "detective_mafia_hits": detective_hits,
        "detective_hit_rate": detective_hits / len(detective_checks) if detective_checks else 0.0,
        "doctor_protects": len(doctor_protects),
        "doctor_self_protects": doctor_self_protects,
        "doctor_protected_detective": doctor_protected_detective,
        "forced_floor_messages": forced_floor_messages,
        "forced_floor_attempts": forced_floor_attempts,
        "quality_offer_count": len(quality_offers),
        "avg_offer_quality": avg_quality(quality_offers, "quality_score"),
        "avg_offer_redundancy_risk": avg_quality(quality_offers, "redundancy_risk"),
        "selected_quality_messages": len(selected_quality_messages),
        "avg_selected_quality": avg_quality(selected_quality_messages, "quality_score"),
        "low_quality_offer_count": sum(1 for event in quality_offers if float(event.get("quality_score") or 0) < 3),
    }


def post_player_metrics(
    events: list[dict[str, Any]],
    roles: dict[str, str],
    final_alive: list[str],
    lineup: dict[str, AgentSpec],
) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    final_alive_set = set(final_alive)
    claims = public_role_claims(events)
    for name in PLAYER_NAMES:
        spec = lineup.get(name.lower())
        role = roles[name]
        faction_key = "mafia" if role == "Mafia" else "good"
        spec = spec or lineup.get(role.lower()) or lineup.get(faction_key) or lineup["default"]
        player_claims = [claim for claim in claims if claim.get("speaker") == name]
        eliminated_day = None
        killed_night = None
        votes_cast = 0
        votes_received = 0
        messages_spoken = 0
        for event in events:
            if event.get("type") == "elimination" and event.get("target") == name:
                eliminated_day = event.get("day")
            elif event.get("type") == "night_result" and str(event.get("message", "")).startswith(f"{name} was killed"):
                killed_night = event.get("night")
            elif event.get("type") == "vote":
                if event.get("voter") == name:
                    votes_cast += 1
                if event.get("target") == name:
                    votes_received += 1
            elif event.get("type") == "discussion" and event.get("speaker") == name:
                messages_spoken += 1
        metrics[name] = {
            "role": role,
            "faction": "mafia" if role == "Mafia" else "good",
            "provider": spec.provider,
            "model": spec.model,
            "architecture": spec.architecture,
            "alive_final": name in final_alive_set,
            "eliminated_day": eliminated_day,
            "killed_night": killed_night,
            "messages_spoken": messages_spoken,
            "votes_cast": votes_cast,
            "votes_received": votes_received,
            "role_claims": len(player_claims),
            "false_role_claims": sum(1 for claim in player_claims if roles.get(name) != claim.get("role")),
        }
    return metrics


def run_game(seed: int, lineup: dict[str, AgentSpec], protocol: str, max_days: int, tie_policy: str = "random") -> dict[str, Any]:
    start = time.perf_counter()
    rng = random.Random(seed)
    roles = assign_roles(seed)
    players = build_players(roles, lineup)
    moderator_spec = lineup.get("moderator") or lineup.get("ttt_moderator")
    events: list[dict[str, Any]] = [{
        "type": "system",
        "message": "Game start. Roles are hidden. There are 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.",
    }]
    stats = GameStats()
    winner = check_winner(players)
    day = 0

    while winner is None and day < max_days:
        day += 1

        kill_target = choose_mafia_kill(players, events, day, protocol, stats, rng)

        detective_names = [name for name in alive_players(players) if players[name].role == "Detective"]
        if detective_names:
            detective = players[detective_names[0]]
            candidates = [name for name in alive_players(players) if name != detective.name]
            unchecked = [name for name in candidates if name not in detective.investigations]
            detect_target = choose_target(detective, players, events, "detective_check", unchecked or candidates, day, protocol, stats, rng)
            result = "Mafia" if players[detect_target].role == "Mafia" else "not Mafia"
            detective.investigations[detect_target] = result
            events.append({
                "type": "detective_check",
                "night": day,
                "detective": detective.name,
                "target": detect_target,
                "result": result,
            })
        else:
            detect_target = None

        doctor_names = [name for name in alive_players(players) if players[name].role == "Doctor"]
        if doctor_names:
            doctor = players[doctor_names[0]]
            candidates = alive_players(players)
            protect_target = choose_target(doctor, players, events, "doctor_save", candidates, day, protocol, stats, rng)
            doctor.last_protected = protect_target
            events.append({
                "type": "doctor_save",
                "night": day,
                "doctor": doctor.name,
                "target": protect_target,
            })
        else:
            protect_target = None

        if kill_target and kill_target == protect_target:
            night_message = "No one died during the night."
            stats.doctor_saves += 1
        elif kill_target and players[kill_target].alive:
            players[kill_target].alive = False
            night_message = f"{kill_target} was killed during the night."
        else:
            night_message = "No one died during the night."
        events.append({"type": "night_result", "night": day, "message": night_message})

        winner = check_winner(players)
        if winner is not None:
            break

        run_discussion(players, events, day, protocol, stats, rng, moderator_spec=moderator_spec)

        votes: dict[str, str] = {}
        for name in alive_players(players):
            player = players[name]
            candidates = [candidate for candidate in alive_players(players) if candidate != name]
            target = choose_target(player, players, events, "vote", candidates, day, protocol, stats, rng)
            votes[name] = target
            events.append({"type": "vote", "day": day, "voter": name, "target": target})

        counts = Counter(votes.values())
        if counts:
            max_votes = max(counts.values())
            tied = sorted([name for name, count in counts.items() if count == max_votes])
            if len(tied) > 1 and tie_policy == "no_elimination":
                stats.tie_no_eliminations += 1
                events.append({
                    "type": "no_elimination",
                    "day": day,
                    "message": f"No one was eliminated because the vote tied among: {', '.join(tied)}.",
                    "tied": tied,
                })
            else:
                eliminated = rng.choice(tied)
                players[eliminated].alive = False
                events.append({
                    "type": "elimination",
                    "day": day,
                    "message": f"{eliminated} was eliminated by vote. Their role was {players[eliminated].role}.",
                    "target": eliminated,
                    "role": players[eliminated].role,
                    "tie": len(tied) > 1,
                })

        winner = check_winner(players)

    if winner is None:
        mafia_count = len(alive_mafia(players))
        good_count = len([name for name in alive_players(players) if players[name].role in GOOD_ROLES])
        winner = "mafia" if mafia_count >= good_count else "good"
        events.append({"type": "system", "message": f"Max days reached; adjudicated winner: {winner}."})

    stats.elapsed_sec = round(time.perf_counter() - start, 3)
    final_alive = alive_players(players)
    metrics = post_game_metrics(events, roles, final_alive)
    player_metrics = post_player_metrics(events, roles, final_alive, lineup)
    return {
        "seed": seed,
        "protocol": protocol,
        "winner": winner,
        "mafia_win": winner == "mafia",
        "good_win": winner == "good",
        "days": day,
        "roles": roles,
        "final_alive": final_alive,
        "final_alive_roles": {name: players[name].role for name in final_alive},
        "events": events,
        "stats": stats.__dict__,
        "metrics": metrics,
        "player_metrics": player_metrics,
        "lineup": {key: spec.label for key, spec in lineup.items()},
        "tie_policy": tie_policy,
    }


def make_lineup(kind: str, default_spec: AgentSpec, alt_spec: AgentSpec | None = None) -> dict[str, AgentSpec]:
    if kind == "homogeneous":
        return {"default": default_spec}
    if kind == "small_good_large_mafia":
        if alt_spec is None:
            raise ValueError("small_good_large_mafia requires --alt-model")
        return {"default": default_spec, "good": default_spec, "mafia": alt_spec}
    if kind == "large_good_small_mafia":
        if alt_spec is None:
            raise ValueError("large_good_small_mafia requires --alt-model")
        return {"default": alt_spec, "good": alt_spec, "mafia": default_spec}
    raise ValueError(f"Unknown lineup kind: {kind}")


def summarize(rows: list[dict[str, Any]], output_prefix: Path) -> None:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row.get("scenario") or row["cell"],
            row.get("lineup_digest") or row["model"],
            row.get("architecture", "mixed"),
            row["protocol"],
        )
        groups[key].append(row)
    summary_rows = []
    def avg(items: list[dict[str, Any]], key: str) -> float:
        return sum(float(item.get(key, 0) or 0) for item in items) / len(items) if items else 0.0

    for (cell, model, architecture, protocol), items in sorted(groups.items()):
        n = len(items)
        summary_rows.append({
            "cell": cell,
            "model": model,
            "architecture": architecture,
            "protocol": protocol,
            "n": n,
            "good_wins": sum(item["good_win"] for item in items),
            "mafia_wins": sum(item["mafia_win"] for item in items),
            "good_win_rate": sum(item["good_win"] for item in items) / n if n else 0.0,
            "avg_days": avg(items, "days"),
            "avg_parse_failures": avg(items, "parse_failures"),
            "avg_invalid_actions": avg(items, "invalid_actions"),
            "avg_api_errors": avg(items, "api_errors"),
            "avg_discussion_messages": avg(items, "discussion_messages"),
            "avg_waits": avg(items, "waits"),
            "avg_scheduler_calls": avg(items, "scheduler_calls"),
            "avg_scheduler_rounds": avg(items, "scheduler_rounds"),
            "avg_candidate_messages": avg(items, "candidate_messages"),
            "avg_deferred_messages": avg(items, "deferred_messages"),
            "avg_revac_review_calls": avg(items, "revac_review_calls"),
            "avg_moderator_scheduler_calls": avg(items, "moderator_scheduler_calls"),
            "avg_moderator_generator_calls": avg(items, "moderator_generator_calls"),
            "avg_moderator_interventions": avg(items, "moderator_interventions"),
            "avg_moderator_wait_decisions": avg(items, "moderator_wait_decisions"),
            "avg_moderator_forced_interventions": avg(items, "moderator_forced_interventions"),
            "avg_moderator_parse_failures": avg(items, "moderator_parse_failures"),
            "avg_moderator_gap_seconds": avg(items, "moderator_avg_message_gap_seconds"),
            "avg_moderator_rate_deviation": avg(items, "moderator_message_rate_deviation"),
            "avg_forced_floor_messages": avg(items, "forced_floor_messages"),
            "avg_forced_floor_attempts": avg(items, "forced_floor_attempts"),
            "avg_role_claims": avg(items, "role_claims"),
            "avg_false_role_claims": avg(items, "false_role_claims"),
            "avg_role_claim_deception_rate": avg(items, "role_claim_deception_rate"),
            "avg_mafia_false_claims": avg(items, "mafia_false_claims"),
            "avg_good_false_claims": avg(items, "good_false_claims"),
            "avg_doctor_saves": avg(items, "doctor_saves"),
            "avg_mafia_kill_votes": avg(items, "mafia_kill_votes"),
            "avg_tie_no_eliminations": avg(items, "tie_no_eliminations"),
            "avg_mafia_alive_final": avg(items, "mafia_alive_final"),
            "avg_quality_offer_count": avg(items, "quality_offer_count"),
            "avg_offer_quality": avg(items, "avg_offer_quality"),
            "avg_offer_redundancy_risk": avg(items, "avg_offer_redundancy_risk"),
            "avg_selected_quality": avg(items, "avg_selected_quality"),
            "avg_low_quality_offer_count": avg(items, "low_quality_offer_count"),
            "avg_sec": avg(items, "elapsed_sec"),
        })

    csv_path = output_prefix.with_name(output_prefix.name + "_summary.csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()) if summary_rows else [])
        if summary_rows:
            writer.writeheader()
            writer.writerows(summary_rows)

    md_path = output_prefix.with_name(output_prefix.name + "_summary.md")
    lines = [
        "# Seven-Player Mafia Benchmark",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "| cell | model/lineup | architecture | protocol | n | good win rate | parse | api errors | msgs | waits | revac | mod sched | mod gen | mod cues | mod waits | mod forced | mod parse | mod gap | rate dev | claims | false claims | deception | doctor saves | mafia kill votes | mafia alive | avg days | avg sec |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {cell} | {model} | {architecture} | {protocol} | {n} | {good_win_rate:.3f} | "
            "{avg_parse_failures:.2f} | {avg_api_errors:.2f} | {avg_discussion_messages:.2f} | "
            "{avg_waits:.2f} | {avg_revac_review_calls:.2f} | {avg_moderator_scheduler_calls:.2f} | "
            "{avg_moderator_generator_calls:.2f} | {avg_moderator_interventions:.2f} | "
            "{avg_moderator_wait_decisions:.2f} | {avg_moderator_forced_interventions:.2f} | "
            "{avg_moderator_parse_failures:.2f} | {avg_moderator_gap_seconds:.2f} | {avg_moderator_rate_deviation:.2f} | "
            "{avg_role_claims:.2f} | {avg_false_role_claims:.2f} | {avg_role_claim_deception_rate:.2f} | "
            "{avg_doctor_saves:.2f} | {avg_mafia_kill_votes:.2f} | "
            "{avg_mafia_alive_final:.2f} | {avg_days:.2f} | {avg_sec:.2f} |".format(**row)
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def flatten_game_result(
    result: dict[str, Any],
    *,
    cell: str,
    model: str,
    architecture: str,
    protocol: str,
    game_index: int,
    scenario: str | None = None,
    description: str | None = None,
    digest: str | None = None,
    tie_policy: str = "random",
) -> dict[str, Any]:
    stats = {key: value for key, value in result["stats"].items() if key != "call_records"}
    flat = {
        "cell": cell,
        "model": model,
        "architecture": architecture,
        "protocol": protocol,
        "tie_policy": tie_policy,
        "game_index": game_index,
        "seed": result["seed"],
        "winner": result["winner"],
        "good_win": result["good_win"],
        "mafia_win": result["mafia_win"],
        "days": result["days"],
        **stats,
        **result.get("metrics", {}),
    }
    if scenario:
        flat["scenario"] = scenario
        flat["description"] = description or ""
        flat["lineup_digest"] = digest or ""
        flat["lineup"] = "; ".join(f"{key}={value}" for key, value in sorted(result["lineup"].items()))
    return flat


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["gemma4:e2b"])
    parser.add_argument("--architectures", nargs="+", default=["baseline", "grail", "revac", "wolf"])
    parser.add_argument("--protocols", nargs="+", default=["round_robin", "time_to_talk"])
    parser.add_argument("--games", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7000)
    parser.add_argument("--max-days", type=int, default=4)
    parser.add_argument("--lineup", choices=["homogeneous", "small_good_large_mafia", "large_good_small_mafia"], default="homogeneous")
    parser.add_argument("--alt-model", default=None)
    parser.add_argument("--alt-architecture", default="baseline")
    parser.add_argument("--moderator-model", default=None)
    parser.add_argument("--moderator-architecture", default="baseline")
    parser.add_argument("--moderator-reasoning-effort", default=None)
    parser.add_argument("--scenario-file", type=Path, default=None)
    parser.add_argument("--scenario", action="append", default=None, help="Scenario name to run from --scenario-file. May be repeated.")
    parser.add_argument("--tie-policy", choices=["random", "no_elimination"], default="random")
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--top-p", type=float, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[3] / "reports" / "seven_player_mafia")
    args = parser.parse_args()

    workspace_root = Path(__file__).resolve().parents[3]
    load_env_file(workspace_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_prefix = args.output_dir / f"seven_player_mafia_{timestamp}"
    jsonl_path = output_prefix.with_suffix(".jsonl")

    rows: list[dict[str, Any]] = []
    with jsonl_path.open("w", encoding="utf-8") as handle:
        if args.scenario_file:
            scenarios = load_scenarios(args.scenario_file)
            wanted = set(args.scenario or [])
            for scenario_config in scenarios:
                scenario_name = scenario_config["name"]
                if wanted and scenario_name not in wanted:
                    continue
                lineup = make_lineup_from_assignments(scenario_config["assignments"], args)
                digest = lineup_digest(lineup)
                protocols = scenario_config.get("protocols") or [scenario_config.get("protocol", args.protocols[0])]
                games = int(scenario_config.get("games", args.games))
                seed0 = int(scenario_config.get("seed", args.seed))
                max_days = int(scenario_config.get("max_days", args.max_days))
                tie_policy = scenario_config.get("tie_policy", args.tie_policy)
                description = scenario_config.get("description", "")
                for protocol in protocols:
                    for game_index in range(games):
                        seed = seed0 + game_index
                        print(f"running scenario={scenario_name} protocol={protocol} seed={seed}", flush=True)
                        result = run_game(seed, lineup, protocol, max_days, tie_policy=tie_policy)
                        flat = flatten_game_result(
                            result,
                            cell=scenario_name,
                            model="mixed",
                            architecture="mixed",
                            protocol=protocol,
                            game_index=game_index,
                            scenario=scenario_name,
                            description=description,
                            digest=digest,
                            tie_policy=tie_policy,
                        )
                        rows.append(flat)
                        handle.write(json.dumps({"summary": flat, "game": result}, ensure_ascii=False) + "\n")
                        handle.flush()
                stop_lineup_models(lineup)
        else:
            for model in args.models:
                for architecture in args.architectures:
                    architecture = normalize_architecture(architecture)
                    default_spec = parse_model_spec(model, architecture, args.reasoning_effort, args.temperature, args.top_p, args.top_k)
                    alt_spec = parse_model_spec(args.alt_model, args.alt_architecture, args.reasoning_effort, args.temperature, args.top_p, args.top_k) if args.alt_model else None
                    lineup = make_lineup(args.lineup, default_spec, alt_spec)
                    if args.moderator_model:
                        lineup["moderator"] = parse_model_spec(
                            args.moderator_model,
                            args.moderator_architecture,
                            args.moderator_reasoning_effort,
                            args.temperature,
                            args.top_p,
                            args.top_k,
                        )
                    for protocol in args.protocols:
                        for game_index in range(args.games):
                            seed = args.seed + game_index
                            print(f"running cell={args.lineup} model={model} architecture={architecture} protocol={protocol} seed={seed}", flush=True)
                            result = run_game(seed, lineup, protocol, args.max_days, tie_policy=args.tie_policy)
                            flat = flatten_game_result(
                                result,
                                cell=args.lineup,
                                model=model,
                                architecture=architecture,
                                protocol=protocol,
                                game_index=game_index,
                                tie_policy=args.tie_policy,
                            )
                            rows.append(flat)
                            handle.write(json.dumps({"summary": flat, "game": result}, ensure_ascii=False) + "\n")
                            handle.flush()
                    stop_lineup_models(lineup)

    summarize(rows, output_prefix)
    print(json.dumps({
        "jsonl": str(jsonl_path),
        "summary_csv": str(output_prefix.with_name(output_prefix.name + "_summary.csv")),
        "summary_md": str(output_prefix.with_name(output_prefix.name + "_summary.md")),
        "rows": len(rows),
    }, indent=2))


if __name__ == "__main__":
    main()
