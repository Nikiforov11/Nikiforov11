import { EVENTS } from '../core/events.js';

export class Stairs extends Phaser.Physics.Arcade.Sprite
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
        
        //Defino una zona de interacción en la escalera y le habilito físicas y un debugColor
        this.interactionZone = this.scene.add.zone(_posX, _posY, this.width, this.height)
        .setOrigin(0.5,1);        
        this.scene.physics.add.existing(this.interactionZone,true);
        //No necesito bloquear la gravedad pq la he creado con 'true' (cuerpo estático)
        //this.interactionZone.body.setAllowGravity(false).setImmovable(true);
        this.interactionZone.body.debugBodyColor = 0xFFFF00;

        //Añado la zona de interacción al contenedor de escaleras
        this.scene.stairsGroup.add(this.interactionZone);        
        // Me suscribo al evento de que el student está listo
        this.scene.events.once(
            EVENTS.STUDENT_READY,
            this.onStudentReady,
            this
        );
    }

    onStudentReady(_student)
    {
        this.scene.physics.add.collider
        (
            _student,
            this.scene.stairsCapTopGroup,
            null,
            (_student, _capTopZone) => _capTopZone.isSolid === true,
            this                
        );     
    }

    

    setPieceType(_pieceType)
    {
        switch(_pieceType)
        {
            case 'cap':
                this.setFrame(0);
                //Ajusto el body de la zona de interacción para que no sobresalga
                //la altura debe ser 9 pixeles desde la base del segmento
                this.interactionZone.body.setSize(this.width,9).setOffset(0,this.height - 9);
                //Añadimos una segunda zona para que actue de colisión en la parte superior de la escalera
                if(!this.capTopZone)
                {
                    const thickness = 4; //Grosor de la zona de colisión superior
                    this.capTopZone = this.scene.add.zone(this.x, this.y - this.height + 9, this.width, thickness)
                    .setOrigin(0.5,1);
                    this.scene.physics.add.existing(this.capTopZone,true);
                    this.capTopZone.body.debugBodyColor = 0xFF00FF;
                    this.capTopZone.isSolid = false; //empieza como trigger
                    this.capTopZone.isCapTop = true;
                    this.scene.stairsCapTopGroup.add(this.capTopZone);
                }
                break;
            case 'segment':
                this.setFrame(1);
                break;
            case 'base':
                this.setFrame(3);
                break;              
        }   
    }    
}