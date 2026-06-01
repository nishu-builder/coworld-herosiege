from __future__ import annotations

import asyncio
import gzip
import json
import os
import zlib
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from herosiege.game.engine import HeroSiege, HeroSiegeConfig

CLIENT_DIR = Path(__file__).parent / "client"
ART_DIR = Path(__file__).parent.parent / "art"
GAME_HOST = os.environ.get("COGAME_HOST", "0.0.0.0")
GAME_PORT = int(os.environ.get("COGAME_PORT", "8080"))
HTTP_USER_AGENT = "coworld-herosiege/0.1"

REPLAY_MODE = "COGAME_LOAD_REPLAY_URI" in os.environ
REPLAY_LOAD_URI = os.environ.get("COGAME_LOAD_REPLAY_URI", "")


def read_data(uri: str) -> bytes:
    parsed = urlparse(uri)
    if parsed.scheme in ("http", "https"):
        request = Request(uri, headers={"User-Agent": HTTP_USER_AGENT})
        with urlopen(request, timeout=30) as response:
            return response.read()
    if parsed.scheme == "file":
        return Path(unquote(parsed.path)).read_bytes()
    if parsed.scheme == "":
        return Path(uri).read_bytes()
    raise ValueError(f"Unsupported URI for read_data: {uri}")


def artifact_method(env_var: str) -> Literal["POST", "PUT"]:
    method = os.environ.get(env_var, "PUT").upper()
    if method not in {"POST", "PUT"}:
        raise ValueError(f"{env_var} must be PUT or POST")
    return cast(Literal["POST", "PUT"], method)


def write_data(uri: str, data: bytes | str, *, content_type: str, http_method: Literal["POST", "PUT"]) -> None:
    if isinstance(data, str):
        data = data.encode()
    parsed = urlparse(uri)
    if parsed.scheme in ("http", "https"):
        request = Request(uri, data=data, method=http_method)
        request.add_header("Content-Type", content_type)
        request.add_header("User-Agent", HTTP_USER_AGENT)
        with urlopen(request, timeout=60):
            return
    path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(uri)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def load_replay_data(replay_uri: str) -> dict[str, Any]:
    raw = read_data(replay_uri)
    if replay_uri.endswith(".json.z"):
        raw = zlib.decompress(raw)
    elif replay_uri.endswith(".json.gz"):
        raw = gzip.decompress(raw)
    return cast(dict[str, Any], json.loads(raw))


def load_config() -> tuple[HeroSiegeConfig, list[str], list[str], float]:
    raw = json.loads(read_data(os.environ["COGAME_CONFIG_URI"]))
    tokens = raw["tokens"]
    names = [p["name"] for p in raw["players"]]
    config = HeroSiegeConfig(
        width=raw["width"],
        height=raw["height"],
        max_ticks=raw["max_ticks"],
        tick_rate=raw["tick_rate"],
        num_heroes=len(tokens),
        num_waves=raw["num_waves"],
    )
    return config, tokens, names, float(raw["player_connect_timeout"])


class Session:
    def __init__(self) -> None:
        self.config, self.tokens, self.names, self.connect_timeout = load_config()
        self.game = HeroSiege(self.config)
        self.players: dict[int, WebSocket] = {}
        self.moves: list[str | None] = [None] * len(self.tokens)
        self.interacts: list[bool] = [False] * len(self.tokens)
        self.frames: list[dict[str, Any]] = []
        self.started = False
        self.done = False
        self.paused = False
        self.tick_rate = float(self.config.tick_rate)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global session
    if REPLAY_MODE:
        yield
        return
    session = Session()
    timeout_task = asyncio.create_task(_start_after_timeout())
    yield
    timeout_task.cancel()
    with suppress(asyncio.CancelledError):
        await timeout_task


app = FastAPI(lifespan=lifespan)
app.mount("/art", StaticFiles(directory=ART_DIR), name="art")
server: uvicorn.Server
session: Session


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/client/global")
def global_client() -> HTMLResponse:
    return HTMLResponse((CLIENT_DIR / "global.html").read_text())


@app.get("/client/player")
def player_client() -> HTMLResponse:
    return HTMLResponse((CLIENT_DIR / "player.html").read_text())


@app.get("/client/replay")
def replay_client() -> HTMLResponse:
    return HTMLResponse((CLIENT_DIR / "replay.html").read_text())


@app.websocket("/replay")
async def replay_viewer(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "replay", **load_replay_data(REPLAY_LOAD_URI)})
    async for command in websocket.iter_json():
        await websocket.send_json({"type": "control", "command": command})


@app.websocket("/global")
async def global_viewer(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(_snapshot())
    while not session.done:
        await asyncio.sleep(0.1)
        await websocket.send_json(_snapshot())


@app.websocket("/admin")
async def admin(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json(_snapshot())
    async for command in websocket.iter_json():
        if command["command"] == "pause":
            session.paused = True
        elif command["command"] == "resume":
            session.paused = False
        elif command["command"] == "tick_rate":
            session.tick_rate = float(command["tick_rate"])
        await websocket.send_json(_snapshot())


@app.websocket("/player")
async def player(websocket: WebSocket) -> None:
    slot = int(websocket.query_params["slot"])
    token = websocket.query_params["token"]
    if slot < 0 or slot >= len(session.tokens) or session.tokens[slot] != token:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    session.players[slot] = websocket
    await websocket.send_json(_observation(slot))
    if len(session.players) == len(session.tokens) and not session.started:
        session.started = True
        asyncio.create_task(_play_game())
    try:
        async for message in websocket.iter_json():
            if message.get("interact"):
                session.interacts[slot] = True
            else:
                session.moves[slot] = str(message.get("move", "stay"))
    finally:
        if session.players.get(slot) is websocket:
            del session.players[slot]
            session.moves[slot] = None
            session.interacts[slot] = False


def _tick_actions() -> list[dict[str, Any] | None]:
    actions: list[dict[str, Any] | None] = []
    for slot in range(len(session.tokens)):
        if session.interacts[slot]:
            actions.append({"interact": True})
        elif session.moves[slot] is not None:
            actions.append({"move": session.moves[slot]})
        else:
            actions.append(None)
    session.interacts = [False] * len(session.tokens)
    return actions


async def _start_after_timeout() -> None:
    await asyncio.sleep(session.connect_timeout)
    if not session.started and not session.done:
        session.started = True
        asyncio.create_task(_play_game())


async def _play_game() -> None:
    await asyncio.sleep(0.5)
    while not session.game.done:
        if session.paused:
            await asyncio.sleep(0.1)
            continue
        session.game.step(_tick_actions())
        session.frames.append(_snapshot())
        for slot, ws in list(session.players.items()):
            await ws.send_json(_observation(slot))
        await asyncio.sleep(1.0 / session.tick_rate)

    results = session.game.results()
    write_data(
        os.environ["COGAME_RESULTS_URI"],
        json.dumps(results),
        content_type="application/json",
        http_method=artifact_method("COGAME_RESULTS_METHOD"),
    )
    write_data(
        os.environ["COGAME_SAVE_REPLAY_URI"],
        json.dumps(
            {
                "config": session.game.config.__dict__,
                "player_names": session.names,
                "frames": session.frames,
                "results": results,
            }
        ),
        content_type="application/json",
        http_method=artifact_method("COGAME_SAVE_REPLAY_METHOD"),
    )
    session.done = True
    server.should_exit = True
    for slot, ws in session.players.items():
        await ws.send_json({**_observation(slot), "type": "final", "done": True})
    await asyncio.sleep(0.5)


def _snapshot() -> dict[str, Any]:
    return {"type": "state", "tick_rate": session.tick_rate, "paused": session.paused, **session.game.snapshot()}


def _observation(slot: int) -> dict[str, Any]:
    return {**_snapshot(), "type": "observation", "slot": slot}


if __name__ == "__main__":
    server = uvicorn.Server(uvicorn.Config(app, host=GAME_HOST, port=GAME_PORT))
    server.run()
