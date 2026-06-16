from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "multimodel_holy_grail_scenarios.json"

GEMMA_SAMPLER = {"temperature": 1.0, "top_p": 0.95, "top_k": 64}

MODERATOR_BASE = {
    "provider": "modal_base_bf16",
    "model": "google/gemma-4-12B-it",
    "architecture": "baseline",
    **GEMMA_SAMPLER,
}

MODELS = {
    "mafia_gemma_bf16": {
        "provider": "modal_transformers",
        "model": "Alfaxad/mafia-gemma-4-12B-it",
        **GEMMA_SAMPLER,
    },
    "mafia_gemma_gguf_q8": {
        "provider": "modal_gguf",
        "model": "Alfaxad/mafia-gemma-4-12B-it-gguf",
        **GEMMA_SAMPLER,
    },
    "gpt5_medium": {
        "provider": "openai",
        "model": "gpt-5",
        "reasoning_effort": "medium",
        "temperature": 0,
    },
    "gpt5mini": {
        "provider": "openai",
        "model": "gpt-5-mini",
        "reasoning_effort": "low",
        "temperature": 0,
    },
    "claude_opus_4_8": {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "temperature": 0,
    },
    "claude_sonnet_4_6": {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "temperature": 0,
    },
    "gemini_2_5_pro_osv": {
        "provider": "osv_gateway",
        "model": "vertex_ai/gemini-2.5-pro",
        "temperature": 0,
    },
}

FRONTIER = ["gpt5_medium", "gpt5mini", "claude_opus_4_8", "claude_sonnet_4_6", "gemini_2_5_pro_osv"]
LOCAL = ["mafia_gemma_bf16", "mafia_gemma_gguf_q8"]
PLAYER_NAMES = ["ariel", "blake", "casey", "devon", "emery", "finley", "gray"]
ALLSTAR_MODELS = [
    "mafia_gemma_bf16",
    "mafia_gemma_gguf_q8",
    "gpt5_medium",
    "gpt5mini",
    "claude_opus_4_8",
    "claude_sonnet_4_6",
    "gemini_2_5_pro_osv",
]


def with_holy_grail(name: str) -> dict:
    spec = dict(MODELS[name])
    spec["architecture"] = "holy_grail"
    return spec


def scenario(name: str, description: str, protocol: str, assignments: dict, seed: int, games: int = 1) -> dict:
    return {
        "name": name,
        "description": description,
        "seed": seed,
        "games": games,
        "max_days": 6,
        "tie_policy": "random",
        "protocol": protocol,
        "assignments": assignments,
    }


def build_pairwise() -> list[dict]:
    scenarios: list[dict] = []
    seed = 10100
    for local in LOCAL:
        for opponent in FRONTIER:
            scenarios.append(
                scenario(
                    f"{local}_mafia_holy_grail_vs_{opponent}_good_holy_grail_moderated_quality_ttt",
                    (
                        f"{local} controls both Mafia and {opponent} controls all good roles. "
                        "All player agents use Holy Grail under the base Gemma BF16 TTT moderator."
                    ),
                    "moderated_quality_time_to_talk",
                    {
                        "default": with_holy_grail(opponent),
                        "good": with_holy_grail(opponent),
                        "mafia": with_holy_grail(local),
                        "moderator": MODERATOR_BASE,
                    },
                    seed,
                )
            )
            seed += 1
            scenarios.append(
                scenario(
                    f"{local}_good_holy_grail_vs_{opponent}_mafia_holy_grail_moderated_quality_ttt",
                    (
                        f"{local} controls all good roles and {opponent} controls both Mafia. "
                        "All player agents use Holy Grail under the base Gemma BF16 TTT moderator."
                    ),
                    "moderated_quality_time_to_talk",
                    {
                        "default": with_holy_grail(opponent),
                        "good": with_holy_grail(local),
                        "mafia": with_holy_grail(opponent),
                        "moderator": MODERATOR_BASE,
                    },
                    seed,
                )
            )
            seed += 1
    return scenarios


def build_allstars() -> list[dict]:
    scenarios: list[dict] = []
    for rotation, seed in enumerate([10200, 10201, 10202, 10203]):
        rotated = ALLSTAR_MODELS[rotation:] + ALLSTAR_MODELS[:rotation]
        assignments = {"default": with_holy_grail("gpt5mini"), "moderator": MODERATOR_BASE}
        for player, model_name in zip(PLAYER_NAMES, rotated, strict=True):
            assignments[player] = with_holy_grail(model_name)
        scenarios.append(
            scenario(
                f"allstar_holy_grail_rotation_{rotation}",
                (
                    "Mixed-model table with Mafia Gemma BF16, Mafia Gemma GGUF Q8, GPT-5 medium, "
                    "GPT-5-mini, Claude Opus 4.8, Claude Sonnet 4.6, and Gemini 2.5 Pro OSV. "
                    "Every player uses Holy Grail; seats rotate across rows."
                ),
                "moderated_quality_time_to_talk",
                assignments,
                seed,
            )
        )
    return scenarios


def build() -> list[dict]:
    return [*build_pairwise(), *build_allstars()]


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"scenarios": build()}, indent=2) + "\n", encoding="utf-8")
    print(OUT)
