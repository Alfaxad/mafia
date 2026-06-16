# Midnight Table: Seven-Player Mafia — Game Design Document

## 0. Technical Architecture

**Archetype:** `ui_heavy`
**Game Title:** `Midnight Table: Seven-Player Mafia`
**Resolution:** `1536x1024`
**Tilemaps:** Not used.

### Base Classes Used

| Scene | Base Class | Template |
|---|---|---|
| Role Reveal | `BaseChapterScene` | `_TemplateChapter.ts` |
| Main Table Mafia Loop | `BaseBattleScene` | `_TemplateBattle.ts` |
| Endgame Reveal / Timeline | `BaseEndingScene` | `_TemplateEnding.ts` |

### Scene Flow

```text
TitleScreen -> RoleRevealScene -> MainTableScene -> EndgameScene -> TitleScreen
```

`MainTableScene` internal loop:

```text
Night -> Dawn -> Day Discussion -> Accusation / Hot Seat -> Vote -> Elimination / Reveal -> check win -> repeat
```

### `LevelManager.LEVEL_ORDER`

```json
["RoleRevealScene", "MainTableScene", "EndgameScene"]
```

### Scene Keys in `scene.start()`

| Source | Destination |
|---|---|
| `TitleScreen` | `"RoleRevealScene"` |
| `RoleRevealScene` | `"MainTableScene"` |
| `MainTableScene` | `"EndgameScene"` |
| `EndgameScene` | `"TitleScreen"` |

### Persistent Game State Keys (GameDataManager)

| Key | Purpose |
|---|---|
| `mafia.rolesByPlayerId` | Hidden role assignment for all 7 players |
| `mafia.aliveByPlayerId` | Alive/dead state |
| `mafia.playerRole` | Human player's private role |
| `mafia.humanVisibleMafiaPartnerIds` | Only populated if human is Mafia |
| `mafia.detectiveResults` | Private Detective investigation history |
| `mafia.doctorProtectHistory` | Doctor protection history |
| `mafia.claimLedger` | Public role claims by player |
| `mafia.voteHistory` | Public vote records per day |
| `mafia.deathHistory` | Death and elimination records |
| `mafia.gameLog` | Public narrator log |
| `mafia.chatLog` | Public discussion lines |
| `mafia.timeline` | Replay timeline for Endgame scene |
| `mafia.suspicionScores` | Deterministic AI suspicion table |
| `mafia.phaseName` | Current phase label |
| `mafia.dayNumber` | Current day counter |
| `mafia.nightNumber` | Current night counter |
| `mafia.lastWinner` | `"town"` or `"mafia"` |
| `mafia.lastEndingType` | `"victory"` or `"defeat"` from human perspective |

---

## 1. Visual Style & Asset Registry

**Style Anchor:** A moody 1930s detective parlor at midnight, circular mahogany table under warm amber lamplight, deep shadows, gold UI trim, blood-red Mafia accents.

> Split asset generation into multiple calls (>8 assets). Call 1: backgrounds + UI + audio. Call 2: portraits.

### Backgrounds
- `role_reveal_bg` — Dark detective parlor entrance, velvet curtains, rain-streaked windows, sealed envelope, warm lamp glow. (1536*1024)
- `main_table_bg` — Circular mahogany parlor table, seven chairs, candlelight, noir shadows, red voting tokens. (1536*1024)
- `endgame_bg` — Aftermath parlor at dawn, scattered role cards, red strings, dossiers, cold blue light. (1536*1024)

### Portraits (5 expressions each: neutral, suspicious, confident, shocked, dead)
- `player_*` — Human guest, dark formal jacket
- `nora_*` — Poised archivist, silver brooch
- `kai_*` — Quick-witted gambler, loosened tie
- `mira_*` — Soft-spoken pianist, elegant dress
- `jules_*` — Flamboyant playwright, red scarf
- `lena_*` — Retired inspector, gray coat
- `owen_*` — Nervous scholar, round glasses

### UI Images
- `table_panel`, `role_card_back`, `role_card_mafia`, `role_card_detective`, `role_card_doctor`, `role_card_villager`, `vote_marker`, `claim_marker`, `speaker_ring`, `dead_overlay`, `button_noir`

### Audio
- BGM: `role_reveal_bgm`, `main_table_bgm`, `endgame_bgm`
- SFX: `click_sfx`, `correct_sfx`, `wrong_sfx`, `damage_sfx`, `vote_sfx`, `night_sfx`, `dawn_sfx`, `victory_sfx`

---

## 2. Game Configuration

Merge into `src/gameConfig.json` (keep `screenSize`, `debugConfig`, `renderConfig`). See tool output — key blocks: `gameplayConfig`, `battleConfig` (compat), `dialogueConfig`, `mafiaConfig`.

`mafiaConfig` important values:
- `playerCount`:7, `mafiaCount`:2, `detectiveCount`:1, `doctorCount`:1, `villagerCount`:3
- `seatPositions`: 7 entries (player x768 y800; nora 455,705; kai 315,470; mira 500,255; jules 768,190; lena 1036,255; owen 1221,470)
- `leftPanel` {x24,y116,w310,h790}, `rightPanel` {x1202,y116,w310,h790}, `topBanner` {x768,y46,w920,h78}, `bottomActionPanel` {x768,y954,w1180,h100}
- Suspicion weights: `initialSuspicion`:10, silence:2, accusation:4, counterAccuse:5, voteTown:3, voteMafia:-4, contradiction:8, protectedPartner:-6, detectiveHint:6, doctorClaimRisk:5
- Thresholds: `aiConfidenceRevealThreshold`:18, `aiVoteThreshold`:14, `aiMafiaRedirectThreshold`:12
- `mafiaWinParityOffset`:0

---

## 3. Entity / Scene Architecture

### 3.1 `RoleRevealScene` (BaseChapterScene, copy `_TemplateChapter.ts`)

Hooks:
- `createBackground`: `role_reveal_bg`
- `createCharacters`: human portrait `player` with 5 expressions, center
- `createUI`: sealed `role_card_back` centered
- `getBackgroundMusicKey`: `"role_reveal_bgm"`
- `initializeDialogues`: Role Reveal script (Section 4.1)
- `onDialogueEvent`: handle `assign_roles`, `show_role_card`, `show_mafia_partner_if_applicable`, `play_sfx`, `record_timeline` — store all into GameDataManager
- `onChoiceMade`: store `role_reveal_acknowledgement` to `mafia.roleRevealChoice`
- `onChapterComplete`: start `"MainTableScene"`

Role bag: `["Mafia","Mafia","Detective","Doctor","Villager","Villager","Villager"]`
Player order before shuffle: `["player","nora","kai","mira","jules","lena","owen"]`
Hidden-info rules preserved (human sees own role; mafia sees partner; detective/doctor private).

### 3.2 `MainTableScene` (BaseBattleScene, copy `_TemplateBattle.ts`)

Used as UI-heavy state container. NO cards, NO quiz.

Hooks:
- `useTurnCycle`: `false`
- `initializeBattle`: set compat HP, load `mafia.*`; if missing redirect to RoleRevealScene; no QuizModal
- `createBackground`: `main_table_bg`
- `createCombatants`: 7 CharacterPortrait at seatPositions; overlays speaker_ring/vote_marker/claim_marker/dead_overlay
- `createHUD`: top banner, alive count, timer (StatusBar), left ledger panel, right chat/log panel, bottom action area, reaction buttons
- `getCardDeck`: `[]`; `getQuestionBank`: `[]`; `getEnemyConfig`: `undefined`
- `getBackgroundMusicKey`: `"main_table_bgm"`
- `getGameplayHints`: Section 4.6
- `onBattleStart`: Night 1, banner "Night Falls", night_sfx, render night buttons for human role
- `onPlayerTurnStart`: refresh all UI
- `onEnemyAction`/`executeEnemyTurn`: resolve scripted AI (Section 4.5), then completeEnemyTurn
- `onBattleEnd`: store winner/ending/reveals/timeline, start EndgameScene

Phase action buttons:
| Phase | Role | Buttons |
|---|---|---|
| Night | Mafia | Kill, Pass |
| Night | Detective | Investigate, Pass |
| Night | Doctor | Protect, Pass |
| Night | Villager | Pass |
| Dawn | Any | Continue |
| Discussion | Any | Ask, Accuse, Defend, Claim Role, Pass |
| Hot Seat (accused) | Any | Defend, Claim Role, Accuse, Pass |
| Hot Seat (other) | Any | Ask, Accuse, Pass |
| Vote | Any | Vote, Pass |
| Elimination | Any | Continue |

Win conditions (checked after each night kill and vote):
- Town: both Mafia dead
- Mafia: alive Mafia >= alive Town
Ending type from human perspective: win if human's faction wins.

### 3.3 `EndgameScene` (BaseEndingScene, copy `_TemplateEnding.ts`)

Hooks:
- `createBackground`: `endgame_bg`
- `getEndingData`: read `mafia.lastEndingType`/`mafia.lastWinner`
  - victory: title "The Table Has Spoken", desc "You survived the midnight game and uncovered the truth hidden beneath the candlelight."
  - defeat: title "Midnight Belongs to the Guilty", desc "The parlor falls silent as the wrong names are buried and the guilty inherit the table."
- `createEndingContent`: winner banner, 7 portraits, full role reveal, final alive/dead, match summary
- `showResults`: day/night counts, Mafia/Town eliminated, vote history, death history, timeline
- `getEndingMusicKey`: `"endgame_bgm"`
- `onContinue`: start `"TitleScreen"`

---

## 4. Content Design

No tilemap.

### 4.1 Role Reveal Dialogue Script
Narrator intro (2 lines) -> play_sfx click -> assign_roles event -> "A sealed card waits" -> show_role_card -> wait 900 -> branch on playerRole (Mafia/Detective/Doctor/Villager flavor) -> choice `role_reveal_acknowledgement` (Observe silently / Prepare to lead / Watch for contradictions) -> record_timeline -> "The lamps dim. The first night begins." -> play_sfx night.

### 4.2 Character Profiles
| id | name | personality | color | side seat |
|---|---|---|---|---|
| player | You | human guest | deep red | center |
| nora | Nora | methodical archivist, tracks claims/votes | indigo | left |
| kai | Kai | charming gambler, redirects/jokes | gold | left |
| mira | Mira | cautious pianist, emotional reads | violet | left |
| jules | Jules | dramatic playwright, loud claims | crimson | right |
| lena | Lena | retired inspector, direct pressure | steel blue | right |
| owen | Owen | nervous scholar, remembers details | green | right |

### 4.5 Deterministic Scripted AI Design
No LLM. Table-driven logic inside MainTableScene hooks.

**Suspicion model:** each AI keeps `suspicion[targetId]`. Updated by events:
- silence (no claim/action during discussion): +silenceWeight to that player
- accusation: accuser raises +accusationWeight on accused
- counter-accuse (defending by accusing accuser): +counterAccuseWeight
- voting out a confirmed Town (post-reveal): +voteTownWeight on voter
- voting out Mafia: voteMafiaWeight (negative) on voter
- contradicted claim (two players claim same unique role): +contradictionWeight on both
- detective public guilty hint: +detectiveHintWeight on hinted target

**Night actions:**
- Mafia AI: pick highest-suspicion living non-Mafia target (avoid partner via protectedPartnerWeight); the two mafia coordinate on one target.
- Detective AI: investigate highest-suspicion living unknown player; store private result.
- Doctor AI: protect likely-town high-value player (self or last-accused town), cannot repeat same target consecutive nights.

**Day discussion (max `maxDiscussionLinesPerAI` lines each):** AI emits short 8-20 word lines from personality templates. Lines create evidence cards (claim/accusation/defense/alibi/vote-intent) appended to claim ledger.
- Town AI: pressure highest-suspicion player, point out contradictions/silence.
- Mafia AI: redirect onto a town target when own suspicion > `aiMafiaRedirectThreshold`; sometimes softly defend partner.
- Detective AI: if found Mafia and suspicion gap > `aiConfidenceRevealThreshold`, reveal/hint.
- Doctor AI: claim cautiously only when heavily pressured.

**Voting:** each AI votes for living player with highest suspicion above `aiVoteThreshold`, else Pass. Mafia AI never votes partner; pushes town target. Human votes via UI. Plurality top vote eliminated; tie = no elimination.

### 4.6 Gameplay Hints (getGameplayHints)
- "Watch who stays silent — silence draws suspicion."
- "Claims can be checked. Two Detectives means one is lying."
- "Vote patterns reveal hidden alliances."
- "Protect yourself by reading the room, not just the cards."
- "The Mafia win by blending in. Find the cracks."

---

## 5. Implementation Roadmap

1. MERGE `src/gameConfig.json` (+gameplayConfig, battleConfig compat, dialogueConfig, mafiaConfig)
2. CREATE `src/game/MafiaTypes.ts` — shared types (Role, PlayerId, PhaseName, evidence cards, state interfaces)
3. CREATE `src/game/MafiaEngine.ts` — pure logic: role dealing/shuffle, suspicion model, night resolution, AI chat lines, vote tally, win check
4. UPDATE `src/LevelManager.ts` — LEVEL_ORDER
5. UPDATE `src/main.ts` — register RoleRevealScene, MainTableScene, EndgameScene
6. UPDATE `src/scenes/TitleScreen.ts` — title text + bg
7. COPY `_TemplateChapter.ts` -> `src/scenes/RoleRevealScene.ts`
8. COPY `_TemplateBattle.ts` -> `src/scenes/MainTableScene.ts` (table UI + phase loop)
9. COPY `_TemplateEnding.ts` -> `src/scenes/EndgameScene.ts`
10. Fix asset-pack.json title_bg
11. VERIFY: self-review, npm run build, npm run test, npm run dev
