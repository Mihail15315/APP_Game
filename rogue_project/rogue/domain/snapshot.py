# -*- coding: utf-8 -*-
"""Снимок состояния игры для слоя представления.

Snapshot — проекция состояния домена, которую View использует для
отрисовки. Никаких ссылок на curses.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rogue.domain.entities import Player, Level, Item


@dataclass
class Snapshot:
    level: Level
    player: Player
    floor: int
    total_levels: int
    message: str
    game_over: bool
    show_title: bool = False
    show_inventory: bool = False
    show_highscores: bool = False
    inv_cursor: int = 0
    highscores: list = field(default_factory=list)
    won: bool = False
    visible_enemies: list = field(default_factory=list)
