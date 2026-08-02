import { EVENTS } from '../core/events.js';

export class Door extends Phaser.Physics.Arcade.Sprite
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
        // Añadir a la escena y habilitar físicas
        this.scene.add.existing(this);
        this.setOrigin(.5,1);
        
        //Defino una zona de interacción alrededor de la puerta y le habilito físicas y un debugColor
        this.interactionZone = this.scene.add.zone(_posX, _posY, this.width + 30, this.height + 10)
        .setOrigin(0.5,1);        
        this.scene.physics.world.enable(this.interactionZone);
        this.interactionZone.body.setAllowGravity(false).setImmovable(true);
        this.interactionZone.body.debugBodyColor = 0x00FF00;

        // Me suscribo al evento de que el student está listo
        this.scene.events.once(
            EVENTS.STUDENT_READY,
            this.onStudentReady,
            this
        );
        // Me suscribo al evento de que el student ha recogido una llave
        this.scene.events.once(
            EVENTS.STUDENT_PICKUP_KEY,
            this.onStudentPickedUpKey,
            this
        );
    }

    onStudentPickedUpKey()
    {
        if(this.isExit)
        {
            this.isDoorOpen(true);
        }
    }

    onStudentReady(_student)
    {
        this.student = _student;

        this.scene.physics.add.overlap(
            this.student, 
            this.interactionZone, 
            this.onStudentInDoorZone,
            null,
            this
        );
    }

    onStudentInDoorZone()
    {
        if(this.isExit)
        {
            if(this.isOpen)
            {
                console.log("Student in open exit door zone");
                this.scene.events.emit(EVENTS.STUDENT_IN_OPENED_DOOR_ZONE, this);
            }else
            {
                this.scene.events.emit(EVENTS.STUDENT_FIND_KEY, this);
            }           
        }
    }
    
    isExitDoor(_isExit)
    {
        this.isExit=_isExit;
        this.setTint(_isExit ? 0x00FF00 : 0xFFFFFF);
    }

    isDoorOpen(_isOpen)
    {
        this.isOpen=_isOpen;
        this.setFrame(_isOpen ? 2 : 1);
        if(!this.isExit&&this.isOpen) this.setFrame(3);
    }    
}