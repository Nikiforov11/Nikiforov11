import { EVENTS } from '../core/events.js';

export class Button extends Phaser.Physics.Arcade.Sprite 
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
        this.setTint(0xFF0000);
        this.setOrigin(0.5,1);
        this.setFrame(5); //frame de botón sin presionar
        this.body.setSize(this.width, this.height - 4).setOffset(0,4); //ajustamos el tamaño del body para que no incluya la parte inferior del botón  
        this.body.setAllowGravity(false);
        this.body.setImmovable(true);
        this.pressed = false;

        // Me suscribo al evento de que el student está listo
        /*
        this.scene.events.once(
            EVENTS.STUDENT_READY,
            this.onStudentReady,
            this
        );
        */
    }
    /*
    onStudentReady(_student)
    {
        this.scene.physics.add.collider
        (
            _student,
            this,
            this.interactButton,
            null,
            this                
        );

        this.scene.physics.add.collider
        (
            this.scene.blocksGroup,
            this,
            this.interactButtonByBlock,
            null,
            this                
        );

    }
    */
    interactButtonByBlock(_block,_button)
    {
        // SEGURIDAD
        //Solo botones PUSH
        console.log('buttonType:'+this.buttonType);
        if (this.buttonType !== 'push') return;
        //Si ya está pulsado, fuera
        console.log('Pressed?:'+this.pressed);
        if (this.pressed) return;    
        // Solo bloques PUSH
         console.log('blockType?:'+_block.blockType);
        if (_block.blockType !== 'push') return;
        // Solo si coinciden los grupos
        console.log('blockGroup?:'+_block.blockGroup);
        console.log('buttonGroup?:'+this.buttonGroup);
        if (_block.blockGroup !== this.buttonGroup) return;
        //Solo activar si hay un empuje lateral (así evito que se active por caída encima)
        const lateralHit =
        (_block.body.touching.right && _button.body.touching.left)
        || (_block.body.touching.left  && _button.body.touching.right);
        if (!lateralHit) return;

        this.pressed = true;
        this.setFrame(3); //frame de botón presionado
        //ajustamos el tamaño del body para que no incluya la parte inferior del botón
        if(this.angle<0)
        {
            this.body.setSize(this.width-8, this.height).setOffset(0,6);    
        }else if(this.angle>0)
        {
            this.body.setSize(this.width-8, this.height).setOffset(8,6);
        }
        this.scene.events.emit(EVENTS.BUTTON_PRESSED, this.buttonGroup);
    }
   
    interactButton(_student,_button)
    {
        console.log('Student vs button!');
        console.log('buttonType:'+this.buttonType);
        console.log('Pressed?:'+this.pressed);
        // SEGURIDAD
        //Solo botones STOMP    
        if(this.buttonType !== 'stomp' || this.pressed) return;
        
        console.log('Student stomped the button!');
        if(this.angle<0)
        {
            console.log('touching left?:'+this.body.touching.left);
            if(this.body.touching.left)
            {
                this.body.setSize(this.width-8, this.height).setOffset(0,6);    
            }
            
        }else if(this.angle>0)
        {
            console.log('touching right?:'+this.body.touching.right);
            if(this.body.touching.right)
            {
                this.body.setSize(this.width-8, this.height).setOffset(8,6);
            }
            
        } else if(this.angle===0)
        {
            console.log('touching up?:'+this.body.touching.up); 
            if(this.body.touching.up)
            {
                this.body.setSize(this.width, this.height - 8).setOffset(0,8); //ajustamos el tamaño del body para que no incluya la parte inferior del botón
            }
        }

                   
        console.log('Button pressed!');
        this.pressed = true;
        this.setFrame(3); //frame de botón presionado
        this.scene.events.emit(EVENTS.BUTTON_PRESSED, this.buttonGroup);
    }

    setButtonGroup(_buttonGroup)
    {
        this.buttonGroup = _buttonGroup;                  
    }

    setButtonType(_buttonType)
    {
        this.buttonType = _buttonType;
        this.body.setImmovable(true);
        this.body.setAllowGravity(false);
        if(this.angle<0)
        {
            this.body.setSize(this.width-4, this.height).setOffset(-4,6);    
        }else if(this.angle>0)
        {
            this.body.setSize(this.width-4, this.height).setOffset(8,6);
        }
        switch(this.buttonType)
        {
            case 'stomp':
                this.setTint(0xFEA300);
            break;
            case 'push':
                this.setTint(0xFD4400);
            break;              
        }          
    }
}