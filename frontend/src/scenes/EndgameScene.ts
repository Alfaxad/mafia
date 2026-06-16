import Phaser from 'phaser';
import { actorName, seatTexturePrefix, type EventView, type MafiaGameView } from '../game/BackendClient';
import * as utils from '../utils';

export class EndgameScene extends Phaser.Scene {
  private view!: MafiaGameView;
  private bgm?: Phaser.Sound.BaseSound;
  private keydownHandler?: (event: KeyboardEvent) => void;

  constructor() {
    super({ key: 'EndgameScene' });
  }

  create(): void {
    const view = window.__MAFIA_VIEW__;
    if (!view) {
      this.scene.start('TitleScreen');
      return;
    }
    this.view = view;
    this.createBackground();
    this.createContent();
    this.bgm = utils.safeAddSound(this, 'endgame_bgm', { volume: 0.34, loop: true });
    this.bgm?.play();
    utils.safeAddSound(this, view.winner === view.human.team ? 'victory_sfx' : 'damage_sfx', { volume: 0.45 })?.play();
    this.keydownHandler = (event) => {
      if (event.code === 'Enter' || event.code === 'Space') this.restart();
    };
    document.addEventListener('keydown', this.keydownHandler);
    this.input.on('pointerdown', this.restart, this);
    this.events.once('shutdown', () => this.cleanup());
  }

  private createBackground(): void {
    const cam = this.cameras.main;
    if (utils.textureExists(this, 'endgame_bg')) {
      const bg = this.add.image(cam.width / 2, cam.height / 2, 'endgame_bg');
      bg.setDisplaySize(cam.width, cam.height);
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x000000, 0.48);
    } else {
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x070504, 1);
    }
  }

  private createContent(): void {
    const cam = this.cameras.main;
    const townWon = this.view.winner === 'town';
    const playerWon = this.view.winner === this.view.human.team;
    this.add.text(cam.width / 2, 58, townWon ? 'THE TRUTH EMERGES' : 'THE SHADOWS PREVAIL', {
      fontFamily: 'Georgia',
      fontSize: '52px',
      color: townWon ? '#e8c87a' : '#eb5757',
      stroke: '#000',
      strokeThickness: 6,
    }).setOrigin(0.5);
    this.add.text(cam.width / 2, 112, playerWon ? 'You survived on the winning side.' : 'The table moved against your side.', {
      fontFamily: 'monospace',
      fontSize: '18px',
      color: '#d6d2c4',
    }).setOrigin(0.5);
    this.add.text(155, 90, `Winner: ${(this.view.winner ?? 'unknown').toUpperCase()}`, {
      fontFamily: 'monospace',
      fontSize: '18px',
      color: playerWon ? '#6fcf97' : '#eb5757',
    }).setOrigin(0.5);

    this.renderRoles();
    this.renderSummary();
    this.renderTimeline();
    this.add.text(cam.width / 2, cam.height - 34, 'Click or press ENTER to return to play again', {
      fontFamily: 'monospace',
      fontSize: '17px',
      color: '#e8c87a',
      stroke: '#000',
      strokeThickness: 3,
    }).setOrigin(0.5);
  }

  private renderRoles(): void {
    const startX = 164;
    const gap = 202;
    const y = 280;
    this.view.players.forEach((player, i) => {
      const x = startX + i * gap;
      const prefix = this.texturePrefixFor(player.id);
      const key = player.alive ? `${prefix}_neutral` : `${prefix}_dead`;
      const fallback = `${prefix}_neutral`;
      const useKey = utils.textureExists(this, key) ? key : utils.textureExists(this, fallback) ? fallback : '';
      this.add.rectangle(x, y + 50, 160, 260, 0x0c0a12, 0.78).setStrokeStyle(2, 0x6b5326);
      if (useKey) {
        const img = this.add.image(x, y - 4, useKey);
        img.setScale(Math.min(130 / img.height, 132 / img.width));
        if (!player.alive) img.setTint(0x8b8791);
      } else {
        this.add.rectangle(x, y - 4, 112, 130, 0x3a2418, 0.8);
      }
      this.add.text(x, y + 86, player.isHuman ? `${player.name} (You)` : player.name, {
        fontFamily: 'monospace',
        fontSize: '15px',
        color: '#e8dcc0',
        stroke: '#000',
        strokeThickness: 3,
      }).setOrigin(0.5);
      this.add.text(x, y + 112, String(player.role ?? 'Unknown').toUpperCase(), {
        fontFamily: 'monospace',
        fontSize: '14px',
        color: player.role === 'Mafia' ? '#eb5757' : '#6fcf97',
        stroke: '#000',
        strokeThickness: 3,
      }).setOrigin(0.5);
      this.add.text(x, y + 136, player.alive ? 'survived' : 'eliminated', {
        fontFamily: 'monospace',
        fontSize: '12px',
        color: player.alive ? '#6fcf97' : '#b8443c',
      }).setOrigin(0.5);
    });
  }

  private renderSummary(): void {
    const deaths = this.view.players.filter((p) => !p.alive);
    const mafiaDeaths = deaths.filter((p) => p.role === 'Mafia').length;
    const townDeaths = deaths.length - mafiaDeaths;
    this.add.rectangle(250, 662, 380, 314, 0x0c0a12, 0.82).setStrokeStyle(2, 0x6b5326);
    this.add.text(250, 526, 'MATCH SUMMARY', {
      fontFamily: 'Georgia',
      fontSize: '22px',
      color: '#e8c87a',
    }).setOrigin(0.5);
    const lines = [
      `Win condition: ${this.view.winner === 'town' ? 'All Mafia eliminated' : 'Mafia reached parity'}`,
      `Day reached: ${this.view.day}`,
      `Alive: ${this.view.aliveCount}/7`,
      `Mafia eliminated: ${mafiaDeaths}/2`,
      `Town lost: ${townDeaths}`,
      `Moderator turns: ${String(this.view.metrics?.moderator_turns ?? 'n/a')}`,
    ];
    this.add.text(82, 566, lines.join('\n'), {
      fontFamily: 'monospace',
      fontSize: '14px',
      color: '#d6d2c4',
      lineSpacing: 9,
      wordWrap: { width: 330 },
    });
  }

  private renderTimeline(): void {
    this.add.rectangle(930, 682, 920, 364, 0x0c0a12, 0.82).setStrokeStyle(2, 0x6b5326);
    this.add.text(930, 526, 'REPLAY TIMELINE', {
      fontFamily: 'Georgia',
      fontSize: '22px',
      color: '#e8c87a',
    }).setOrigin(0.5);
    const important = this.view.events
      .filter((event) => ['dawn_announced', 'player_eliminated', 'vote_resolved', 'vote_tied', 'game_over', 'doctor_save', 'investigation_result'].includes(event.type))
      .slice(-12)
      .map((event) => this.timelineLine(event));
    this.add.text(500, 566, important.join('\n') || 'No major events recorded.', {
      fontFamily: 'monospace',
      fontSize: '14px',
      color: '#d6d2c4',
      lineSpacing: 8,
      wordWrap: { width: 830 },
    });
  }

  private timelineLine(event: EventView): string {
    if (event.type === 'dawn_announced') return `D${event.day} Dawn: ${String(event.payload.message ?? '')}`;
    if (event.type === 'player_eliminated') return `D${event.day}: ${actorName(this.view, event.actor)} eliminated (${String(event.payload.revealed_role ?? 'role hidden')}).`;
    if (event.type === 'vote_resolved') return `D${event.day}: Vote eliminated ${actorName(this.view, String(event.payload.eliminated ?? ''))}.`;
    if (event.type === 'vote_tied') return `D${event.day}: Vote tied; no elimination.`;
    if (event.type === 'doctor_save') return `D${event.day}: Doctor save prevented a kill.`;
    if (event.type === 'game_over') return `D${event.day}: ${String(event.payload.winner ?? '').toUpperCase()} wins.`;
    return `D${event.day}: ${event.type}`;
  }

  private restart(): void {
    utils.safeAddSound(this, 'click_sfx', { volume: 0.34 })?.play();
    this.cleanup();
    window.__MAFIA_VIEW__ = undefined;
    window.__MAFIA_READY__ = undefined;
    window.__MAFIA_AGENT_MODE__ = undefined;
    window.__MAFIA_PLAYER_NAME__ = undefined;
    window.__MAFIA_AVATAR_ID__ = undefined;
    window.location.replace(`${window.location.origin}${window.location.pathname}?newGame=${Date.now()}`);
  }

  private cleanup(): void {
    this.bgm?.stop();
    if (this.keydownHandler) document.removeEventListener('keydown', this.keydownHandler);
    this.input.off('pointerdown', this.restart, this);
  }

  private texturePrefixFor(playerId: string): string {
    if (playerId === this.view.human.id) {
      return window.__MAFIA_AVATAR_ID__ ?? this.view.humanAvatar ?? 'player';
    }
    return seatTexturePrefix[playerId] ?? 'player';
  }
}
