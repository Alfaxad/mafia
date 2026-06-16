import Phaser from 'phaser';
import { BackendClient } from '../game/BackendClient';
import * as utils from '../utils';

type TutorialStep = {
  title: string;
  body: string;
  role?: 'Mafia' | 'Detective' | 'Doctor' | 'Villager';
};

type AvatarOption = {
  id: string;
  name: string;
  asset: string;
  description: string;
};

const STEPS: TutorialStep[] = [
  {
    title: 'Welcome To the Town',
    body: 'Seven seats. One human. Six AI guests. Two Mafia hide inside the room while Town tries to expose them.',
  },
  {
    title: 'Mafia',
    role: 'Mafia',
    body: 'Two Mafia know each other. At night they choose a victim. By day they bluff, deflect, and survive the vote.',
  },
  {
    title: 'Detective',
    role: 'Detective',
    body: 'The Detective investigates one living player each night and privately learns whether that player is Mafia.',
  },
  {
    title: 'Doctor',
    role: 'Doctor',
    body: 'The Doctor protects one player each night. If the Mafia chose that same target, the kill fails.',
  },
  {
    title: 'Villagers',
    role: 'Villager',
    body: 'Villagers have no night power. Their tools are memory, pressure, defense, claims, and public votes.',
  },
  {
    title: 'How The Table Moves',
    body: 'Night actions resolve first. Dawn reports deaths. Day discussion is moderated. Accusations can put a player on the hot seat, then the living vote publicly.',
  },
  {
    title: 'Win Conditions',
    body: 'Town wins when both Mafia are eliminated. Mafia wins once they equal or outnumber the living Town.',
  },
];

const AVATARS: AvatarOption[] = [
  {
    id: 'player',
    name: 'AVATAR 1',
    asset: 'player_neutral',
    description: '',
  },
  {
    id: 'player_female_generated',
    name: 'AVATAR 2',
    asset: 'player_female_generated_neutral',
    description: '',
  },
];

const AVATAR_STEP = STEPS.length;
const SETUP_STEP = STEPS.length + 1;

export class TitleScreen extends Phaser.Scene {
  private uiContainer?: Phaser.GameObjects.DOMElement;
  private backgroundMusic?: Phaser.Sound.BaseSound;
  private client = new BackendClient();
  private step = 0;
  private selectedAvatarIndex = 0;
  private isSettingUp = false;
  private isReady = false;
  private playerName = 'TruthSeeker';
  private error = '';
  private keydownHandler?: (event: KeyboardEvent) => void;

  constructor() {
    super({ key: 'TitleScreen' });
  }

  create(): void {
    this.step = 0;
    this.isSettingUp = false;
    this.isReady = false;
    this.error = '';
    this.createBackground();
    this.backgroundMusic = utils.safeAddSound(this, 'role_reveal_bgm', { volume: 0.3, loop: true });
    this.backgroundMusic?.play();
    this.createDOMUI();
    this.bindKeys();
    this.events.once('shutdown', () => this.cleanup());
  }

  private createBackground(): void {
    const cam = this.cameras.main;
    if (utils.textureExists(this, 'role_reveal_bg')) {
      const bg = this.add.image(cam.width / 2, cam.height / 2, 'role_reveal_bg');
      bg.setDisplaySize(cam.width, cam.height);
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x000000, 0.34);
    } else {
      this.add.rectangle(cam.width / 2, cam.height / 2, cam.width, cam.height, 0x080604, 1);
    }
  }

  private createDOMUI(): void {
    const html = `
      <div id="title-root" class="fixed inset-0 z-[1000] pointer-events-auto" style="font-family: Georgia, 'Times New Roman', serif;">
        <div class="onboarding-shell">
          <div class="brand-lockup">
            <div class="hat">◆</div>
            <h1>MAFIA</h1>
          </div>
          <section class="tutorial-card">
            <div id="tutorial-role-card" class="role-card-slot"></div>
            <div class="copy">
              <p id="tutorial-kicker" class="kicker">Mafia Tutorial</p>
              <h2 id="tutorial-title"></h2>
              <p id="tutorial-body"></p>
              <div id="avatar-controls" class="avatar-controls" style="display:none;">
                <button id="avatar-prev" type="button" aria-label="Previous avatar">‹</button>
                <div>
                  <strong id="avatar-name"></strong>
                  <span id="avatar-description"></span>
                </div>
                <button id="avatar-next" type="button" aria-label="Next avatar">›</button>
              </div>
              <form id="setup-form" class="setup-form" style="display:none;">
                <label for="player-name-input">What should the table call you?</label>
                <input id="player-name-input" maxlength="32" autocomplete="name" spellcheck="false" value="${this.playerName}" />
                <label for="agent-mode-display">Game Mode</label>
                <input id="agent-mode-display" value="Online" readonly />
                <button id="setup-room-button" type="submit">Set up the room</button>
              </form>
              <p id="setup-status" class="setup-status"></p>
              <p id="tutorial-error" class="tutorial-error"></p>
            </div>
          </section>
          <footer class="title-footer">
            <button id="tutorial-back" type="button">Back</button>
            <span id="tutorial-progress"></span>
            <span id="tutorial-hint">Press Enter to continue</span>
          </footer>
        </div>
      </div>
      <style>
        .onboarding-shell{position:absolute;inset:0;display:grid;grid-template-rows:auto 1fr auto;align-items:center;justify-items:center;padding:40px;color:#f4dfbd;text-shadow:0 2px 0 #000;}
        .brand-lockup{text-align:center;}
        .brand-lockup h1{margin:0;font-size:72px;letter-spacing:6px;color:#e8c87a;text-shadow:0 0 24px rgba(175,54,42,.45),4px 4px 0 #000;}
        .hat{color:#b8443c;font-size:22px;margin-bottom:4px;}
        .tutorial-card{width:min(1040px,78vw);min-height:420px;display:grid;grid-template-columns:280px 1fr;gap:34px;align-items:center;padding:30px 36px;background:linear-gradient(135deg,rgba(13,11,15,.9),rgba(24,14,10,.82));border:2px solid #6b5326;box-shadow:0 0 38px rgba(0,0,0,.65), inset 0 0 32px rgba(110,76,38,.18);}
        .role-card-slot{height:360px;display:grid;place-items:center;overflow:hidden;}
        .role-card-slot img{max-width:230px;max-height:340px;filter:drop-shadow(0 18px 26px rgba(0,0,0,.75));}
        .role-card-slot img.avatar-preview{max-width:270px;max-height:360px;object-fit:contain;}
        .copy{font-family:monospace;min-width:0;}
        .kicker{margin:0 0 10px;color:#b8443c;text-transform:uppercase;letter-spacing:2px;font-size:14px;}
        .copy h2{font-family:Georgia,'Times New Roman',serif;font-size:42px;margin:0 0 14px;color:#e8c87a;line-height:1.05;}
        .copy p{font-size:18px;line-height:1.55;color:#e8dcc0;margin:0;max-width:68ch;}
        .avatar-controls{margin-top:24px;grid-template-columns:52px 1fr 52px;gap:14px;align-items:center;max-width:520px;}
        .avatar-controls button,.title-footer button{min-width:44px;min-height:44px;border:1px solid #6b5326;background:rgba(12,10,18,.88);color:#f4dfbd;font:700 24px monospace;cursor:pointer;}
        .avatar-controls button:hover,.title-footer button:hover{background:#3a2418;}
        .avatar-controls button:focus-visible,.title-footer button:focus-visible,.setup-form input:focus-visible,.setup-form button:focus-visible{outline:2px solid #e8c87a;outline-offset:3px;}
        .avatar-controls strong{display:block;color:#e8c87a;font-size:16px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;}
        .avatar-controls span{display:block;color:#d6d2c4;font-size:14px;line-height:1.45;}
        .setup-form{margin-top:24px;display:grid;grid-template-columns:1fr;gap:10px;max-width:460px;}
        .setup-form label{font-size:13px;text-transform:uppercase;color:#b99b70;letter-spacing:1px;}
        .setup-form input{height:42px;border:1px solid #6b5326;background:rgba(6,5,7,.88);color:#f4dfbd;padding:0 12px;font:16px monospace;outline:none;}
        .setup-form input[readonly]{color:#e8c87a;background:rgba(24,18,12,.78);}
        .setup-form button{height:48px;border:1px solid #a56a36;background:#4a1414;color:#f4dfbd;font:700 16px monospace;cursor:pointer;}
        .setup-form button:hover{background:#7a2828;}
        .setup-form button[disabled]{cursor:not-allowed;opacity:.65;}
        .setup-status{margin-top:16px!important;color:#e8c87a!important;font-size:16px!important;}
        .tutorial-error{margin-top:10px!important;color:#ff8c7d!important;font-size:14px!important;white-space:pre-wrap;}
        .title-footer{width:min(1040px,78vw);display:grid;grid-template-columns:120px 1fr 300px;align-items:center;color:#e8c87a;font:17px monospace;padding-bottom:34px;gap:14px;}
        #tutorial-progress{text-align:center;}
        #tutorial-hint{text-align:right;animation:titlePulse 1s alternate infinite;}
        @media (prefers-reduced-motion: reduce){#tutorial-hint{animation:none;}}
        @keyframes titlePulse{from{opacity:.45}to{opacity:1}}
      </style>
    `;
    this.uiContainer = utils.initUIDom(this, html);
    this.renderTutorial();
    this.bindDOMControls();
  }

  private bindDOMControls(): void {
    const form = document.getElementById('setup-form') as HTMLFormElement | null;
    form?.addEventListener('submit', (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (this.isReady) {
        this.playClick();
        this.startGame();
        return;
      }
      this.playClick();
      void this.setupRoom();
    });
    document.getElementById('player-name-input')?.addEventListener('input', (event) => {
      const target = event.target as HTMLInputElement;
      this.playerName = target.value.trim() || 'You';
    });
    document.getElementById('avatar-prev')?.addEventListener('click', (event) => {
      event.stopPropagation();
      this.playClick();
      this.rotateAvatar(-1);
    });
    document.getElementById('avatar-next')?.addEventListener('click', (event) => {
      event.stopPropagation();
      this.playClick();
      this.rotateAvatar(1);
    });
    document.getElementById('tutorial-back')?.addEventListener('click', (event) => {
      event.stopPropagation();
      if (this.step > 0 && !this.isSettingUp) this.playClick();
      this.goBack();
    });
  }

  private bindKeys(): void {
    this.keydownHandler = (event: KeyboardEvent) => {
      const active = document.activeElement;
      if (active instanceof HTMLInputElement && !active.readOnly) return;
      if (event.code === 'Escape') {
        event.preventDefault();
        if (this.step > 0 && !this.isSettingUp) this.playClick();
        this.goBack();
        return;
      }
      if (this.step === AVATAR_STEP && (event.code === 'ArrowLeft' || event.code === 'ArrowRight')) {
        event.preventDefault();
        this.playClick();
        this.rotateAvatar(event.code === 'ArrowLeft' ? -1 : 1);
        return;
      }
      if (event.code !== 'Enter' && event.code !== 'Space') return;
      event.preventDefault();
      if (this.isReady) {
        this.playClick();
        this.startGame();
      } else if (this.step < SETUP_STEP) {
        this.playClick();
        this.step += 1;
        this.renderTutorial();
      }
    };
    document.addEventListener('keydown', this.keydownHandler);
  }

  private get selectedAvatar(): AvatarOption {
    return AVATARS[this.selectedAvatarIndex] ?? AVATARS[0];
  }

  private rotateAvatar(delta: number): void {
    this.selectedAvatarIndex = (this.selectedAvatarIndex + delta + AVATARS.length) % AVATARS.length;
    this.renderTutorial();
  }

  private goBack(): void {
    if (this.isSettingUp) return;
    if (this.step > 0) {
      this.isReady = false;
      this.error = '';
      this.step -= 1;
      this.renderTutorial();
    }
  }

  private renderTutorial(): void {
    const avatarStep = this.step === AVATAR_STEP;
    const setup = this.step >= SETUP_STEP;
    const step = STEPS[Math.min(this.step, STEPS.length - 1)];
    const avatar = this.selectedAvatar;
    const title = document.getElementById('tutorial-title');
    const body = document.getElementById('tutorial-body');
    const kicker = document.getElementById('tutorial-kicker');
    const progress = document.getElementById('tutorial-progress');
    const hint = document.getElementById('tutorial-hint');
    const form = document.getElementById('setup-form') as HTMLFormElement | null;
    const avatarControls = document.getElementById('avatar-controls');
    const avatarName = document.getElementById('avatar-name');
    const avatarDescription = document.getElementById('avatar-description');
    const card = document.getElementById('tutorial-role-card');
    const status = document.getElementById('setup-status');
    const error = document.getElementById('tutorial-error');
    const back = document.getElementById('tutorial-back') as HTMLButtonElement | null;
    const setupButton = document.getElementById('setup-room-button') as HTMLButtonElement | null;

    if (title) title.textContent = setup ? 'Take Your Seat' : avatarStep ? 'Choose Your Face' : step.title;
    if (body) {
      body.textContent = setup
        ? 'The Moderator will let you in soon...'
        : avatarStep
          ? 'Pick the table portrait other players will see. Appearance never reveals your role.'
          : step.body;
    }
    if (kicker) kicker.textContent = setup ? 'Room Setup' : avatarStep ? 'Avatar Selection' : 'Mafia Tutorial';
    if (progress) progress.textContent = setup ? 'Online room check' : `${Math.min(this.step + 1, SETUP_STEP + 1)} / ${SETUP_STEP + 1}`;
    if (hint) hint.textContent = this.isReady ? 'READY - Press Enter to play' : setup ? 'Set up the room to continue' : 'Press Enter to continue';
    if (form) form.style.display = setup ? 'grid' : 'none';
    if (avatarControls) avatarControls.style.display = avatarStep ? 'grid' : 'none';
    if (avatarName) avatarName.textContent = avatar.name;
    if (avatarDescription) avatarDescription.textContent = avatar.description;
    if (back) {
      back.disabled = this.step === 0 || this.isSettingUp;
      back.style.visibility = this.step === 0 ? 'hidden' : 'visible';
    }
    if (setupButton) {
      setupButton.disabled = this.isSettingUp;
      setupButton.textContent = this.isSettingUp ? 'Setting up the room...' : this.isReady ? 'Ready' : 'Set up the room';
    }
    if (status) {
      status.textContent = this.isSettingUp
        ? 'Setting up the room..'
        : this.isReady
          ? 'Room ready. Roles are sealed.'
          : '';
    }
    if (error) error.textContent = this.error;
    if (card) {
      if (setup || avatarStep) {
        card.innerHTML = `<img class="avatar-preview" src="/assets/${avatar.asset}.png" alt="${avatar.name} avatar" />`;
      } else if (step.role) {
        card.innerHTML = `<img src="/assets/role_card_${step.role.toLowerCase()}.png" alt="${step.role} role card" />`;
      } else {
        card.innerHTML = '<img src="/assets/role_card_back.png" alt="Hidden role card" />';
      }
    }
  }

  private async setupRoom(): Promise<void> {
    if (this.isSettingUp) return;
    this.isSettingUp = true;
    this.isReady = false;
    this.error = '';
    this.renderTutorial();
    try {
      const ready = await this.client.ready('Online');
      window.__MAFIA_READY__ = ready;
      if (!ready.ready) {
        const failed = ready.checks.find((check) => !check.ready);
        throw new Error(failed?.error ? `${failed.name}: ${failed.error}` : 'Online services are not ready.');
      }
      const seedBytes = new Uint32Array(1);
      window.crypto?.getRandomValues(seedBytes);
      const seed = seedBytes[0] || Math.floor(Math.random() * 2_000_000_000) + 1;
      const game = await this.client.newGame({
        seed,
        humanName: this.playerName,
        humanRole: 'Random',
        agentMode: 'Online',
        humanAvatar: this.selectedAvatar.id,
      });
      window.__MAFIA_VIEW__ = game;
      window.__MAFIA_PLAYER_NAME__ = this.playerName;
      window.__MAFIA_AGENT_MODE__ = 'Online';
      window.__MAFIA_AVATAR_ID__ = this.selectedAvatar.id;
      this.isReady = true;
      utils.safeAddSound(this, 'correct_sfx', { volume: 0.45 })?.play();
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
      utils.safeAddSound(this, 'wrong_sfx', { volume: 0.35 })?.play();
    } finally {
      this.isSettingUp = false;
      this.renderTutorial();
    }
  }

  private startGame(): void {
    if (!this.isReady) return;
    this.cleanup();
    this.backgroundMusic?.stop();
    this.cameras.main.fadeOut(450, 0, 0, 0);
    this.time.delayedCall(450, () => this.scene.start('RoleRevealScene'));
  }

  private playClick(volume = 0.32): void {
    utils.safeAddSound(this, 'click_sfx', { volume })?.play();
  }

  private cleanup(): void {
    if (this.keydownHandler) document.removeEventListener('keydown', this.keydownHandler);
    this.uiContainer?.destroy();
  }
}
