# -*- coding: utf-8 -*-
"""Туман войны.

Правила (по заданию 4):
  - Неизведанные комнаты/коридоры не отображаются (UNKNOWN).
  - Просмотренные, но без игрока, комнаты рисуются только как стены/пол (EXPLORED).
  - Текущая комната игрока: видны стены, пол, акторы, предметы (VISIBLE).
  - Коридор: туман рассеивается в области прямой видимости по лучам
    (алгоритм Брезенхэма) до первой стены.
"""
from __future__ import annotations

from rogue.domain.entities import (
    Position, Level, Room, Visibility, TileType, DIRECTIONS_8,
)


def init_visibility(level: Level) -> None:
    h, w = level.map.height, level.map.width
    level.visibility = [[Visibility.UNKNOWN for _ in range(w)] for _ in range(h)]


def room_of(level: Level, pos: Position) -> Room | None:
    for r in level.rooms:
        if r.contains(pos):
            return r
    return None


def _reveal_room(level: Level, room: Room, state: Visibility) -> None:
    for y in range(room.y, room.y + room.height):
        for x in range(room.x, room.x + room.width):
            if 0 <= y < level.map.height and 0 <= x < level.map.width:
                if level.visibility[y][x].value < state.value:
                    level.visibility[y][x] = state


def _bresenham(x0, y0, x1, y1):
    """Генератор точек на отрезке (x0,y0)->(x1,y1) по алгоритму Брезенхэма."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _cast_ray(level: Level, origin: Position, target: Position, radius: int) -> None:
    """Бросить луч до target, отмечая клетки как VISIBLE до первой стены."""
    for x, y in _bresenham(origin.x, origin.y, target.x, target.y):
        if not level.map.in_bounds(Position(x, y)):
            return
        if level.visibility[y][x] != Visibility.VISIBLE:
            level.visibility[y][x] = Visibility.VISIBLE
        # стена видна, но луч дальше не идёт
        if level.map.tiles[y][x] == TileType.WALL:
            return


def update_visibility(level: Level, player_pos: Position, radius: int = 6) -> None:
    """Пересчитать туман войны при ходе игрока."""
    if not level.visibility:
        init_visibility(level)

    # 1) Все VISIBLE клеточки, которых больше нет в зоне — стать EXPLORED
    for y in range(level.map.height):
        for x in range(level.map.width):
            if level.visibility[y][x] == Visibility.VISIBLE:
                level.visibility[y][x] = Visibility.EXPLORED

    cur_room = room_of(level, player_pos)
    if cur_room is not None:
        # В комнате игрока: вся комната видна
        _reveal_room(level, cur_room, Visibility.VISIBLE)
        # также подсветить стены-границы коридоров, примыкающих к комнате
    else:
        # Игрок в коридоре: видны клетки в радиусе (ray casting по 8 направлениям
        # + лучи к границам), первая стена останавливает луч
        for d in DIRECTIONS_8:
            for r in range(1, radius + 1):
                tgt = Position(player_pos.x + d.x * r, player_pos.y + d.y * r)
                if not level.map.in_bounds(tgt):
                    break
                _cast_ray(level, player_pos, tgt, radius)
                if level.map.tile_at(tgt) == TileType.WALL:
                    break
        # сам игрок всегда видит свою клетку и соседей
        for d in [Position(0, 0)] + DIRECTIONS_8:
            p = player_pos + d
            if level.map.in_bounds(p):
                level.visibility[p.y][p.x] = Visibility.VISIBLE
