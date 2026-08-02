/**
* Constantes globales del juego.
* No dependen de Phaser ni de instancias específicas.
* Son valores inmutables que describen el "mundo" del juego.
*/

export const GAME_SIZE = 
{
    WIDTH: 576,
    HEIGHT: 320
};

export const LEVEL = 
{
    LEVEL_ACTUAL: 1,
    MAX_LEVELS: 12
};

export const LEVEL_SIZE = 
{
    LEVEL1_WIDTH: 576,  // 36 * 16
    LEVEL1_HEIGHT: 320  // 20 * 16
};

export const PHYSICS = 
{
    TYPE:'arcade',
    GRAVITY: 900,
    DEBUG: true
};

export const STUDENT = 
{
    SPEED: 150,
    CLIMB_SPEED: 100,
    JUMP_FORCE: -300,
    DASH_FORCE: 400,
    MAX_JUMPS: 1,
    JUMP_STATIC_FRAME: 36,
    JUMP_MOVING_FRAME: 15,
    NEXT_DUST_TIME: 1000/4 //cada 250 ms
};

export const RENDER = 
{
    PIXEL_ART: true
};

export const SCALE = 
{
    MODE: 'FIT',                // Phaser.Scale.FIT
    AUTO_CENTER: 'CENTER_BOTH', // Phaser.Scale.CENTER_BOTH
    ZOOM: 1                     //Para pixelart: escala lógica x2 sin deformar
}