Proceed with the implementation plan you just wrote. The plan is approved.

Do not call `exit_plan_mode` again. Do not ask for confirmation. Implement directly using the existing generated assets, `GAME_DESIGN.md`, and the OpenGame templates already in this workspace.

Important requirements:
- Keep this standalone. Do not wire to any external Mafia repo, Modal service, Gradio app, backend, or database.
- Use the generated `public/assets` files already present.
- Create `src/game/MafiaTypes.ts` and `src/game/MafiaEngine.ts`.
- Create `src/scenes/RoleRevealScene.ts`, `src/scenes/MainTableScene.ts`, and `src/scenes/EndgameScene.ts`.
- Update `src/gameConfig.json`, `src/main.ts`, `src/LevelManager.ts`, and `src/scenes/TitleScreen.ts`.
- Preserve hidden role information: true roles only show to the owning human player where legal, to Mafia partner only if human is Mafia, on death reveal, and in the endgame reveal.
- Implement a complete 7-player Mafia loop: role reveal, night, dawn, discussion, hot seat, vote, elimination, repeat, Town/Mafia win conditions.
- Use deterministic scripted AI personalities. Do not add real LLM calls.
- Use custom Phaser seat visuals for the 7-seat circular table if `CharacterPortrait` cannot support arbitrary x/y positioning.
- Build and test before finishing. If a build error occurs, inspect it, patch it, and rerun until the game builds successfully.
