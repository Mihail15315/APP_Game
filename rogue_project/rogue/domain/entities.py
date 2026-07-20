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
    """Подтип: для эликсиров/свитков указывает, какую характеристику менять;
    для оружия — что это оружие; для еды/сокровищ — нет подтипа."""
    NONE = "—"
    AGILITY = "ловкость"
    STRENGTH = "сила"
    MAX_HP = "макс_здоровье"
    WEAPON = "оружие"


@dataclass
class Item:
    """Игровой предмет.

    Поля-«дельты» интерпретируются в зависимости от типа:
      - еда: health восстанавливает здоровье;
      - эликсир: временно +подтип (agility/strength/max_health), по истечении
        восстанавливает прежние значения;
      - свиток: постоянно +подтип;
      - оружие: strength — модификатор урона;
      - сокровище: cost — стоимость в таблицу рекордов.
    """
    item_type: ItemType
    sub_type: ItemSubType = ItemSubType.NONE
    health: int = 0           # восстановление здоровья (еда)
    max_health: int = 0       # +к макс. здоровью (эликсиры/свитки)
    agility: int = 0          # +к ловкости
    strength: int = 0         # +к силе (или урон оружия)
    cost: int = 0             # стоимость (сокровище)
    duration: int = 0         # длительность эффекта эликсира (в ходах)
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
    """Базовый персонаж (игрок и противники)."""
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
class Player(Character):
    """Игрок."""
    experience: int = 0
    treasures: int = 0                 # суммарная стоимость собранных сокровищ
    weapon: Item | None = None         # экипированное оружие
    backpack: list[Item] = field(default_factory=list)
    # активные временные эффекты (эликсиры): список (end_turn, max_health_bonus,
    # agility_bonus, strength_bonus, max_hp_total — на сколько подняли макс)
    effects: list[list] = field(default_factory=list)
    # спец-состояния (от особых монстров)
    sleeping: int = 0                  # ходов сна осталось
    max_hp_drain: int = 0              # вампир уменьшил max_health

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
    """Учётная ячейка одного типа предметов (до 9 штук)."""
    item_type: ItemType
    items: list[Item] = field(default_factory=list)

    @property
    def is_full(self) -> bool:
        return len(self.items) >= 9


@dataclass
class Room:
    """Прямоугольная комната на карте."""
    x: int          # левый верхний угол
    y: int
    width: int
    height: int
    index: int = 0  # позиция в сетке 3×3 (0..8)

    @property
    def center(self) -> Position:
        return Position(self.x + self.width // 2, self.y + self.height // 2)

    def random_floor(self, rng) -> Position:
        import random
        return Position(
            rng.randint(self.x + 1, self.x + self.width - 2),
            rng.randint(self.y + 1, self.y + self.height - 2),
        )

    def contains(self, pos: Position) -> bool:
        return (self.x <= pos.x < self.x + self.width and
                self.y <= pos.y < self.y + self.height)


@dataclass
class Corridor:
    """Связь между двумя комнатами. Карвинг коридора делает генератор карты."""
    a: int   # индекс комнаты
    b: int   # индекс комнаты


@dataclass
class Enemy(Character):
    """Противник. type_name задаётся в enemies.py через фабрики."""
    type_name: str = ""
    display: str = "?"
    color: int = 0          # индекс цвета curses (для view)
    hostility: int = 0      # дистанция, с которой начинает преследовать
    treasures: int = 0      # сокровищ выпадает при победе
    # специфичные поля:
    rest: int = 0           # огр отдыхает (1 ход после атаки)
    guaranteed_hit_next: bool = False  # огр гарантированно бьёт после отдыха
    first_strike_miss: bool = False    # вампир: первый удар игрока — промах
    visible: bool = True    # привидение: периодически невидимо
    pattern_dir: int = 0    # направление собственного паттерна
    engaged: bool = False   # вступил в бой (для смены паттерна на преследование)
    phase: int = 0          # фаза для периодических эффектов


@dataclass
class Level:
    """Уровень подземелья."""
    index: int                       # 0-based: 0..20
    map: "DungeonMap" = None         # type: ignore
    rooms: list[Room] = field(default_factory=list)
    corridors: list[Corridor] = field(default_factory=list)
    enemies: list[Enemy] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    item_positions: dict = field(default_factory=dict)  # (x,y) -> Item
    start: Position = field(default_factory=lambda: Position(0, 0))
    stairs: Position = field(default_factory=lambda: Position(0, 0))


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
        return self.in_bounds(pos) and self.tile_at(pos) in (TileType.FLOOR, TileType.DOOR, TileType.STAIRS_DOWN)

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
