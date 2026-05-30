# Hero Siege Global Protocol

Browsers request `GET /client/global` to load the global viewer, which opens the `/global` WebSocket. The server sends a
full state snapshot immediately on connect and then every tick while the episode runs:

```json
{
  "type": "state",
  "tick_rate": 10,
  "paused": false,
  "width": 20,
  "height": 20,
  "tick": 12,
  "wave": 1,
  "num_waves": 2,
  "done": false,
  "outcome": null,
  "sanctum": { "x": 10, "y": 10, "hp": 240, "max_hp": 240 },
  "portals": [{ "x": 10, "y": 1 }],
  "shrines": [{ "x": 7, "y": 7, "kind": "arcane_forge" }],
  "heroes": [{ "x": 9, "y": 11, "hp": 55, "max_hp": 55, "gold": 0, "essence": 0, "kills": 0, "alive": true }],
  "monsters": [{ "x": 10, "y": 2, "kind": "skeleton", "hp": 12, "max_hp": 12 }],
  "monsters_slain": 0,
  "waves_survived": 0
}
```

For local development, `GET /client/admin` opens the `/admin` WebSocket, which accepts `{ "command": "pause" }`,
`{ "command": "resume" }`, and `{ "command": "tick_rate", "tick_rate": 15 }`. Sprite art for each object and agent is
served under `/art/<file>.png` and resolved by the clients via a name-to-file map. `outcome` is `null` while the siege
is in progress, then one of `"win"`, `"loss"`, or `"timeout"` when `done` becomes true.
