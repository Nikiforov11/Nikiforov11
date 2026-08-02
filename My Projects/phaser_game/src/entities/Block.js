import { EVENTS } from '../core/events.js';

export class Block extends Phaser.Physics.Arcade.Sprite 
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
        this.setOrigin(0.5,1);
        //this.body.setAllowGravity(true);
        //this.body.setImmovable(true);
        //this.canPush = false;
        this.isBeingPushed = false;
        //Evita que patine
        this.body.setDragX(3000);
        this.pushVelX =0;
        this.lastGrounded = false;
        this.airVelX = 0;


       //this.scene.physics.add.collider(this.scene.collisions,this);

        this.destroySound = this.scene.sound.add('snd_destroyBlock', Phaser.Sound.BaseSound);
        this.landSound = this.scene.sound.add('snd_blockImpact', Phaser.Sound.BaseSound);
        this.slideSound = this.scene.sound.add('snd_slideBlock', Phaser.Sound.BaseSound);

        // Me suscribo al evento de que el student está listo
       /*
        this.scene.events.once(
            EVENTS.STUDENT_READY,
            this.onStudentReady,
            this
        );
        */
        // Me suscribo al evento de que el boton se ha presionado
        this.scene.events.on(
            EVENTS.BUTTON_PRESSED,
            this.checkGroup,
            this
        );

        this.once(Phaser.GameObjects.Events.DESTROY, () => {
            this.scene?.events.off(EVENTS.BUTTON_PRESSED, this.checkGroup, this);
        });
    }

    /*
    onStudentReady(_student)
    {
        this.scene.physics.add.collider(
            _student, 
            this, 
            this.pushBlock, 
            null, 
            this
        );   
        
        this.scene.physics.add.collider
        (
            this.scene.blocksGroup,
            this                
        );
    }
    */

    pushBlock(_student, _block)
    {
        if(this.blockType=='toogle') return;
        
        if(_student.body.blocked.down && _block.body.blocked.up)
        {
            _block.body.setVelocityX(0);
            return;
        }

        const pushing = 
        (_student.body.touching.left && _block.body.touching.right) 
        || (_student.body.touching.right && _block.body.touching.left);

        if(pushing && Math.abs(_student.body.velocity.x)>5)
        {
            this.isBeingPushed=true;
            this.pushVelX = _student.body.velocity.x;
        }        
    }
    /*
    preUpdate(time, delta)
    {
        super.preUpdate(time, delta);

        if (this.blockType !== 'push') return;

        const groundedNow = this.body.blocked.down || this.body.onFloor() || this.body.touching.down;

        if (this.isBeingPushed)
        {
            if (this.pushVelX < 0 && this.body.touching.left)
            {
             this.body.setVelocityX(0);   
            }else if (this.pushVelX > 0 && this.body.touching.right)
            {
                this.body.setVelocityX(0);
            }else
            {
                this.body.setVelocityX(this.pushVelX);
            }
        }
        else
        {
            this.body.setVelocityX(0);            
        }

        // Reset cada frame: si no hay contacto este frame, no sigue moviéndose
        this.isBeingPushed = false;    
    }
    */

    preUpdate(time, delta)
    {
        super.preUpdate(time, delta);

        if (this.blockType !== 'push') return;

        const groundedNow = this.body.blocked.down || this.body.onFloor() || this.body.touching.down;

        const moving = Math.abs(this.body.velocity.x) > 10;

        // Si ACABO de despegar (antes estaba en suelo y ahora no)
        if (!groundedNow && this.lastGrounded)
        {
            // guardo la velocidad horizontal del momento
            this.airVelX = this.body.velocity.x;
        }

        // Mientras está en el aire, mantengo la velocidad X guardada
        if (!groundedNow)
        {
            this.body.setVelocityX(this.airVelX);
        }

        // Mientras está en el suelo, si lo empujan, se mueve con el empuje.
        // Si NO lo empujan, se frena (no "hielo").
        if (groundedNow)
        {
            if (this.isBeingPushed)
            {
                this.body.setVelocityX(this.pushVelX);
            }
            else
            {
                this.body.setVelocityX(0);
            }
        }

        // Si ACABO de aterrizar (antes no estaba en suelo y ahora sí)
        if (groundedNow && !this.lastGrounded)
        {
            // se para al aterrizar
            this.body.setVelocityX(0);

            // Reproduzco el sonido de impacto con el suelo, si no se está reproduciendo
            if (this.landSound && !this.landSound.isPlaying)
                this.landSound.play({ loop: false, volume: 0.5 });
        }

        const shouldSlideSound = this.isBeingPushed && groundedNow && moving;

        if (shouldSlideSound)
        {
            if (!this.slideSound.isPlaying)
                this.slideSound.play({ loop: true, volume: 0.35 });
        }
        else
        {
            if (this.slideSound.isPlaying)
                this.slideSound.pause(); // o stop()
        }

        this.lastGrounded = groundedNow;
        this.isBeingPushed = false;
    }

    checkGroup(_buttonGroup)
    {
        if(this.blockGroup === _buttonGroup && this.blockType === 'toogle')
        {
            console.log('Block group matched!');
            this.destroySound.play({loop:false, volume: 0.5});
            if(this.blockState)
            {
                this.setBlockState(false);
                  
                this.setFrame(2); //frame de bloque desactivado
                this.body.debugBodyColor = 0x00FF00; //cambiamos el color del body para debug a verde
                this.body.enable = false; //deshabilitamos el body para que no colisione
            }else
            {
                this.setBlockState(true);
                this.setFrame(1); //frame de bloque activado
                this.body.enable = true; //habilitamos el body para que colisione
            }
            
        }
    }

    setBlockGroup(_blockGroup)
    {
        this.blockGroup = _blockGroup;
        if(this.blockType==='toogle' && _blockGroup=='B')
        {
            this.setTint(0xFD4400);                     
        }         
    }

    setBlockState(_blockState)
    {
        this.blockState = _blockState;
        if(!this.blockState)
        {
            this.setFrame(2); //frame de bloque desactivado 
            this.body.enable = false; //deshabilitamos el body para que no colisione  
        }
    }

    setBlockGroup(_blockGroup)
    {
        this.blockGroup = _blockGroup;
        if(this.blockType==='toogle' && _blockGroup=='B')
        {
            this.setTint(0xFD4400);                     
        }         
    }

    setBlockType(_blockType)
    {
        this.blockType = _blockType;
        switch(this.blockType)
        {
            case 'toogle':
                this.setFrame(1); //frame de bloque toogle
                this.setTint(0xFEA300);
                this.body.setAllowGravity(false);
                this.setImmovable(true);
            break;
            case 'push':
                this.setFrame(0); //frame de bloque push
                this.setTint(0xFF00FF);
                this.body.setAllowGravity(true);
            break;              
        }          
    }
}