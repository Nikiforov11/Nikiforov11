import { EVENTS } from '../core/events.js';

export class Npc extends Phaser.Physics.Arcade.Sprite 
{
    /**
    * @param {Phaser.Scene} _scene   - escena en la que se instanciará
    * @param {number} _posX          - posición X del sprite
    * @param {number} _posY          - posición Y del sprite
    * @param {string} _texture       - key/spriteTag del spritesheet/atlas
    */
    constructor(_scene,_posX,_posY,_texture)
    { //instanciar el objeto
        super(_scene,_posX,_posY,_texture);
        // Añadir a la escena
        this.scene.add.existing(this);
        //Ajustamos el punto de pivote del npc para que no caiga
        this.setOrigin(.5,1);
        //Cargamos las animaciones
        this.anims.play("npc_idle",true); 
        
        //Le doy un color distintivo para diferenciarlo
        this.setTint(0xA4167F); //MagENTI
        
        //Defino una zona de interacción alrededor del NPC y le habilito físicas y un debugColor
        this.interactionZone = this.scene.add.zone(_posX, _posY, this.width + 20, this.height + 5)
        .setOrigin(0.5,1);        
        this.scene.physics.world.enable(this.interactionZone);
        this.interactionZone.body.setAllowGravity(false).setImmovable(true);
        this.interactionZone.body.debugBodyColor = 0xFFFFFF;

        // Me suscribo al evento de que el student está listo
        this.scene.events.once(
            EVENTS.STUDENT_READY,
            this.onStudentReady,
            this
        );

        //Inicializo variables de control para la interacción NPC<->Student
        this.student = null;
        this.isStudentInZone = false;
    }

    onStudentReady(_student)
    {
        this.student = _student;   
    }

    preUpdate(_time,_delta)
    {
        super.preUpdate(_time,_delta);

        if(!this.student) return;

        const isStudentInZoneNow = this.scene.physics.overlap(this.student, this.interactionZone);

        if(isStudentInZoneNow && !this.isStudentInZone)
        {
            //El student acaba de entrar en la zona de interacción
            this.scene.events.emit(EVENTS.NPC_STUDENT_IN_ZONE, this);
            this.isStudentInZone = true;
            this.interactionZone.body.debugBodyColor = 0x00FF00;
            console.log("Student in NPC zone");
        }
        else if(!isStudentInZoneNow && this.isStudentInZone)
        {
            //El student acaba de salir de la zona de interacción
            this.scene.events.emit(EVENTS.NPC_STUDENT_OUT_ZONE, this);
            this.isStudentInZone = false;
            this.interactionZone.body.debugBodyColor = 0xFFFFFF;
            console.log("Student out of NPC zone");
        }
    }
}