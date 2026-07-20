# -*- coding: utf-8 -*-
"""Команды игры.

Абстракция пользовательского ввода, не зависящая от curses. Слой
presentation переводит коды клавиш в эти значения, domain работает только
с Command.
"""
from enum import Enum, auto


class Command(Enum):
    MOVE_UP = auto()
    MOVE_DOWN = auto()
    MOVE_LEFT = auto()
    MOVE_RIGHT = auto()
    WAIT = auto()           # пропустить ход (противники ходят)
    PICKUP = auto()         # подобрать (обычно автомат, но оставлено)
    USE = auto()            # открыть меню использования предмета
    EQUIP = auto()          # экипировать оружие из рюкзака
    DROP = auto()           # выбросить оружие
    SHOW_INVENTORY = auto()  # показать рюкзак
    NEXT_ITEM = auto()      # навигация в меню (вниз)
    PREV_ITEM = auto()      # навигация в меню (вверх)
    SHOW_HIGHSCORES = auto()
    QUIT = auto()
    CONFIRM = auto()
    IGNORE = auto()
