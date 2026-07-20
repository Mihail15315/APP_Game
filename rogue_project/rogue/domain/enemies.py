# -*- coding: utf-8 -*-
"""5 типов противников с характеристиками, цветами и особыми правилами.

Цвет — индекс curses color_pair, который инициализируется в presentation.
Здесь живёт только число (домен не зависит от curses).
"""
from __future__ import annotations

import random

from rogue.domain.entities import Enemy, Position

# Имена типов
ZOMBIE = "zombie"
VAMPIRE = "vampire"
GHOST = "ghost"
OGRE = "ogre"
SERPENT = "serpent"

# Цветовые индексы (согласовано с presentation/view.py)
COLOR_ZOMBIE = 10
COLOR_VAMPIRE = 11
COLOR_GHOST = 12
COLOR_OGRE = 13
COLOR_SERPENT = 14


def _make(type_name, display, color, hp, ag, st, host, treas, pos):
    return Enemy(
        pos=pos, max_health=hp, health=hp, agility=ag, strength=st,
        type_name=type_name, display=display, color=color,
        hostility=host, treasures=treas,
    )


def make_zombie(rng, pos):
    return _make(ZOMBIE, "z", COLOR_ZOMBIE,
                 hp=rng.randint(15, 25), ag=3, st=6, host=4, treas=rng.randint(5, 12), pos=pos)


def make_vampire(rng, pos):
    return _make(VAMPIRE, "v", COLOR_VAMPIRE,
                 hp=rng.randint(20, 30), ag=9, st=7, host=7, treas=rng.randint(15, 30), pos=pos)


def make_ghost(rng, pos):
    return _make(GHOST, "g", COLOR_GHOST,
                 hp=rng.randint(8, 14), ag=11, st=3, host=3, treas=rng.randint(8, 18), pos=pos)


def make_ogre(rng, pos):
    return _make(OGRE, "O", COLOR_OGRE,
                 hp=rng.randint(30, 45), ag=4, st=14, host=5, treas=rng.randint(20, 40), pos=pos)


def make_serpent(rng, pos):
    return _make(SERPENT, "s", COLOR_SERPENT,
                 hp=rng.randint(12, 20), ag=14, st=6, host=8, treas=rng.randint(12, 25), pos=pos)


# Пул противников в зависимости от глубины уровня (0..20)
def pool_for_depth(depth: int):
    """Какие типы монстров могут появиться на данной глубине."""
    pool = [ZOMBIE]
    if depth >= 2:
        pool.append(GHOST)
    if depth >= 4:
        pool.append(VAMPIRE)
    if depth >= 6:
        pool.append(SERPENT)
    if depth >= 9:
        pool.append(OGRE)
    return pool


_FACTORIES = {
    ZOMBIE: make_zombie,
    VAMPIRE: make_vampire,
    GHOST: make_ghost,
    OGRE: make_ogre,
    SERPENT: make_serpent,
}


def make_enemy(type_name: str, rng, pos: Position) -> Enemy:
    return _FACTORIES[type_name](rng, pos)
