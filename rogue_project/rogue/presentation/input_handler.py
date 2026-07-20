# -*- coding: utf-8 -*-
"""Обработчик ввода: клавиша curses → доменная Command."""
from __future__ import annotations

import curses

from rogue.domain.commands import Command


class InputHandler:
    def __init__(self, screen: curses.window) -> None:
        self._s = screen

    def get_command(self) -> Command:
        key = self._s.getch()
        return self.key_to_command(key)

    @staticmethod
    def key_to_command(key: int) -> Command:
        if key in (curses.KEY_UP, ord("k"), ord("K")):
            return Command.MOVE_UP
        if key in (curses.KEY_DOWN, ord("j"), ord("J")):
            return Command.MOVE_DOWN
        if key in (curses.KEY_LEFT, ord("h"), ord("H")):
            return Command.MOVE_LEFT
        if key in (curses.KEY_RIGHT, ord("l"), ord("L")):
            return Command.MOVE_RIGHT
        if key == ord("."):
            return Command.WAIT
        if key in (ord("i"), ord("I")):
            return Command.SHOW_INVENTORY
        if key in (ord("H"),):  # Shift+H — не конфликтует; используем 'r'
            return Command.SHOW_HIGHSCORES
        if key in (ord("r"), ord("R")):
            return Command.SHOW_HIGHSCORES
        if key in (ord("g"), ord("G")):
            return Command.PICKUP
        if key in (ord("u"), ord("U")):
            return Command.USE
        if key in (ord("w"), ord("W")):
            return Command.EQUIP
        if key in (ord("d"), ord("D")):
            return Command.DROP
        if key in (ord("q"), ord("Q")):
            return Command.QUIT
        if key in (curses.KEY_ENTER, 10, 13, 32):
            return Command.CONFIRM
        return Command.IGNORE
