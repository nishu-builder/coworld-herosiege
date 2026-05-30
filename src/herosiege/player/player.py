from __future__ import annotations

import asyncio
import json
import os
from typing import Any, cast

import websockets


def _dist(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _nearest_monster(obs: dict[str, Any], hero: dict[str, Any]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_d = 1 << 30
    for m in obs["monsters"]:
        d = _dist(hero["x"], hero["y"], m["x"], m["y"])
        if d < best_d:
            best_d, best = d, m
    return best


def _champion_move(obs: dict[str, Any], slot: int) -> dict[str, str]:
    hero = obs["heroes"][slot]
    target = _nearest_monster(obs, hero)
    goal = target if target is not None else obs["sanctum"]
    dx, dy = _sign(goal["x"] - hero["x"]), _sign(goal["y"] - hero["y"])
    if abs(goal["x"] - hero["x"]) >= abs(goal["y"] - hero["y"]):
        move = "right" if dx > 0 else "left" if dx < 0 else ("down" if dy > 0 else "up")
    else:
        move = "down" if dy > 0 else "up" if dy < 0 else ("right" if dx > 0 else "left")
    return {"move": move}


async def main() -> None:
    url = os.environ["COWORLD_PLAYER_WS_URL"]
    async with websockets.connect(url) as websocket:
        async for raw_message in websocket:
            message = cast(dict[str, Any], json.loads(raw_message))
            if message.get("type") == "final" or message.get("done"):
                return
            if message.get("type") == "observation":
                await websocket.send(json.dumps(_champion_move(message, message["slot"])))


if __name__ == "__main__":
    asyncio.run(main())
