/**
 * ============================================================================
 * MAFIA ENGINE — Pure deterministic game logic for Seven-Player Mafia
 * ============================================================================
 * No Phaser dependency. Fully testable. Holds the authoritative match state.
 * A module-level singleton (getEngine / newEngine) is shared across scenes.
 */

import type {
  Role,
  PlayerId,
  Faction,
  PhaseName,
  Winner,
  PlayerProfile,
  PlayerState,
  EvidenceCard,
  ChatLine,
  LogLine,
  VoteRecord,
  VoteRound,
  DeathRecord,
  DetectiveResult,
  ProtectRecord,
  TimelineEntry,
  NightResult,
  VoteResult,
  NightChoices,
} from './MafiaTypes';

// ---------------------------------------------------------------------------
// Static profiles (non-secret)
// ---------------------------------------------------------------------------

export const PLAYER_ORDER: PlayerId[] = [
  'player',
  'nora',
  'kai',
  'mira',
  'jules',
  'lena',
  'owen',
];

export const PROFILES: Record<PlayerId, PlayerProfile> = {
  player: { id: 'player', name: 'You', personality: 'human guest', color: 0xb8443c, isHuman: true, texturePrefix: 'player' },
  nora: { id: 'nora', name: 'Nora', personality: 'methodical archivist', color: 0x6c5ce7, isHuman: false, texturePrefix: 'nora' },
  kai: { id: 'kai', name: 'Kai', personality: 'charming gambler', color: 0xe8c87a, isHuman: false, texturePrefix: 'kai' },
  mira: { id: 'mira', name: 'Mira', personality: 'cautious pianist', color: 0xa55eea, isHuman: false, texturePrefix: 'mira' },
  jules: { id: 'jules', name: 'Jules', personality: 'dramatic playwright', color: 0xd63031, isHuman: false, texturePrefix: 'jules' },
  lena: { id: 'lena', name: 'Lena', personality: 'retired inspector', color: 0x4a7ba6, isHuman: false, texturePrefix: 'lena' },
  owen: { id: 'owen', name: 'Owen', personality: 'nervous scholar', color: 0x4caf50, isHuman: false, texturePrefix: 'owen' },
};

const ROLE_BAG: Role[] = [
  'Mafia',
  'Mafia',
  'Detective',
  'Doctor',
  'Villager',
  'Villager',
  'Villager',
];

export function factionOf(role: Role): Faction {
  return role === 'Mafia' ? 'mafia' : 'town';
}

// ---------------------------------------------------------------------------
// Deterministic RNG (mulberry32)
// ---------------------------------------------------------------------------

function makeRng(seed: number): () => number {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Tunable weights (mirror gameConfig.mafiaConfig defaults).
interface Weights {
  initial: number;
  silence: number;
  accusation: number;
  counterAccuse: number;
  voteTown: number;
  voteMafia: number;
  contradiction: number;
  protectedPartner: number;
  detectiveHint: number;
  revealThreshold: number;
  voteThreshold: number;
  redirectThreshold: number;
  maxLines: number;
}

const DEFAULT_WEIGHTS: Weights = {
  initial: 10,
  silence: 2,
  accusation: 4,
  counterAccuse: 5,
  voteTown: 3,
  voteMafia: -4,
  contradiction: 8,
  protectedPartner: 6,
  detectiveHint: 6,
  revealThreshold: 18,
  voteThreshold: 14,
  redirectThreshold: 12,
  maxLines: 2,
};

// ---------------------------------------------------------------------------
// Engine
// ---------------------------------------------------------------------------

export class MafiaEngine {
  readonly profiles = PROFILES;
  players: Record<PlayerId, PlayerState>;
  suspicion: Record<PlayerId, Record<PlayerId, number>> = {} as any;

  phase: PhaseName = 'Night';
  dayNumber = 0;
  nightNumber = 0;
  winner: Winner = null;

  humanMafiaPartnerIds: PlayerId[] = [];
  detectiveResults: DetectiveResult[] = [];
  doctorProtectHistory: ProtectRecord[] = [];
  claimLedger: EvidenceCard[] = [];
  voteHistory: VoteRound[] = [];
  deathHistory: DeathRecord[] = [];
  gameLog: LogLine[] = [];
  chatLog: ChatLine[] = [];
  timeline: TimelineEntry[] = [];

  private rng: () => number;
  private weights: Weights;

  constructor(seed: number = Date.now(), weights: Partial<Weights> = {}) {
    this.rng = makeRng(seed);
    this.weights = { ...DEFAULT_WEIGHTS, ...weights };
    this.players = {} as any;
  }

  // ---- Setup --------------------------------------------------------------

  dealRoles(): void {
    const bag = [...ROLE_BAG];
    // Fisher-Yates with deterministic rng
    for (let i = bag.length - 1; i > 0; i--) {
      const j = Math.floor(this.rng() * (i + 1));
      [bag[i], bag[j]] = [bag[j], bag[i]];
    }
    PLAYER_ORDER.forEach((id, idx) => {
      this.players[id] = {
        id,
        role: bag[idx],
        alive: true,
        claimedRole: null,
        diedOnDay: 0,
        deathCause: null,
      };
    });

    // Initialize suspicion tables (per AI viewer toward every other player)
    PLAYER_ORDER.forEach((viewer) => {
      this.suspicion[viewer] = {} as any;
      PLAYER_ORDER.forEach((target) => {
        if (target !== viewer) this.suspicion[viewer][target] = this.weights.initial;
      });
    });

    // Human Mafia partner visibility
    const mafiaIds = this.getMafiaIds();
    if (this.players.player.role === 'Mafia') {
      this.humanMafiaPartnerIds = mafiaIds.filter((id) => id !== 'player');
    }
  }

  // ---- Queries ------------------------------------------------------------

  get humanRole(): Role {
    return this.players.player.role;
  }
  get humanFaction(): Faction {
    return factionOf(this.humanRole);
  }
  list(): PlayerState[] {
    return PLAYER_ORDER.map((id) => this.players[id]);
  }
  living(): PlayerState[] {
    return this.list().filter((p) => p.alive);
  }
  livingIds(): PlayerId[] {
    return this.living().map((p) => p.id);
  }
  getMafiaIds(): PlayerId[] {
    return this.list().filter((p) => p.role === 'Mafia').map((p) => p.id);
  }
  livingMafia(): PlayerState[] {
    return this.living().filter((p) => p.role === 'Mafia');
  }
  livingTown(): PlayerState[] {
    return this.living().filter((p) => p.role !== 'Mafia');
  }
  livingAIIds(): PlayerId[] {
    return this.livingIds().filter((id) => id !== 'player');
  }

  // ---- Suspicion helpers --------------------------------------------------

  private addSuspicion(viewer: PlayerId, target: PlayerId, amt: number): void {
    if (viewer === target) return;
    if (!this.suspicion[viewer]) return;
    const cur = this.suspicion[viewer][target] ?? this.weights.initial;
    this.suspicion[viewer][target] = Math.max(0, cur + amt);
  }

  /** Bump suspicion of `target` for every living viewer except the target. */
  private bumpRoom(target: PlayerId, amt: number, except?: PlayerId): void {
    this.livingIds().forEach((viewer) => {
      if (viewer === target || viewer === except) return;
      this.addSuspicion(viewer, target, amt);
    });
  }

  /** Aggregate suspicion that all living AI hold toward a target. */
  roomSuspicion(target: PlayerId): number {
    return this.livingAIIds().reduce(
      (sum, viewer) => sum + (viewer === target ? 0 : this.suspicion[viewer]?.[target] ?? 0),
      0,
    );
  }

  // ---- Night --------------------------------------------------------------

  beginNight(): void {
    this.nightNumber += 1;
    this.phase = 'Night';
    this.pushLog(`Night ${this.nightNumber} falls. The town sleeps.`);
  }

  /** AI mafia consensus target (highest room-suspicion living town). */
  aiMafiaTarget(): PlayerId | null {
    const candidates = this.livingTown();
    if (candidates.length === 0) return null;
    return this.argMax(candidates.map((p) => p.id), (id) => this.roomSuspicion(id));
  }

  /** AI detective target (highest suspicion living, not yet investigated). */
  aiDetectiveTarget(detId: PlayerId): PlayerId | null {
    const done = new Set(this.detectiveResults.map((r) => r.targetId));
    const candidates = this.livingIds().filter((id) => id !== detId && !done.has(id));
    if (candidates.length === 0) return null;
    return this.argMax(candidates, (id) => this.suspicion[detId]?.[id] ?? 0);
  }

  /** AI doctor target (protect self, or last-accused town; no repeat). */
  aiDoctorTarget(docId: PlayerId): PlayerId | null {
    const last = this.doctorProtectHistory[this.doctorProtectHistory.length - 1];
    const lastTarget = last ? last.targetId : null;
    const lastAccused = this.lastAccusedTarget();
    const prefer: (PlayerId | null)[] = [lastAccused, docId];
    for (const cand of prefer) {
      if (cand && cand !== lastTarget && this.players[cand].alive) return cand;
    }
    const fallback = this.livingIds().filter((id) => id !== lastTarget);
    return fallback.length ? fallback[0] : docId;
  }

  /** Resolve the night given finalized choices. Records death + checks win. */
  resolveNight(choices: NightChoices): NightResult {
    if (choices.detectiveTarget) {
      const isMafia = this.players[choices.detectiveTarget].role === 'Mafia';
      this.detectiveResults.push({
        night: this.nightNumber,
        targetId: choices.detectiveTarget,
        isMafia,
      });
      // Detective grows private suspicion based on result.
      const detId = this.findRoleHolder('Detective');
      if (detId) this.addSuspicion(detId, choices.detectiveTarget, isMafia ? 40 : -8);
    }
    if (choices.doctorTarget) {
      this.doctorProtectHistory.push({ night: this.nightNumber, targetId: choices.doctorTarget });
    }

    let killedId: PlayerId | null = null;
    let savedByDoctor = false;
    if (choices.mafiaTarget) {
      if (choices.doctorTarget === choices.mafiaTarget) {
        savedByDoctor = true;
      } else {
        killedId = choices.mafiaTarget;
        this.killPlayer(killedId, 'mafia');
      }
    }
    this.checkWin();
    return { killedId, savedByDoctor };
  }

  // ---- Dawn / Discussion --------------------------------------------------

  beginDay(): void {
    this.dayNumber += 1;
    this.phase = 'Discussion';
  }

  /**
   * Generate deterministic AI discussion lines and evidence cards.
   * Returns the produced chat lines (also appended to chatLog).
   */
  generateDiscussion(): ChatLine[] {
    const produced: ChatLine[] = [];
    const speakers = this.livingAIIds();

    // First pass: confident detective hint (if any AI detective found mafia).
    const detId = this.findRoleHolder('Detective');
    if (detId && detId !== 'player' && this.players[detId].alive) {
      const found = this.detectiveResults.find(
        (r) => r.isMafia && this.players[r.targetId].alive,
      );
      if (found) {
        const gap = (this.suspicion[detId]?.[found.targetId] ?? 0) - this.weights.initial;
        if (gap > this.weights.revealThreshold) {
          const t = this.profiles[found.targetId].name;
          const line = this.line(detId, 'Discussion', `I investigated ${t}. I'm certain — that's our Mafia.`);
          produced.push(line);
          this.addEvidence('accusation', detId, found.targetId, `${this.profiles[detId].name} claims Detective on ${t}`);
          this.bumpRoom(found.targetId, this.weights.detectiveHint * 3, detId);
        }
      }
    }

    for (const sid of speakers) {
      const self = this.players[sid];
      const isMafia = self.role === 'Mafia';
      let target: PlayerId | null;

      if (isMafia) {
        // Mafia redirect onto highest-suspicion town when feeling heat.
        const heat = this.roomSuspicion(sid);
        if (heat > this.weights.redirectThreshold * (this.livingAIIds().length - 1)) {
          target = this.argMax(
            this.livingTown().map((p) => p.id).filter((id) => id !== sid),
            (id) => this.suspicion[sid]?.[id] ?? 0,
          );
        } else {
          target = this.aiTopSuspect(sid, true);
        }
        // Softly avoid accusing partner.
        const partner = this.getMafiaIds().find((id) => id !== sid);
        if (target === partner) target = this.aiTopSuspect(sid, true, partner ?? undefined);
      } else {
        target = this.aiTopSuspect(sid, false);
      }

      if (!target) continue;
      const text = this.chatTemplate(sid, target);
      const cl = this.line(sid, 'Discussion', text);
      produced.push(cl);
      this.addEvidence('accusation', sid, target, `${this.profiles[sid].name} suspects ${this.profiles[target].name}`);
      this.bumpRoom(target, this.weights.accusation, sid);
      // Counter-accuse: accused's own table rises toward the accuser.
      if (this.players[target].alive && target !== 'player') {
        this.addSuspicion(target, sid, this.weights.counterAccuse);
      }
    }
    return produced;
  }

  /** Player makes a public claim of a role. */
  recordClaim(speaker: PlayerId, role: Role): void {
    this.players[speaker].claimedRole = role;
    this.addEvidence('claim', speaker, undefined, `${this.profiles[speaker].name} claims ${role}`);
    // Contradiction: two players claim the same unique role.
    const dupes = this.list().filter((p) => p.claimedRole === role && role !== 'Villager');
    if (dupes.length >= 2) {
      dupes.forEach((p) => this.bumpRoom(p.id, this.weights.contradiction));
    }
  }

  /** Player accuses another publicly. */
  recordAccusation(speaker: PlayerId, target: PlayerId): void {
    this.addEvidence('accusation', speaker, target, `${this.profiles[speaker].name} accuses ${this.profiles[target].name}`);
    this.bumpRoom(target, this.weights.accusation, speaker);
  }

  recordDefense(speaker: PlayerId): void {
    this.addEvidence('defense', speaker, undefined, `${this.profiles[speaker].name} defends themselves`);
    this.bumpRoom(speaker, -this.weights.accusation);
  }

  // ---- Vote ---------------------------------------------------------------

  beginVote(): void {
    this.phase = 'Vote';
  }

  /** Deterministic AI votes (excludes human). */
  computeAIVotes(): VoteRecord[] {
    return this.livingAIIds().map((sid) => {
      const self = this.players[sid];
      const isMafia = self.role === 'Mafia';
      const partner = isMafia ? this.getMafiaIds().find((id) => id !== sid) : undefined;
      const target = this.aiTopSuspect(sid, isMafia, partner ?? undefined);
      if (!target) return { voterId: sid, targetId: 'pass' as const };
      const score = this.suspicion[sid]?.[target] ?? 0;
      if (score < this.weights.voteThreshold) return { voterId: sid, targetId: 'pass' as const };
      return { voterId: sid, targetId: target };
    });
  }

  /** Tally all votes (human + AI). Plurality wins; tie = no elimination. */
  tallyVotes(votes: VoteRecord[]): VoteResult {
    const counts = new Map<PlayerId, number>();
    votes.forEach((v) => {
      if (v.targetId === 'pass') return;
      counts.set(v.targetId, (counts.get(v.targetId) ?? 0) + 1);
    });
    let top: PlayerId | null = null;
    let max = 0;
    let tie = false;
    counts.forEach((c, id) => {
      if (c > max) {
        max = c;
        top = id;
        tie = false;
      } else if (c === max) {
        tie = true;
      }
    });

    const round: VoteRound = {
      day: this.dayNumber,
      votes,
      eliminatedId: tie || !top ? null : top,
    };
    this.voteHistory.push(round);

    votes.forEach((v) => {
      if (v.targetId === 'pass') return;
      this.addEvidence('vote', v.voterId, v.targetId, `${this.profiles[v.voterId].name} votes ${this.profiles[v.targetId].name}`);
    });

    if (tie || !top) {
      this.pushLog(`The vote is deadlocked. No one is eliminated on Day ${this.dayNumber}.`);
      return { eliminatedId: null, role: null, tie: true };
    }
    const role = this.players[top].role;
    this.killPlayer(top, 'vote');
    this.checkWin();
    return { eliminatedId: top, role, tie: false };
  }

  // ---- Death / Win --------------------------------------------------------

  private killPlayer(id: PlayerId, cause: 'mafia' | 'vote'): void {
    const p = this.players[id];
    if (!p.alive) return;
    p.alive = false;
    p.diedOnDay = this.dayNumber;
    p.deathCause = cause;
    this.deathHistory.push({ playerId: id, day: this.dayNumber, cause, role: p.role });
    const how = cause === 'mafia' ? 'found dead at dawn' : 'voted out by the table';
    this.pushTimeline(this.phase, `${this.profiles[id].name} (${p.role}) was ${how}.`);
  }

  checkWin(): Winner {
    const mafia = this.livingMafia().length;
    const town = this.livingTown().length;
    if (mafia === 0) this.winner = 'town';
    else if (mafia >= town) this.winner = 'mafia';
    else this.winner = null;
    if (this.winner) this.phase = 'GameOver';
    return this.winner;
  }

  get endingType(): 'victory' | 'defeat' {
    return this.winner === this.humanFaction ? 'victory' : 'defeat';
  }

  // ---- Logging helpers ----------------------------------------------------

  pushLog(text: string): void {
    this.gameLog.push({ text, day: this.dayNumber, phase: this.phase });
  }
  pushTimeline(phase: PhaseName, text: string): void {
    this.timeline.push({ day: this.dayNumber, phase, text });
  }
  line(speakerId: PlayerId, phase: PhaseName, text: string): ChatLine {
    const cl: ChatLine = { speakerId, text, day: this.dayNumber, phase };
    this.chatLog.push(cl);
    return cl;
  }
  private addEvidence(
    kind: EvidenceCard['kind'],
    sourceId: PlayerId,
    targetId: PlayerId | undefined,
    text: string,
  ): void {
    this.claimLedger.push({ kind, sourceId, targetId, text, day: this.dayNumber });
  }

  // ---- Internal utilities -------------------------------------------------

  private findRoleHolder(role: Role): PlayerId | null {
    const p = this.list().find((x) => x.role === role);
    return p ? p.id : null;
  }

  private lastAccusedTarget(): PlayerId | null {
    for (let i = this.claimLedger.length - 1; i >= 0; i--) {
      const e = this.claimLedger[i];
      if (e.kind === 'accusation' && e.targetId && this.players[e.targetId].alive) {
        return e.targetId;
      }
    }
    return null;
  }

  private aiTopSuspect(
    viewer: PlayerId,
    isMafia: boolean,
    avoid?: PlayerId,
  ): PlayerId | null {
    const table = this.suspicion[viewer] ?? {};
    const candidates = this.livingIds().filter((id) => {
      if (id === viewer) return false;
      if (avoid && id === avoid) return false;
      if (isMafia && this.players[id].role === 'Mafia') return false; // never target own faction
      return true;
    });
    if (candidates.length === 0) return null;
    return this.argMax(candidates, (id) => table[id] ?? 0);
  }

  private argMax(ids: PlayerId[], score: (id: PlayerId) => number): PlayerId | null {
    let best: PlayerId | null = null;
    let bestScore = -Infinity;
    for (const id of ids) {
      const s = score(id);
      if (s > bestScore) {
        bestScore = s;
        best = id;
      }
    }
    return best;
  }

  // ---- AI chat templates --------------------------------------------------

  private chatTemplate(speaker: PlayerId, target: PlayerId): string {
    const t = this.profiles[target].name;
    const byPersonality: Record<PlayerId, string[]> = {
      player: [`I have my eyes on ${t}.`],
      nora: [
        `Look at the record — ${t}'s story doesn't line up.`,
        `${t} has dodged every direct question. That's a pattern.`,
      ],
      kai: [
        `No offense ${t}, but you're sweating for a reason.`,
        `I'd bet my last chip on ${t} being dirty.`,
      ],
      mira: [
        `Something about ${t} feels wrong to me tonight.`,
        `I keep watching ${t}'s hands. They won't stay still.`,
      ],
      jules: [
        `The villain reveals themselves — and it is ${t}!`,
        `Mark my words, ${t} is performing innocence.`,
      ],
      lena: [
        `Cut the theatrics. ${t}, where were you?`,
        `In my experience, quiet ones like ${t} hide the most.`,
      ],
      owen: [
        `Um — earlier ${t} said something that contradicts now.`,
        `I-I think we should look harder at ${t}.`,
      ],
    };
    const pool = byPersonality[speaker] ?? [`I suspect ${t}.`];
    const idx = Math.floor(this.rng() * pool.length);
    return pool[idx];
  }

  // ---- Persistence snapshot (for debugging / ending) ----------------------

  snapshot() {
    return {
      players: this.players,
      winner: this.winner,
      dayNumber: this.dayNumber,
      nightNumber: this.nightNumber,
      deathHistory: this.deathHistory,
      voteHistory: this.voteHistory,
      timeline: this.timeline,
    };
  }
}

// ---------------------------------------------------------------------------
// Module-level singleton shared across scenes
// ---------------------------------------------------------------------------

let activeEngine: MafiaEngine | null = null;

export function newEngine(seed?: number): MafiaEngine {
  activeEngine = new MafiaEngine(seed ?? Date.now());
  activeEngine.dealRoles();
  return activeEngine;
}

export function getEngine(): MafiaEngine | null {
  return activeEngine;
}

export function setEngine(engine: MafiaEngine | null): void {
  activeEngine = engine;
}
