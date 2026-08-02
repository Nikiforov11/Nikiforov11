import { STUDENT } from '../core/constants.js';
import { EVENTS } from '../core/events.js';

export class Student extends Phaser.Physics.Arcade.Sprite 
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
        //Me guardo la posición inicial para resetearla en caso de muerte
        this.initialX = _posX;
        this.initialY = _posY;
        //Ajustamos el punto de pivote del student para que no caiga, alienándolo con la puerta
        this.setOrigin(.5,1);
        //Activamos las colisiones
        this.setColliders();
        //Cargamos las animaciones
        this.anims.play("student_idle",true);
        
        //Ajusto los saltos máximos restantes
        this.remaining_jumps = STUDENT.MAX_JUMPS;
        //Ajusto el frame que mostará cuando esté en el aire (inicialmente estático)
        this.jump_frame = STUDENT.JUMP_STATIC_FRAME;

        //Inicilializo las partículas de polvo al correr/saltar/aterrizar
        this.initDust();
        this.nextWalkDustTime = 0; // “cadencia” de pasos

        //Control de Input
        this.cursors = this.scene.input.keyboard.createCursorKeys();
    }

    initDust()
    {
        //Defino la configuración del emisor de partículas de polvo
        const dustConfig = {
            //frequency: -1, //No emito automáticamente
            speed: { min: 10, max: 20 },    
            gravityY: 20,
            scale: { start: 0.6, end: 0 },
            //alpha: { start: 1, end: 0 },
            lifespan: {min:50,max:300},
            //blendMode: 'ADD',
            quantity: 1,
            follow: this
        };

        this.dustParticles = this.scene.add.particles(0,0,'dust',dustConfig);        
    }

    isOnGround() 
    {
    // Combinación robusta con tilemaps
        return this.body.blocked.down || this.body.onFloor();
    }

    emitWalkDust(actualTime)
    {
        //Comprobamos la velocidad absoluta para evitar emitir partículas cuando está parado
        const speedX = Math.abs(this.body.velocity.x);

        //Condiciones de salida: no está en el suelo o va muy despacio o no ha pasado el tiempo suficiente
        if (!this.isOnGround() || speedX < 20 || actualTime < this.nextWalkDustTime) return;
        
        //Emitimos las partículas de polvo
        //Actualizo la siguiente vez que puedo emitir partículas
        this.nextWalkDustTime = actualTime + STUDENT.NEXT_DUST_TIME;
        //Posiciono el emisor de partículas en los pies del student
        this.dustParticles.setPosition(this.x, this.y);
        //Oriento las partículas según la dirección del movimiento. Para ello, uso el flipX del sprite
        //const angle = this.flipX ? {min: -20, max: 20} : {min: 160, max: 200};
        const angle = this.flipX ? {min: -30, max: -60} : {min: 30, max: 60};
        this.dustParticles.setAngle(angle);
        //Emito las partículas
        this.dustParticles.explode();
    }

    setColliders()
    {
        if (this.scene.collisions) { 
            //Por si hemos instanciado al Student antes de crear la capa layer_collisions
            this.scene.physics.add.collider
            (
                this,
                this.scene.collisions
            );    
        }
    }
    /*
    hitHero(_enemy,_hero)
    {
        if(this.body.touching.down && _enemy.body.touching.up)
        {
            if(--_enemy.health<=0)
            {
                _enemy.destroy();
                //Incrementar puntos
            }
            this.body.setVelocityY(HERO.JUMP_FORCE);     
        }else
        {
            //Decrementar el shiled del hero y comprobar gameover
            if(--this.health<0)
            {
                //go to scene 'gameover'
            }
            else
            {
                //actualizar la UI del shield
                console.log(this.health);
                this.scene.game.events.emit(EVENTS.HERO_DAMAGED,this.health);
                //resetear la escena
                this.body.reset(65,100);
                this.scene.cameras.main.shake(500,0.05);
                this.scene.cameras.main.flash(250,255,0,0);
            }
        }
    }
    */

    preUpdate(time,delta)
    {
        super.preUpdate(time,delta);

        if(this.cursors.left.isDown)
        { //ME MUEVO A LA IZQUIERDA
            this.body.setVelocityX(-STUDENT.SPEED); // ← negativo a la izquierda    
            this.setFlipX(true); 
            if (this.isOnGround()) this.anims.play('student_walk',true);
           this.dustParticles.setVisible(true);  
        }else
        if(this.cursors.right.isDown)
        { //ME MUEVO A LA DERECHA
            this.body.setVelocityX(STUDENT.SPEED); 
            this.setFlipX(false);      
            if (this.isOnGround()) this.anims.play('student_walk',true);
            this.dustParticles.setVisible(true);   
        }else
        {
            this.body.setVelocityX(0);  
            this.anims.play('student_idle',true); 
            this.dustParticles.setVisible(false);
        }
        
        if(this.cursors.space.isDown
           && this.body.onFloor()
           //&& this.body.blocked.down  
           && Phaser.Input.Keyboard.DownDuration(this.cursors.space,250))
           
        {
            this.body.setVelocityY(STUDENT.JUMP_FORCE);              
        } 
        
        if(!this.body.onFloor())
        {
            this.anims.stop().setFrame(36);
        }

        //Emitir partículas de polvo al correr  
        //this.emitWalkDust(time);
    }
}