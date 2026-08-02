# Little Things: Phaser Edition

This project is a small pixel-art platformer built with the **Phaser game engine**.
It is a compact exploration and puzzle game where the player moves through a set
of handcrafted levels, interacts with objects, collects items, and reaches the
exit while learning the level's mechanics.

## What is this project about?

I built this as a fun way to practice **game scene management**, **physics-based
movement**, **tilemap-based level design**, and **Phaser scene orchestration**.
The game is intentionally lightweight and self-contained: it uses bundled assets,
map JSON files, and a few custom game entities instead of relying on any external
backend or database.

## Gameplay loop

The player starts in the main menu, then enters a level where they need to:

- move around the environment,
- interact with doors, buttons, blocks and stairs,
- collect the key when needed,
- avoid hazards such as spikes,
- use the NPC interaction flow and the level-specific puzzle logic,
- reach the exit to advance.

The project is structured around a small set of level scenes and a HUD scene that
runs alongside the main level.

## Controls

- **A / D** or **Left / Right** — move
- **Space** — jump
- **Shift** — dash
- **W / Up** — climb / interact where relevant
- **E** — interact with NPC or objects
- **Z** — zoom camera
- **R** — restart the current level
- **B / N** — previous / next level
- **Down** — drop through one-way platforms

## Project structure

```text
phaser_game/
├── index.html              # entry point for the browser game
├── readme.md               # project documentation
├── assets/                 # sprites, fonts, sounds, tilesets and tile maps
├── libs/                   # Phaser engine dependency
└── src/                    # game logic, scenes, entities and UI
```

## Main code areas

- `src/main.js` — starts the Phaser game and registers the scenes
- `src/core/config.js` — engine configuration
- `src/scenes/Menu.js` — title screen and game start
- `src/scenes/Level.js` — core gameplay scene and level loading
- `src/scenes/Credits.js` — end screen / credits scene
- `src/entities/` — player and interactive level objects
- `src/ui/Hud.js` — in-game HUD

## How to run it

Because this is a browser game, the simplest way to run it is to serve the
folder with a small local HTTP server.

From the repository root:

```powershell
cd "My Projects/phaser_game"
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/
```

If you are running from VS Code, you can also launch the project with a simple
local preview extension or a lightweight server, as long as the game files are
served through HTTP instead of opened directly as a file.

## Tech stack

- **Phaser** — game engine
- **JavaScript** — gameplay and scene logic
- **Tiled maps** — level layout and collision layers
- **Pixel-art assets** — sprites, objects and UI

## Notes

This is a small personal game project, so the focus here is on learning by
building: level loading, collisions, movement states, object interaction, and a
clean scene-based structure. It is simple, but it gives a solid feel for how a
browser game can be organized in a way that is easy to extend later.
