import { EVENTS } from '../core/events.js';

export class Key extends Phaser.Physics.Arcade.Sprite 
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
        this.scene.physics.world.enable(this);
        this.setTint(0x00FF00);
        this.setOrigin(0.5,1);
        this.body.setAllowGravity(false);
        this.body.setImmovable(true);

        this.pickUpKeySound = this.scene.sound.add('snd_pickUpKey', Phaser.Sound.BaseSound);

        // Me suscribo al evento de que el student está listo
        this.scene.events.once(
            EVENTS.STUDENT_READY,
            this.onStudentReady,
            this
        );
    }

    onStudentReady(_student)
    {
        this.scene.physics.add.overlap
        (
            _student,
            this,
            this.onStudentPickedUpKey,
            null,
            this                
        );     
    }
   
    onStudentPickedUpKey(_student,_key)
    {
        this.scene.events.emit(EVENTS.STUDENT_PICKUP_KEY, _student);
        this.pickUpKeySound.play({loop:false, volume: 0.5});
        this.destroy();    
    }
}