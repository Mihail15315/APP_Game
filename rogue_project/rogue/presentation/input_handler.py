# -*- coding: utf-8 -*-
"""Обработчик ввода: клавиша curses → доменная Command.

Схема управления (по заданию 4):
  WASD — движение;  . — ждать
  h — оружие;  j — еда;  k — эликсир;  e — свиток
  0-9 — выбор в меню
  i — рюкзак;  t — статистика;  r — рекорды
"""
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
        # движение WASD (и стрелки для совместимости)
        if key in (curses.KEY_UP, ord("w"), ord("W")):
            return Command.MOVE_UP
        if key in (curses.KEY_DOWN, ord("s"), ord("S")):
            return Command.MOVE_DOWN
        if key in (curses.KEY_LEFT, ord("a"), ord("A")):
            return Command.MOVE_LEFT
        if key in (curses.KEY_RIGHT, ord("d"), ord("D")):
            return Command.MOVE_RIGHT
        if key == ord("."):
            return Command.WAIT
        # использование предметов
        if key in (ord("h"), ord("H")):
            return Command.USE_WEAPON
        if key in (ord("j"), ord("J")):
            return Command.USE_FOOD
        if key in (ord("k"), ord("K")):
            return Command.USE_POTION
        if key in (ord("e"), ord("E")):
            return Command.USE_SCROLL
        # выбор в меню 0-9
        if key in (ord("0"), curses.KEY_DC):
            return Command.SELECT_0
        for n in range(1, 10):
            if key == ord(str(n)):
                return [Command.SELECT_1, Command.SELECT_2, Command.SELECT_3,
                        Command.SELECT_4, Command.SELECT_5, Command.SELECT_6,
                        Command.SELECT_7, Command.SELECT_8, Command.SELECT_9][n - 1]
        # экраны
        if key in (ord("i"), ord("I")):
            return Command.SHOW_INVENTORY
        if key in (ord("t"), ord("T")):
            return Command.SHOW_STATISTICS
        if key in (ord("r"), ord("R")):
            return Command.SHOW_HIGHSCORES
        # выход / подтверждение
        if key in (ord("q"), ord("Q")):
            return Command.QUIT
        if key in (curses.KEY_ENTER, 10, 13, 32):
            return Command.CONFIRM
        if key in (ord("n"), ord("N")):
            return Command.NEW_GAME
        if key in (ord("c"), ord("C")):
            return Command.CONTINUE_SESSION
        return Command.IGNORE
