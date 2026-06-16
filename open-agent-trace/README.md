# Open Agent Trace

This folder archives the OpenGame/OpenAgent generation inputs and output used to bootstrap the visual Mafia game prototype.

## Contents

- `seven-player-mafia/` is the renamed copy of the original OpenGame workspace `seven-player-mafia-opus48`.
- Prompt files used during generation are preserved in that folder:
  - `MAFIA_GAME_PROMPT.md`
  - `CONTINUE_IMPLEMENTATION_PROMPT.md`
  - `IMPLEMENT_NOW_PROMPT.md`
  - `.qwen/system.md`
- `GAME_DESIGN.md`, source files, generated assets, build output, and OpenGame run reports are included.

`node_modules/` is intentionally omitted. Recreate dependencies with:

```bash
cd open-agent-trace/seven-player-mafia
npm install
```

The production game in this repository is integrated separately under `src/mafia`, `frontend`, and `modal`.
