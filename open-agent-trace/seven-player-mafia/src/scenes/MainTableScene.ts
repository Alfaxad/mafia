import Phaser from 'phaser';
import { getEngine, newEngine, PLAYER_ORDER } from '../game/MafiaEngine';
import type { MafiaEngine } from '../game/MafiaEngine';
import type { PlayerId, Role, VoteRecord, NightChoices } from '../game/MafiaTypes';
import * as utils from '../utils';

interface Seat {
  id: PlayerId;
  x: number;
  y: number;
  container: Phaser.GameObjects.Container;
  portrait: Phaser.GameObjects.Image | Phaser.GameObjects.Rectangle;
  nameText: Phaser.GameObjects.Text;
  ring?: Phaser.GameObjects.Image | Phaser.GameObjects.Arc;
  voteBadge?: Phaser.GameObjects.Text;
  deadOverlay?: Phaser.GameObjects.GameObject;
}

const SEAT_POS: Record<PlayerId, { x: number; y: number }> = {
  player: { x: 768, y: 800 },
  nora: { x: 455, y: 705 },
  kai: { x: 315, y: 470 },
  mira: { x: 500, y: 255 },
  jules: { x: 768, y: 190 },
  lena: { x: 1036, y: 255 },
  owen: { x: 1221, y: 470 },
};

export class MainTableScene extends Phaser.Scene {
  private engine!: MafiaEngine;
  private bgm?: Phaser.Sound.BaseSound;

  private seats: Record<PlayerId, Seat> = {} as any;
  private bannerText!: Phaser.GameObjects.Text;
  private aliveText!: Phaser.GameObjects.Text;
  private ledgerText!: Phaser.GameObjects.Text;
  private chatText!: Phaser.GameObjects.Text;
  private actionButtons: Phaser.GameObjects.Container[] = [];
  private busy = false;

  // pending night decision storage
  private pendingNight: NightChoices = { mafiaTarget: null, detectiveTarget: null, doctorTarget: null };

  constructor() {
    super({ key: 'MainTableScene' });
  }

  create(): void {
    let e = getEngine();
    if (!e) {
      // Safety fallback: if engine missing, create one and warn.
      e = newEngine();
    }
    this.engine = e;
    this.busy = false;
    this.seats = {} as any;
    this.actionButtons = [];

    this.createBackground();
    this.createTable();
    this.createSeats();
    this.createHUD();
    this.playMusic();

    this.cameras.main.fadeIn(450, 0, 0, 0);
    this.events.once('shutdown', () => this.bgm?.stop());

    this.time.delayedCall(500, () => this.enterNight());
  }

  // ---- Construction -------------------------------------------------------

  private createBackground(): void {
    const cam = this.cameras.main;
    if (utils.textureExists(this, 'main_table_bg')) {
      const bg = this.add.image(cam.width / 2, cam.height / 2, 'main_table_bg');
      bg.setDisplaySize(cam.width, cam.height);
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x000000, 0.25);
    } else {
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x1a1320, 1);
    }
  }

  private createTable(): void {
    // Circular table centroid
    const cx = 768;
    const cy = 470;
    this.add.ellipse(cx, cy, 560, 430, 0x3a2418, 0.55).setStrokeStyle(6, 0x6b5326, 0.8);
    this.add.ellipse(cx, cy, 470, 350, 0x4a2f1d, 0.5);
  }

  private createSeats(): void {
    PLAYER_ORDER.forEach((id) => {
      const pos = SEAT_POS[id];
      const prof = this.engine.profiles[id];
      const container = this.add.container(pos.x, pos.y);

      // speaker ring (hidden by default)
      let ring: Phaser.GameObjects.Image | Phaser.GameObjects.Arc;
      if (utils.textureExists(this, 'speaker_ring')) {
        const r = this.add.image(0, 0, 'speaker_ring');
        r.setScale(150 / r.height);
        ring = r;
      } else {
        ring = this.add.circle(0, 0, 80, 0xe8c87a, 0).setStrokeStyle(4, 0xe8c87a);
      }
      ring.setVisible(false);
      container.add(ring);

      // portrait
      const key = `${prof.texturePrefix}_neutral`;
      let portrait: Phaser.GameObjects.Image | Phaser.GameObjects.Rectangle;
      if (utils.textureExists(this, key)) {
        const img = this.add.image(0, 0, key);
        img.setScale(Math.min(140 / img.height, 140 / img.width));
        portrait = img;
      } else {
        portrait = this.add.rectangle(0, 0, 110, 130, prof.color, 0.85).setStrokeStyle(3, 0xffffff, 0.4);
      }
      container.add(portrait);

      // name plate
      const nameText = this.add
        .text(0, 78, prof.name, {
          fontFamily: 'monospace',
          fontSize: '18px',
          color: '#e8dcc0',
          stroke: '#000',
          strokeThickness: 3,
        })
        .setOrigin(0.5);
      container.add(nameText);

      // vote badge
      const voteBadge = this.add
        .text(46, -60, '', {
          fontFamily: 'monospace',
          fontSize: '16px',
          color: '#eb5757',
          stroke: '#000',
          strokeThickness: 3,
        })
        .setOrigin(0.5);
      container.add(voteBadge);

      this.seats[id] = { id, x: pos.x, y: pos.y, container, portrait, nameText, ring, voteBadge };
    });
  }

  private createHUD(): void {
    // Top banner
    this.add.rectangle(768, 46, 920, 78, 0x0c0a12, 0.82).setStrokeStyle(2, 0x6b5326);
    this.bannerText = this.add
      .text(768, 36, '', {
        fontFamily: 'monospace',
        fontSize: '26px',
        color: '#e8c87a',
        stroke: '#000',
        strokeThickness: 4,
      })
      .setOrigin(0.5);
    this.aliveText = this.add
      .text(768, 64, '', {
        fontFamily: 'monospace',
        fontSize: '15px',
        color: '#d6d2c4',
      })
      .setOrigin(0.5);

    // Left ledger panel
    this.add.rectangle(24 + 155, 116 + 395, 310, 790, 0x0c0a12, 0.78).setStrokeStyle(2, 0x6b5326);
    this.add
      .text(24 + 12, 116 + 10, 'CLAIM / VOTE LEDGER', {
        fontFamily: 'monospace',
        fontSize: '15px',
        color: '#b8443c',
        stroke: '#000',
        strokeThickness: 3,
      });
    this.ledgerText = this.add.text(24 + 12, 116 + 40, '', {
      fontFamily: 'monospace',
      fontSize: '13px',
      color: '#d6d2c4',
      lineSpacing: 4,
      wordWrap: { width: 286 },
    });

    // Right chat/log panel
    this.add.rectangle(1202 + 155, 116 + 395, 310, 790, 0x0c0a12, 0.78).setStrokeStyle(2, 0x6b5326);
    this.add
      .text(1202 + 12, 116 + 10, 'TABLE TALK', {
        fontFamily: 'monospace',
        fontSize: '15px',
        color: '#b8443c',
        stroke: '#000',
        strokeThickness: 3,
      });
    this.chatText = this.add.text(1202 + 12, 116 + 40, '', {
      fontFamily: 'monospace',
      fontSize: '13px',
      color: '#d6d2c4',
      lineSpacing: 4,
      wordWrap: { width: 286 },
    });

    this.refreshHUD();
  }

  private playMusic(): void {
    this.bgm = utils.safeAddSound(this, 'main_table_bgm', { volume: 0.28, loop: true });
    this.bgm?.play();
  }

  // ---- HUD refresh --------------------------------------------------------

  private refreshHUD(): void {
    const e = this.engine;
    this.aliveText.setText(
      `Alive: ${e.living().length}/7   \u2022   Mafia remain: ${e.livingMafia().length}   \u2022   Day ${e.dayNumber} / Night ${e.nightNumber}`,
    );

    // Ledger: recent evidence
    const recent = e.claimLedger.slice(-14);
    this.ledgerText.setText(recent.map((c) => `\u2022 ${c.text}`).join('\n'));

    // Chat: recent lines (show speaker name)
    const lines = e.chatLog.slice(-16);
    this.chatText.setText(
      lines
        .map((l) => {
          const who = l.speakerId === 'narrator' ? '\u2014' : e.profiles[l.speakerId as PlayerId].name;
          return `${who}: ${l.text}`;
        })
        .join('\n'),
    );

    // Seat states
    PLAYER_ORDER.forEach((id) => {
      const seat = this.seats[id];
      const p = e.players[id];
      if (!p.alive && !seat.deadOverlay) {
        this.markDead(seat);
      }
    });
  }

  private markDead(seat: Seat): void {
    const prof = this.engine.profiles[seat.id];
    const deadKey = `${prof.texturePrefix}_dead`;
    if (seat.portrait instanceof Phaser.GameObjects.Image && utils.textureExists(this, deadKey)) {
      seat.portrait.setTexture(deadKey);
    } else if (seat.portrait instanceof Phaser.GameObjects.Image) {
      seat.portrait.setTint(0x556);
    }
    if (utils.textureExists(this, 'dead_overlay')) {
      const ov = this.add.image(0, 0, 'dead_overlay');
      ov.setScale(140 / ov.height);
      ov.setAlpha(0.85);
      seat.container.add(ov);
      seat.deadOverlay = ov;
    } else {
      const x = this.add.text(0, 0, '\u2620', { fontSize: '60px', color: '#eb5757' }).setOrigin(0.5);
      seat.container.add(x);
      seat.deadOverlay = x;
    }
    seat.nameText.setColor('#776');
  }

  private setSpeaker(id: PlayerId | null): void {
    PLAYER_ORDER.forEach((pid) => {
      const r = this.seats[pid].ring;
      if (r) r.setVisible(pid === id && this.engine.players[pid].alive);
    });
  }

  private setBanner(text: string): void {
    this.bannerText.setText(text);
  }

  private showVoteBadges(votes: VoteRecord[]): void {
    PLAYER_ORDER.forEach((id) => {
      const seat = this.seats[id];
      if (seat.voteBadge) seat.voteBadge.setText('');
    });
    const counts = new Map<PlayerId, number>();
    votes.forEach((v) => {
      if (v.targetId === 'pass') return;
      counts.set(v.targetId, (counts.get(v.targetId) ?? 0) + 1);
    });
    counts.forEach((c, id) => {
      const seat = this.seats[id];
      if (seat.voteBadge) seat.voteBadge.setText(`\u2715${c}`);
    });
  }

  private clearVoteBadges(): void {
    PLAYER_ORDER.forEach((id) => this.seats[id].voteBadge?.setText(''));
  }

  // ---- Action button area -------------------------------------------------

  private clearButtons(): void {
    this.actionButtons.forEach((b) => b.destroy());
    this.actionButtons = [];
  }

  /** Render a row of buttons in the bottom action panel. */
  private showButtons(buttons: { label: string; onClick: () => void; color?: number }[]): void {
    this.clearButtons();
    const panelY = 962;
    const total = buttons.length;
    const btnW = 200;
    const gap = 18;
    const totalW = total * btnW + (total - 1) * gap;
    let x = 768 - totalW / 2 + btnW / 2;

    buttons.forEach((b) => {
      const c = this.add.container(x, panelY);
      const bg = this.add
        .rectangle(0, 0, btnW, 60, b.color ?? 0x2a1f14, 0.95)
        .setStrokeStyle(2, 0x6b5326)
        .setInteractive({ useHandCursor: true });
      const label = this.add
        .text(0, 0, b.label, {
          fontFamily: 'monospace',
          fontSize: '17px',
          color: '#e8dcc0',
          stroke: '#000',
          strokeThickness: 3,
          align: 'center',
          wordWrap: { width: btnW - 16 },
        })
        .setOrigin(0.5);
      bg.on('pointerover', () => bg.setFillStyle(0x7a2828, 0.95));
      bg.on('pointerout', () => bg.setFillStyle(b.color ?? 0x2a1f14, 0.95));
      bg.on('pointerdown', () => {
        utils.safeAddSound(this, 'click_sfx', { volume: 0.35 })?.play();
        b.onClick();
      });
      c.add([bg, label]);
      this.actionButtons.push(c);
      x += btnW + gap;
    });
  }

  /** Prompt the human to pick a living target from a list. */
  private promptTarget(
    candidates: PlayerId[],
    prompt: string,
    onPick: (id: PlayerId) => void,
    allowCancel?: () => void,
  ): void {
    this.setBanner(prompt);
    const buttons = candidates.map((id) => ({
      label: this.engine.profiles[id].name,
      onClick: () => onPick(id),
    }));
    if (allowCancel) buttons.push({ label: 'Back', onClick: allowCancel });
    this.showButtons(buttons);
  }

  // =========================================================================
  // PHASE: NIGHT
  // =========================================================================

  private enterNight(): void {
    this.engine.beginNight();
    this.pendingNight = { mafiaTarget: null, detectiveTarget: null, doctorTarget: null };
    this.clearVoteBadges();
    this.setSpeaker(null);
    this.refreshHUD();
    this.setBanner('Night Falls');
    utils.safeAddSound(this, 'night_sfx', { volume: 0.5 })?.play();
    this.cameras.main.flash(300, 0, 0, 20);

    // Pre-compute AI night choices (mafia/detective/doctor among NPCs).
    this.computeAINightChoices();

    const role = this.engine.humanRole;
    const human = this.engine.players.player;
    this.time.delayedCall(900, () => {
      if (!human.alive) {
        this.setBanner('Night Falls \u2014 you are dead. The living act in shadow.');
        this.showButtons([{ label: 'Wait for dawn', onClick: () => this.resolveNightStep() }]);
        return;
      }
      switch (role) {
        case 'Mafia':
          this.humanNightMafia();
          break;
        case 'Detective':
          this.humanNightDetective();
          break;
        case 'Doctor':
          this.humanNightDoctor();
          break;
        default:
          this.setBanner('Night Falls \u2014 you have no night action. Rest, Villager.');
          this.showButtons([{ label: 'Pass the night', onClick: () => this.resolveNightStep() }]);
      }
    });
  }

  private computeAINightChoices(): void {
    const e = this.engine;
    // Mafia: if human is NOT mafia, AI mafia consensus target.
    if (e.humanRole !== 'Mafia') {
      this.pendingNight.mafiaTarget = e.aiMafiaTarget();
    }
    // Detective: if human is NOT detective and an AI detective lives.
    const detId = e.list().find((p) => p.role === 'Detective')?.id;
    if (detId && detId !== 'player' && e.players[detId].alive) {
      this.pendingNight.detectiveTarget = e.aiDetectiveTarget(detId);
    }
    // Doctor: if human is NOT doctor and an AI doctor lives.
    const docId = e.list().find((p) => p.role === 'Doctor')?.id;
    if (docId && docId !== 'player' && e.players[docId].alive) {
      this.pendingNight.doctorTarget = e.aiDoctorTarget(docId);
    }
  }

  private humanNightMafia(): void {
    const partner = this.engine.humanMafiaPartnerIds[0];
    const partnerNote = partner ? ` (with ${this.engine.profiles[partner].name})` : '';
    this.showButtons([
      {
        label: 'Choose a victim',
        color: 0x4a1414,
        onClick: () => {
          const targets = this.engine.livingTown().map((p) => p.id);
          this.promptTarget(targets, `Mafia${partnerNote}: who dies tonight?`, (id) => {
            this.pendingNight.mafiaTarget = id;
            this.resolveNightStep();
          });
        },
      },
      { label: 'Spare everyone (Pass)', onClick: () => { this.pendingNight.mafiaTarget = null; this.resolveNightStep(); } },
    ]);
  }

  private humanNightDetective(): void {
    this.showButtons([
      {
        label: 'Investigate',
        color: 0x14304a,
        onClick: () => {
          const targets = this.engine.livingIds().filter((id) => id !== 'player');
          this.promptTarget(targets, 'Detective: whom do you investigate?', (id) => {
            this.pendingNight.detectiveTarget = id;
            this.resolveNightStep();
          });
        },
      },
      { label: 'Pass', onClick: () => { this.pendingNight.detectiveTarget = null; this.resolveNightStep(); } },
    ]);
  }

  private humanNightDoctor(): void {
    this.showButtons([
      {
        label: 'Protect someone',
        color: 0x144a2a,
        onClick: () => {
          const targets = this.engine.livingIds();
          this.promptTarget(targets, 'Doctor: whom do you protect?', (id) => {
            this.pendingNight.doctorTarget = id;
            this.resolveNightStep();
          });
        },
      },
      { label: 'Pass', onClick: () => { this.pendingNight.doctorTarget = null; this.resolveNightStep(); } },
    ]);
  }

  private resolveNightStep(): void {
    this.clearButtons();
    const result = this.engine.resolveNight(this.pendingNight);

    // Private detective feedback for the human.
    let detectiveNote = '';
    if (this.engine.humanRole === 'Detective' && this.pendingNight.detectiveTarget) {
      const last = this.engine.detectiveResults[this.engine.detectiveResults.length - 1];
      if (last) {
        detectiveNote = ` Your investigation: ${this.engine.profiles[last.targetId].name} is ${last.isMafia ? 'MAFIA' : 'not Mafia'}.`;
      }
    }

    this.refreshHUD();
    this.enterDawn(result.killedId, result.savedByDoctor, detectiveNote);
  }

  // =========================================================================
  // PHASE: DAWN
  // =========================================================================

  private enterDawn(killedId: PlayerId | null, saved: boolean, detectiveNote: string): void {
    this.engine.phase = 'Dawn';
    utils.safeAddSound(this, 'dawn_sfx', { volume: 0.5 })?.play();
    this.cameras.main.flash(300, 40, 30, 10);

    let msg: string;
    if (saved) {
      msg = 'Dawn breaks. A scream in the night \u2014 but the Doctor reached them in time. No one died.';
      this.engine.pushTimeline('Dawn', 'The Doctor saved the Mafia\u2019s target. No death.');
    } else if (killedId) {
      const name = this.engine.profiles[killedId].name;
      const role = this.engine.players[killedId].role;
      msg = `Dawn breaks. ${name} was found dead at the table \u2014 they were a ${role}.`;
      utils.safeAddSound(this, 'damage_sfx', { volume: 0.4 })?.play();
    } else {
      msg = 'Dawn breaks. Remarkably, everyone is still breathing.';
      this.engine.pushTimeline('Dawn', 'A quiet night. No one died.');
    }
    this.engine.pushLog(msg);
    this.setBanner('Dawn');
    this.refreshHUD();

    if (this.engine.checkWin()) {
      this.showButtons([{ label: 'Continue', onClick: () => this.endGame() }]);
      return;
    }

    this.showButtons([
      {
        label: 'Continue',
        onClick: () => {
          this.clearButtons();
          this.enterDiscussion();
        },
      },
    ]);

    // surface detective note in chat for the human only
    if (detectiveNote) {
      this.engine.line('player', 'Dawn', `(Private)${detectiveNote}`);
      this.refreshHUD();
    }
  }

  // =========================================================================
  // PHASE: DISCUSSION
  // =========================================================================

  private enterDiscussion(): void {
    this.engine.beginDay();
    this.setBanner(`Day ${this.engine.dayNumber} \u2014 Discussion`);
    this.engine.pushLog(`Day ${this.engine.dayNumber} discussion begins.`);

    // Generate and stream AI discussion lines.
    const lines = this.engine.generateDiscussion();
    this.streamLines(lines, () => this.humanDiscussionTurn());
  }

  private streamLines(
    lines: { speakerId: PlayerId | 'narrator'; text: string }[],
    done: () => void,
  ): void {
    let i = 0;
    const showNext = () => {
      if (i >= lines.length) {
        this.setSpeaker(null);
        done();
        return;
      }
      const l = lines[i++];
      if (l.speakerId === 'narrator') {
        this.refreshHUD();
        this.time.delayedCall(900, showNext);
        return;
      }
      this.setSpeaker(l.speakerId as PlayerId);
      this.setPortraitMood(l.speakerId as PlayerId, 'suspicious');
      this.refreshHUD();
      this.time.delayedCall(900, showNext);
    };
    showNext();
  }

  private setPortraitMood(id: PlayerId, _mood: string): void {
    // Only neutral/dead expressions are guaranteed; pulse the portrait instead.
    const seat = this.seats[id];
    if (!seat || !this.engine.players[id].alive) return;
    this.tweens.add({ targets: seat.container, scale: 1.08, duration: 160, yoyo: true });
  }

  private humanDiscussionTurn(): void {
    if (!this.engine.players.player.alive) {
      this.setBanner(`Day ${this.engine.dayNumber} \u2014 you watch in silence (deceased).`);
      this.showButtons([{ label: 'Proceed to vote', onClick: () => this.enterHotSeat() }]);
      return;
    }
    this.setBanner(`Day ${this.engine.dayNumber} \u2014 Your turn to speak`);
    this.showButtons([
      { label: 'Ask around', onClick: () => this.humanAsk() },
      { label: 'Accuse', onClick: () => this.humanAccuse() },
      { label: 'Defend self', onClick: () => this.humanDefend() },
      { label: 'Claim role', onClick: () => this.humanClaim() },
      { label: 'Stay silent (Pass)', onClick: () => this.enterHotSeat() },
    ]);
  }

  private humanAsk(): void {
    const targets = this.engine.livingIds().filter((id) => id !== 'player');
    this.promptTarget(
      targets,
      'Whom do you press for answers?',
      (id) => {
        this.engine.line('player', 'Discussion', `${this.engine.profiles[id].name}, what are you hiding?`);
        // pressed player gains slight suspicion in the room's eyes
        this.engine.recordAccusation('player', id);
        this.refreshHUD();
        this.humanDiscussionTurn();
      },
      () => this.humanDiscussionTurn(),
    );
  }

  private humanAccuse(): void {
    const targets = this.engine.livingIds().filter((id) => id !== 'player');
    this.promptTarget(
      targets,
      'Whom do you accuse of being Mafia?',
      (id) => {
        this.engine.line('player', 'Discussion', `I accuse ${this.engine.profiles[id].name} of being Mafia!`);
        this.engine.recordAccusation('player', id);
        this.refreshHUD();
        this.humanDiscussionTurn();
      },
      () => this.humanDiscussionTurn(),
    );
  }

  private humanDefend(): void {
    this.engine.line('player', 'Discussion', 'You are all wrong about me \u2014 I am on the town\u2019s side.');
    this.engine.recordDefense('player');
    this.refreshHUD();
    this.humanDiscussionTurn();
  }

  private humanClaim(): void {
    const roles: Role[] = ['Villager', 'Doctor', 'Detective', 'Mafia'];
    this.showButtons([
      ...roles.map((r) => ({
        label: `Claim ${r}`,
        onClick: () => {
          this.engine.recordClaim('player', r);
          this.engine.line('player', 'Discussion', `For the record \u2014 I am the ${r}.`);
          this.refreshHUD();
          this.humanDiscussionTurn();
        },
      })),
      { label: 'Back', onClick: () => this.humanDiscussionTurn() },
    ]);
  }

  // =========================================================================
  // PHASE: HOT SEAT
  // =========================================================================

  private enterHotSeat(): void {
    this.clearButtons();
    this.engine.phase = 'HotSeat';
    // Accused = highest room-suspicion living player.
    const living = this.engine.livingIds();
    let accused: PlayerId | null = null;
    let max = -Infinity;
    living.forEach((id) => {
      const s = this.engine.roomSuspicion(id);
      if (s > max) {
        max = s;
        accused = id;
      }
    });

    if (!accused) {
      this.enterVote();
      return;
    }
    this.setSpeaker(accused);
    const name = this.engine.profiles[accused].name;
    this.setBanner(`Hot Seat: ${name} faces the table`);
    this.engine.pushLog(`${name} is put on the hot seat.`);
    this.engine.pushTimeline('HotSeat', `${name} faced the table\u2019s suspicion.`);

    // AI accused defends or counters; human accused gets a UI.
    if (accused === 'player') {
      this.showButtons([
        { label: 'Defend self', onClick: () => { this.engine.recordDefense('player'); this.engine.line('player','HotSeat','I swear I am innocent. Look elsewhere.'); this.refreshHUD(); this.enterVote(); } },
        { label: 'Claim role', onClick: () => this.humanClaimThen(() => this.enterVote()) },
        { label: 'Stay silent', onClick: () => this.enterVote() },
      ]);
    } else {
      // Scripted defense line.
      const defenseLine = this.engine.players[accused].role === 'Mafia'
        ? 'This is absurd \u2014 you are wasting the night chasing the wrong person.'
        : 'I have done nothing wrong. Vote me and you hand the night to the Mafia.';
      this.engine.line(accused, 'HotSeat', defenseLine);
      this.engine.recordDefense(accused);
      this.refreshHUD();
      this.showButtons([{ label: 'Proceed to vote', onClick: () => this.enterVote() }]);
    }
  }

  private humanClaimThen(after: () => void): void {
    const roles: Role[] = ['Villager', 'Doctor', 'Detective', 'Mafia'];
    this.showButtons([
      ...roles.map((r) => ({
        label: `Claim ${r}`,
        onClick: () => {
          this.engine.recordClaim('player', r);
          this.engine.line('player', 'HotSeat', `I am the ${r}, I tell you!`);
          this.refreshHUD();
          after();
        },
      })),
      { label: 'Back', onClick: () => this.enterHotSeat() },
    ]);
  }

  // =========================================================================
  // PHASE: VOTE
  // =========================================================================

  private enterVote(): void {
    this.clearButtons();
    this.setSpeaker(null);
    this.engine.beginVote();
    this.setBanner(`Day ${this.engine.dayNumber} \u2014 The Vote`);

    if (!this.engine.players.player.alive) {
      this.tallyAndResolve(this.engine.computeAIVotes());
      return;
    }

    const targets = this.engine.livingIds().filter((id) => id !== 'player');
    this.showButtons([
      {
        label: 'Cast your vote',
        color: 0x4a1414,
        onClick: () => {
          this.promptTarget(targets, 'Vote to eliminate:', (id) => {
            const votes = this.engine.computeAIVotes();
            votes.push({ voterId: 'player', targetId: id });
            this.tallyAndResolve(votes);
          });
        },
      },
      {
        label: 'Abstain (Pass)',
        onClick: () => {
          const votes = this.engine.computeAIVotes();
          votes.push({ voterId: 'player', targetId: 'pass' });
          this.tallyAndResolve(votes);
        },
      },
    ]);
  }

  private tallyAndResolve(votes: VoteRecord[]): void {
    this.clearButtons();
    utils.safeAddSound(this, 'vote_sfx', { volume: 0.45 })?.play();
    this.showVoteBadges(votes);
    const result = this.engine.tallyVotes(votes);
    this.refreshHUD();

    this.time.delayedCall(1100, () => this.enterElimination(result.eliminatedId, result.tie));
  }

  // =========================================================================
  // PHASE: ELIMINATION
  // =========================================================================

  private enterElimination(eliminatedId: PlayerId | null, tie: boolean): void {
    this.engine.phase = 'Elimination';
    this.clearVoteBadges();

    let msg: string;
    if (tie || !eliminatedId) {
      msg = 'The vote splits. No one is banished tonight.';
    } else {
      const name = this.engine.profiles[eliminatedId].name;
      const role = this.engine.players[eliminatedId].role;
      msg = `${name} is dragged from the table \u2014 they were a ${role}.`;
      utils.safeAddSound(this, 'damage_sfx', { volume: 0.4 })?.play();
    }
    this.engine.pushLog(msg);
    this.setBanner('Elimination');
    this.refreshHUD();

    if (this.engine.checkWin()) {
      this.showButtons([{ label: 'See the truth', onClick: () => this.endGame() }]);
      return;
    }
    this.showButtons([
      {
        label: 'Continue to night',
        onClick: () => {
          this.clearButtons();
          this.enterNight();
        },
      },
    ]);
  }

  // =========================================================================
  // END
  // =========================================================================

  private endGame(): void {
    this.clearButtons();
    this.engine.checkWin();
    this.cameras.main.fadeOut(500, 0, 0, 0);
    this.time.delayedCall(500, () => {
      this.bgm?.stop();
      this.scene.start('EndgameScene');
    });
  }
}
