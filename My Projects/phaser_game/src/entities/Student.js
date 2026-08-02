import { LEVEL, STUDENT } from '../core/constants.js';
import { EVENTS } from '../core/events.js';

export class Student extends Phaser.Physics.Arcade.Sprite {
    /**
    * @param {Phaser.Scene} _scene   - escena en la que se instanciará
    * @param {number} _posX          - posición X del sprite
    * @param {number} _posY          - posición Y del sprite
    * @param {string} _texture       - key/spriteTag del spritesheet/atlas
    */
    constructor(_scene, _posX, _posY, _texture) { //instanciar el objeto
        super(_scene, _posX, _posY, _texture);
        // Añadir a la escena y habilitar físicas
        this.scene.add.existing(this);
        this.scene.physics.world.enable(this);
        //Me guardo la posición inicial para resetearla en caso de muerte
        this.initialX = _posX;
        this.initialY = _posY;
        //Ajustamos el punto de pivote del student para que no caiga, alienándolo con la puerta
        this.setOrigin(0.5, 1);
        //Activamos las colisiones
        //this.setColliders();
        //Cargamos las animaciones
        this.anims.play("student_idle", true);

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

        /*
        this.dropThroughPlatform = false;
        this.scene.input.keyboard.on('keydown-DOWN', () => {
            console.log("DOWN");
            this.dropThroughPlatform = true;
            this.scene.time.delayedCall(200, () => this.dropThroughPlatform = false);
        });
        */

        //Control de Input
        this.cursors = this.scene.input.keyboard.createCursorKeys();
        this.autoMove = false;

        //Varibles para el control de escaleras
        this.onStairs = false;
        this.prevAllowGravity = this.body.allowGravity;

        //Cargo sonidos
        this.dashSound = this.scene.sound.add('snd_dash', Phaser.Sound.BaseSound);
        this.jumpSound = this.scene.sound.add('snd_jump', Phaser.Sound.BaseSound);
        this.groundedSound = this.scene.sound.add('snd_grounded', Phaser.Sound.BaseSound);
        this.deathSound = this.scene.sound.add('snd_death', Phaser.Sound.BaseSound);
        this.walkSound = this.scene.sound.add('snd_walk', Phaser.Sound.BaseSound);
        this.climbSound = this.scene.sound.add('snd_climb', Phaser.Sound.BaseSound);
        this.closeDoorSound = this.scene.sound.add('snd_closeDoor', Phaser.Sound.BaseSound);
        this.potionSound = this.scene.sound.add('snd_potion', Phaser.Sound.BaseSound);


        //Variable para saber si tiene el power-up de dash
        this.hasDash = false;
        this.dashKey = this.cursors.shift;
        this.lastMoveDir = 1; //1 derecha, -1 izquierda
        this.isDashing = false;
        this.dashVelX = 0;
        this.dashEndTime = 0;
        this.nextDashTime = 0;
        this.dashDuration = 140; //ms
        this.dashCooldown = 250; //ms

        //Me inscribo al evento de que el student ha entrado en la zona de una puerta abierta
        this.scene.events.once(EVENTS.STUDENT_IN_OPENED_DOOR_ZONE, this.onStudentInOpenedDoorZone, this);
        //Me inscribo al evento de que el student ha muerto
        this.scene.events.once(EVENTS.STUDENT_DIED, this.onStudentDied, this);
        //Me inscribo al evento de que el student recibe un power-up de dash
        this.scene.events.on(EVENTS.STUDENT_DASH, this.onDashEffect, this);
        //Me inscribo al evento de que el student recibe un power-up de doble salto
        this.scene.events.on(EVENTS.STUDENT_DOUBLE_JUMP, this.onDoubleJumpEffect, this);
        //Me inscribo al evento de que el student pierde los efectos de power-up
        this.scene.events.on(EVENTS.STUDENT_NO_EFFECT, this.onNoEffect, this);
    }

    onDashEffect(_student) {
        STUDENT.MAX_JUMPS = 1;
        this.hasDash = true;
        this.setTint(0x00FF00); //Lo teñimos de verde para indicar el dash
        if (!this.potionSound.isPlaying)
            this.potionSound.play({ loop: false, volume: 0.3 });
    }

    onDoubleJumpEffect(_student) {
        STUDENT.MAX_JUMPS = 2;
        this.hasDash = false;
        this.setTint(0x00FFFF); //Lo teñimos de cyan para indicar el doble salto
        if (!this.potionSound.isPlaying)
            this.potionSound.play({ loop: false, volume: 0.3 });
    }

    onNoEffect(_student) {
        STUDENT.MAX_JUMPS = 1;
        this.hasDash = false;
        this.setTint(0xFFFFFF); //Quito cualquier tintado
        if (!this.potionSound.isPlaying)
            this.potionSound.play({ loop: false, volume: 0.3 });
    }

    canJump() {
        //Primero, miramos si justo acabo de pulsar el botón de salto (SPACE)
        if (!Phaser.Input.Keyboard.JustDown(this.cursors.space)) return;

        //Si aún me quedan saltos disponibles, puedo saltar (esté en el suelo o no)
        if (this.remaining_jumps > 0) {
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

    initDusts() {
        //Defino la configuración del emisor de partículas de polvo
        const walkDustConfig = {
            frequency: -1, //No emito automáticamente
            speed: { min: 12, max: 35 },
            gravityY: 50,
            scale: { start: 0.38, end: 0 },
            //alpha: { start: 1, end: 0 },
            lifespan: { min: 110, max: 300 },
            //blendMode: 'ADD',
            quantity: 1
            //follow: this
        };

        this.walkParticles = this.scene.add.particles(0, 0, 'dust', walkDustConfig);

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

        this.dashParticles = this.scene.add.particles(0, 0, 'dust', {
            frequency: -1,
            lifespan: { min: 160, max: 340 },
            speed: { min: 40, max: 140 },
            gravityY: 0,
            scale: { start: 0.6, end: 0 },
            //alpha: { start: 0.9, end: 0 },
            angle: { min: 150, max: 210 },   // hacia arriba (270 = arriba)
            quantity: 1,
            tint: 0x00FF00
        });
        this.dashParticles.setDepth(999);

        //Me mapeo la explosion de las particulas de muerte en la tecla M para testear  
        this.scene.input.keyboard.on('keydown-M', () => {
            this.deathParticles.explode(30, this.x, this.y - 10);
        });

        this.deathParticles.setDepth(999);

    }

    onStudentDied(_student) {
        this.setVisible(false);
        this.deathParticles.explode(30, _student.x, _student.y - 10);
        this.deathSound.play({ loop: false, volume: 0.3 });

        this.scene.time.delayedCall(800, () => {
            //Reinicio la escena
            this.scene.scene.restart();
        });
    }

    isOnGround() {
        // 1. Check standard physics flags (good for tilemaps)
        if (this.body.blocked.down || this.body.onFloor() || this.body.touching.down) return true;

        // 2. Fallback: Geometric check for custom bodies (Blocks, Buttons)
        // We check a small rectangle just below the feet.
        const bodies = this.scene.physics.overlapRect(
            this.body.x + 2,                // Shrink slightly to avoid wall friction issues
            this.body.y + this.body.height,
            this.body.width - 4,
            4                               // Check 4 pixels deep
        );

        // Filter results
        for (let i = 0; i < bodies.length; i++) {
            const body = bodies[i];

            // Ignore ourselves
            if (body === this.body) continue;

            // If it's a solid body, we consider it ground
            if (!body.isSensor) return true;
        }

        return false;
    }

    emitWalkDust(actualTime) {
        //Comprobamos la velocidad absoluta para evitar emitir partículas cuando está parado
        const speedX = Math.abs(this.body.velocity.x);

        //Calculamos la cadencia: cuando más rápido, más frecuencia
        const cadence = Phaser.Math.Clamp(130 - speedX * 0.25, 45, 130);

        //Condiciones de salida: no está en el suelo o va muy despacio o no ha pasado el tiempo suficiente
        if (!this.isOnGround() || speedX < 40 || actualTime < this.nextWalkDustTime) return;

        //Emitimos las partículas de polvo
        //Actualizo la siguiente vez que puedo emitir partículas
        this.nextWalkDustTime = actualTime + cadence;

        //Oriento las partículas según la dirección del movimiento. Para ello, uso el flipX del sprite
        //const angle = this.flipX ? {min: -20, max: 20} : {min: 160, max: 200};
        const angle = this.flipX ? { min: 200, max: 240 } : { min: 300, max: 340 };
        this.walkParticles.setEmitterAngle(angle);
        //Calculamos la cantidad e partículas según la velocidad
        const quantity = speedX > 140 ? 8 : 3;

        //Emito las partículas
        this.walkParticles.explode(quantity, this.x, this.y);
        if (!this.walkSound.isPlaying) {
            this.walkSound.play({ loop: true, volume: 0.3 });
        }

    }

    emitJumpDust() {
        this.jumpParticles.explode(8, this.x, this.y);   // explode(count, x, y) :contentReference[oaicite:2]{index=2}
        this.jumpSound.play({ loop: false, volume: 0.5 });
    }

    emitLandDust(fallSpeed) {
        // Más caída = más polvo
        const qty = Phaser.Math.Clamp(Math.floor(fallSpeed / 40), 10, 26);
        this.landParticles.explode(qty, this.x, this.y);
        this.groundedSound.play({ loop: false, volume: 0.5 });
    }

    tryDash(time) {
        if (!this.hasDash) return;
        if (this.autoMove) return;
        if (!Phaser.Input.Keyboard.JustDown(this.dashKey)) return;
        if (time < this.nextDashTime) return;

        // Si estoy dashing ahora mismo, no vuelvas a lanzarlo
        if (this.isDashing) return;

        // Dirección: input > velocidad > última dirección recordada
        let dir = 0;

        if (this.cursors.left.isDown) dir = -1;
        else if (this.cursors.right.isDown) dir = 1;
        else if (Math.abs(this.body.velocity.x) > 10) dir = (this.body.velocity.x > 0) ? 1 : -1;
        else dir = this.lastMoveDir || (this.flipX ? -1 : 1);

        // Recordatorio para futuros dashes “en estático”
        this.lastMoveDir = dir;

        // Orientación sprite
        this.setFlipX(dir < 0);

        // Activo dash
        this.isDashing = true;
        this.dashVelX = dir * STUDENT.DASH_FORCE;
        this.dashEndTime = time + this.dashDuration;
        this.nextDashTime = time + this.dashCooldown;

        // Mantengo Y tal cual, sólo empuje horizontal
        this.body.setVelocityX(this.dashVelX);
        this.dashSound.play({ loop: false, volume: 0.3 });

        // Nube verde hacia atrás
        this.emitDashDust(dir);
    }

    emitDashDust(dashDir) {
        if (!this.dashParticles) return;

        // Emisión contraria al dash
        const angle = (dashDir > 0)
            ? { min: 150, max: 210 }   // dash derecha -> polvo izquierda
            : { min: -30, max: 30 };  // dash izquierda -> polvo derecha

        this.dashParticles.setEmitterAngle(angle);

        // Un poco por detrás de los pies
        const offsetX = (dashDir > 0) ? -8 : 8;
        this.dashParticles.explode(12, this.x + offsetX, this.y - 8);
    }

    setColliders() {
        if (this.scene.collisions) {
            //Por si hemos instanciado al Student antes de crear la capa layer_collisions
            this.scene.physics.add.collider
                (
                    this,
                    this.scene.collisions
                );
        }
    }

    onStudentInOpenedDoorZone(_door) {
        //Bloqueamos el control del student
        this.autoMove = true;
        this.setVelocity(0, 0);

        this.scene.add.tween
            ({
                targets: this,
                duration: 200,
                x: _door.x,
                y: _door.y,
                onComplete: () => {
                    this.walkSound.pause();
                    this.scene.add.tween
                        ({
                            targets: this,
                            duration: 200,
                            alpha: 0,
                            onComplete: () => {
                                _door.setFrame(0); //Puerta cerrada
                                this.closeDoorSound.play({ loop: false, volume: 0.3 });
                                //Añadimos un delay antes de reiniciar la escena
                                this.scene.time.delayedCall(1000, () => {
                                    //Incremento el nivel y reinicio la escena <- Salto de nivel
                                    if (LEVEL.LEVEL_ACTUAL < LEVEL.MAX_LEVELS) {
                                        LEVEL.LEVEL_ACTUAL++;
                                        this.walkSound.stop();
                                        this.scene.scene.restart();
                                    } else {
                                        //cerramos la escena de HUD y vamos a créditos
                                        this.scene.scene.stop('hud');
                                        this.scene.sound.stopAll();
                                        this.scene.scene.start('credits');
                                    }
                                });
                            }
                        });
                }
            });
    }

    preUpdate(time, delta) {
        super.preUpdate(time, delta);

        let onGround = this.isOnGround();

        if (onGround) {
            this.lastOnGroundTime = time;
        }
        else {
            // Coyote time: si hace poco que dejé el suelo, sigo "en el suelo"
            // buffer de 100ms
            if (time - this.lastOnGroundTime < 100) {
                onGround = true;
            }
        }

        // DASH: desactivar cuando vence
        if (this.isDashing && time >= this.dashEndTime) {
            this.isDashing = false;
            this.dashVelX = 0;
        }

        const onStairsNow = this.scene.stairsGroup
            ? this.scene.physics.overlap(this, this.scene.stairsGroup)
            : false;

        //1) Hago la gestión de entrada/salidad de escaleras
        if (onStairsNow && !this.onStairs) {
            //Acabo de entrar en las escaleras
            this.onStairs = true;
            this.walkSound.pause();
            this.prevAllowGravity = this.body.allowGravity;
            //Desactivo la gravedad para poder controlar el movimiento vertical                
            this.body.setAllowGravity(false);
        } else if (!onStairsNow && this.onStairs) {
            //Acabo de salir de las escaleras
            this.onStairs = false;
            this.walkSound.pause();
            this.climbSound.pause();
            //Restauro la gravedad previa al entrar en las escaleras o la fuerzo a true
            this.body.setAllowGravity(this.prevAllowGravity ?? true);
        }

        //2) Controlo el movimiento horizontal, esté o no es las escaleras
        if (!this.autoMove && !this.isDashing) {
            if (this.cursors.left.isDown) { //ME MUEVO A LA IZQUIERDA
                this.body.setVelocityX(-STUDENT.SPEED); // ← negativo a la izquierda    
                this.setFlipX(true); //Oriento el sprite a la izquierda
                this.lastMoveDir = -1; //Para el dash
                //Controlo que no esté ni en el aire ni en las escaleras para reproducir la animación de caminar
                if (onGround && !this.onStairs) this.anims.play('student_walk', true);
            } else
                if (this.cursors.right.isDown) { //ME MUEVO A LA DERECHA
                    this.body.setVelocityX(STUDENT.SPEED);
                    this.setFlipX(false); //Oriento el sprite a la derecha (por defecto)  
                    this.lastMoveDir = 1; //Para el dash    
                    //Controlo que no esté ni en el aire ni en las escaleras para reproducir la animación de caminar
                    if (onGround && !this.onStairs) this.anims.play('student_walk', true);
                } else {
                    this.body.setVelocityX(0);
                    this.walkSound.pause();
                    //Controlo que no esté ni en el aire ni en las escaleras para reproducir la animación de idle  
                    if (onGround && !this.onStairs) {
                        this.anims.play('student_idle', true);
                    }
                }
        } else if (this.isDashing) {
            //Durante el dash, mantengo la velocidad de dash
            this.body.setVelocityX(this.dashVelX);
        }

        //3) Controlo el movimiento vertical sólo si estoy en las escaleras 
        //Control vertical en escaleras
        if (this.onStairs) {
            if (this.cursors.up.isDown) {
                this.body.setVelocityY(-STUDENT.CLIMB_SPEED); // ← negativo hacia arriba
                this.walkSound.pause();
                this.anims.play('student_climb', true);
                if (!this.climbSound.isPlaying)
                    this.climbSound.play({ loop: true, volume: 0.5 });
            } else
                if (this.cursors.down.isDown) {
                    this.body.setVelocityY(STUDENT.CLIMB_SPEED);
                    this.walkSound.pause();
                    this.anims.play('student_climb', true);
                    if (!this.climbSound.isPlaying)
                        this.climbSound.play({ loop: true, volume: 0.5 });
                } else {
                    this.body.setVelocityY(0);
                    this.anims.stop().setFrame(24);
                    this.climbSound.pause();
                }

            return; //Salimos del preUpdate aquí para no mezclar con el salto
        }

        // DASH (SHIFT)
        this.tryDash(time);

        //4) Si llegamos hasta aquí, no estoy en las escaleras y puedo comprobar si student puede saltar 
        //Condición:(JustDown para detectar el instante de pulsación + remaining_jumps)
        //Si puede, salta
        this.canJump();

        //5) Cortamos el salto, con JustUp, para hacer un salto variable en base a la intensidad de pulsado
        if (Phaser.Input.Keyboard.JustUp(this.cursors.space) && this.body.velocity.y < 0) {
            this.body.setVelocityY(this.body.velocity.y * 0.5);
        }

        //6) Comprobamos si estoy en el suelo y no estoy subiendo para resetear los saltos
        if (this.isOnGround() && this.body.velocity.y >= 0) {
            //Reseteamos los saltos disponibles
            this.remaining_jumps = STUDENT.MAX_JUMPS;
        }

        //7) Comprobamos si acabo de aterrizar para emitir partículas de polvo
        if (this.isOnGround() && this.body.velocity.y === 0 && this.lastVelocityY > 80) {
            this.emitLandDust(this.lastVelocityY);
        }

        // Guardar para el siguiente frame
        this.lastVelocityY = this.body.velocity.y;

        //8) Si estoy en el aire, pongo el frame de salto
        const inAir = !onGround && !this.onStairs;

        if (inAir) {
            this.walkSound.pause();

            //Si estaba moviendose horizontalmente, cambio la animación a salto
            const movingInput =
                this.cursors.left.isDown                //Izquierda
                || this.cursors.right.isDown            //Derecha
                || this.isDashing                       //Dash
                || Math.abs(this.body.velocity.x) > 10; //Movimiento horizontal “natural”
            this.jump_frame = movingInput
                ? STUDENT.JUMP_MOVING_FRAME
                : STUDENT.JUMP_STATIC_FRAME;
        }

        if (!this.body.onFloor() && !this.body.touching.down) {
            this.anims.stop().setFrame(this.jump_frame);
        }
        //Emitir partículas de polvo al correr  
        this.emitWalkDust(time);
    }
}