You are continuing an already-started OpenGame project in this exact folder:
`/Users/alfaxad/Desktop/AI/Games/OpenGame/agent-test/games/seven-player-mafia-opus48`.

Do not regenerate assets. Do not regenerate the GDD. Do not call `exit_plan_mode`. Do not ask for confirmation. Implement, build, test, patch, and finish.

Current state:
- `GAME_DESIGN.md` exists and contains the target design.
- `public/assets/` already contains generated backgrounds, portraits, role cards, UI markers, and wav audio.
- `src/game/MafiaTypes.ts` already exists.
- `src/game/MafiaEngine.ts`, `src/scenes/RoleRevealScene.ts`, `src/scenes/MainTableScene.ts`, and `src/scenes/EndgameScene.ts` still need to be created.
- `src/gameConfig.json`, `src/main.ts`, `src/LevelManager.ts`, and `src/scenes/TitleScreen.ts` may already have partial updates. Audit and repair them as needed.

Implement a complete standalone seven-player Mafia game:
- 7 players: 1 human (`player`) and 6 scripted AI (`nora`, `kai`, `mira`, `jules`, `lena`, `owen`).
- Roles: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.
- Flow: Role Reveal -> Night -> Dawn -> Day Discussion -> Hot Seat -> Vote -> Elimination -> repeat -> Endgame.
- Town wins when both Mafia are dead.
- Mafia wins when living Mafia are greater than or equal to living Town.
- Preserve hidden information. The browser must not reveal true roles until legal reveal/death/endgame, except the human's own role and human Mafia partner when applicable.
- Use deterministic scripted AI: suspicion scores, short personality chat, legal night actions, legal votes, Mafia partner protection, Detective result handling, Doctor protect handling.
- Render a moody parlor table UI using Phaser primitives and generated assets:
  - circular seven-seat table
  - left claim/vote/death ledger
  - right chat/game log
  - top phase banner/alive count/timer
  - bottom phase action buttons
  - endgame role reveal and timeline

Constraints:
- Keep everything local/self-contained.
- Do not connect to external Mafia repos, Modal, Gradio, databases, or live LLMs.
- If a generated asset key is missing, use a safe fallback rather than crashing.
- Build and test before finishing. If `npm run build` fails, inspect, patch, and rerun until it passes.

Start by reading only the files you need, then write the missing files. Keep implementation concise enough to fit in tool calls; it is acceptable to implement a polished prototype rather than every optional flourish.
