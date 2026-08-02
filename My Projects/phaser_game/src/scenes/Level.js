import { STUDENT, LEVEL, LEVEL_SIZE, SCALE } from "../core/constants.js";
import { Block } from '../entities/Block.js';
import { Button } from '../entities/Button.js';
import { Door } from '../entities/Door.js';
import { Key } from '../entities/Key.js';
import { Npc } from '../entities/Npc.js';
import { Potion } from '../entities/Potion.js';
import { Spike } from '../entities/Spike.js';
import { Stairs } from '../entities/Stairs.js';
import { Student } from '../entities/Student.js';

import { EVENTS } from '../core/events.js';

export class Level extends Phaser.Scene {
    constructor() {
        super({ key: 'level' });
    }

    preload() { //Carga assets en memoria
        this.cameras.main.setBackgroundColor('#000');
        this.load.setPath('assets/tiled/maps');
        this.load.tilemapTiledJSON('level' + LEVEL.LEVEL_ACTUAL, 'level' + LEVEL.LEVEL_ACTUAL + '.json');
    }

    create() { //Pinta assets en pantalla
        console.log('Creating level: ' + LEVEL.LEVEL_ACTUAL);

        if (!this.ambientLevel)
            this.ambientLevel = this.sound.add('snd_ambientLevel', Phaser.Sound.BaseSound);
        if (!this.ambientLevel.isPlaying)
            this.ambientLevel.play({ loop: true, volume: 0.05 });

        //Limpiamos todos los eventos zombies
        //this.removeZombieEvents();

        //Pintamos el nivel
        //Cargo el JSON
        this.map = this.make.tilemap({ key: 'level' + LEVEL.LEVEL_ACTUAL });
        //Cargo los tilesets
        // IMPORTANTE: el primer argumento debe coincidir con el "Nombre del tileset" en Tiled.
        // El segundo argumento es la 'key' del asset cargado con this.load.image(...), que cambiamos
        // por el tileset_object del paso previo
        // Si coinciden, puedo dejar sólo 1
        const tileset = this.map.addTilesetImage('ts-monochrome_tilemap_transparent');
        //Pinto las CAPAS/LAYERS
        this.map.createLayer('layer_bg_details', tileset);
        this.map.createLayer('layer_walls', tileset);
        this.map.createLayer('layer_platforms', tileset);
        this.map.createLayer('layer_fg_details', tileset);
        //this.map.createLayer('layer_ui',tileset);
        //Activo la capa de colisiones
        this.collisions = this.map.createLayer('layer_collisions', tileset)
            .setVisible(false)
            .setActive(true);
        //Defino con qué se colisiona en la layer_collisions
        this.map.setCollisionByExclusion([-1], true, true, 'layer_collisions');

        //Activo las colsiones con las plataformas oneWay
        this.oneWayPlatforms = this.map.createLayer('layer_oneWay_platforms', tileset)
            .setVisible(false)
            .setActive(true);
        //Defino con qué se colisiona en la layer_oneWayPlatforms
        this.oneWayPlatforms.setCollisionByExclusion([-1], true);
        // Importante: que SOLO tenga cara superior (one-way real)
        this.oneWayPlatforms.forEachTile(t => {
            t.collideLeft = false;
            t.collideRight = false;
            t.collideDown = false;
            t.collideUp = true;   // solo desde arriba
        });


        //this.loadAnimations();

        //Creamos un grupo para las escaleras
        this.stairsGroup = this.physics.add.staticGroup();
        this.stairsCapTopGroup = this.physics.add.staticGroup();
        this.blocksGroup = this.physics.add.group();
        this.buttonsGroup = this.physics.add.group();

        //Leer e instanciar todos las entidades/entities del nivel
        this.entities = this.map.getObjectLayer('level_entities');
        //console.log(this.entities);
        this.entities.objects.forEach(function (entity) {
            //console.log(entity);
            switch (entity.type) {
                case 'Button':
                    let _button = new Button(this, entity.x, entity.y, entity.type.toLowerCase());
                    this.buttonsGroup.add(_button);
                    if (entity.properties.length > 1) {
                        _button.angle = entity.rotation;
                        _button.setButtonType(entity.properties[1].value);
                        _button.setButtonGroup(entity.properties[0].value);
                    } else {
                        _button.setButtonType(entity.properties[0].value);
                    }
                    break;
                case 'Block':
                    let _block = new Block(this, entity.x, entity.y, entity.type.toLowerCase());
                    this.blocksGroup.add(_block);
                    if (entity.properties.length > 1) {
                        _block.setBlockType(entity.properties[2].value);
                        _block.setBlockState(entity.properties[1].value);
                        _block.setBlockGroup(entity.properties[0].value);
                    } else {
                        _block.setBlockType(entity.properties[0].value);
                    }
                    break;
                case 'Door':
                    let _door = new Door(this, entity.x, entity.y, entity.type.toLowerCase());
                    _door.isExitDoor(entity.properties[0].value);
                    _door.isDoorOpen(entity.properties[1].value);
                    break;
                case 'Key':
                    this.key = new Key(this, entity.x, entity.y, entity.type.toLowerCase());
                    break;
                case 'Npc':
                    this.npc = new Npc(this, entity.x, entity.y, entity.type.toLowerCase());
                    break;
                case 'Potion':
                    let _potion = new Potion(this, entity.x, entity.y, entity.type.toLowerCase());
                    _potion.setPotionType(entity.properties[0].value);
                    break;
                case 'Spike':
                    let _spike = new Spike(this, entity.x, entity.y, entity.type.toLowerCase());
                    break;
                case 'Stairs':
                    let _stairs = new Stairs(this, entity.x, entity.y, entity.type.toLowerCase());
                    _stairs.setPieceType(entity.properties[0].value);
                    break;
                case 'Student':
                    this.student = new Student(this, entity.x, entity.y, entity.type.toLowerCase());
                    break;
                default:
                    console.log('Entidad no reconocida: ' + entity.type);
                    break;
            }
        }, this);

        this.events.emit(EVENTS.STUDENT_READY, this.student);

        this.setColliders();

        //this.scene.launch('hud');
        //No llamo simplemente a la escena HUD, sino que miro primero por si ya existe, por si vengo de un reset
        if (!this.scene.isActive('hud')) {
            this.scene.launch('hud');
        } else {
            this.scene.bringToTop('hud');
        }
        //Me aseguro de apuntar correctamente los listeners de la HUD a esta escena
        this.scene.get('hud').setListeners(this);

        this.dropThroughPlatform = false;
        this.input.keyboard.on('keydown-DOWN', () => {
            console.log("DOWN");
            this.dropThroughPlatform = true;
            this.time.delayedCall(200, () => this.dropThroughPlatform = false);
        });

        //Vamos a mapear la tecla R para reiniciar el nivel
        this.input.keyboard.on('keydown-R', () => {
            this.scene.restart();
        });

        //Vamos a mapear la tecla N para ir al siguiente nivel
        this.input.keyboard.on('keydown-N', () => {
            if (LEVEL.LEVEL_ACTUAL < LEVEL.MAX_LEVELS) LEVEL.LEVEL_ACTUAL++;
            this.scene.restart();
        });

        //Vamos a mapear la tecla B para ir al nivel previo
        this.input.keyboard.on('keydown-B', () => {
            if (LEVEL.LEVEL_ACTUAL > 1) LEVEL.LEVEL_ACTUAL--;
            this.scene.restart();
        });

        //Vamos a mapear la tecla E para que envie un evento de interacción
        this.input.keyboard.on('keydown-E', () => {
            this.events.emit(EVENTS.NPC_STUDENT_INTERACT, this.npc);
        });

        this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
            this.input.keyboard.off('keydown-R');
            this.input.keyboard.off('keydown-N');
            this.input.keyboard.off('keydown-B');
            this.input.keyboard.off('keydown-E');
            this.input.keyboard.off('keydown-Z');
            this.input.keyboard.off('keydown-DOWN');

            this.colliders?.forEach(c => c?.destroy());
            this.colliders = [];

            this.removeZombieEvents();
        });

        //Vamos a mapear la tecla Z para hacer un zoom de cámara y que la cámara siga al student. Si se pulsa otra vez, vuelve al zoom normal   
        //Forzamos el tamaño del mundo para que la cámara no se salga de los límites al hacer zoom  
        this.cameras.main.setBounds(0, 0, LEVEL_SIZE.WIDTH * SCALE, LEVEL_SIZE.HEIGHT * SCALE);

        this.zoomed = false;
        this.originalCameraPos = null;

        //Zoom sound
        this.zoomSound = this.sound.add('snd_zoom', Phaser.Sound.BaseSound);

        this.input.keyboard.on('keydown-Z', () => {
            const cam = this.cameras.main;
            this.zoomSound.play({ loop: false, volume: 0.5 });
            if (!this.zoomed) {
                this.originalCameraPos = { x: cam.scrollX, y: cam.scrollY };
                this.zoomed = true;
                cam.zoomTo(2, 500);
                cam.startFollow(this.student, true, 0.1, 0.1);
            }
            else {
                this.zoomed = false;
                cam.stopFollow();
                cam.zoomTo(1, 500);
                if (this.originalCameraPos) {
                    cam.pan
                        (
                            this.originalCameraPos.x + cam.width / 2,
                            this.originalCameraPos.y + cam.height / 2,
                            500
                        );
                }
            }
        });
    }

    setColliders() {
        this.colliders = [];

        // Student ↔ Tilemap
        this.colliders.push(
            this.physics.add.collider(this.student, this.collisions)
        );

        // Student ↔ oneWay Platforms
        this.colliders.push(
            this.physics.add.collider(
                this.student,
                this.oneWayPlatforms,
                null,
                (student, tile) => {
                    // Solo colisiona si el student está bajando (o quieto en Y)
                    //if (student.body.velocity.y < 0) return false;

                    //Miro si ha hecho dropThroughPlatform
                    if (this.dropThroughPlatform) return false;

                    //Si está subiendo, no colisiona
                    const tileTop = tile.getTop();
                    const studentBottom = student.body.bottom;
                    return studentBottom <= tileTop + 2;
                }
            )
        );

        // Blocks ↔ Tilemap
        this.colliders.push(
            this.physics.add.collider(this.blocksGroup, this.collisions)
        );

        // Buttons ↔ Tilemap
        this.colliders.push(
            this.physics.add.collider(this.buttonsGroup, this.collisions)
        );

        // Student ↔ Blocks (empujar)
        this.colliders.push(
            this.physics.add.collider(
                this.student,
                this.blocksGroup,
                (student, block) => block.pushBlock(student, block)
            )
        );
        // Student ↔ Buttons (presionar)
        this.colliders.push(
            this.physics.add.collider(
                this.student,
                this.buttonsGroup,
                (student, button) => {
                    button.interactButton(student, button);
                }
            )
        );

        // Blocks ↔ Blocks
        this.colliders.push(
            this.physics.add.collider(this.blocksGroup, this.blocksGroup)
        );

        // Blocks ↔ Buttons (push)
        this.colliders.push(
            this.physics.add.collider(
                this.blocksGroup,
                this.buttonsGroup,
                (block, button) => button.interactButtonByBlock(block, button)
            )
        );
    }

    removeZombieEvents() {
        // Limpieza anti-"zombies" tras scene.restart()
        this.events.off(EVENTS.STUDENT_READY);
        this.events.off(EVENTS.STUDENT_DIED);
        this.events.off(EVENTS.STUDENT_IN_OPENED_DOOR_ZONE);

        this.events.off(EVENTS.NPC_STUDENT_IN_ZONE);
        this.events.off(EVENTS.NPC_STUDENT_OUT_ZONE);
        this.events.off(EVENTS.NPC_STUDENT_INTERACT);
    }
} 