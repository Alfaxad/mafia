#!/usr/bin/env bash
set -euo pipefail

RUN_NAME="${1:-mafia-gemma4-12b-sft-v0}"
DEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${DEST_ROOT}/reports/modal/${RUN_NAME}"

mkdir -p "${DEST}"
modal volume get mafia-gemma4-checkpoints "/experiments/${RUN_NAME}/reports" "${DEST}/" || true
modal volume get mafia-gemma4-checkpoints "/experiments/${RUN_NAME}/config.resolved.json" "${DEST}/" || true
modal volume get mafia-gemma4-checkpoints "/experiments/${RUN_NAME}/trainer_state.json" "${DEST}/" || true

echo "Pulled Modal artifacts into ${DEST}"
