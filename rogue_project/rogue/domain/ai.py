# -*- coding: utf-8 -*-
"""ИИ противников.

Два режима движения:
  1) Собственный паттерн (до начала преследования) — у каждого типа свой.
  2) Преследование игрока по кратчайшему пути (BFS по проходимым клеткам),
     если игрок в радиусе hostility и путь существует.

Если игрок в радиусе, но пути нет — продолжаем собственный паттерн.
"""
from __future__ import annotations

from collections import deque

from rogue.domain.entities import (
    Enemy, Player, DungeonMap, Position, DIRECTIONS_8, DIRECTIONS_4,
)
from rogue.domain.enemies import ZOMBIE, VAMPIRE, GHOST, OGRE, SERPENT


def _bfs_next(start: Position, goal: Position, dmap: DungeonMap,
              occupied: set) -> Position | None:
    """Вернуть следующую клетку на кратчайшем пути start→goal или None."""
    if start == goal:
        return start
    q = deque([start])
    came = {start: None}
    while q:
        cur = q.popleft()
        for d in DIRECTIONS_8:
            nxt = cur + d
            if nxt in came:
                continue
            if nxt == goal or (dmap.is_walkable(nxt) and nxt not in occupied):
                came[nxt] = cur
                if nxt == goal:
                    # откат к первому шагу
                    step = nxt
                    while came[step] != start:
                        step = came[step]
                    return step
                q.append(nxt)
        if len(came) > 4000:   # защита от раздувания
            break
    return None


def _can_chase(enemy: Enemy, player: Player, dmap: DungeonMap,
               occupied: set) -> Position | None:
    """Если игрок в радиусе hostility и путь есть — вернуть шаг к нему."""
    if enemy.pos.chebyshev(player.pos) <= enemy.hostility:
        nxt = _bfs_next(enemy.pos, player.pos, dmap, occupied)
        if nxt is not None:
            return nxt
    return None


def _pattern_step(enemy: Enemy, dmap: DungeonMap, occupied: set, rng) -> Position:
    """Шаг собственного паттерна движения (до боя)."""
    cur = enemy.pos
    if enemy.type_name == ZOMBIE:
        # медленно бродит
        d = rng.choice(DIRECTIONS_4)
        return cur + d if dmap.is_walkable(cur + d) else cur

    if enemy.type_name == GHOST:
        # телепортируется по комнате / случайно
        d = rng.choice(DIRECTIONS_8)
        for _ in range(3):
            cand = cur + d
            if dmap.is_walkable(cand):
                return cand
            d = rng.choice(DIRECTIONS_8)
        return cur

    if enemy.type_name == VAMPIRE:
        # двигается к игроку даже дальше обычного (агрессивный)
        d = rng.choice(DIRECTIONS_8)
        return cur + d if dmap.is_walkable(cur + d) else cur

    if enemy.type_name == OGRE:
        # ходит на 2 клетки по прямой
        d = rng.choice(DIRECTIONS_4)
        mid = cur + d
        far = cur + Position(d.x * 2, d.y * 2)
        if dmap.is_walkable(far) and far not in occupied:
            return far
        if dmap.is_walkable(mid) and mid not in occupied:
            return mid
        return cur

    if enemy.type_name == SERPENT:
        # по диагонали, меняя сторону
        diag = [(1, -1), (-1, -1), (1, 1), (-1, 1)]
        dx, dy = diag[enemy.pattern_dir % 4]
        if rng.random() < 0.3:
            enemy.pattern_dir += 1
        cand = cur + Position(dx, dy)
        if dmap.is_walkable(cand):
            return cand
        enemy.pattern_dir += 1
        dx, dy = diag[enemy.pattern_dir % 4]
        cand = cur + Position(dx, dy)
        return cand if dmap.is_walkable(cand) else cur

    d = rng.choice(DIRECTIONS_4)
    return cur + d if dmap.is_walkable(cur + d) else cur


def move_enemy(enemy: Enemy, player: Player, dmap: DungeonMap,
               occupied: set, rng) -> Position:
    """Решить, куда пойдёт противник. Возвращает новую позицию.

    occupied — множество занятых другими существами позиций (без enemy).
    """
    # Огр отдыхает после атаки — стоит на месте
    if enemy.rest > 0:
        enemy.rest -= 1
        return enemy.pos

    # Преследование, если вступил в бой или игрок рядом и путь есть
    if enemy.engaged or enemy.pos.chebyshev(player.pos) <= enemy.hostility:
        step = _can_chase(enemy, player, dmap, occupied)
        if step is not None:
            enemy.engaged = True
            return step
    # Иначе собственный паттерн
    return _pattern_step(enemy, dmap, occupied, rng)
