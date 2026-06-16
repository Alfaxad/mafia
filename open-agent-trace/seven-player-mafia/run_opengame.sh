#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/alfaxad/Desktop/AI/Games"
OPENGAME="$ROOT/OpenGame"
ENV_FILE="$ROOT/env.txt"
GAME_DIR="$OPENGAME/agent-test/games/seven-player-mafia-opus48"

anthropic_key="$(grep '^ANTHROPIC_KEY=' "$ENV_FILE" | sed -E 's/^ANTHROPIC_KEY=//' | sed -E 's/^"//;s/"$//')"
openai_key="$(grep '^OPEN_AI_KEY=' "$ENV_FILE" | sed -E 's/^OPEN_AI_KEY=//' | sed -E 's/^"//;s/"$//')"

export ANTHROPIC_API_KEY="$anthropic_key"
export ANTHROPIC_BASE_URL="https://api.anthropic.com"
export ANTHROPIC_MODEL="claude-opus-4-8"

export OPENGAME_REASONING_PROVIDER="openai-compat"
export OPENGAME_REASONING_API_KEY="$openai_key"
export OPENGAME_REASONING_BASE_URL="https://api.openai.com/v1"
export OPENGAME_REASONING_MODEL="gpt-5.5"

export OPENGAME_IMAGE_PROVIDER="openai-compat"
export OPENGAME_IMAGE_API_KEY="$openai_key"
export OPENGAME_IMAGE_BASE_URL="https://api.openai.com/v1"
export OPENGAME_IMAGE_MODEL="gpt-image-2"

export QWEN_SYSTEM_MD="1"
export GAME_TEMPLATES_DIR="$OPENGAME/agent-test/templates"
export GAME_DOCS_DIR="$OPENGAME/agent-test/docs"
export MODEL_REQUEST_TIMEOUT="1200000"

cd "$GAME_DIR"

node "$OPENGAME/dist/cli.js" \
  --auth-type anthropic \
  --model claude-opus-4-8 \
  --yolo \
  --output-format stream-json \
  --include-partial-messages \
  --prompt "$(cat MAFIA_GAME_PROMPT.md)"
