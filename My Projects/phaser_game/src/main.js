//Cargamos el Intellisense
/// <reference path="./types/phaser.d.ts" />

//Importamos la configuración del motor
import { buildConfig } from './core/config.js';
//Importamos las escenas
import { Menu } from './scenes/Menu.js';
import { Level } from './scenes/Level.js';
import { Hud } from './ui/Hud.js';
import { Credits } from './scenes/Credits.js';

const game = new Phaser.Game
(
    buildConfig({
    // Orden en el que se registran/arrancan
    scenes: [
      Menu,    // el menú principal, donde se precarga todo
      Level,  // la escena de nivel
      Hud,     // se lanza luego en paralelo
      Credits
    ],
  })
);

