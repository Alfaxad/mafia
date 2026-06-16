import Phaser from 'phaser';
import { actorName, roleCardKey, type MafiaGameView, type Role } from '../game/BackendClient';
import * as utils from '../utils';

export class RoleRevealScene extends Phaser.Scene {
  private bgm?: Phaser.Sound.BaseSound;
  private uiContainer?: Phaser.GameObjects.DOMElement;
  private cardImg?: Phaser.GameObjects.Image;
  private step = 0;
  private view!: MafiaGameView;

  constructor() {
    super({ key: 'RoleRevealScene' });
  }

  create(): void {
    const view = window.__MAFIA_VIEW__;
    if (!view) {
      this.scene.start('TitleScreen');
      return;
    }
    this.view = view;
    this.step = 0;
    this.createBackground();
    this.createCardArt();
    this.playMusic();
    this.createUI();
    this.cameras.main.fadeIn(500, 0, 0, 0);
    this.events.once('shutdown', () => this.cleanup());
  }

  private createBackground(): void {
    const cam = this.cameras.main;
    if (utils.textureExists(this, 'role_reveal_bg')) {
      const bg = this.add.image(cam.width / 2, cam.height / 2, 'role_reveal_bg');
      bg.setDisplaySize(cam.width, cam.height);
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x000000, 0.36);
    } else {
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x14101c, 1);
    }
  }

  private createCardArt(): void {
    const cam = this.cameras.main;
    const key = utils.textureExists(this, 'role_card_back') ? 'role_card_back' : '';
    if (!key) return;
    this.cardImg = this.add.image(cam.width / 2, cam.height / 2 - 42, key);
    this.cardImg.setScale(Math.min(420 / this.cardImg.height, 280 / this.cardImg.width));
    this.cardImg.setDepth(4);
  }

  private playMusic(): void {
    this.bgm = utils.safeAddSound(this, 'role_reveal_bgm', { volume: 0.35, loop: true });
    this.bgm?.play();
  }

  private createUI(): void {
    const html = `
      <div id="rr-root" class="fixed inset-0 z-[1000] pointer-events-none flex flex-col items-center justify-end pb-16" style="font-family:Georgia,'Times New Roman',serif;">
        <div id="rr-narration" class="pointer-events-auto text-center px-8 py-5" style="max-width:980px;background:rgba(12,10,18,.84);border:2px solid #6b5326;box-shadow:0 0 28px rgba(0,0,0,.7), inset 0 0 28px rgba(110,76,38,.16);">
          <div id="rr-text" style="color:#e8dcc0;font:24px/1.45 monospace;text-shadow:2px 2px 0 #000;"></div>
          <div id="rr-hint" style="color:#b8443c;font:15px monospace;margin-top:14px;letter-spacing:1px;">Click or press ENTER to continue</div>
        </div>
      </div>`;
    this.uiContainer = utils.initUIDom(this, html);
    this.input.keyboard?.on('keydown-ENTER', this.advance, this);
    this.input.keyboard?.on('keydown-SPACE', this.advance, this);
    this.input.on('pointerdown', this.advance, this);
    this.renderStep();
  }

  private roleFlavor(role: Role): string {
    if (role === 'Mafia') {
      const team = (this.view.human.privateInfo.mafia_team as string[] | undefined) ?? [];
      const partners = team.filter((id) => id !== this.view.human.id).map((id) => actorName(this.view, id));
      return `You are MAFIA. Your partner is ${partners.join(' and ') || 'hidden in the room'}. Blend in, mislead the table, and survive public votes.`;
    }
    if (role === 'Detective') return 'You are the DETECTIVE. Each night, investigate one living player and privately learn if they are Mafia.';
    if (role === 'Doctor') return 'You are the DOCTOR. Each night, protect one player. If Mafia choose that player, the kill fails.';
    return 'You are a VILLAGER. You have no night power, but your voice and vote can save the Town.';
  }

  private setText(text: string, hint = 'Click or press ENTER to continue'): void {
    const el = document.getElementById('rr-text');
    const hintEl = document.getElementById('rr-hint');
    if (el) el.textContent = text;
    if (hintEl) hintEl.textContent = hint;
  }

  private advance(): void {
    utils.safeAddSound(this, 'click_sfx', { volume: 0.34 })?.play();
    this.step += 1;
    this.renderStep();
  }

  private renderStep(): void {
    const role = this.view.human.role;
    switch (this.step) {
      case 0:
        this.setText(`${this.view.human.name}, your seat is ready. The moderator has sealed every role.`);
        break;
      case 1:
        this.setText('The table knows only what is public. Your card is yours alone.');
        break;
      case 2:
        if (this.cardImg) {
          const key = roleCardKey[role];
          this.tweens.add({
            targets: this.cardImg,
            scaleX: 0,
            duration: 170,
            yoyo: true,
            onYoyo: () => this.cardImg?.setTexture(key),
          });
        }
        this.setText(this.roleFlavor(role));
        break;
      case 3:
        this.setText('The first night begins. The moderator will keep the room moving without revealing private truth.');
        break;
      default:
        this.finish();
    }
  }

  private finish(): void {
    this.cleanup();
    this.cameras.main.fadeOut(450, 0, 0, 0);
    this.time.delayedCall(450, () => {
      this.bgm?.stop();
      this.scene.start('MainTableScene');
    });
  }

  private cleanup(): void {
    this.input.keyboard?.off('keydown-ENTER', this.advance, this);
    this.input.keyboard?.off('keydown-SPACE', this.advance, this);
    this.input.off('pointerdown', this.advance, this);
    this.uiContainer?.destroy();
  }
}
