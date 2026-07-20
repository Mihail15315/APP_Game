# -*- coding: utf-8 -*-
"""Точка входа. Внедрение зависимостей и инициализация curses."""
from __future__ import annotations

import sys
import curses

from rogue.data.game_repository import FileGameRepository
from rogue.controllers.game_controller import GameController
from rogue.domain.game import Game
from rogue.presentation.view import (
    GameView, C_DEFAULT, C_PLAYER, C_WALL, C_STATUS, C_TITLE, C_MSG,
    C_FLOOR, C_STAIRS, C_ITEM, C_ZOMBIE, C_VAMPIRE, C_GHOST, C_OGRE, C_SERPENT,
)
from rogue.presentation.input_handler import InputHandler


def _init_colors() -> None:
    curses.curs_set(0)
    curses.noecho()
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        curses.init_pair(C_DEFAULT, curses.COLOR_WHITE, bg)
        curses.init_pair(C_PLAYER, curses.COLOR_YELLOW, bg)
        curses.init_pair(C_WALL, curses.COLOR_CYAN, bg)
        curses.init_pair(C_STATUS, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(C_TITLE, curses.COLOR_GREEN, bg)
        curses.init_pair(C_MSG, curses.COLOR_RED, bg)
        curses.init_pair(C_FLOOR, curses.COLOR_WHITE, bg)
        curses.init_pair(C_STAIRS, curses.COLOR_MAGENTA, bg)
        curses.init_pair(C_ITEM, curses.COLOR_BLUE, bg)
        curses.init_pair(C_ZOMBIE, curses.COLOR_GREEN, bg)
        curses.init_pair(C_VAMPIRE, curses.COLOR_RED, bg)
        curses.init_pair(C_GHOST, curses.COLOR_WHITE, bg)
        curses.init_pair(C_OGRE, curses.COLOR_YELLOW, bg)
        curses.init_pair(C_SERPENT, curses.COLOR_WHITE, bg)


def main(stdscr: curses.window) -> int:
    _init_colors()
    repository = FileGameRepository()
    game = Game(repository=repository)
    view = GameView(stdscr)
    input_handler = InputHandler(stdscr)
    controller = GameController(game, view, input_handler, repository)
    controller.run()
    return 0


def cli_main() -> None:
    try:
        sys.exit(curses.wrapper(main))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    cli_main()
