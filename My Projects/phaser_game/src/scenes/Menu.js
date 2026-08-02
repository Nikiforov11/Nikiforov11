import { STUDENT, LEVEL, LEVEL_SIZE, SCALE } from "../core/constants.js";

export class Menu extends Phaser.Scene
{
    constructor()
    {
        super({key:'menu'});
    }

    preload()
    { //Carga assets en memoria
        this.cameras.main.setBackgroundColor('#000');
        
        this.load.setPath('assets/sprites/static');
        this.load.image('dust','spr_dustTrail.png');
        this.load.image('key','spr_key.png');
        this.load.image('potion','spr_potion.png');
        this.load.image('spike','spr_spike.png');
        
        this.load.setPath('assets/sprites/spritesheets');
        this.load.spritesheet('block','spr_block.png',
        {frameWidth:16,frameHeight:16});
        this.load.spritesheet('button','spr_button.png',
        {frameWidth:16,frameHeight:16});
        this.load.spritesheet('door','spr_door.png',
        {frameWidth:16,frameHeight:16});
        this.load.spritesheet('npc','spr_npc.png',
        {frameWidth:16,frameHeight:16});
        this.load.spritesheet('stairs','spr_stairs.png',
        {frameWidth:16,frameHeight:16});
        this.load.spritesheet('student','spr_student.png',
        {frameWidth:16,frameHeight:16});
        
        this.load.setPath('assets/tiled/tilesets');   
        this.load.image('ts-monochrome_tilemap_transparent','ts-monochrome_tilemap_transparent.png');

        this.load.setPath('assets/sprites/ui');
        this.load.image('interact','spr_interact.png');
        this.load.image('lvl1_msg','spr_level1_message.png');
        this.load.image('lvl2_msg','spr_level2_message.png');
        this.load.image('lvl3_msg','spr_level3_message.png');
        this.load.image('lvl4_msg','spr_level4_message.png');
        this.load.image('lvl6_msg','spr_level6_message.png');
                
        this.load.setPath('assets/fonts/');
        this.load.bitmapFont('LvlFont','DTM.png','DTM.fnt');
        this.load.bitmapFont('UItext','DSW15.png','DSW15.fnt');

        this.load.setPath('assets/sounds'); 
        this.load.audio('snd_ambientCredits','snd_ambientCredits.mp3');
        this.load.audio('snd_ambientLevel','snd_ambientLevel.mp3');
        this.load.audio('snd_ambientMainMenu','snd_ambientMainMenu.mp3');
        this.load.audio('snd_blockImpact','snd_blockImpact.wav');
        this.load.audio('snd_climb','snd_climb.mp3');
        this.load.audio('snd_closeDoor','snd_closeDoor.wav');
        this.load.audio('snd_dash','snd_dash.wav');
        this.load.audio('snd_death','snd_death.wav');
        this.load.audio('snd_destroyBlock','snd_destroyBlock.wav');
        this.load.audio('snd_findKey','snd_findKey.wav');
        this.load.audio('snd_grounded','snd_grounded.mp3');
        this.load.audio('snd_jump','snd_jump.wav');
        this.load.audio('snd_msg','snd_msg.wav');
        this.load.audio('snd_pickUpKey','snd_pickUpKey.wav');
        this.load.audio('snd_potion','snd_potion.wav');
        this.load.audio('snd_slideBlock','snd_slideBlock.wav');
        this.load.audio('snd_walk','snd_walk.wav');
        this.load.audio('snd_zoom','snd_zoom.wav');
    }

    create()
    { //Pinta assets en pantalla
        const wide = this.scale.width;
        const high = this.scale.height;
        
        this.loadAnimations();

        this.ambientMainMenu = this.sound.add('snd_ambientMainMenu', Phaser.Sound.BaseSound);
        this.ambientMainMenu.play({loop:true, volume: 0.5});

        this.clickButtonSound = this.sound.add('snd_grounded', Phaser.Sound.BaseSound);

        //Inicializo la UI
        this.titleText = this.add.bitmapText
        (
            wide/2,50,
            'LvlFont',
            'LITTLE THINGS',
            50  
        ).setOrigin(0.5);
        
        this.titleText = this.add.bitmapText
        (
            wide/2+120,80,
            'LvlFont',
            'Phaser Edition',
            20  
        ).setOrigin(1,0.5);

        
        //instanciamos el Student y el npc con las animacione idle
        this.student = this.add.sprite(wide/2 - 85, 39, 'student') 
        .setOrigin(0.5,1);
        this.student.anims.play('student_idle', true);
        this.npc = this.add.sprite(wide/2 + 60, 40, 'npc')
        .setOrigin(0.5,1)
        .setTint(0xA4167F); //MagENTI        
        this.npc.anims.play('npc_idle', true);

        //Creamos un cuadro que usaremos a modo de botón para iniciar el juego, con un texto dentro
        this.startButton = this.add.rectangle
        (
            wide/2, high - 100,
            150, 30,
            0x777777
        ).setOrigin(0.5);
        this.startText = this.add.bitmapText
        (
            wide/2, high - 102,
            'UItext',
            'START GAME',
            25  
        ).setOrigin(0.5);

        //Hacemos el botón interactivo
        this.startButton.setInteractive({useHandCursor: true})
        .on('pointerup', () => this.startGame())
        .on('pointerdown', () => 
        {
            this.startButton.setFillStyle(0x111111);
            this.startButton.setScale(0.95);
            this.clickButtonSound.play({loop:false, volume: 0.5});
        })
        .on('pointerover', () => 
        {
            this.startButton.setFillStyle(0xAAAAAA);
            this.startButton.setScale(1.05);
        })
        .on('pointerout', () => 
        {
            this.startButton.setFillStyle(0x777777);
            this.startButton.setScale(1);
        });  
    }

    startGame()
    {
        //Iniciamos la escena del nivel 1
        this.ambientMainMenu.stop();
        LEVEL.LEVEL_ACTUAL = 1;
        this.scene.start('level');
    }

    loadAnimations()
    {
        this.anims.create(
        {
            key: 'student_idle',
            frames:this.anims.generateFrameNumbers('student', 
            {start:0, end: 2}),
            frameRate: 3,
            repeat: -1
        });
        
        this.anims.create(
        {
            key: 'student_walk',
            frames:this.anims.generateFrameNumbers('student', 
            {start:12, end: 15}),
            frameRate: 10,
            repeat: -1
        });

        this.anims.create(
        {
            key: 'student_climb',
            frames:this.anims.generateFrameNumbers('student', 
            {start:24, end: 25}),
            frameRate: 4,
            repeat: -1
        });
        this.anims.create(
        {
            key: 'npc_idle',
            frames:this.anims.generateFrameNumbers('npc', { frames: [0, 5] }),
            frameRate: 4,
            repeat: -1
        });      
    }    
} 