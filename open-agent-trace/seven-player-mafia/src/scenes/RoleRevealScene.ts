import Phaser from 'phaser';
import { newEngine } from '../game/MafiaEngine';
import type { Role } from '../game/MafiaTypes';
import * as utils from '../utils';

/**
 * RoleRevealScene — deals hidden roles, reveals the human's own card (and Mafia
 * partner when applicable), then transitions to the main table.
 */
export class RoleRevealScene extends Phaser.Scene {
  private bgm?: Phaser.Sound.BaseSound;
  private uiContainer?: Phaser.GameObjects.DOMElement;
  private step = 0;
  private engine!: ReturnType<typeof newEngine>;

  constructor() {
    super({ key: 'RoleRevealScene' });
  }

  create(): void {
    this.step = 0;
    this.engine = newEngine();

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
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x000000, 0.35);
    } else {
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x14101c, 1);
    }
  }

  private cardImg?: Phaser.GameObjects.Image;
  private createCardArt(): void {
    const cam = this.cameras.main;
    const key = utils.textureExists(this, 'role_card_back') ? 'role_card_back' : '';
    if (key) {
      this.cardImg = this.add.image(cam.width / 2, cam.height / 2 - 40, key);
      const maxH = 420;
      const scale = maxH / this.cardImg.height;
      this.cardImg.setScale(scale);
    } else {
      this.cardImg = undefined;
    }
  }

  private roleCardKey(role: Role): string {
    const map: Record<Role, string> = {
      Mafia: 'role_card_mafia',
      Detective: 'role_card_detective',
      Doctor: 'role_card_doctor',
      Villager: 'role_card_villager',
    };
    const k = map[role];
    return utils.textureExists(this, k) ? k : 'role_card_back';
  }

  private playMusic(): void {
    this.bgm = utils.safeAddSound(this, 'role_reveal_bgm', { volume: 0.35, loop: true });
    this.bgm?.play();
  }

  private flavorFor(role: Role): string {
    switch (role) {
      case 'Mafia': {
        const partners = this.engine.humanMafiaPartnerIds
          .map((id) => this.engine.profiles[id].name)
          .join(' and ');
        return `You are MAFIA. Your partner is ${partners || 'unknown'}. Blend in, mislead the table, and survive the votes.`;
      }
      case 'Detective':
        return 'You are the DETECTIVE. Each night you may investigate one guest to learn if they are Mafia. Guard your secret.';
      case 'Doctor':
        return 'You are the DOCTOR. Each night you may protect one guest from the Mafia\u2019s blade. Choose wisely.';
      default:
        return 'You are a VILLAGER. You have no night power \u2014 only your wits, your voice, and your vote.';
    }
  }

  private createUI(): void {
    const html = `
      <div id="rr-root" class="fixed inset-0 z-[1000] font-retro pointer-events-none flex flex-col items-center justify-end pb-16" style="background:transparent;">
        <div id="rr-narration" class="pointer-events-auto text-center px-8 py-5 rounded-lg" style="max-width:920px; background:rgba(12,10,18,0.82); border:2px solid #6b5326; box-shadow:0 0 24px rgba(0,0,0,0.6);">
          <div id="rr-text" style="color:#e8dcc0; font-size:24px; line-height:1.5; text-shadow:2px 2px 0 #000;"></div>
          <div id="rr-hint" style="color:#b8443c; font-size:15px; margin-top:14px; letter-spacing:1px;">Click or press ENTER to continue</div>
        </div>
      </div>`;
    this.uiContainer = utils.initUIDom(this, html);

    this.input.keyboard?.on('keydown-ENTER', this.advance, this);
    this.input.keyboard?.on('keydown-SPACE', this.advance, this);
    this.input.on('pointerdown', this.advance, this);

    this.time.delayedCall(60, () => this.renderStep());
  }

  private setText(text: string, hint = 'Click or press ENTER to continue'): void {
    const el = document.getElementById('rr-text');
    const hintEl = document.getElementById('rr-hint');
    if (el) el.textContent = text;
    if (hintEl) hintEl.textContent = hint;
  }

  private advance(): void {
    this.step += 1;
    this.renderStep();
  }

  private renderStep(): void {
    const role = this.engine.humanRole;
    switch (this.step) {
      case 0:
        this.setText('Rain taps the windows of the old parlor. Seven guests take their seats around the midnight table.');
        break;
      case 1:
        utils.safeAddSound(this, 'click_sfx', { volume: 0.4 })?.play();
        this.setText('Among you, two carry knives behind their smiles. A sealed card waits at your place.');
        break;
      case 2:
        // Reveal the human's role card art.
        if (this.cardImg) {
          const key = this.roleCardKey(role);
          if (utils.textureExists(this, key)) {
            this.tweens.add({
              targets: this.cardImg,
              scaleX: 0,
              duration: 180,
              yoyo: true,
              onYoyo: () => this.cardImg?.setTexture(key),
            });
          }
        }
        this.engine.pushTimeline('Night', `You were dealt the role of ${role}.`);
        this.setText(this.flavorFor(role));
        break;
      case 3:
        this.setText('The lamps dim to a single amber glow. Decide how you will play tonight.', '');
        this.showChoices();
        return;
      case 4:
        this.setText('The first night begins. Listen closely \u2014 the truth hides in the dark.');
        utils.safeAddSound(this, 'night_sfx', { volume: 0.5 })?.play();
        break;
      default:
        this.finish();
        return;
    }
  }

  private showChoices(): void {
    const root = document.getElementById('rr-root');
    if (!root) return;
    const opts = ['Observe silently', 'Prepare to lead', 'Watch for contradictions'];
    const wrap = document.createElement('div');
    wrap.className = 'pointer-events-auto';
    wrap.style.cssText = 'display:flex; gap:14px; margin-top:18px; justify-content:center;';
    opts.forEach((label) => {
      const b = document.createElement('button');
      b.textContent = label;
      b.style.cssText =
        'cursor:pointer; padding:12px 18px; font-size:16px; color:#e8dcc0; background:rgba(40,30,20,0.9); border:2px solid #6b5326; border-radius:8px;';
      b.onmouseenter = () => (b.style.background = 'rgba(120,40,40,0.85)');
      b.onmouseleave = () => (b.style.background = 'rgba(40,30,20,0.9)');
      b.onclick = (e) => {
        e.stopPropagation();
        utils.safeAddSound(this, 'click_sfx', { volume: 0.4 })?.play();
        this.engine.pushTimeline('Night', `You chose to "${label}".`);
        wrap.remove();
        this.step = 4;
        this.renderStep();
      };
      wrap.appendChild(b);
    });
    document.getElementById('rr-narration')?.appendChild(wrap);
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
  }
}
