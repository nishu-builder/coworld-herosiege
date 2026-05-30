# Hero Siege Player Protocol

Browsers request `GET /client/player?slot=<slot>&token=<token>` to load the player client, which opens the
`/player?slot=<slot>&token=<token>` WebSocket. Bundled or submitted player containers connect to the same `/player`
route via `COWORLD_PLAYER_WS_URL`.

The server sends an observation every tick:

```json
{
  "type": "observation",
  "slot": 0,
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

The player replies with either a move or a shrine interaction:

```json
{ "move": "right" }
```

```json
{ "interact": true }
```

`move` is one of `up`, `down`, `left`, `right`, or `stay`. Moving into a monster attacks it; moving into a shrine is
blocked (step adjacent and send `interact` instead). Invalid messages are treated as `stay`. Any hero slot with no
connected player is driven by a built-in melee AI. Bad tokens are rejected during the WebSocket handshake. The final
message carries `"type": "final"` with `"done": true`.
