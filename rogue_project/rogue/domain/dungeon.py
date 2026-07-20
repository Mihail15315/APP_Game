# -*- coding: utf-8 -*-
"""Генератор подземелий.

Каждый уровень: сетка 3×3 комнат, соединённых коридорами так, что граф
комнат связен (из любой комнаты можно дойти в любую). Стартовая комната
(индекс 0) пуста. В остальных могут быть противники и предметы. В одной из
комнат — лестница (>) на следующий уровень.
"""
from __future__ import annotations

import random

from rogue.domain.entities import (
    Level, Room, Corridor, DungeonMap, TileType, Position, Enemy, Item,
)
from rogue.domain import enemies as en
from rogue.domain import items as it


# Размеры карты
MAP_W, MAP_H = 80, 30

# Сетка комнат 3×3: позиции центров колонок/строк
def _room_grid(rng):
    """Размещает 9 комнат в сетке 3×3 со случайными размерами и промежутками."""
    rooms = []
    # колонки: x-старты; строки: y-старты
    col_x = [1, 28, 55]
    row_y = [1, 11, 21]
    idx = 0
    for r in range(3):
        for c in range(3):
            w = rng.randint(7, 10)
            h = rng.randint(4, 6)
            x = col_x[c] + rng.randint(0, 2)
            y = row_y[r] + rng.randint(0, 1)
            rooms.append(Room(x=x, y=y, width=w, height=h, index=idx))
            idx += 1
    return rooms


def _connect(rng, rooms):
    """Связать комнаты так, чтобы граф был связным. Сначала остовное дерево
    по соседним комнатам, затем несколько случайных доп. рёбер."""
    # соседние индексы в сетке 3×3
    def neighbors(i):
        r, c = divmod(i, 3)
        res = []
        if r > 0: res.append(i - 3)   # вверх
        if r < 2: res.append(i + 3)   # вниз
        if c > 0: res.append(i - 1)   # влево
        if c < 2: res.append(i + 1)   # вправо
        return res

    visited = [False] * 9
    corridors = []
    # DFS-остов
    stack = [0]
    visited[0] = True
    while stack:
        cur = stack[-1]
        nbs = [n for n in neighbors(cur) if not visited[n]]
        if not nbs:
            stack.pop()
            continue
        nxt = rng.choice(nbs)
        corridors.append(Corridor(min(cur, nxt), max(cur, nxt)))
        visited[nxt] = True
        stack.append(nxt)
    # доп. связи для кольцевости (чтобы не было тупиковых деревьев)
    for _ in range(3):
        i, j = rng.sample(range(9), 2)
        if j in neighbors(i):
            corridors.append(Corridor(min(i, j), max(i, j)))
    # убрать дубли
    uniq = {(c.a, c.b): c for c in corridors}
    return list(uniq.values())


def _carve_room(tiles, room: Room):
    for y in range(room.y, room.y + room.height):
        for x in range(room.x, room.x + room.width):
            if 0 <= y < MAP_H and 0 <= x < MAP_W:
                tiles[y][x] = TileType.FLOOR


def _carve_corridor(tiles, a: Room, b: Room, rng):
    """L-образный коридор между центрами двух комнат."""
    ax, ay = a.center.x, a.center.y
    bx, by = b.center.x, b.center.y
    path = []
    if rng.random() < 0.5:
        # сначала по X, потом по Y
        for x in range(min(ax, bx), max(ax, bx) + 1):
            path.append((x, ay))
        for y in range(min(ay, by), max(ay, by) + 1):
            path.append((bx, y))
    else:
        for y in range(min(ay, by), max(ay, by) + 1):
            path.append((ax, y))
        for x in range(min(ax, bx), max(ax, bx) + 1):
            path.append((x, by))
    for x, y in path:
        if 0 <= y < MAP_H and 0 <= x < MAP_W:
            if tiles[y][x] == TileType.WALL:
                tiles[y][x] = TileType.FLOOR


def _empty_map():
    return [[TileType.WALL] * MAP_W for _ in range(MAP_H)]


def generate_level(index: int, rng) -> Level:
    """Сгенерировать уровень по индексу (0..20)."""
    rooms = _room_grid(rng)
    corridors = _connect(rng, rooms)
    tiles = _empty_map()
    for room in rooms:
        _carve_room(tiles, room)
    for c in corridors:
        _carve_corridor(tiles, rooms[c.a], rooms[c.b], rng)

    dmap = DungeonMap(width=MAP_W, height=MAP_H, tiles=tiles)
    level = Level(index=index, map=dmap, rooms=rooms, corridors=corridors)

    # Стартовая комната = 0
    start_room = rooms[0]
    level.start = start_room.random_floor(rng)

    # Лестница в случайной дальней комнате (не в стартовой)
    stairs_room = rng.choice(rooms[1:])
    level.stairs = stairs_room.random_floor(rng)
    dmap.set_tile(level.stairs, TileType.STAIRS_DOWN)

    # Заполнение остальных комнат
    _populate(level, rng, index)

    return level


def _populate(level: Level, rng, depth: int):
    """Разместить противников и предметы по комнатам (кроме стартовой)."""
    # Количество противников растёт с глубиной
    n_enemies = min(3 + depth // 2, 12)
    # Предметов становится меньше с глубиной
    n_items = max(1, 4 - depth // 5)
    pool = en.pool_for_depth(depth)

    occupied = {level.start, level.stairs}
    for room in level.rooms[1:]:
        # 1-2 противника на комнату
        for _ in range(rng.randint(0, 2)):
            if n_enemies <= 0:
                break
            pos = room.random_floor(rng)
            tries = 0
            while pos in occupied and tries < 10:
                pos = room.random_floor(rng)
                tries += 1
            occupied.add(pos)
            tname = rng.choice(pool)
            e = en.make_enemy(tname, rng, pos)
            level.enemies.append(e)
            n_enemies -= 1
        # 0-1 предмет на комнату
        if n_items > 0 and rng.random() < 0.6:
            pos = room.random_floor(rng)
            tries = 0
            while pos in occupied and tries < 10:
                pos = room.random_floor(rng)
                tries += 1
            occupied.add(pos)
            item = it.make_random(rng, depth)
            level.items.append(item)
            level.item_positions[(pos.x, pos.y)] = item
            n_items -= 1
