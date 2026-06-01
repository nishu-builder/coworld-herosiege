from __future__ import annotations

import asyncio
import json
import os
from typing import Any, cast

import websockets
from websockets.exceptions import ConnectionClosed

FORGE_COST = 20
SPRING_COST = 15
CARDINALS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def _dist(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


def _passable(obs: dict[str, Any], x: int, y: int) -> bool:
    if x <= 0 or y <= 0 or x >= obs["width"] - 1 or y >= obs["height"] - 1:
        return False
    if x == obs["sanctum"]["x"] and y == obs["sanctum"]["y"]:
        return False
    return not any(p["x"] == x and p["y"] == y for p in obs["portals"])


def _hero_step(obs: dict[str, Any], slot: int, gx: int, gy: int) -> str:
    hero = obs["heroes"][slot]
    monsters = {(m["x"], m["y"]) for m in obs["monsters"]}
    others = {(h["x"], h["y"]) for i, h in enumerate(obs["heroes"]) if i != slot and h["alive"]}
    best_move = "stay"
    best_key: tuple[int, int] | None = None
    for move, (cx, cy) in CARDINALS.items():
        nx, ny = hero["x"] + cx, hero["y"] + cy
        attack = (nx, ny) in monsters
        if not attack and (not _passable(obs, nx, ny) or (nx, ny) in others):
            continue
        key = (0 if attack else 1, _dist(nx, ny, gx, gy))
        if best_key is None or key < best_key:
            best_key, best_move = key, move
    return best_move


def _champion_move(obs: dict[str, Any], slot: int) -> dict[str, Any]:
    hero = obs["heroes"][slot]
    monsters = obs["monsters"]
    for shrine in obs["shrines"]:
        if _dist(hero["x"], hero["y"], shrine["x"], shrine["y"]) > 1:
            continue
        if shrine["kind"] == "healing_spring" and hero["hp"] <= hero["max_hp"] // 2 and hero["gold"] >= SPRING_COST:
            return {"interact": True}
        if shrine["kind"] == "arcane_forge" and hero["gold"] >= FORGE_COST and not monsters:
            return {"interact": True}
    sanctum = obs["sanctum"]
    goal = min(monsters, key=lambda m: _dist(m["x"], m["y"], sanctum["x"], sanctum["y"])) if monsters else sanctum
    return {"move": _hero_step(obs, slot, goal["x"], goal["y"])}


async def main() -> None:
    url = os.environ["COWORLD_PLAYER_WS_URL"]
    async with websockets.connect(url) as websocket:
        try:
            async for raw_message in websocket:
                message = cast(dict[str, Any], json.loads(raw_message))
                if message.get("type") == "final" or message.get("done"):
                    return
                if message.get("type") == "observation":
                    await websocket.send(json.dumps(_champion_move(message, message["slot"])))
        except ConnectionClosed:
            return


if __name__ == "__main__":
    asyncio.run(main())
