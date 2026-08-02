import { LEVEL, STUDENT } from '../core/constants.js';
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
        this.setOrigin(0.5,1);
        //Activamos las colisiones
        this.setColliders();
        //Cargamos las animaciones
        this.anims.play("student_idle",true);

        //Me aseguro que student está en la capa superior
        this.setDepth(10);
        
        //Ajusto los saltos máximos restantes
        this.remaining_jumps = STUDENT.MAX_JUMPS;

        //Ajusto el frame que mostará cuando esté en el aire (inicialmente estático)
        this.jump_frame = STUDENT.JUMP_STATIC_FRAME;

        //Inicilializo las partículas de polvo al correr/saltar/aterrizar
        this.initDusts();
        this.nextWalkDustTime = 0; // “cadencia” de pasos
        this.lastVelocityY = 0; // para medir la velocidad de caída

        //Control de Input
        this.cursors = this.scene.input.keyboard.createCursorKeys();
        this.autoMove = false;

        //Varibles para el control de escaleras
        this.onStairs = false;
        this.prevAllowGravity = this.body.allowGravity;
        this.stairsLockUntil = 0;
        this.wasOnCapTop = false;
        this.lastCapTopZone = null;
        this.solidCapTopZone = null;

        //Me inscribo al evento de que el student ha entrado en la zona de una puerta abierta
        this.scene.events.once(EVENTS.STUDENT_IN_OPENED_DOOR_ZONE, this.onStudentInOpenedDoorZone, this);
        //Me inscribo al evento de que el student ha muerto
        this.scene.events.once(EVENTS.STUDENT_DIED, this.onStudentDied, this);
    }

    canJump()
    {
        //Primero, miramos si justo acabo de pulsar el botón de salto (SPACE)
        if(!Phaser.Input.Keyboard.JustDown(this.cursors.space)) return;

        //Si aún me quedan saltos disponibles, puedo saltar (esté en el suelo o no)
        if(this.remaining_jumps>0)
        {
            this.emitJumpDust();
            //this.dustParticles.setVisible(false);
            this.remaining_jumps--;
            this.body.setVelocityY(STUDENT.JUMP_FORCE); 
            //Si estaba moviendose horizontalmente, cambio la animación a salto
            const movingInput = this.cursors.left.isDown || this.cursors.right.isDown;
            this.jump_frame = movingInput
            ? STUDENT.JUMP_MOVING_FRAME
            : STUDENT.JUMP_STATIC_FRAME;            
        }
    }

    initDusts()
    {
        //Defino la configuración del emisor de partículas de polvo
        const walkDustConfig = {
            frequency: -1, //No emito automáticamente
            speed: { min: 12, max: 35 },    
            gravityY: 50,
            scale: { start: 0.38, end: 0 },
            //alpha: { start: 1, end: 0 },
            lifespan: {min:110,max:300},
            //blendMode: 'ADD',
            quantity: 1
            //follow: this
        };

        this.walkParticles = this.scene.add.particles(0,0,'dust',walkDustConfig); 
        
        // Puff de salto (más pequeño)
        this.jumpParticles = this.scene.add.particles(0, 0, 'dust', {
            frequency: -1,          
            emitting: false,        
            lifespan: { min: 120, max: 240 },
            speed: { min: 30, max: 90 },
            angle: { min: 240, max: 300 },   // hacia arriba (270 = arriba)
            gravityY: 200,
            scale: { start: 0.55, end: 0 },
            //alpha: { start: 1, end: 0.5 },
            quantity: 100
        });

        // Puff de aterrizaje (más grande)
        this.landParticles = this.scene.add.particles(0, 0, 'dust', {
            frequency: -1,
            emitting: false,
            lifespan: { min: 160, max: 340 },
            speed: { min: 40, max: 140 },
            angle: { min: 220, max: 320 },   // más abierto
            gravityY: 500,
            scale: { start: 0.60, end: 0 },
            //alpha: { start: 0.7, end: 0 },
            quantity: 100
        });

        this.deathParticles = this.scene.add.particles(0, 0, 'dust', {
            frequency: -1,
            lifespan: { min: 250, max: 450 },
            speed: { min: 60, max: 120 },
            //gravityY: 900,
            scale: { start: 1.2, end: 0 },   // gordas
            //alpha: { start: 0.9, end: 0 },
            rotate: { min: 0, max: 360 },
            quantity: 1,
            tint: [0xffffff, 0xFF0000]
        });

        //Me mapeo la explosion de las particulas de muerte en la tecla M para testear  
        this.scene.input.keyboard.on('keydown-M', () =>
        {
            this.deathParticles.explode(30, this.x, this.y - 10);
        });

        this.deathParticles.setDepth(999);

    }

    onStudentDied(_student)
    {
        this.setVisible(false);
        this.deathParticles.explode(30, _student.x, _student.y - 10);

        this.scene.time.delayedCall(800, () =>
        {
            //Reinicio la escena
            this.scene.scene.restart();
        });
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

        //Calculamos la cadencia: cuando más rápido, más frecuencia
        const cadence = Phaser.Math.Clamp(130 - speedX*0.25, 45, 130);

        //Condiciones de salida: no está en el suelo o va muy despacio o no ha pasado el tiempo suficiente
        if (!this.isOnGround() || speedX < 40 || actualTime < this.nextWalkDustTime) return;
        
        //Emitimos las partículas de polvo
        //Actualizo la siguiente vez que puedo emitir partículas
        this.nextWalkDustTime = actualTime + cadence;
        
        //Oriento las partículas según la dirección del movimiento. Para ello, uso el flipX del sprite
        //const angle = this.flipX ? {min: -20, max: 20} : {min: 160, max: 200};
        const angle = this.flipX ? {min: 200, max: 240} : {min: 300, max: 340};
        this.walkParticles.setEmitterAngle(angle);
        //Calculamos la cantidad e partículas según la velocidad
        const quantity = speedX > 140 ? 8:3;

        //Emito las partículas
        this.walkParticles.explode(quantity, this.x, this.y);
    }

    emitJumpDust()
    {
        this.jumpParticles.explode(8, this.x, this.y);   // explode(count, x, y) :contentReference[oaicite:2]{index=2}
    }

    emitLandDust(fallSpeed)
    {
        // Más caída = más polvo
        const qty = Phaser.Math.Clamp(Math.floor(fallSpeed / 40), 10, 26);
        this.landParticles.explode(qty, this.x, this.y);
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
    
    onStudentInOpenedDoorZone(_door)
    {
        //Bloqueamos el control del student
        this.autoMove = true;
        this.setVelocity(0,0);
        
        this.scene.add.tween
        ({
            targets:this,
            duration:200,
            x: _door.x,
            y: _door.y,
            onComplete: () => 
            {
                this.scene.add.tween
                ({
                    targets:this,
                    duration:200,
                    alpha: 0,
                    onComplete: () => 
                    {
                        _door.setFrame(0); //Puerta cerrada
                        //Añadimos un delay antes de reiniciar la escena
                        this.scene.time.delayedCall(1000, () =>
                        {
                            //Incremento el nivel y reinicio la escena <- Salto de nivel
                            if(LEVEL.LEVEL_ACTUAL < LEVEL.MAX_LEVELS) LEVEL.LEVEL_ACTUAL++;
                            this.scene.scene.restart();
                        });
                    }
                }); 
            }
        });
    }

    preUpdate(time,delta)
    {
        super.preUpdate(time,delta);

        const onGround = this.isOnGround();

        const onStairsNow = this.scene.stairsGroup
        ? this.scene.physics.overlap(this, this.scene.stairsGroup)
        : false;

        const wantsToClimb = this.cursors.up.isDown || this.cursors.down.isDown;

        let capTopZoneNow = null;

        const wasOnCapTopPrev = this.wasOnCapTop;

        const onCapTopNow = this.scene.stairsCapTopGroup
        ? this.scene.physics.overlap(this, this.scene.stairsCapTopGroup,(_student, _capTopZone) =>
        {capTopZoneNow = _capTopZone;})
        : false;

        if(onCapTopNow && capTopZoneNow) this.lastCapTopZone = capTopZoneNow;

        this.wasOnCapTop = onCapTopNow;  

        //Salgo de la escalera si estaba en el “techo” del cap y ahora ya no lo estoy y voy hacia arriba 
        if(this.onStairs &&this.wasOnCapTopPrev && !onCapTopNow && this.body.velocity.y<0 && this.lastCapTopZone)
        {
            //1) Activamos el trigger de colisión del cap top zone anterior
            const zone = this.lastCapTopZone;
            zone.isSolid = true; //activo la colisión
            this.solidCapTopZone = zone;
            //2) Salgo de las escaleras
            this.onStairs = false;
            this.body.setAllowGravity(this.prevAllowGravity ?? true);
            this.body.setVelocityY(0);
            //3) Snap pequeño para quedar fuera del segmento de debajo
            this.y = zone.body.top - 1; // justo encima de la zona
            this.body.setVelocity(0,0);
            this.body.reset(this.x, this.y);
            // 4) lock para evitar re-enganche instantáneo
            this.stairsLockUntil = time + 200;
        }

        // Si estoy tocando el “techo” del cap mientras subo, salgo de la escalera
        if (onCapTopNow && this.cursors.up.isDown) {
            const zone = capTopZoneNow;
            if (zone) 
            { 
                zone.isSolid = true; 
                this.solidCapTopZone = zone; 
            }
            this.onStairs = false;
            this.body.setAllowGravity(this.prevAllowGravity ?? true);
            this.body.setVelocityY(0);
            //Snap pequeño para quedar fuera del segmento de debajo
            this.y = zone.body.top - 1; // justo encima de la zona
            this.body.setVelocity(0,0);
            this.body.reset(this.x, this.y);
            // bloqueo re-enganche un instante (evita parpadeos)
            this.stairsLockUntil = time + 200;
        }

        //1) Hago la gestión de entrada/salidad de escaleras
        //Primero, si no estoy en las escaleras, miro si quiero entrar
        if(!this.onStairs)
        {
            //Segundo, si estoy en las escaleras, miro si quiere subir/bajar
            if(onStairsNow && wantsToClimb && time >= this.stairsLockUntil)
            { 
                //Acabo de entrar en las escaleras y quiero subir/bajar
                this.onStairs = true;
                this.prevAllowGravity = this.body.allowGravity;
                //Desactivo la gravedad para poder controlar el movimiento vertical                
                this.body.setAllowGravity(false);
            }
        }else 
        {
            //Si ya estoy en las escaleras:
            //- Salgo si dejo de solaparme con ellas o si estoy en el suelo y no quiero subir/bajar
            if(!onStairsNow || (onGround && !wantsToClimb))
            {
                //Acabo de salir de las escaleras
                this.onStairs = false;
                //Restauro la gravedad previa al entrar en las escaleras o la fuerzo a true
                this.body.setAllowGravity(this.prevAllowGravity ?? true);
            }
        }
        
        //2) Controlo el movimiento horizontal, esté o no es las escaleras
        if(!this.autoMove)
        {
            if(this.cursors.left.isDown)
            { //ME MUEVO A LA IZQUIERDA
                this.body.setVelocityX(-STUDENT.SPEED); // ← negativo a la izquierda    
                this.setFlipX(true); //Oriento el sprite a la izquierda
                //Controlo que no esté ni en el aire ni en las escaleras para reproducir la animación de caminar
                if (onGround && !this.onStairs) this.anims.play('student_walk', true);  
            }else
            if(this.cursors.right.isDown)
            { //ME MUEVO A LA DERECHA
                this.body.setVelocityX(STUDENT.SPEED); 
                this.setFlipX(false); //Oriento el sprite a la derecha (por defecto)      
                //Controlo que no esté ni en el aire ni en las escaleras para reproducir la animación de caminar
                if (onGround && !this.onStairs) this.anims.play('student_walk', true);             
            }else
            {
                this.body.setVelocityX(0);
                //Controlo que no esté ni en el aire ni en las escaleras para reproducir la animación de idle  
                if (onGround && !this.onStairs) this.anims.play('student_idle', true);
            }
        }

        //3) Controlo el movimiento vertical sólo si estoy en las escaleras 
        //Control vertical en escaleras
        if(this.onStairs)
        {
            if(this.cursors.up.isDown)
            {
                this.body.setVelocityY(-STUDENT.CLIMB_SPEED); // ← negativo hacia arriba
                this.anims.play('student_climb',true);
            }else
            if(this.cursors.down.isDown)
            {
                this.body.setVelocityY(STUDENT.CLIMB_SPEED);
                this.anims.play('student_climb',true);
            }else
            {
                this.body.setVelocityY(0);
                this.anims.stop().setFrame(24);
            }
            return; //Salimos del preUpdate aquí para no mezclar con el salto
        }

        //4) Si llegamos hasta aquí, no estoy en las escaleras y puedo comprobar si student puede saltar 
        //Condición:(JustDown para detectar el instante de pulsación + remaining_jumps)
        //Si puede, salta
        this.canJump();

        //5) Cortamos el salto, con JustUp, para hacer un salto variable en base a la intensidad de pulsado
        if(Phaser.Input.Keyboard.JustUp(this.cursors.space) && this.body.velocity.y<0)
        {
            this.body.setVelocityY(this.body.velocity.y * 0.5);
        } 
        
        //6) Comprobamos si estoy en el suelo y no estoy subiendo para resetear los saltos
        if(this.isOnGround() && this.body.velocity.y>=0)
        {
            //Reseteamos los saltos disponibles
            this.remaining_jumps = STUDENT.MAX_JUMPS;            
        }
        
        //7) Comprobamos si acabo de aterrizar para emitir partículas de polvo
        if(this.isOnGround() && this.body.velocity.y === 0 && this.lastVelocityY > 80) 
        {
            this.emitLandDust(this.lastVelocityY);
        }
          
        // Guardar para el siguiente frame
         this.lastVelocityY = this.body.velocity.y;
        
        //8) Si estoy en el aire, pongo el frame de salto
        const inAir = !this.body.onFloor() && !this.onStairs;

        if(inAir)
        {
            //console.log('inAir', inAir, 'L', this.cursors.left.isDown, 'R', this.cursors.right.isDown, 'vx', this.body.velocity.x, 'frame', this.jump_frame);
            //Si estaba moviendose horizontalmente, cambio la animación a salto
            const movingInput = this.cursors.left.isDown || this.cursors.right.isDown;
            const movingVelX = Math.abs(this.body.velocity.x) > 5;
            this.jump_frame = ( movingInput || movingVelX)
            ? STUDENT.JUMP_MOVING_FRAME
            : STUDENT.JUMP_STATIC_FRAME;       
            this.anims.stop().setFrame(this.jump_frame);     
        }

        //Emitir partículas de polvo al correr  
        this.emitWalkDust(time);
    }
}