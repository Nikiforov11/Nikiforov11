/**
 * Tabla centralizada de nombres de eventos del juego.
 * Evita "strings mágicos" repartidos por el código.
 */

export const EVENTS = 
{
    /**
   * Se emite cuando el student está creado y listo para usarse en la escena.
   * payload: (student: Student)
   *
   * Ejemplo de emisión:
   *   this.game.events.emit(EVENTS.STUDENT_READY, this.student);
   */
    STUDENT_READY: 'student:ready',

    /**
    * Se emite cuando el student entra en una zona específica de un NPC.
    * payload: (npc: NPC)
    *
    * Ejemplo de emisión:
    *   this.game.events.emit(EVENTS.NPC_STUDENT_IN_ZONE, npc);
    */
    NPC_STUDENT_IN_ZONE: 'npc:enter',
    
    /**
    * Se emite cuando el student sale de una zona específica de un NPC.
    * payload: (npc: NPC)
    *
    * Ejemplo de emisión:
    *   this.game.events.emit(EVENTS.NPC_STUDENT_OUT_ZONE, npc);
    */
    NPC_STUDENT_OUT_ZONE: 'npc:leave',
    
    /**
    * Se emite cuando el student interactúa en una zona específica de un NPC.
    * payload: (npc: NPC)
    *
    * Ejemplo de emisión:
    *   this.game.events.emit(EVENTS.NPC_STUDENT_INTERACT, npc);
    */
    NPC_STUDENT_INTERACT: 'npc:msg',
    /**
    * Se emite cuando el student interactúa en una zona de una puerta de salida.
    * payload: (door: Door)
    *
    * Ejemplo de emisión:
    *   this.game.events.emit(EVENTS.STUDENT_IN_OPENED_DOOR_ZONE, door);
    */
    STUDENT_IN_OPENED_DOOR_ZONE: 'door:exit',

    /**
    * Se emite cuando el student muere.
    * payload: (student: Student)
    *
    * Ejemplo de emisión:
    *   this.game.events.emit(EVENTS.STUDENT_DIED, student);
    */
    STUDENT_DIED: 'student:died',
    STUDENT_DASH: 'student:dash',
    STUDENT_DOUBLE_JUMP: 'student:double_jump',
    STUDENT_NO_EFFECT: 'student:no_effect',
    STUDENT_PICKUP_KEY: 'student:pickup_key',
    STUDENT_FIND_KEY: 'student:find_key',
    BUTTON_PRESSED: 'button:pressed'
};