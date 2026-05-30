# Hero Siege

A high-fantasy, ARPG-flavored **siege survival** game, built as a self-contained
[Coworld](https://github.com/Metta-AI/coworld). Two heroes defend the central **Sanctum** (the
Eternal Flame) against escalating waves of monsters that pour from **Demon Portals** at the edges of
the arena. It is an homage to the Warcraft 3 custom map *X Hero Siege*.

The game ships with its own real-time tick engine (pure Python, no external simulator), a FastAPI
game server implementing the Coworld game contract, browser clients (live + replay), a bundled
scripted hero bot, and pixel-art sprites.

## Rules

- Monsters spawn in escalating waves from four Demon Portals and march toward the Sanctum.
- A monster that reaches the Sanctum damages it and is consumed. When the Sanctum's HP hits zero, you
  lose.
- Heroes move one cell per tick and attack an adjacent monster by moving into it (bump combat). Kills
  yield **gold** and **essence**.
- Spend resources at shrines (step adjacent, then interact): the **Arcane Forge** raises attack
  damage, the **Healing Spring** restores health, and the **Gold Shrine** converts essence to gold.
- Survive every wave with the Sanctum intact to win.

Any hero slot with no connected player is driven by a built-in melee AI, so the game also runs fully
autonomously for spectating.

## Layout

```
src/herosiege/
  game/engine.py          deterministic, seedable siege engine (no IO)
  game/server.py          FastAPI game runnable (live + replay modes)
  game/client/*.html      global viewer, player, and replay browser clients
  game/docs/*.md          player and global WebSocket protocol specs
  player/player.py        bundled "Champion" hero bot
  art/*.png               16x16 sprites + generate_sprites.py
coworld_manifest_template.json   the Coworld manifest
Dockerfile, compose.yaml         build the game image
```

## Quick start (no Docker)

Run a full headless episode (the bundled AI plays both heroes) and print the results:

```bash
pip install -e .
python -m herosiege.game.engine
# -> {"scores": [...], "waves_survived": N, "monsters_slain": N, "ticks": N}
```

Run the tests:

```bash
pip install -e ".[test]"
pytest
```

## Run it through Coworld (Docker)

These commands use the [`coworld`](https://github.com/Metta-AI/coworld) CLI and a local Docker daemon.

```bash
# 1. Build the game image and hydrate the manifest with resolved image digests.
coworld build compose.yaml coworld_manifest_template.json 0.1.0 tmp/coworld_manifest.json

# 2. Certify: run the game + bundled Champion bots end to end, validate results and replay.
coworld certify tmp/coworld_manifest.json

# 3. Play in the browser. Prints a global viewer link and one player link per hero slot.
coworld play tmp/coworld_manifest.json
```

In `coworld play`, drive a hero with the arrow keys / WASD and use an adjacent shrine with space. Any
slot you do not open is played by the AI.

## Player protocol

Each tick the server sends an observation; the player replies with `{"move": "up|down|left|right|stay"}`
or `{"interact": true}`. Full message shapes are in
[`src/herosiege/game/docs/player_protocol_spec.md`](src/herosiege/game/docs/player_protocol_spec.md)
and [`global_protocol_spec.md`](src/herosiege/game/docs/global_protocol_spec.md).

## Art

Sprites are 16x16 RGBA PNGs in `src/herosiege/art/`, served by the game server at `/art/<file>.png`.
Each browser client maps object/agent names to files through a small `SPRITES` table at the top of the
file, so reskinning is a drop-in: replace a PNG (keeping the filename) or point a `SPRITES` entry at a
new file. The current sprites are generated with no network by:

```bash
python src/herosiege/art/generate_sprites.py
```

To use [Replicate](https://replicate.com) Retro Diffusion art instead, set `REPLICATE_API_TOKEN`,
install `replicate`, and write PNGs into `src/herosiege/art/` with the same filenames (`hero_knight`,
`monster_skeleton`, `monster_demon`, `sanctum`, `demon_portal`, `gold_shrine`). Rebuild the image
afterward so the new art is baked in.
