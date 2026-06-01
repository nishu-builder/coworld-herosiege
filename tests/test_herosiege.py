from __future__ import annotations

import json
from pathlib import Path

from herosiege.game.engine import SHRINE_KINDS, HeroSiege, HeroSiegeConfig, run_headless
from herosiege.player.player import _champion_move

MANIFEST = Path(__file__).resolve().parents[1] / "coworld_manifest_template.json"


def test_map_has_siege_layout() -> None:
    game = HeroSiege(HeroSiegeConfig(width=24, height=24, num_heroes=3))
    assert game.sanctum_x == 12 and game.sanctum_y == 12
    assert len(game.portals) == 4
    assert all(not game._is_wall(p.x, p.y) for p in game.portals)
    assert {s.kind for s in game.shrines} == set(SHRINE_KINDS)
    assert len(game.heroes) == 3
    assert game._is_wall(0, 5) and game._is_wall(12, 0)
    assert not game._is_wall(5, 5)


def test_monsters_spawn_from_portals() -> None:
    game = HeroSiege(HeroSiegeConfig(seed=1))
    for _ in range(12):
        game.step()
    assert len(game.monsters) > 0


def test_headless_episode_terminates_with_valid_results() -> None:
    config = HeroSiegeConfig(seed=7, num_waves=4, max_ticks=4000)
    results = run_headless(config)
    assert set(results) == {"scores", "waves_survived", "monsters_slain", "ticks"}
    assert len(results["scores"]) == config.num_heroes
    assert all(isinstance(s, float) for s in results["scores"])
    assert results["ticks"] > 0
    assert 0 <= results["waves_survived"] <= config.num_waves


def test_simulation_is_deterministic() -> None:
    assert run_headless(HeroSiegeConfig(seed=42, num_waves=3)) == run_headless(HeroSiegeConfig(seed=42, num_waves=3))


def test_player_action_overrides_default_ai() -> None:
    game = HeroSiege(HeroSiegeConfig(num_heroes=1))
    hero = game.heroes[0]
    start = (hero.x, hero.y)
    game.step([{"move": "up"}])
    assert (hero.x, hero.y) == (start[0], start[1] - 1)


def _obs(hero: dict, monsters: list, shrines: list) -> dict:
    return {
        "width": 22,
        "height": 22,
        "sanctum": {"x": 11, "y": 11},
        "portals": [],
        "shrines": shrines,
        "monsters": monsters,
        "heroes": [hero],
    }


def test_champion_bot_returns_valid_action() -> None:
    hero = {"x": 9, "y": 13, "hp": 220, "max_hp": 220, "gold": 0, "alive": True}
    obs = _obs(hero, [{"x": 9, "y": 9}], [])
    assert _champion_move(obs, 0)["move"] in {"up", "down", "left", "right"}

    forge = {"x": 9, "y": 13, "kind": "arcane_forge"}
    rich = {"x": 9, "y": 13, "hp": 220, "max_hp": 220, "gold": 50, "alive": True}
    assert _champion_move(_obs(rich, [], [forge]), 0) == {"interact": True}


def test_manifest_template_shape() -> None:
    raw = json.loads(MANIFEST.read_text())
    assert "version" not in raw["game"], "templates must not pin game.version"
    schema = raw["game"]["config_schema"]
    tokens = schema["properties"]["tokens"]
    assert tokens["minItems"] == tokens["maxItems"] == 2
    assert [p["id"] for p in raw["player"]] == ["champion"]
    assert [p["player_id"] for p in raw["certification"]["players"]] == ["champion", "champion"]
    assert raw["game"]["runnable"]["run"] == ["python", "-m", "herosiege.game.server"]
