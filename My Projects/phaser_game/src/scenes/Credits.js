import { STUDENT, LEVEL, LEVEL_SIZE, SCALE } from "../core/constants.js";

export class Credits extends Phaser.Scene
{
    constructor()
    {
        super({key:'credits'});
    }

    preload()
    { //Carga assets en memoria
        this.cameras.main.setBackgroundColor('#000');
    }

    create()
    { //Pinta assets en pantalla
        const wide = this.scale.width;
        const high = this.scale.height;
        
        this.ambientCredits = this.sound.add('snd_ambientCredits', Phaser.Sound.BaseSound);
        this.ambientCredits.play({loop:true, volume: 0.5});

        //Inicializo la UI
        this.titleText = this.add.bitmapText
        (
            wide/2,50,
            'LvlFont',
            'LITTLE THINGS',
            50  
        ).setOrigin(0.5);
        
        this.titleText = this.add.bitmapText
        (
            wide/2+120,80,
            'LvlFont',
            'Phaser Edition',
            20  
        ).setOrigin(1,0.5);

        
        //instanciamos el Student y el npc con las animacione idle
        this.student = this.add.sprite(wide/2 - 85, 39, 'student') 
        .setOrigin(0.5,1);
        this.student.anims.play('student_idle', true);
        this.npc = this.add.sprite(wide/2 + 60, 40, 'npc')
        .setOrigin(0.5,1)
        .setTint(0xA4167F); //MagENTI        
        this.npc.anims.play('npc_idle', true);

        //Texto de créditos
        this.creditsText = this.add.bitmapText
        (
            wide/2, high/2 + 40,
            'UItext',
            'Special Thanks to the original developers of\n' +
            '"Little Things", JAGSTUDIO:\n\n'+
            '   - Gisela Benito Izquierdo\n'+
            '   - Jan Planes Mazcunan\n' +
            '   - Adrian Diego Fernandez Olivares\n\n' +
            'for creating such a wonderful game!\n\n' +
            'This Phaser Edition has been developed as an \n' +
            'academic exercise by Richard Hebert. 2026.',
                
            16  
        ).setOrigin(0.5);   
        
    }  
} 