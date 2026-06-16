import Phaser from 'phaser';
import {
  BackendClient,
  actorName,
  seatTexturePrefix,
  targetLabel,
  type EventView,
  type MafiaGameView,
  type PlayerView,
  type Role,
  type Suggestion,
} from '../game/BackendClient';
import * as utils from '../utils';

interface Seat {
  id: string;
  container: Phaser.GameObjects.Container;
  portrait: Phaser.GameObjects.Image | Phaser.GameObjects.Rectangle;
  nameText: Phaser.GameObjects.Text;
  badgeText: Phaser.GameObjects.Text;
  ring: Phaser.GameObjects.Arc;
  deadText: Phaser.GameObjects.Text;
}

const SEATS: Record<string, { x: number; y: number }> = {
  p1: { x: 768, y: 768 },
  p2: { x: 1102, y: 710 },
  p3: { x: 1112, y: 496 },
  p4: { x: 1034, y: 260 },
  p5: { x: 768, y: 194 },
  p6: { x: 502, y: 260 },
  p7: { x: 396, y: 496 },
};

const ROLE_COLORS: Record<string, string> = {
  Mafia: '#eb5757',
  Detective: '#74b7e8',
  Doctor: '#6fcf97',
  Villager: '#e8c87a',
};

const PLAYER_COLORS: Record<string, string> = {
  p1: '#e8c87a',
  p2: '#eb5757',
  p3: '#74b7e8',
  p4: '#d9a85f',
  p5: '#6fcf97',
  p6: '#c785ff',
  p7: '#f2994a',
  moderator: '#9ecfff',
};

export class MainTableScene extends Phaser.Scene {
  private client = new BackendClient();
  private view!: MafiaGameView;
  private bgm?: Phaser.Sound.BaseSound;
  private seats: Record<string, Seat> = {};
  private actionButtons: Phaser.GameObjects.Container[] = [];
  private overlay?: Phaser.GameObjects.Container;
  private chatInput?: Phaser.GameObjects.DOMElement;
  private bannerText!: Phaser.GameObjects.Text;
  private subText!: Phaser.GameObjects.Text;
  private aliveText!: Phaser.GameObjects.Text;
  private ledgerText!: Phaser.GameObjects.Text;
  private chatText!: Phaser.GameObjects.Text;
  private suggestionText!: Phaser.GameObjects.Text;
  private ledgerDom?: Phaser.GameObjects.DOMElement;
  private chatDom?: Phaser.GameObjects.DOMElement;
  private suggestionDom?: Phaser.GameObjects.DOMElement;
  private autoAdvanceTimer?: Phaser.Time.TimerEvent;
  private busy = false;
  private lastSoundSeq = 0;

  constructor() {
    super({ key: 'MainTableScene' });
  }

  create(): void {
    const view = window.__MAFIA_VIEW__;
    if (!view) {
      this.scene.start('TitleScreen');
      return;
    }
    this.view = view;
    this.createBackground();
    this.createTable();
    this.createSeats();
    this.createHUD();
    this.createChatInput();
    this.playMusic();
    this.cameras.main.fadeIn(450, 0, 0, 0);
    this.refreshAll();
    this.events.once('shutdown', () => this.cleanup());
  }

  private createBackground(): void {
    const cam = this.cameras.main;
    const key = this.view?.scene?.sceneKey === 'vote' && utils.textureExists(this, 'main_table_bg') ? 'main_table_bg' : 'main_table_bg';
    if (utils.textureExists(this, key)) {
      const bg = this.add.image(cam.width / 2, cam.height / 2, key);
      bg.setDisplaySize(cam.width, cam.height);
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x000000, 0.28);
    } else {
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x110d0a, 1);
    }
  }

  private createTable(): void {
    this.add.rectangle(768, 512, 720, 520, 0x000000, 0.08);
  }

  private createSeats(): void {
    this.view.players.forEach((player) => {
      const pos = SEATS[player.id] ?? { x: 768, y: 500 };
      const container = this.add.container(pos.x, pos.y);
      const ring = this.add.circle(0, 0, player.isHuman ? 88 : 78, 0xe8c87a, 0).setStrokeStyle(4, 0xe8c87a, 0.95);
      ring.setVisible(false);
      container.add(ring);

      const prefix = this.texturePrefixFor(player);
      const portraitKey = `${prefix}_neutral`;
      let portrait: Phaser.GameObjects.Image | Phaser.GameObjects.Rectangle;
      if (utils.textureExists(this, portraitKey)) {
        const img = this.add.image(0, 0, portraitKey);
        img.setScale(Math.min((player.isHuman ? 146 : 132) / img.height, (player.isHuman ? 146 : 132) / img.width));
        portrait = img;
      } else {
        portrait = this.add.rectangle(0, 0, 120, 138, 0x3a2418, 0.92).setStrokeStyle(2, 0x6b5326);
      }
      container.add(portrait);

      const plateWidth = player.isHuman ? 250 : 214;
      const plate = this.add.rectangle(0, 112, plateWidth, 76, 0x0c0a12, 0.92).setStrokeStyle(1, 0x6b5326);
      const nameText = this.add.text(0, 96, player.isHuman ? `${player.name} (You)` : player.name, {
        fontFamily: 'monospace',
        fontSize: player.isHuman ? '17px' : '15px',
        color: '#e8dcc0',
        stroke: '#000',
        strokeThickness: 3,
        fixedWidth: plateWidth - 14,
        fixedHeight: 24,
        wordWrap: { width: plateWidth - 18 },
        align: 'center',
      }).setOrigin(0.5);
      const badgeText = this.add.text(0, 124, '', {
        fontFamily: 'monospace',
        fontSize: '11px',
        color: '#b99b70',
        fixedWidth: plateWidth - 16,
        fixedHeight: 34,
        wordWrap: { width: plateWidth - 20 },
        align: 'center',
      }).setOrigin(0.5);
      const deadText = this.add.text(0, 0, 'ELIMINATED', {
        fontFamily: 'monospace',
        fontSize: '14px',
        color: '#eb5757',
        backgroundColor: '#140708',
        padding: { x: 8, y: 4 },
      }).setOrigin(0.5).setVisible(false);
      container.add([plate, nameText, badgeText, deadText]);
      this.seats[player.id] = { id: player.id, container, portrait, nameText, badgeText, ring, deadText };
    });
  }

  private createHUD(): void {
    this.add.rectangle(768, 58, 920, 108, 0x0c0a12, 0.86).setStrokeStyle(2, 0x6b5326);
    this.bannerText = this.add.text(768, 28, '', {
      fontFamily: 'Georgia',
      fontSize: '30px',
      color: '#e8c87a',
      stroke: '#000',
      strokeThickness: 4,
    }).setOrigin(0.5);
    this.subText = this.add.text(768, 66, '', {
      fontFamily: 'monospace',
      fontSize: '14px',
      color: '#d6d2c4',
    }).setOrigin(0.5);
    this.aliveText = this.add.text(768, 92, '', {
      fontFamily: 'monospace',
      fontSize: '13px',
      color: '#b99b70',
    }).setOrigin(0.5);

    this.add.rectangle(136, 510, 264, 790, 0x0c0a12, 0.78).setStrokeStyle(2, 0x6b5326);
    this.add.text(18, 130, 'STATUS UPDATES', {
      fontFamily: 'monospace',
      fontSize: '15px',
      color: '#b8443c',
      stroke: '#000',
      strokeThickness: 3,
    });
    this.ledgerText = this.add.text(18, 164, '', {
      fontFamily: 'monospace',
      fontSize: '12px',
      color: '#d6d2c4',
      lineSpacing: 4,
      wordWrap: { width: 226 },
    }).setVisible(false);

    this.add.rectangle(1410, 510, 246, 790, 0x0c0a12, 0.8).setStrokeStyle(2, 0x6b5326);
    this.add.text(1308, 130, 'DISCUSSIONS', {
      fontFamily: 'monospace',
      fontSize: '15px',
      color: '#b8443c',
      stroke: '#000',
      strokeThickness: 3,
    });
    this.chatText = this.add.text(1308, 162, '', {
      fontFamily: 'monospace',
      fontSize: '12px',
      color: '#e8dcc0',
      lineSpacing: 5,
      wordWrap: { width: 216 },
    }).setVisible(false);
    this.suggestionText = this.add.text(1308, 772, '', {
      fontFamily: 'monospace',
      fontSize: '12px',
      color: '#b99b70',
      lineSpacing: 5,
      wordWrap: { width: 216 },
    }).setVisible(false);
    this.createInfoDomPanels();
  }

  private createInfoDomPanels(): void {
    const ledger = document.createElement('div');
    ledger.className = 'mafia-ledger-dom-panel';
    this.ledgerDom = this.add.dom(136, 506, ledger).setDepth(18);

    const chat = document.createElement('div');
    chat.className = 'mafia-chat-dom-panel';
    this.chatDom = this.add.dom(1410, 444, chat).setDepth(18);

    const suggestions = document.createElement('div');
    suggestions.className = 'mafia-suggestions-dom-panel';
    suggestions.addEventListener('click', (event) => {
      const target = event.target as HTMLElement | null;
      const button = target?.closest<HTMLButtonElement>('button[data-suggestion-index]');
      if (!button) return;
      event.stopPropagation();
      const index = Number(button.dataset.suggestionIndex ?? '-1');
      const suggestion = (this.view.suggestions ?? [])[index];
      if (suggestion) {
        this.playClick();
        void this.sendSuggestion(suggestion);
      }
    });
    this.suggestionDom = this.add.dom(1410, 806, suggestions).setDepth(18);
  }

  private createChatInput(): void {
    const wrapper = document.createElement('form');
    wrapper.className = 'mafia-chat-compose';
    wrapper.innerHTML = `
      <input class="mafia-chat-dom-input" placeholder="Type your own discussion message..." maxlength="240" />
      <button class="mafia-chat-send" type="submit" aria-label="Send discussion message">Send</button>
    `;
    const input = wrapper.querySelector<HTMLInputElement>('input');
    if (!input) return;
    const sendButton = wrapper.querySelector<HTMLButtonElement>('button');
    const send = () => {
      if (!input.value.trim()) return;
      this.playClick();
      void this.commitAction('message', () => this.client.message(this.view.gameId, input.value.trim()), 'Message sent to the moderator queue.');
      input.value = '';
    };
    input.addEventListener('keydown', (event) => {
      event.stopPropagation();
      if (event.key === 'Enter' && input.value.trim()) {
        send();
      }
    });
    wrapper.addEventListener('submit', (event) => {
      event.preventDefault();
      event.stopPropagation();
      send();
    });
    sendButton?.addEventListener('pointerdown', (event) => event.stopPropagation());
    this.chatInput = this.add.dom(1410, 930, wrapper).setDepth(20);
  }

  private playMusic(): void {
    this.bgm = utils.safeAddSound(this, 'main_table_bgm', { volume: 0.24, loop: true });
    this.bgm?.play();
  }

  private refreshAll(): void {
    window.__MAFIA_VIEW__ = this.view;
    this.bannerText.setText(this.view.scene.title);
    this.subText.setText(this.view.scene.subtitle);
    this.aliveText.setText(`Alive: ${this.view.aliveCount}/7   •   Day ${this.view.day}   •   ${this.view.mode}   •   Your role: ${this.view.human.role}`);
    this.refreshSeats();
    this.refreshLedger();
    this.refreshChat();
    this.refreshSuggestions();
    this.playNewEventSounds();
    this.renderActions();
    this.scheduleAutonomousModeration();
    if (this.view.winner) this.goEndgame();
  }

  private refreshSeats(): void {
    const votes = this.view.votes ?? {};
    const voteCounts = new Map<string, number>();
    Object.values(votes).forEach((target) => voteCounts.set(target, (voteCounts.get(target) ?? 0) + 1));
    this.view.players.forEach((player) => {
      const seat = this.seats[player.id];
      if (!seat) return;
      seat.nameText.setText(player.isHuman ? `${player.name} (You)` : player.name);
      const votesOn = voteCounts.get(player.id);
      seat.badgeText.setText(this.seatStatus(player, votesOn));
      seat.deadText.setVisible(!player.alive);
      seat.container.setAlpha(player.alive ? 1 : 0.5);
      if (!player.alive && seat.portrait instanceof Phaser.GameObjects.Image) {
        const prefix = this.texturePrefixFor(player);
        const deadKey = `${prefix}_dead`;
        if (utils.textureExists(this, deadKey)) seat.portrait.setTexture(deadKey);
        seat.portrait.setTint(0x8b8791);
      }
      if (this.view.hotSeatTarget === player.id) {
        seat.ring.setVisible(true);
      } else {
        seat.ring.setVisible(false);
      }
    });
  }

  private refreshLedger(): void {
    const claimItems = this.view.players
      .filter((player) => player.claimedRole)
      .map((player) => ({ kind: 'claim', text: `${player.name}: claims ${player.claimedRole}` }));
    const voteItems = [
      ...this.view.players
        .filter((player) => player.lastVote)
        .map((player) => ({ kind: 'vote', text: `${player.name} voted ${actorName(this.view, player.lastVote)}` })),
      ...this.view.events
        .filter((event) => ['accusation_started', 'vote_resolved', 'vote_tied'].includes(event.type))
        .slice(-5)
        .map((event) => ({ kind: event.type, text: this.describeEvent(event) })),
    ];
    const deathItems = [
      ...this.view.players
        .filter((player) => !player.alive)
        .map((player) => ({ kind: 'death', text: `${player.name} eliminated` })),
      ...this.view.events
        .filter((event) => ['dawn_announced', 'doctor_save'].includes(event.type))
        .slice(-4)
        .map((event) => ({ kind: event.type, text: this.describeEvent(event) })),
    ];
    if (this.ledgerDom?.node instanceof HTMLElement) {
      this.ledgerDom.node.innerHTML = [
        this.renderLedgerSection('Claims', claimItems),
        this.renderLedgerSection('Votes', voteItems),
        this.renderLedgerSection('Deaths', deathItems),
      ].join('');
      return;
    }
    this.ledgerText.setText(
      [...claimItems, ...voteItems, ...deathItems].map((item) => `• ${item.text}`).join('\n') || '• No status updates yet.',
    );
  }

  private refreshChat(): void {
    const lines = this.view.events
      .filter((event) => event.type === 'player_message' || event.type === 'moderator_cue' || event.type === 'private_moderator_cue')
      .slice(-13)
      .map((event) => {
        const moderator = event.type === 'moderator_cue' || event.type === 'private_moderator_cue';
        const isPrivate = Boolean(event.payload.private);
        const who = moderator ? 'Moderator' : actorName(this.view, event.actor);
        const message = String(event.payload.message ?? '');
        const tone = isPrivate ? 'private' : '';
        return { who, message, tone, moderator, private: isPrivate, actor: event.actor, type: event.type };
      })
      .filter((line, index, all) => {
        const previous = all[index - 1];
        return !previous
          || previous.actor !== line.actor
          || previous.type !== line.type
          || previous.message !== line.message
          || previous.private !== line.private;
      });
    if (this.chatDom?.node instanceof HTMLElement) {
      this.chatDom.node.innerHTML = lines.length
        ? lines.map((line) => `
          <article class="mafia-chat-bubble ${line.moderator ? 'moderator' : line.actor === this.view.human.id ? 'human' : 'ai'} ${line.private ? 'private' : ''}">
            <header><span style="color:${this.playerColor(line.actor, line.moderator)}">${this.escape(line.who)}</span>${line.tone ? `<em>${this.escape(line.tone)}</em>` : ''}</header>
            <p>${this.escape(line.message)}</p>
          </article>
        `).join('')
        : '<div class="mafia-chat-empty">The room is waiting for the first words.</div>';
      this.chatDom.node.scrollTop = this.chatDom.node.scrollHeight;
      return;
    }
    this.chatText.setText(lines.map((line) => `${line.who}${line.tone ? ` [${line.tone}]` : ''}\n  ${line.message}`).join('\n\n') || 'The room is waiting for the first words.');
  }

  private refreshSuggestions(): void {
    const objective = this.view.scene.objective;
    const renderDom = (html: string) => {
      if (this.suggestionDom?.node instanceof HTMLElement) {
        this.suggestionDom.node.innerHTML = html;
        return true;
      }
      return false;
    };
    if (!this.view.human.alive) {
      if (renderDom(`<div class="mafia-suggestion-note">${this.escape('You are eliminated. Watch the remaining players finish the game.')}</div>`)) return;
      this.suggestionText.setText('You are eliminated. Watch the remaining players finish the game.');
      return;
    }
    if (renderDom(`
      <div class="mafia-suggestion-kicker">Objective</div>
      <div class="mafia-suggestion-note">${this.escape(objective)}</div>
    `)) return;
    this.suggestionText.setText(objective);
  }

  private playNewEventSounds(): void {
    const latestSeq = Math.max(0, ...this.view.events.map((event) => event.seq));
    if (!this.lastSoundSeq) {
      this.lastSoundSeq = latestSeq;
      return;
    }
    const fresh = this.view.events.filter((event) => event.seq > this.lastSoundSeq);
    this.lastSoundSeq = latestSeq;
    if (!fresh.length) return;
    if (fresh.some((event) => event.type === 'vote_resolved' || event.type === 'player_eliminated')) {
      utils.safeAddSound(this, 'damage_sfx', { volume: 0.5 })?.play();
      return;
    }
    if (fresh.some((event) => event.type === 'vote_cast' || event.type === 'accusation_started')) {
      utils.safeAddSound(this, 'vote_sfx', { volume: 0.46 })?.play();
      return;
    }
    if (fresh.some((event) => ['player_message', 'moderator_cue', 'private_moderator_cue'].includes(event.type))) {
      utils.safeAddSound(this, 'click_sfx', { volume: 0.28 })?.play();
    }
  }

  private renderActions(): void {
    this.clearButtons();
    this.chatInput?.setVisible(this.view.human.alive && this.view.human.legalActions.includes('message'));
    if (this.busy) {
      this.showButtons([{ label: 'Moderating...', onClick: () => undefined }]);
      return;
    }
    if (!this.view.human.alive) {
      this.showButtons([{ label: 'Watch table advance', onClick: () => this.advance(4) }]);
      return;
    }
    const legal = new Set(this.view.human.legalActions);
    const buttons: { label: string; onClick: () => void; color?: number }[] = [];
    if (legal.has('kill') || legal.has('check') || legal.has('protect')) {
      const action = legal.has('kill') ? 'Choose victim' : legal.has('check') ? 'Investigate' : 'Protect';
      buttons.push({ label: action, color: legal.has('kill') ? 0x4a1414 : legal.has('check') ? 0x14304a : 0x144a2a, onClick: () => this.chooseTarget(action) });
    }
    if (legal.has('sleep')) buttons.push({ label: 'Sleep through night', onClick: () => this.advance(4) });
    if (this.view.phase === 'dawn' || this.view.phase === 'resolution') buttons.push({ label: 'Continue', onClick: () => this.advance(2) });
    if (legal.has('message') && this.view.pendingHumanFloor) {
      buttons.push({
        label: 'Done speaking',
        onClick: () => this.passFloor(),
      });
    }
    if (legal.has('claim')) buttons.push({ label: 'Claim role', onClick: () => this.chooseRoleClaim() });
    if (legal.has('accuse')) buttons.push({ label: 'Accuse', color: 0x4a1414, onClick: () => this.chooseTarget('Accuse') });
    if (legal.has('vote')) buttons.push({ label: 'Vote', color: 0x4a1414, onClick: () => this.chooseTarget('Vote') });
    if (!buttons.length) buttons.push({ label: 'Continue', onClick: () => this.advance(1) });
    this.showButtons(buttons.slice(0, 6));
  }

  private showButtons(buttons: { label: string; onClick: () => void; color?: number }[]): void {
    const btnW = 170;
    const gap = 14;
    const perRow = buttons.length > 4 ? 3 : buttons.length;
    const rowCount = Math.ceil(buttons.length / Math.max(1, perRow));
    const firstY = rowCount > 1 ? 922 : 960;
    buttons.forEach((button, index) => {
      const row = Math.floor(index / perRow);
      const rowButtons = buttons.slice(row * perRow, row * perRow + perRow);
      const col = index % perRow;
      const totalW = rowButtons.length * btnW + (rowButtons.length - 1) * gap;
      const x = 768 - totalW / 2 + btnW / 2 + col * (btnW + gap);
      const y = firstY + row * 66;
      const c = this.add.container(x, y).setDepth(30);
      const bg = this.add.rectangle(0, 0, btnW, 58, button.color ?? 0x2a1f14, 0.96).setStrokeStyle(2, 0x6b5326).setInteractive({ useHandCursor: true });
      const label = this.add.text(0, 0, button.label, {
        fontFamily: 'monospace',
        fontSize: '15px',
        color: '#f4dfbd',
        stroke: '#000',
        strokeThickness: 3,
        wordWrap: { width: btnW - 14 },
        align: 'center',
      }).setOrigin(0.5);
      bg.on('pointerover', () => bg.setFillStyle(0x7a2828, 0.96));
      bg.on('pointerout', () => bg.setFillStyle(button.color ?? 0x2a1f14, 0.96));
      bg.on('pointerdown', () => {
        this.playClick(0.35);
        button.onClick();
      });
      c.add([bg, label]);
      this.actionButtons.push(c);
    });
  }

  private chooseTarget(intent: string): void {
    const allowSelf = intent === 'Protect';
    const targets = this.view.targetChoices.filter((choice) => allowSelf || choice.id !== this.view.human.id);
    this.showOverlay(`${intent}: choose a living player`, targets.map((target) => ({
      label: target.label,
      onClick: () => {
        this.clearOverlay();
        if (intent === 'Accuse') void this.commitAction('accuse', () => this.client.accuse(this.view.gameId, target.id));
        else if (intent === 'Vote') void this.commitAction('vote', () => this.client.vote(this.view.gameId, target.id));
        else void this.commitAction('night action', () => this.client.nightAction(this.view.gameId, target.id));
      },
    })));
  }

  private chooseRoleClaim(): void {
    const roles = (this.view.roleChoices ?? ['Villager', 'Doctor', 'Detective', 'Mafia']) as Role[];
    this.showOverlay('Claim a role publicly', roles.map((role) => ({
      label: role,
      color: ROLE_COLORS[role],
      onClick: () => {
        this.clearOverlay();
        void this.commitAction('claim', () => this.client.claim(this.view.gameId, role));
      },
    })));
  }

  private showOverlay(title: string, options: { label: string; onClick: () => void; color?: string }[]): void {
    this.clearOverlay();
    const overlay = this.add.container(768, 520).setDepth(80);
    overlay.add(this.add.rectangle(0, 0, 560, 460, 0x0c0a12, 0.94).setStrokeStyle(2, 0x6b5326));
    overlay.add(this.add.text(0, -190, title, { fontFamily: 'Georgia', fontSize: '26px', color: '#e8c87a' }).setOrigin(0.5));
    let y = -126;
    options.slice(0, 8).forEach((option) => {
      const bg = this.add.rectangle(0, y, 430, 42, option.color ? parseInt(option.color.slice(1), 16) : 0x2a1f14, 0.96).setStrokeStyle(1, 0x6b5326).setInteractive({ useHandCursor: true });
      const text = this.add.text(0, y, option.label, { fontFamily: 'monospace', fontSize: '16px', color: '#f4dfbd' }).setOrigin(0.5);
      bg.on('pointerdown', () => {
        this.playClick();
        option.onClick();
      });
      overlay.add([bg, text]);
      y += 52;
    });
    const cancel = this.add.rectangle(0, 180, 220, 42, 0x1b1712, 0.96).setStrokeStyle(1, 0x6b5326).setInteractive({ useHandCursor: true });
    const cancelText = this.add.text(0, 180, 'Back', { fontFamily: 'monospace', fontSize: '16px', color: '#e8dcc0' }).setOrigin(0.5);
    cancel.on('pointerdown', () => {
      this.playClick();
      this.clearOverlay();
    });
    overlay.add([cancel, cancelText]);
    this.overlay = overlay;
  }

  private async sendSuggestion(suggestion: Suggestion): Promise<void> {
    await this.commitAction(suggestion.intent, () => this.client.approveSuggestion(this.view.gameId, suggestion), 'Suggested message sent to the moderator queue.');
  }

  private async advance(maxSteps: number): Promise<void> {
    await this.commitAction('advance', () => this.client.advance(this.view.gameId, maxSteps));
  }

  private async passFloor(): Promise<void> {
    await this.commitAction('wait', () => this.client.passFloor(this.view.gameId), 'You waited. The moderator is moving the floor.');
  }

  private scheduleAutonomousModeration(): void {
    this.autoAdvanceTimer?.remove(false);
    this.autoAdvanceTimer = undefined;
    if (this.busy || this.view.winner || !this.view.human.alive || !this.shouldAutonomouslyModerate()) return;
    this.autoAdvanceTimer = this.time.delayedCall(3600, () => {
      this.autoAdvanceTimer = undefined;
      if (!this.busy && this.shouldAutonomouslyModerate()) void this.advance(1);
    });
  }

  private shouldAutonomouslyModerate(): boolean {
    if (this.view.pendingHumanFloor) return false;
    if (this.view.phase !== 'discussion' && this.view.phase !== 'hot_seat') return false;
    const legal = new Set(this.view.human.legalActions);
    return !legal.has('kill') && !legal.has('check') && !legal.has('protect') && !legal.has('vote');
  }

  private async commitAction(label: string, action: () => Promise<MafiaGameView>, successMessage?: string): Promise<void> {
    if (this.busy) return;
    this.busy = true;
    this.bannerText.setText(label === 'advance' ? 'Moderating...' : 'Committing action...');
    this.renderActions();
    let committed = false;
    try {
      const next = await action();
      this.view = next;
      committed = true;
      const sound =
        this.view.winner ? 'victory_sfx'
        : label === 'vote' ? 'vote_sfx'
        : label === 'night action' && this.view.human.role === 'Mafia' ? 'damage_sfx'
        : 'click_sfx';
      utils.safeAddSound(this, sound, { volume: sound === 'damage_sfx' ? 0.45 : 0.35 })?.play();
    } catch (error) {
      this.subText.setText(error instanceof Error ? error.message : String(error));
      utils.safeAddSound(this, 'wrong_sfx', { volume: 0.35 })?.play();
    } finally {
      this.busy = false;
      this.refreshAll();
      if (committed && successMessage) this.subText.setText(successMessage);
    }
  }

  private describeEvent(event: EventView): string {
    if (event.type === 'dawn_announced') return String(event.payload.message ?? 'Dawn was announced.');
    if (event.type === 'accusation_started') return `${actorName(this.view, event.actor)} accused ${actorName(this.view, String(event.payload.target ?? ''))}.`;
    if (event.type === 'vote_resolved') return `Vote resolved: ${actorName(this.view, String(event.payload.eliminated ?? ''))} was eliminated.`;
    if (event.type === 'vote_tied') return 'The vote tied. No one was eliminated.';
    if (event.type === 'doctor_save') return 'No one was eliminated during the night.';
    return event.type;
  }

  private seatStatus(player: PlayerView, votesOn?: number): string {
    if (!player.alive) return 'eliminated';
    if (this.view.hotSeatTarget === player.id) return 'on the hot seat';
    if (votesOn) return `${votesOn} vote${votesOn > 1 ? 's' : ''} on them`;
    if (player.claimedRole) return `claims ${player.claimedRole}`;
    return 'watching';
  }

  private clearButtons(): void {
    this.actionButtons.forEach((button) => button.destroy());
    this.actionButtons = [];
  }

  private clearOverlay(): void {
    this.overlay?.destroy();
    this.overlay = undefined;
  }

  private playClick(volume = 0.32): void {
    utils.safeAddSound(this, 'click_sfx', { volume })?.play();
  }

  private goEndgame(): void {
    this.clearButtons();
    this.clearOverlay();
    this.chatInput?.destroy();
    this.cameras.main.fadeOut(500, 0, 0, 0);
    this.time.delayedCall(520, () => {
      this.bgm?.stop();
      this.scene.start('EndgameScene');
    });
  }

  private cleanup(): void {
    this.bgm?.stop();
    this.autoAdvanceTimer?.remove(false);
    this.autoAdvanceTimer = undefined;
    this.chatInput?.destroy();
    this.ledgerDom?.destroy();
    this.chatDom?.destroy();
    this.suggestionDom?.destroy();
    this.clearButtons();
    this.clearOverlay();
  }

  private escape(value: string): string {
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  private texturePrefixFor(player: PlayerView): string {
    if (player.id === this.view.human.id) {
      return window.__MAFIA_AVATAR_ID__ ?? this.view.humanAvatar ?? player.avatar ?? 'player';
    }
    return seatTexturePrefix[player.id] ?? 'player';
  }

  private playerColor(playerId: string | null, moderator: boolean): string {
    if (moderator) return PLAYER_COLORS.moderator;
    return playerId ? PLAYER_COLORS[playerId] ?? '#e8c87a' : '#e8c87a';
  }

  private renderLedgerSection(title: string, items: { kind: string; text: string }[]): string {
    const rows = items.slice(-6).map((item) => `
      <div class="mafia-ledger-row ${this.escape(String(item.kind))}">
        <span></span><p>${this.escape(item.text)}</p>
      </div>
    `).join('');
    return `
      <section class="mafia-ledger-section">
        <h3>${this.escape(title)}</h3>
        ${rows || '<div class="mafia-ledger-empty">No updates yet.</div>'}
      </section>
    `;
  }
}
