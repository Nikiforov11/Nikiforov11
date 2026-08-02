import { GAME_SIZE, PHYSICS, RENDER, SCALE } from './constants.js';

/**
 * Define y devuelve el objeto de configuración con el que instanciaremos el motor de Phaser.
 *
 * Esta función centraliza toda la configuración general del juego (tamaño, escala,
 * renderizado, físicas, etc.) utilizando las constantes definidas en core/constants.js.
 *
 * Recibe como parámetro un objeto que puede incluir un array de escenas.
 * De esta manera, la configuración se mantiene genérica y reutilizable:
 * distintas inicializaciones del juego pueden inyectar diferentes conjuntos de escenas
 * sin modificar este archivo.
 *
 * @param {object} [options={}] - Objeto de opciones para la configuración.
 * @param {Phaser.Scene[]} [options.scenes=[]] - Array de clases de escena a registrar.
 * @returns {Phaser.Types.Core.GameConfig} Configuración lista para pasar a new Phaser.Game().
 */

export function buildConfig({ scenes = [] } = {}) 
{
  return {
    type: Phaser.AUTO,
    width: GAME_SIZE.WIDTH,
    height: GAME_SIZE.HEIGHT,
    scene: scenes,
    render: { pixelArt: RENDER.PIXEL_ART },
    physics: {
      default: PHYSICS.TYPE,
      arcade: {
        gravity: { y: PHYSICS.GRAVITY },
        debug: PHYSICS.DEBUG,
      },
    },
    scale: {
      mode: Phaser.Scale[SCALE.MODE],
      autoCenter: Phaser.Scale[SCALE.AUTO_CENTER]
      //zoom: SCALE.ZOOM
    },
  };
}    