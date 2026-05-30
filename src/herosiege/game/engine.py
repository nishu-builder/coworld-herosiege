from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

DIRECTIONS: dict[str, tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "stay": (0, 0),
}

MONSTER_STATS: dict[str, dict[str, int]] = {
    "skeleton": {"hp": 12, "damage": 3, "speed": 1, "gold": 5, "essence": 1},
    "imp": {"hp": 8, "damage": 4, "speed": 1, "gold": 6, "essence": 1},
    "hellhound": {"hp": 20, "damage": 6, "speed": 1, "gold": 9, "essence": 2},
    "demon": {"hp": 48, "damage": 11, "speed": 2, "gold": 22, "essence": 4},
}

SHRINE_KINDS = ("arcane_forge", "healing_spring", "gold_shrine")

FORGE_COST = 20
SPRING_COST = 15
SANCTUM_HP = 240
HERO_HP = 55
HERO_DAMAGE = 9
AGGRO_RADIUS = 6
SPAWN_INTERVAL = 3
WAVE_BREAK = 22


@dataclass
class HeroSiegeConfig:
    width: int = 24
    height: int = 24
    max_ticks: int = 4000
    tick_rate: float = 10.0
    num_heroes: int = 2
    num_waves: int = 6
    seed: int = 0


@dataclass
class Hero:
    x: int
    y: int
    hp: int = HERO_HP
    max_hp: int = HERO_HP
    damage: int = HERO_DAMAGE
    gold: int = 0
    essence: int = 0
    kills: int = 0
    alive: bool = True


@dataclass
class Monster:
    x: int
    y: int
    kind: str
    hp: int
    max_hp: int
    damage: int
    speed: int
    move_cooldown: int = 0
    alive: bool = True


@dataclass
class Shrine:
    x: int
    y: int
    kind: str


@dataclass
class Portal:
    x: int
    y: int


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def _dist(ax: int, ay: int, bx: int, by: int) -> int:
    return max(abs(ax - bx), abs(ay - by))


class HeroSiege:
    def __init__(self, config: HeroSiegeConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        self.width = config.width
        self.height = config.height
        self.tick = 0
        self.done = False
        self.outcome: str | None = None
        self.monsters_slain = 0
        self.waves_survived = 0

        cx, cy = self.width // 2, self.height // 2
        self.sanctum_x = cx
        self.sanctum_y = cy
        self.sanctum_hp = SANCTUM_HP
        self.sanctum_max_hp = SANCTUM_HP

        self.portals: list[Portal] = [
            Portal(cx, 1),
            Portal(cx, self.height - 2),
            Portal(1, cy),
            Portal(self.width - 2, cy),
        ]
        self.shrines: list[Shrine] = [
            Shrine(cx - 3, cy - 3, "arcane_forge"),
            Shrine(cx + 3, cy - 3, "healing_spring"),
            Shrine(cx, cy + 3, "gold_shrine"),
        ]
        self.heroes: list[Hero] = [Hero(cx - 1 + (i % 3), cy + 1 + (i // 3)) for i in range(max(1, config.num_heroes))]
        self.monsters: list[Monster] = []

        self.wave = 0
        self.wave_size = 0
        self.spawned_this_wave = 0
        self.spawn_cooldown = 0
        self.between_waves = 0
        self._start_wave()

    def _start_wave(self) -> None:
        self.wave += 1
        self.wave_size = 4 + self.wave * 3
        self.spawned_this_wave = 0
        self.spawn_cooldown = 0
        self.between_waves = 0

    def _wave_kind(self) -> str:
        roll = self.rng.random()
        if self.wave >= 4 and roll < 0.18:
            return "demon"
        if self.wave >= 2 and roll < 0.42:
            return "hellhound"
        if roll < 0.66:
            return "skeleton"
        return "imp"

    def _is_wall(self, x: int, y: int) -> bool:
        return x <= 0 or y <= 0 or x >= self.width - 1 or y >= self.height - 1

    def _is_structure(self, x: int, y: int) -> bool:
        if x == self.sanctum_x and y == self.sanctum_y:
            return True
        if any(p.x == x and p.y == y for p in self.portals):
            return True
        return any(s.x == x and s.y == y for s in self.shrines)

    def _monster_at(self, x: int, y: int) -> Monster | None:
        for m in self.monsters:
            if m.alive and m.x == x and m.y == y:
                return m
        return None

    def _hero_at(self, x: int, y: int) -> Hero | None:
        for h in self.heroes:
            if h.alive and h.x == x and h.y == y:
                return h
        return None

    def _passable(self, x: int, y: int) -> bool:
        return not self._is_wall(x, y) and not self._is_structure(x, y)

    def _nearest_monster(self, hero: Hero) -> Monster | None:
        best: Monster | None = None
        best_d = 1 << 30
        for m in self.monsters:
            if not m.alive:
                continue
            d = _dist(hero.x, hero.y, m.x, m.y)
            if d < best_d:
                best_d, best = d, m
        return best

    def _nearest_hero(self, x: int, y: int) -> Hero | None:
        best: Hero | None = None
        best_d = 1 << 30
        for h in self.heroes:
            if not h.alive:
                continue
            d = _dist(x, y, h.x, h.y)
            if d < best_d:
                best_d, best = d, h
        return best

    def _shrine_adjacent(self, hero: Hero) -> Shrine | None:
        for s in self.shrines:
            if _dist(hero.x, hero.y, s.x, s.y) <= 1:
                return s
        return None

    def _use_shrine(self, hero: Hero, shrine: Shrine) -> None:
        if shrine.kind == "arcane_forge":
            if hero.gold >= FORGE_COST:
                hero.gold -= FORGE_COST
                hero.damage += 3
        elif shrine.kind == "healing_spring":
            if hero.gold >= SPRING_COST and hero.hp < hero.max_hp:
                hero.gold -= SPRING_COST
                hero.hp = min(hero.max_hp, hero.hp + 20)
        elif shrine.kind == "gold_shrine":
            if hero.essence >= 1:
                hero.essence -= 1
                hero.gold += 12

    def _slay(self, monster: Monster, by: Hero | None) -> None:
        monster.alive = False
        self.monsters_slain += 1
        stats = MONSTER_STATS[monster.kind]
        if by is not None:
            by.gold += stats["gold"]
            by.essence += stats["essence"]
            by.kills += 1

    def _step_toward(self, x: int, y: int, gx: int, gy: int) -> tuple[int, int] | None:
        dx, dy = _sign(gx - x), _sign(gy - y)
        for cx, cy in ((dx, dy), (dx, 0), (0, dy)):
            if cx == 0 and cy == 0:
                continue
            nx, ny = x + cx, y + cy
            if self._passable(nx, ny) and self._monster_at(nx, ny) is None and self._hero_at(nx, ny) is None:
                return nx, ny
        return None

    def default_hero_action(self, hero: Hero) -> dict[str, Any]:
        shrine = self._shrine_adjacent(hero)
        if shrine is not None:
            if shrine.kind == "healing_spring" and hero.hp <= hero.max_hp // 2 and hero.gold >= SPRING_COST:
                return {"interact": True}
            if shrine.kind == "arcane_forge" and hero.gold >= FORGE_COST and self._nearest_monster(hero) is None:
                return {"interact": True}
        target = self._nearest_monster(hero)
        goal_x, goal_y = (target.x, target.y) if target is not None else (self.sanctum_x, self.sanctum_y)
        dx, dy = _sign(goal_x - hero.x), _sign(goal_y - hero.y)
        if abs(goal_x - hero.x) >= abs(goal_y - hero.y):
            move = "right" if dx > 0 else "left" if dx < 0 else ("down" if dy > 0 else "up")
        else:
            move = "down" if dy > 0 else "up" if dy < 0 else ("right" if dx > 0 else "left")
        return {"move": move}

    def _act_hero(self, hero: Hero, action: dict[str, Any] | None) -> None:
        if action is None:
            action = self.default_hero_action(hero)
        if action.get("interact"):
            shrine = self._shrine_adjacent(hero)
            if shrine is not None:
                self._use_shrine(hero, shrine)
            return
        move = action.get("move", "stay")
        if move not in DIRECTIONS:
            move = "stay"
        ddx, ddy = DIRECTIONS[move]
        nx, ny = hero.x + ddx, hero.y + ddy
        monster = self._monster_at(nx, ny)
        if monster is not None:
            monster.hp -= hero.damage
            if monster.hp <= 0:
                self._slay(monster, hero)
        elif self._passable(nx, ny) and self._hero_at(nx, ny) is None:
            hero.x, hero.y = nx, ny

    def _spawn(self) -> None:
        if self.between_waves > 0:
            self.between_waves -= 1
            if self.between_waves == 0:
                self._start_wave()
            return
        if self.spawned_this_wave >= self.wave_size:
            return
        self.spawn_cooldown += 1
        if self.spawn_cooldown < SPAWN_INTERVAL:
            return
        self.spawn_cooldown = 0
        self.spawned_this_wave += 1
        portal = self.portals[self.rng.randrange(len(self.portals))]
        kind = self._wave_kind()
        stats = MONSTER_STATS[kind]
        self.monsters.append(
            Monster(
                x=portal.x,
                y=portal.y,
                kind=kind,
                hp=stats["hp"],
                max_hp=stats["hp"],
                damage=stats["damage"],
                speed=stats["speed"],
            )
        )

    def _move_monster(self, monster: Monster) -> None:
        monster.move_cooldown += 1
        if monster.move_cooldown < monster.speed:
            return
        monster.move_cooldown = 0

        if _dist(monster.x, monster.y, self.sanctum_x, self.sanctum_y) <= 1:
            self.sanctum_hp -= monster.damage
            monster.alive = False
            return

        hero = self._nearest_hero(monster.x, monster.y)
        if hero is not None and _dist(monster.x, monster.y, hero.x, hero.y) <= 1:
            hero.hp -= monster.damage
            if hero.hp <= 0:
                hero.alive = False
            return

        if hero is not None and _dist(monster.x, monster.y, hero.x, hero.y) <= AGGRO_RADIUS:
            goal_x, goal_y = hero.x, hero.y
        else:
            goal_x, goal_y = self.sanctum_x, self.sanctum_y
        nxt = self._step_toward(monster.x, monster.y, goal_x, goal_y)
        if nxt is not None:
            monster.x, monster.y = nxt

    def step(self, actions: list[dict[str, Any] | None] | None = None) -> None:
        if self.done:
            return
        actions = actions or [None] * len(self.heroes)
        for hero, action in zip(self.heroes, actions, strict=False):
            if hero.alive:
                self._act_hero(hero, action)

        self._spawn()

        for monster in self.monsters:
            if monster.alive:
                self._move_monster(monster)

        self.monsters = [m for m in self.monsters if m.alive]
        self.tick += 1

        wave_cleared = self.between_waves == 0 and self.spawned_this_wave >= self.wave_size and not self.monsters
        if self.sanctum_hp <= 0 or all(not h.alive for h in self.heroes):
            self.done = True
            self.outcome = "loss"
        elif wave_cleared:
            self.waves_survived = self.wave
            if self.wave >= self.config.num_waves:
                self.done = True
                self.outcome = "win"
            else:
                self.between_waves = WAVE_BREAK
        elif self.tick >= self.config.max_ticks:
            self.done = True
            self.outcome = "timeout"

    def scores(self) -> list[float]:
        win_bonus = 200.0 if self.outcome == "win" else 0.0
        shared = float(self.waves_survived) * 50.0 + float(self.monsters_slain) + win_bonus
        return [shared + float(h.kills) * 5.0 + float(h.gold) for h in self.heroes]

    def results(self) -> dict[str, Any]:
        return {
            "scores": self.scores(),
            "waves_survived": self.waves_survived,
            "monsters_slain": self.monsters_slain,
            "ticks": self.tick,
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "tick": self.tick,
            "wave": self.wave,
            "num_waves": self.config.num_waves,
            "done": self.done,
            "outcome": self.outcome,
            "sanctum": {"x": self.sanctum_x, "y": self.sanctum_y, "hp": self.sanctum_hp, "max_hp": self.sanctum_max_hp},
            "portals": [{"x": p.x, "y": p.y} for p in self.portals],
            "shrines": [{"x": s.x, "y": s.y, "kind": s.kind} for s in self.shrines],
            "heroes": [
                {
                    "x": h.x,
                    "y": h.y,
                    "hp": h.hp,
                    "max_hp": h.max_hp,
                    "gold": h.gold,
                    "essence": h.essence,
                    "kills": h.kills,
                    "alive": h.alive,
                }
                for h in self.heroes
            ],
            "monsters": [{"x": m.x, "y": m.y, "kind": m.kind, "hp": m.hp, "max_hp": m.max_hp} for m in self.monsters],
            "monsters_slain": self.monsters_slain,
            "waves_survived": self.waves_survived,
        }


def run_headless(config: HeroSiegeConfig) -> dict[str, Any]:
    game = HeroSiege(config)
    while not game.done:
        game.step()
    return game.results()


if __name__ == "__main__":
    import json

    result = run_headless(HeroSiegeConfig())
    print(json.dumps(result, indent=2))
