import Phaser from 'phaser';
import { BaseEndingScene, type EndingData } from './BaseEndingScene';
import { getEngine, PLAYER_ORDER } from '../game/MafiaEngine';
import type { MafiaEngine } from '../game/MafiaEngine';
import * as utils from '../utils';

/**
 * EndgameScene — reveals every hidden role, the winning faction, and the full
 * match timeline. Reading happens only here (legal endgame reveal).
 */
export class EndgameScene extends BaseEndingScene {
  private engine: MafiaEngine | null = null;

  constructor() {
    super({ key: 'EndgameScene' });
  }

  protected getEndingData(): EndingData {
    this.engine = getEngine();
    const winner = this.engine?.winner ?? 'town';
    const isVictory = this.engine ? this.engine.endingType === 'victory' : true;
    if (isVictory) {
      return {
        title: 'The Table Has Spoken',
        text: 'You survived the midnight game and uncovered the truth hidden beneath the candlelight.',
        type: 'victory',
        musicKey: 'endgame_bgm',
        stats: { Winner: winner === 'town' ? 'Town' : 'Mafia' },
      };
    }
    return {
      title: 'Midnight Belongs to the Guilty',
      text: 'The parlor falls silent as the wrong names are buried and the guilty inherit the table.',
      type: 'defeat',
      musicKey: 'endgame_bgm',
      stats: { Winner: winner === 'town' ? 'Town' : 'Mafia' },
    };
  }

  protected createBackground(): void {
    const cam = this.cameras.main;
    if (utils.textureExists(this, 'endgame_bg')) {
      const bg = this.add.image(cam.width / 2, cam.height / 2, 'endgame_bg');
      bg.setDisplaySize(cam.width, cam.height);
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x000010, 0.45);
    } else {
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x0a0e1a, 1);
    }
  }

  protected createEndingContent(): void {
    const cam = this.cameras.main;
    const d = this.endingData!;
    const victory = d.type === 'victory';
    const accent = victory ? '#e8c87a' : '#b8443c';

    this.add
      .text(cam.width / 2, 70, d.title, {
        fontFamily: 'monospace',
        fontSize: '52px',
        color: accent,
        stroke: '#000000',
        strokeThickness: 6,
        align: 'center',
      })
      .setOrigin(0.5);

    this.add
      .text(cam.width / 2, 132, d.text ?? '', {
        fontFamily: 'monospace',
        fontSize: '20px',
        color: '#d6d2c4',
        align: 'center',
        wordWrap: { width: 1000 },
      })
      .setOrigin(0.5);

    const winner = this.engine?.winner ?? 'town';
    this.add
      .text(cam.width / 2, 196, winner === 'town' ? 'TOWN WINS' : 'MAFIA WINS', {
        fontFamily: 'monospace',
        fontSize: '30px',
        color: winner === 'town' ? '#6fcf97' : '#eb5757',
        stroke: '#000000',
        strokeThickness: 4,
      })
      .setOrigin(0.5);

    this.renderRoleReveal();
  }

  private renderRoleReveal(): void {
    if (!this.engine) return;
    const cam = this.cameras.main;
    const cols = 7;
    const slotW = cam.width / cols;
    const y = 320;

    PLAYER_ORDER.forEach((id, i) => {
      const p = this.engine!.players[id];
      const prof = this.engine!.profiles[id];
      const x = slotW * i + slotW / 2;

      const portraitKey = p.alive
        ? `${prof.texturePrefix}_neutral`
        : `${prof.texturePrefix}_dead`;
      const fallback = `${prof.texturePrefix}_neutral`;
      const useKey = utils.textureExists(this, portraitKey)
        ? portraitKey
        : utils.textureExists(this, fallback)
          ? fallback
          : '';

      if (useKey) {
        const img = this.add.image(x, y, useKey);
        const maxH = 150;
        img.setScale(Math.min(maxH / img.height, (slotW - 16) / img.width));
        if (!p.alive) img.setTint(0x888899);
      } else {
        this.add.rectangle(x, y, slotW - 20, 150, prof.color, 0.5);
      }

      this.add
        .text(x, y + 90, prof.name, {
          fontFamily: 'monospace',
          fontSize: '18px',
          color: '#e8dcc0',
          stroke: '#000',
          strokeThickness: 3,
        })
        .setOrigin(0.5);

      const roleColor = p.role === 'Mafia' ? '#eb5757' : '#6fcf97';
      this.add
        .text(x, y + 114, p.role.toUpperCase(), {
          fontFamily: 'monospace',
          fontSize: '16px',
          color: roleColor,
          stroke: '#000',
          strokeThickness: 3,
        })
        .setOrigin(0.5);

      this.add
        .text(x, y + 136, p.alive ? 'survived' : `fell D${p.diedOnDay}`, {
          fontFamily: 'monospace',
          fontSize: '13px',
          color: '#9a96a8',
        })
        .setOrigin(0.5);
    });
  }

  protected showResults(): void {
    if (!this.engine) return;
    const e = this.engine;
    const cam = this.cameras.main;

    const mafiaDown = e.deathHistory.filter((d) => d.role === 'Mafia').length;
    const townDown = e.deathHistory.filter((d) => d.role !== 'Mafia').length;

    const summaryLines = [
      `Days played: ${e.dayNumber}    Nights played: ${e.nightNumber}`,
      `Mafia eliminated: ${mafiaDown} / 2    Town lost: ${townDown}`,
    ];

    this.add
      .text(cam.width / 2, 500, summaryLines.join('\n'), {
        fontFamily: 'monospace',
        fontSize: '18px',
        color: '#e8c87a',
        align: 'center',
        lineSpacing: 6,
      })
      .setOrigin(0.5);

    // Timeline panel
    const panelX = cam.width / 2;
    const panelY = 560;
    const panelW = 1100;
    const panelH = 360;
    this.add
      .rectangle(panelX, panelY + panelH / 2, panelW, panelH, 0x0c0a12, 0.8)
      .setStrokeStyle(2, 0x6b5326);

    this.add
      .text(panelX, panelY + 16, 'THE NIGHT IN REVIEW', {
        fontFamily: 'monospace',
        fontSize: '18px',
        color: '#b8443c',
        stroke: '#000',
        strokeThickness: 3,
      })
      .setOrigin(0.5, 0);

    const entries = e.timeline.slice(-12);
    const text = entries
      .map((t) => `D${t.day} \u00b7 ${t.phase}: ${t.text}`)
      .join('\n');
    this.add.text(panelX - panelW / 2 + 24, panelY + 48, text || 'A quiet night.', {
      fontFamily: 'monospace',
      fontSize: '15px',
      color: '#d6d2c4',
      lineSpacing: 6,
      wordWrap: { width: panelW - 48 },
    });

    this.add
      .text(cam.width / 2, cam.height - 36, 'Click or press ENTER to return to the title', {
        fontFamily: 'monospace',
        fontSize: '18px',
        color: '#e8c87a',
        stroke: '#000',
        strokeThickness: 3,
      })
      .setOrigin(0.5);

    utils.safeAddSound(this, e.endingType === 'victory' ? 'victory_sfx' : 'damage_sfx', {
      volume: 0.5,
    })?.play();
  }

  protected onContinue(): void {
    this.scene.start('TitleScreen');
  }
}
