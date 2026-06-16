# Build "Midnight Table: Seven-Player Mafia"

Create a complete, polished, playable 2D web game for a standard seven-player Mafia match. This is a standalone OpenGame project. Do not connect to any external Mafia repository, Modal service, Gradio app, backend, database, or existing codebase. Build everything needed inside this project folder using the OpenGame template architecture.

## Core Game

Mafia is a social deduction party game where a hidden minority, the Mafia, tries to eliminate the larger group, the Town, while the Town tries to identify and vote out all Mafia.

Build a local playable implementation with:

- 7 players around a table.
- 1 human player and 6 simulated AI/personality-driven players.
- Roles: 2 Mafia, 1 Detective, 1 Doctor, 3 Villagers.
- Classic loop: Role Reveal -> Night -> Dawn -> Day Discussion -> Accusation / Hot Seat -> Vote -> Elimination / Reveal -> repeat.
- Win conditions:
  - Town wins when both Mafia are eliminated.
  - Mafia wins when Mafia equal or outnumber the remaining Town.

## Hidden Information Rules

The game must preserve hidden-role information:

- The human sees only their own role.
- Mafia know the other Mafia member.
- Detective privately sees investigation results.
- Doctor privately sees protection choices.
- Villagers see only public information.
- The UI must not reveal true roles until death or endgame, except to the owning player when appropriate.

## Required Roles

Mafia:
- At night, choose a player to eliminate.
- During day, pretend to be Town, mislead, accuse, defend, and vote.

Detective:
- At night, investigate one living player and learn whether that player is Mafia or not Mafia.
- During day, decide whether to reveal, hint, or keep quiet.

Doctor:
- At night, protect one living player.
- If the protected player is targeted by Mafia, the kill fails.

Villager:
- No night action.
- Uses discussion, claims, voting, and observation.

Moderator / Narrator:
- Not a player.
- Assigns roles, runs phases, announces dawn results, manages votes, and keeps the game fair.

## UI / UX Direction

Make a social deduction table, not a plain chatroom.

Main desktop layout:
- Center: a circular/parlor table with seven character seats.
- Left: claim ledger, role claims, contradiction cards, vote history, death history.
- Right: chat, game log tab, message input, quick reaction buttons.
- Bottom: phase-specific action buttons such as Ask, Accuse, Defend, Claim Role, Vote, Investigate, Protect, Kill, Pass.
- Top: current phase, timer/status, alive count, narrator cue.

The player should instantly understand:
- Who is alive.
- Who is speaking.
- Who is accused.
- Who claimed what.
- Who is voting for whom.
- What the current phase expects from them.

## Visual Style

Use a moody but readable detective-parlor style:
- Dark mystery room, warm table lighting, gold/red UI accents, readable large text.
- Stylized portraits or silhouettes for seven recurring cast members.
- Strong seat identity: each character has name, color accent, personality label, alive/dead state, vote marker, claim marker, and current speaker ring.
- Avoid role-spoiling portraits. Do not visually imply someone is Doctor, Detective, or Mafia through obvious props.

Cast names and personalities:
- You: the human player.
- Nora: calm, controlled, persuasive.
- Kai: fast-talking, jokey, overconfident.
- Mira: analytical, precise, sometimes tunnel-visioned.
- Jules: quiet vote historian, speaks late.
- Lena: emotional, loyal, easily swayed.
- Owen: procedural, skeptical, suspicious of chaos.

Roles should be randomized each new game.

## Game Flow Details

Role Reveal:
- Show the human's secret role with a short explanation.
- If human is Mafia, show the Mafia partner.

Night:
- Mafia choose a target.
- Detective chooses someone to investigate.
- Doctor chooses someone to protect.
- If human's role has no night action, show a quiet waiting/narration screen.
- Simulated AI players should make legal night choices.

Dawn:
- Announce who died or that no one died.
- Update alive/dead states and vote/death history.

Day Discussion:
- Simulated AI players post short public messages.
- Messages should create evidence cards automatically when they are claims, accusations, defenses, alibis, or vote intentions.
- Human can type a custom message or click structured actions.
- Keep AI messages short and human-like, usually 8-20 words.

Accusation / Hot Seat:
- Allow players to accuse a living player.
- Show the accused prominently at the table.
- Let human submit or choose a short final statement when accused or voting.

Vote:
- All living players vote for one living player or pass if allowed.
- Show vote arrows/tokens around the table.
- If someone receives a majority or top vote depending on your implementation, eliminate them.
- Reveal eliminated role.

Endgame:
- Show victory/defeat title.
- Reveal all roles.
- Show match summary, key votes, night actions, claims, and a replay timeline.

## Simulated AI Player Behavior

This first standalone game does not need real LLM calls. Use deterministic or lightweight scripted AI personalities that feel alive:

- Every AI should have a suspicion score for each other player.
- AI updates suspicion based on claims, votes, silence, accusations, and investigation-like public statements.
- Mafia AI should try to avoid impossible claims, redirect suspicion, and protect the Mafia partner sometimes.
- Town AI should pressure contradictions and suspicious voting patterns.
- Detective AI may reveal or hint when they find Mafia.
- Doctor AI may claim cautiously if pressured.
- AI votes should be legal and based on visible public state plus hidden role objectives.

Make the behavior understandable and fun rather than mathematically perfect.

## Required Screens / Components

Implement these as scenes/components where appropriate:

- Title / Start screen.
- Role reveal screen.
- Main table scene for night/day/vote flow.
- Claim ledger panel.
- Vote board / vote history panel.
- Chat and game log panel.
- Phase banner transitions: Night Falls, Dawn Breaks, Discussion Begins, Voting Begins, Role Revealed, Victory.
- Endgame reveal and timeline.

## Interactions

The human should be able to:

- Start a new game.
- View their private role info.
- Send chat messages.
- Ask, accuse, defend, claim role, and vote.
- Use night action buttons when their role requires it.
- Mark private suspicion/trust on other players.
- Inspect player cards.
- Review claims and vote history.
- Play the game to completion.

## Implementation Constraints

- Use the OpenGame workflow faithfully.
- The game should classify as `ui_heavy`.
- Use template classes and hooks; do not invent unavailable APIs.
- Use Phaser/TypeScript from the OpenGame templates.
- Keep everything local and self-contained.
- Generated placeholder art is acceptable if asset generation is unavailable, but the final game must still be visually coherent.
- If image generation is available, generate a parlor background, neutral portraits, role cards, and UI panels.
- Build and test before finishing.

## Quality Bar

The output should feel like a small, complete social deduction game prototype:

- Game reaches Town or Mafia win condition.
- No hidden-role leakage.
- No invalid night actions or votes.
- Clear phase transitions.
- Clear action affordances.
- Readable seven-seat table.
- Useful claim and vote history.
- Endgame reveals what happened.

Work autonomously until the game builds successfully and is playable.
