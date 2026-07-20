# -*- coding: utf-8 -*-
"""Игровой контроллер (MVC Controller): ввод → логика → отрисовка."""
from __future__ import annotations

from rogue.domain.game import Game
from rogue.domain.repository import GameRepository
from rogue.presentation.view import GameView
from rogue.presentation.input_handler import InputHandler


class GameController:
    def __init__(self, game: Game, view: GameView, input_handler: InputHandler,
                 repository: GameRepository | None = None) -> None:
        self._game = game
        self._view = view
        self._input = input_handler
        self._repository = repository
        self._exit = False

    def run(self) -> None:
        self._view.render(self._game.snapshot())
        while not self._exit:
            cmd = self._input.get_command()
            self._game.handle(cmd)
            if self._game.should_exit():
                self._exit = True
            self._view.render(self._game.snapshot())
