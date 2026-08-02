import { LEVEL } from '../core/constants.js';
import { EVENTS } from '../core/events.js';

export class Hud extends Phaser.Scene {
    constructor() {
      super({ key: 'hud' });
    }
  
    preload()
    { //Carga assets en memoria
        /*
        this.load.setPath('assets/sprites/ui');
        this.load.image('interact','spr_interact.png');
        this.load.image('lvl1_msg','spr_level1_message.png');
                
        this.load.setPath('assets/fonts/');
        this.load.bitmapFont('LvlFont','DTM.png','DTM.fnt');
        this.load.bitmapFont('UItext','DSW12.png','DSW12.fnt');
        */
    }

    
    create()
    {
        const wide = this.scale.width;
        const high = this.scale.height;
        
        //Inicializo la UI
        this.interactUI = this.add.sprite(wide/2, high/2, 'interact')
        .setVisible(false)
        .setOrigin(0.5);
        // Guardar escala base para poder aplicarla multiplicada por el zoom de la cámara
        this.interactBaseScale = this.interactUI.scaleX || 1;
        this.UImsg = this.add.sprite(wide/2, high/2, 'lvl'+LEVEL.LEVEL_ACTUAL+'_msg')
        .setVisible(false)
        .setScale(.5)
        .setOrigin(0.5,1);
        
        this.LvlText = this.add.bitmapText(
        wide,high-22,
        'LvlFont',
        'Lvl '+LEVEL.LEVEL_ACTUAL,
        18  
        )
        .setOrigin(1,0);

        this.UIkey = this.add.image(22,high-22,'key').setOrigin(0,0).setVisible(false);

        this.isStudentInZone = false;

    }
    setListeners(_levelScene)
    {
        // 1) Miro si ya existía una levelScene asignada, lo que implica que vengo de un reset
        if(this.levelScene)
        {
            this.levelScene.events.off(EVENTS.NPC_STUDENT_IN_ZONE, this.onStudentInZone, this);
            this.levelScene.events.off(EVENTS.NPC_STUDENT_OUT_ZONE, this.onStudentLeaveZone,this);
            this.levelScene.events.off(EVENTS.NPC_STUDENT_INTERACT, this.onStudentInteractsNPC,this);
            this.levelScene.events.off(EVENTS.STUDENT_PICKUP_KEY, this.onStudentPickedUpKey,this);
            this.levelScene.events.off(EVENTS.STUDENT_FIND_KEY, this.onStudentFindKey,this);
            this.interactUI.setVisible(false);
            this.UImsg.setVisible(false);
            this.UIkey.setVisible(false);
            this.LvlText.text = 'Lvl '+LEVEL.LEVEL_ACTUAL;
            this.UImsg.setTexture('lvl'+LEVEL.LEVEL_ACTUAL+'_msg');
        }
        
        this.levelScene = _levelScene;
        
        this.levelScene.events.on(EVENTS.NPC_STUDENT_IN_ZONE, this.onStudentInZone, this);
        this.levelScene.events.on(EVENTS.NPC_STUDENT_OUT_ZONE, this.onStudentLeaveZone,this);
        this.levelScene.events.on(EVENTS.NPC_STUDENT_INTERACT, this.onStudentInteractsNPC,this);
        this.levelScene.events.on(EVENTS.STUDENT_PICKUP_KEY, this.onStudentPickedUpKey,this);
        this.levelScene.events.on(EVENTS.STUDENT_FIND_KEY, this.onStudentFindKey,this);  
        this.msgSound = this.levelScene.sound.add('snd_msg', Phaser.Sound.BaseSound); 
        this.findKeySound = this.levelScene.sound.add('snd_findKey', Phaser.Sound.BaseSound);
            
    }

    onStudentFindKey()
    {
        if(!this.findKeySound.isPlaying)
        {
            this.findKeySound.play({loop:false, volume: 0.5});
            this.add.tween
            ({
                targets:this.levelScene.key,
                duration:500,
                ease:'Sine.easeInOut',
                scale:1.5,
                yoyo:true,
                loop:true       
            });
        }        
    }

    onStudentPickedUpKey()
    {
        this.UIkey.setVisible(true);
    }

    onStudentInZone(_npc)
    {
        console.log("HUD: Student in NPC zone");
        //Se debe tener en cuenta que puede haber zoom, por lo que debo ajustar la posición de la UI
        const cam = this.levelScene.cameras.main;
        //Necesito la posición en pantalla del NPC
        console.log(_npc.x, _npc.y);
        console.log(cam.scrollX, cam.scrollY, cam.zoom, cam.x, cam.y);


        // Convertir coordenadas del mundo a coordenadas de pantalla considerando viewport y zoom
        const sx = (_npc.x - cam.worldView.x) * cam.zoom + cam.x;
        const sy = (_npc.y - cam.worldView.y) * cam.zoom + cam.y;
        const offset = 24 * cam.zoom;
        this.activeNpc = _npc;
        // Escalar el sprite del UI según el zoom de la cámara para mantener la relación visual
        this.interactUI.setScale(this.interactBaseScale * cam.zoom);
        this.interactUI.setPosition(sx, sy - offset);
        this.interactUI.setVisible(true);
        this.isStudentInZone = true;
    }

    onStudentInteractsNPC(_npc)
    {
        if(!this.isStudentInZone) return;
        
        const cam = this.levelScene.cameras.main;
        // Convert world coordinates to screen coordinates (viewport + zoom)
        const sx = (_npc.x - cam.worldView.x) * cam.zoom + cam.x;
        const sy = (_npc.y - cam.worldView.y) * cam.zoom + cam.y;
        const offset = 32 * cam.zoom;

        this.msgSound.play();

        if(this.UImsg.visible)
        {
            this.add.tween
            ({
                targets:this.UImsg,
                duration:1000,
                ease:'Sine.easeInOut',
                scale:0.5,
                x: sx,
                y: sy - offset,
                onComplete: () => 
                {
                    this.UImsg.setVisible(false);
                    this.UImsg.setScale(.5);
                }
            });
        }else
        {
            this.UImsg.setPosition(sx, sy - offset);
            this.UImsg.setVisible(true);
            
            this.add.tween
            ({
                targets:this.UImsg,
                duration:1000,
                ease:'Sine.easeInOut',
                scale:1,
                x: this.scale.width/2,
                y: this.scale.height/2
            });
        }
    }

    update()
    {
        if(!this.isStudentInZone || !this.levelScene || !this.activeNpc) return;
        const cam = this.levelScene.cameras.main;
        const sx = (this.activeNpc.x - cam.worldView.x) * cam.zoom + cam.x;
        const sy = (this.activeNpc.y - cam.worldView.y) * cam.zoom + cam.y;
        const offset = 24 * cam.zoom;
        // Actualizar posición y escala en tiempo real por si el jugador hace zoom/pan mientras está en zona
        this.interactUI.setScale(this.interactBaseScale * cam.zoom);
        this.interactUI.setPosition(sx, sy - offset);
    }

    onStudentLeaveZone(_npc)
    {
        console.log("HUD: Student out NPC zone");
        this.interactUI.setVisible(false);
        // Restaurar escala base cuando se vaya el NPC
        this.interactUI.setScale(this.interactBaseScale);
        this.UImsg.setVisible(false);
        this.activeNpc = null;
        this.isStudentInZone = false;
        this.UImsg.setScale(.5);
    }

}