# -*- coding: utf-8 -*-
"""Генератор подземелий.

Каждый уровень: сетка 3×3 комнат (9 секций), соединённых коридорами.
Граф комнат гарантированно связен (проверка после генерации). В каждой
комнате случайные размер и положение. Коридоры хранят свою геометрию
(координаты клеток), чтобы по ним тоже можно было ходить.

Стартовая комната помечена is_start, в конечной (is_end) — лестница.
"""
from __future__ import annotations

import random

from rogue.domain.entities import (
    Level, Room, Corridor, DungeonMap, TileType, Position, Enemy, Item,
)
from rogue.domain import enemies as en
from rogue.domain import items as it
from rogue.domain import fog


MAP_W, MAP_H = 80, 40

# Сетка 3×3: границы секций (каждая ~26×13)
_SECTION_W = MAP_W // 3
_SECTION_H = MAP_H // 3


def _section_origin(idx: int) -> tuple[int, int]:
    """Вернуть (x0, y0) — левый верхний угол секции для комнаты idx (0..8)."""
    r, c = divmod(idx, 3)
    return c * _SECTION_W, r * _SECTION_H


def _make_rooms(rng) -> list[Room]:
    rooms = []
    for idx in range(9):
        sx, sy = _section_origin(idx)
        w = rng.randint(7, 12)
        h = rng.randint(5, 8)
        # поместить комнату в пределах секции с отступом
        max_dx = max(1, _SECTION_W - w - 2)
        max_dy = max(1, _SECTION_H - h - 2)
        x = sx + rng.randint(1, max_dx)
        y = sy + rng.randint(1, max_dy)
        rooms.append(Room(x=x, y=y, width=w, height=h, index=idx))
    return rooms


def _neighbors_in_grid(i: int) -> list[int]:
    r, c = divmod(i, 3)
    res = []
    if r > 0: res.append(i - 3)
    if r < 2: res.append(i + 3)
    if c > 0: res.append(i - 1)
    if c < 2: res.append(i + 1)
    return res


def _is_connected(rooms_count: int, corridors: list[Corridor]) -> bool:
    """Проверка связности графа (BFS по неориентированным рёбрам)."""
    adj = {i: set() for i in range(rooms_count)}
    for c in corridors:
        adj[c.a].add(c.b)
        adj[c.b].add(c.a)
    seen = {0}
    stack = [0]
    while stack:
        cur = stack.pop()
        for n in adj[cur]:
            if n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == rooms_count


def _connect(rng, rooms: list[Room]) -> list[Corridor]:
    """Сгенерировать коридоры: остов (DFS) + доп. рёбра для циклов.
    Гарантирует связность."""
    corridors: list[Corridor] = []

    def add_edge(i, j):
        a, b = (i, j) if i < j else (j, i)
        for c in corridors:
            if c.a == a and c.b == b:
                return
        corridors.append(Corridor(a=a, b=b))

    visited = [False] * len(rooms)
    visited[0] = True
    stack = [0]
    while stack:
        cur = stack[-1]
        nbs = [n for n in _neighbors_in_grid(cur) if not visited[n]]
        if not nbs:
            stack.pop()
            continue
        nxt = rng.choice(nbs)
        add_edge(cur, nxt)
        visited[nxt] = True
        stack.append(nxt)
    # доп. рёбра для колец (3-5 штук)
    for _ in range(rng.randint(3, 5)):
        i, j = rng.sample(range(len(rooms)), 2)
        if j in _neighbors_in_grid(i):
            add_edge(i, j)
    assert _is_connected(len(rooms), corridors), "граф комнат несвязен"
    return corridors


def _carve_room(tiles, room: Room):
    for y in range(room.y, room.y + room.height):
        for x in range(room.x, room.x + room.width):
            if 0 <= y < MAP_H and 0 <= x < MAP_W:
                tiles[y][x] = TileType.FLOOR


def _carve_corridor(tiles, a: Room, b: Room, rng) -> list[Position]:
    """L-образный коридор. Возвращает список вырезанных клеток."""
    ax, ay = a.center.x, a.center.y
    bx, by = b.center.x, b.center.y
    cells = []
    if rng.random() < 0.5:
        for x in range(min(ax, bx), max(ax, bx) + 1):
            cells.append(Position(x, ay))
        for y in range(min(ay, by), max(ay, by) + 1):
            cells.append(Position(bx, y))
    else:
        for y in range(min(ay, by), max(ay, by) + 1):
            cells.append(Position(ax, y))
        for x in range(min(ax, bx), max(ax, bx) + 1):
            cells.append(Position(x, by))
    for p in cells:
        if 0 <= p.y < MAP_H and 0 <= p.x < MAP_W:
            if tiles[p.y][p.x] == TileType.WALL:
                tiles[p.y][p.x] = TileType.FLOOR
    return cells


def _empty_map():
    return [[TileType.WALL] * MAP_W for _ in range(MAP_H)]


def generate_level(index: int, rng) -> Level:
    rooms = _make_rooms(rng)
    corridors = _connect(rng, rooms)
    tiles = _empty_map()
    for room in rooms:
        _carve_room(tiles, room)
    for c in corridors:
        c.cells = _carve_corridor(tiles, rooms[c.a], rooms[c.b], rng)

    dmap = DungeonMap(width=MAP_W, height=MAP_H, tiles=tiles)
    # стартовая — комната 0, конечная — самая «дальняя» (другой конец сетки)
    rooms[0].is_start = True
    rooms[8].is_end = True
    level = Level(index=index, map=dmap, rooms=rooms, corridors=corridors)

    level.start = rooms[0].random_floor(rng)
    level.stairs = rooms[8].random_floor(rng)
    dmap.set_tile(level.stairs, TileType.STAIRS_DOWN)

    _populate(level, rng, index)
    fog.init_visibility(level)
    return level


def _populate(level: Level, rng, depth: int):
    n_enemies = min(2 + depth // 2, 10)
    n_items = max(1, 4 - depth // 6)
    pool = en.pool_for_depth(depth)

    occupied = {level.start, level.stairs}
    # стартовая комната пуста; остальные — заполняем
    for room in level.rooms[1:]:
        for _ in range(rng.randint(0, 2)):
            if n_enemies <= 0:
                break
            pos = _free_cell(room, rng, occupied)
            if pos is None:
                continue
            tname = rng.choice(pool)
            level.enemies.append(en.make_enemy(tname, rng, pos))
            n_enemies -= 1
        if n_items > 0 and rng.random() < 0.6:
            pos = _free_cell(room, rng, occupied)
            if pos is not None:
                item = it.make_random(rng, depth)
                level.items.append(item)
                level.item_positions[(pos.x, pos.y)] = item
                n_items -= 1


def _free_cell(room: Room, rng, occupied) -> Position | None:
    for _ in range(20):
        p = room.random_floor(rng)
        if p not in occupied:
            occupied.add(p)
            return p
    return None
