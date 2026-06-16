import Phaser from 'phaser';
import { screenSize, debugConfig, renderConfig } from './gameConfig.json';
import './styles/tailwind.css';

// Import scenes
import { Preloader } from './scenes/Preloader';
import { TitleScreen } from './scenes/TitleScreen';
import UIScene from './scenes/UIScene';
import { PauseUIScene } from './scenes/PauseUIScene';
import { VictoryUIScene } from './scenes/VictoryUIScene';
import { GameCompleteUIScene } from './scenes/GameCompleteUIScene';
import { GameOverUIScene } from './scenes/GameOverUIScene';

// Mafia game scenes
import { RoleRevealScene } from './scenes/RoleRevealScene';
import { MainTableScene } from './scenes/MainTableScene';
import { EndgameScene } from './scenes/EndgameScene';

const config: Phaser.Types.Core.GameConfig = {
  type: Phaser.CANVAS,
  width: screenSize.width.value,
  height: screenSize.height.value,
  backgroundColor: '#1a1a2e',
  parent: 'game-container',
  dom: {
    createContainer: true,
  },
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  physics: {
    default: 'arcade',
    arcade: {
      fps: 120,
      debug: debugConfig.debug.value,
      debugShowBody: debugConfig.debug.value,
      debugShowStaticBody: debugConfig.debug.value,
      debugShowVelocity: debugConfig.debug.value,
    },
  },
  pixelArt: renderConfig.pixelArt.value,
};

const game = new Phaser.Game(config);

// Strictly add scenes in the following order: Preloader, TitleScreen, level scenes, UI-related scenes

// Preloader: Load all game resources
game.scene.add('Preloader', Preloader, true);

// TitleScreen
game.scene.add('TitleScreen', TitleScreen);

// Mafia game scenes
game.scene.add('RoleRevealScene', RoleRevealScene);
game.scene.add('MainTableScene', MainTableScene);
game.scene.add('EndgameScene', EndgameScene);

// UI-related scenes
game.scene.add('UIScene', UIScene);
game.scene.add('PauseUIScene', PauseUIScene);
game.scene.add('VictoryUIScene', VictoryUIScene);
game.scene.add('GameCompleteUIScene', GameCompleteUIScene);
game.scene.add('GameOverUIScene', GameOverUIScene);
