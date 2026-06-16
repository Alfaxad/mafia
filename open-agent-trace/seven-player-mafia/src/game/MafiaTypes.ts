/**
 * ============================================================================
 * MAFIA TYPES — Shared type definitions for Midnight Table: Seven-Player Mafia
 * ============================================================================
 * Pure data types. No Phaser dependency. Consumed by MafiaEngine and scenes.
 */

/** The four hidden roles in the game. */
export type Role = 'Mafia' | 'Detective' | 'Doctor' | 'Villager';

/** Stable identifiers for the seven seats. */
export type PlayerId =
  | 'player'
  | 'nora'
  | 'kai'
  | 'mira'
  | 'jules'
  | 'lena'
  | 'owen';

/** Faction a role belongs to. */
export type Faction = 'town' | 'mafia';

/** Phases of the day/night loop. */
export type PhaseName =
  | 'Night'
  | 'Dawn'
  | 'Discussion'
  | 'HotSeat'
  | 'Vote'
  | 'Elimination'
  | 'GameOver';

/** Winner of the match. */
export type Winner = 'town' | 'mafia' | null;

/** Static, non-secret profile information for a seat. */
export interface PlayerProfile {
  id: PlayerId;
  name: string;
  personality: string;
  /** Hex accent color, e.g. 0x6c5ce7. */
  color: number;
  /** Human-controlled seat? */
  isHuman: boolean;
  /** Texture key prefix for portraits (e.g. "nora" -> "nora_neutral"). */
  texturePrefix: string;
}

/** Mutable per-player runtime state. */
export interface PlayerState {
  id: PlayerId;
  role: Role;
  alive: boolean;
  /** Publicly claimed role, or null if never claimed. */
  claimedRole: Role | null;
  /** Day number the player died, or 0 if alive. */
  diedOnDay: number;
  /** How the player died. */
  deathCause: 'mafia' | 'vote' | null;
}

/** A kind of public evidence card created from chat lines / actions. */
export type EvidenceKind =
  | 'claim'
  | 'accusation'
  | 'defense'
  | 'alibi'
  | 'vote'
  | 'reveal';

/** A public evidence card shown in the claim ledger. */
export interface EvidenceCard {
  kind: EvidenceKind;
  /** Who produced the evidence. */
  sourceId: PlayerId;
  /** Optional target referenced by the evidence. */
  targetId?: PlayerId;
  /** Short human-readable text. */
  text: string;
  day: number;
}

/** A single public chat line. */
export interface ChatLine {
  speakerId: PlayerId | 'narrator';
  text: string;
  day: number;
  phase: PhaseName;
}

/** A public game-log (narrator) entry. */
export interface LogLine {
  text: string;
  day: number;
  phase: PhaseName;
}

/** A recorded vote in a single voting round. */
export interface VoteRecord {
  voterId: PlayerId;
  targetId: PlayerId | 'pass';
}

/** A complete day's vote tally. */
export interface VoteRound {
  day: number;
  votes: VoteRecord[];
  /** Eliminated player id, or null if no elimination (tie/all pass). */
  eliminatedId: PlayerId | null;
}

/** A death/elimination history entry. */
export interface DeathRecord {
  playerId: PlayerId;
  day: number;
  cause: 'mafia' | 'vote';
  /** Role revealed on death. */
  role: Role;
}

/** A private detective investigation result. */
export interface DetectiveResult {
  night: number;
  targetId: PlayerId;
  isMafia: boolean;
}

/** A private doctor protection record. */
export interface ProtectRecord {
  night: number;
  targetId: PlayerId;
}

/** A replay timeline entry shown in the endgame. */
export interface TimelineEntry {
  day: number;
  phase: PhaseName;
  text: string;
}

/** Result of resolving a night. */
export interface NightResult {
  /** Player killed by mafia, or null if no one died. */
  killedId: PlayerId | null;
  /** True if the mafia target was saved by the doctor. */
  savedByDoctor: boolean;
}

/** Result of resolving a day vote. */
export interface VoteResult {
  eliminatedId: PlayerId | null;
  role: Role | null;
  tie: boolean;
}

/** Pending human/AI night choices for the current night. */
export interface NightChoices {
  mafiaTarget: PlayerId | null;
  detectiveTarget: PlayerId | null;
  doctorTarget: PlayerId | null;
}
