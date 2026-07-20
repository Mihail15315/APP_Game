# -*- coding: utf-8 -*-
"""Команды игры. Абстракция пользовательского ввода без curses."""
from enum import Enum, auto


class Command(Enum):
    # движение (WASD)
    MOVE_UP = auto()
    MOVE_DOWN = auto()
    MOVE_LEFT = auto()
    MOVE_RIGHT = auto()
    WAIT = auto()
    # использование из рюкзака (h/j/k/e) — открыть список выбора
    USE_WEAPON = auto()    # h
    USE_FOOD = auto()      # j
    USE_POTION = auto()    # k
    USE_SCROLL = auto()    # e
    # выбор предмета в меню (0-9)
    SELECT_0 = auto()
    SELECT_1 = auto()
    SELECT_2 = auto()
    SELECT_3 = auto()
    SELECT_4 = auto()
    SELECT_5 = auto()
    SELECT_6 = auto()
    SELECT_7 = auto()
    SELECT_8 = auto()
    SELECT_9 = auto()
    # экраны
    SHOW_INVENTORY = auto()
    SHOW_STATISTICS = auto()
    SHOW_HIGHSCORES = auto()
    # мета
    QUIT = auto()
    CONFIRM = auto()
    IGNORE = auto()
    CONTINUE_SESSION = auto()
    NEW_GAME = auto()


def select_to_index(cmd: Command) -> int | None:
    """SELECT_N → N (0..9), иначе None."""
    mapping = {
        Command.SELECT_0: 0, Command.SELECT_1: 1, Command.SELECT_2: 2,
        Command.SELECT_3: 3, Command.SELECT_4: 4, Command.SELECT_5: 5,
        Command.SELECT_6: 6, Command.SELECT_7: 7, Command.SELECT_8: 8,
        Command.SELECT_9: 9,
    }
    return mapping.get(cmd)
