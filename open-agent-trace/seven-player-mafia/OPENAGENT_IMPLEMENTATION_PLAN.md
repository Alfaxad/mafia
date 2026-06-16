# OpenAgent Implementation Plan

This is the implementation plan written by OpenGame/OpenAgent before it began the seven-player Mafia prototype implementation.

## Midnight Table: Seven-Player Mafia

### Config And Registration

1. `gameConfig.json`: set `screenSize` to `1536x1024`, merge `gameplayConfig`, `dialogueConfig`, and `mafiaConfig`, while keeping `debugConfig` and `renderConfig`.
2. `main.ts`: register `RoleRevealScene`, `MainTableScene`, and `EndgameScene`.
3. `LevelManager.ts`: set `LEVEL_ORDER = ["RoleRevealScene", "MainTableScene", "EndgameScene"]`.
4. `TitleScreen.ts`: set title text to `MIDNIGHT TABLE`, use `role_reveal_bg`, and use `role_reveal_bgm`.

### Core Logic

5. Create `src/game/MafiaTypes.ts` for shared Mafia game types.
6. Create `src/game/MafiaEngine.ts` as the singleton `mafiaGame`, responsible for:
   - random role dealing,
   - per-AI suspicion model,
   - night resolution: Mafia kill, Detective investigate, Doctor protect,
   - scripted personality-driven discussion lines and evidence cards,
   - vote tally with plurality resolution and tie meaning no elimination,
   - win checks: Town wins when both Mafia are dead; Mafia wins when Mafia count is greater than or equal to Town count.

### Scenes

7. `RoleRevealScene.ts`, extending `BaseChapterScene`:
   - deals roles,
   - reveals only the human player's role,
   - reveals Mafia partner only if the human is Mafia,
   - transitions into `MainTableScene`.

8. `MainTableScene.ts`, extending `BaseBattleScene` with `useTurnCycle=false`:
   - circular seven-seat table,
   - left ledger panel for claims, votes, and deaths,
   - right chat/log panel with DOM text input and reaction buttons,
   - top phase banner, timer, and alive count,
   - bottom phase action buttons,
   - drives the `Night -> Dawn -> Discussion -> HotSeat -> Vote -> Elimination` loop,
   - preserves hidden information,
   - transitions into `EndgameScene`.

9. `EndgameScene.ts`, extending `BaseEndingScene`:
   - victory or defeat title,
   - full role reveal for all seven players,
   - match summary,
   - replay timeline,
   - transition back to `TitleScreen`.

### Verification

10. Run self-review.
11. Run `npm run build`.
12. Run `npm run test`.
13. Run `npm run dev`.

### Hidden-Information Guarantee

Seats render neutral/dead textures only. True roles are never drawn until death or endgame. Placeholder fallbacks are used for missing expression textures.

## Trace Source

The original plan is preserved in `reports/opengame_run.stream.jsonl` as the `exit_plan_mode` payload from the OpenGame/OpenAgent session.
