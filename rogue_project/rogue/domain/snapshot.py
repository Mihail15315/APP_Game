# -*- coding: utf-8 -*-
"""Снимок состояния игры для слоя представления."""
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
    show_statistics: bool = False
    show_highscores: bool = False
    # меню выбора предмета (когда нажато h/j/k/e)
    show_selection: bool = False
    selection_items: list = field(default_factory=list)   # list[Item]
    selection_kind: str = ""        # "weapon"/"food"/"potion"/"scroll"
    selection_allow_zero: bool = False   # для оружия (убрать из рук)
    inv_cursor: int = 0
    highscores: list = field(default_factory=list)
    statistics: dict = field(default_factory=dict)
    won: bool = False
    visible_enemies: list = field(default_factory=list)
    # стартовый вопрос: продолжить сохранённую сессию?
    show_continue_prompt: bool = False
