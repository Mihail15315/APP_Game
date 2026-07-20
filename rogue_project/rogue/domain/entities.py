# -*- coding: utf-8 -*-
"""Игровые сущности домена.

Не зависят ни от curses, ни от хранилища. Все числовые характеристики,
логика изменения состояния и взаимного расположения живут здесь.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TileType(Enum):
    """Тип клетки. value — символ для отображения по умолчанию."""
    WALL = "#"
    FLOOR = "."
    STAIRS_DOWN = ">"   # переход на следующий уровень
    DOOR = "+"


class Visibility(Enum):
    """Состояние клетки для тумана войны."""
    UNKNOWN = 0    # никогда не видел — не рисуем
    EXPLORED = 1   # видел, но сейчас не виден — рисуем только стены/пол
    VISIBLE = 2    # виден сейчас — рисуем всё


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def __add__(self, other: "Position") -> "Position":
        return Position(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Position") -> "Position":
        return Position(self.x - other.x, self.y - other.y)

    def chebyshev(self, other: "Position") -> int:
        """Расстояние Чебышёва (8-связное)."""
        return max(abs(self.x - other.x), abs(self.y - other.y))

    def manhattan(self, other: "Position") -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)


UP = Position(0, -1)
DOWN = Position(0, 1)
LEFT = Position(-1, 0)
RIGHT = Position(1, 0)
UPLEFT = Position(-1, -1)
UPRIGHT = Position(1, -1)
DOWNLEFT = Position(-1, 1)
DOWNRIGHT = Position(1, 1)
DIRECTIONS_4 = [UP, DOWN, LEFT, RIGHT]
DIRECTIONS_8 = [UP, DOWN, LEFT, RIGHT, UPLEFT, UPRIGHT, DOWNLEFT, DOWNRIGHT]


# ====== Предметы ======
class ItemType(Enum):
    """Тип предмета."""
    FOOD = "еда"
    POTION = "эликсир"
    SCROLL = "свиток"
    WEAPON = "оружие"
    TREASURE = "сокровище"


class ItemSubType(Enum):
    NONE = "—"
    AGILITY = "ловкость"
    STRENGTH = "сила"
    MAX_HP = "макс_здоровье"
    WEAPON = "оружие"


@dataclass
class Item:
    """Игровой предмет."""
    item_type: ItemType
    sub_type: ItemSubType = ItemSubType.NONE
    health: int = 0
    max_health: int = 0
    agility: int = 0
    strength: int = 0
    cost: int = 0
    duration: int = 0
    name: str = ""

    @property
    def display_char(self) -> str:
        return {
            ItemType.FOOD: "%",
            ItemType.POTION: "!",
            ItemType.SCROLL: "?",
            ItemType.WEAPON: ")",
            ItemType.TREASURE: "*",
        }[self.item_type]


# ====== Персонажи ======
@dataclass
class Character:
    """Базовый персонаж."""
    pos: Position
    max_health: int
    health: int
    agility: int
    strength: int

    def is_alive(self) -> bool:
        return self.health > 0

    def take_damage(self, dmg: int) -> None:
        self.health -= dmg


@dataclass
class PlayerStats:
    """Накапливаемая статистика прохождения (по заданию 4)."""
    treasures: int = 0
    enemies_killed: int = 0
    food_eaten: int = 0
    potions_drunk: int = 0
    scrolls_read: int = 0
    hits_dealt: int = 0
    hits_taken: int = 0
    steps: int = 0


@dataclass
class Player(Character):
    """Игрок."""
    experience: int = 0
    treasures: int = 0
    weapon: Item | None = None
    backpack: list[Item] = field(default_factory=list)
    effects: list[list] = field(default_factory=list)
    sleeping: int = 0
    max_hp_drain: int = 0
    stats: PlayerStats = field(default_factory=PlayerStats)

    @property
    def effective_strength(self) -> int:
        s = self.strength
        for _, _, sb, _, _ in self.effects:
            s += sb
        return s

    @property
    def effective_agility(self) -> int:
        a = self.agility
        for _, ab, _, _, _ in self.effects:
            a += ab
        return a

    @property
    def effective_max_health(self) -> int:
        return self.max_health + sum(mh for _, _, _, mh, _ in self.effects)


@dataclass
class BackpackSlot:
    item_type: ItemType
    items: list[Item] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return len(self.items) >= 9


@dataclass
class Room:
    x: int
    y: int
    width: int
    height: int
    index: int = 0
    is_start: bool = False
    is_end: bool = False

    @property
    def center(self) -> Position:
        return Position(self.x + self.width // 2, self.y + self.height // 2)

    def random_floor(self, rng) -> Position:
        return Position(
            rng.randint(self.x + 1, self.x + self.width - 2),
            rng.randint(self.y + 1, self.y + self.height - 2),
        )

    def contains(self, pos: Position) -> bool:
        return (self.x <= pos.x < self.x + self.width and
                self.y <= pos.y < self.y + self.height)


@dataclass
class Corridor:
    """Связь между двумя комнатами + сохранённая геометрия клеток коридора."""
    a: int
    b: int
    cells: list = field(default_factory=list)   # list[Position]


@dataclass
class Enemy(Character):
    type_name: str = ""
    display: str = "?"
    color: int = 0
    hostility: int = 0
    treasures: int = 0
    rest: int = 0
    first_strike_miss: bool = False
    visible: bool = True
    pattern_dir: int = 0
    engaged: bool = False
    phase: int = 0


@dataclass
class Level:
    index: int
    map: "DungeonMap" = None  # type: ignore
    rooms: list[Room] = field(default_factory=list)
    corridors: list[Corridor] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    item_positions: dict = field(default_factory=dict)
    start: Position = field(default_factory=lambda: Position(0, 0))
    stairs: Position = field(default_factory=lambda: Position(0, 0))
    # туман войны: сетка видимости клеток
    visibility: list = field(default_factory=list)


@dataclass
class DungeonMap:
    width: int
    height: int
    tiles: list[list[TileType]] = field(default_factory=list)

    def in_bounds(self, pos: Position) -> bool:
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height

    def tile_at(self, pos: Position) -> TileType:
        if not self.in_bounds(pos):
            return TileType.WALL
        return self.tiles[pos.y][pos.x]

    def is_walkable(self, pos: Position) -> bool:
        return (self.in_bounds(pos)
                and self.tile_at(pos) in (TileType.FLOOR, TileType.DOOR, TileType.STAIRS_DOWN))

    def set_tile(self, pos: Position, t: TileType) -> None:
        if self.in_bounds(pos):
            self.tiles[pos.y][pos.x] = t


@dataclass
class GameSession:
    """Игровая сессия: состояние прохождения."""
    player: Player
    level_index: int = 0
    total_levels: int = 21
    treasures: int = 0
    alive: bool = True
    won: bool = False
    turn: int = 0
