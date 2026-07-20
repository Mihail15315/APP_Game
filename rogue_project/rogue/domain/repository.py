# -*- coding: utf-8 -*-
"""Порт доступа к данным (Dependency Inversion).

Определяется в ДОМЕНЕ, реализуется в слое data. Бизнес-логика зависит
только от этой абстракции.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class GameRepository(ABC):
    @abstractmethod
    def save_highscore(self, record: dict) -> None:
        """Добавить запись о прошедшей игре в таблицу рекордов."""

    @abstractmethod
    def load_highscores(self) -> list[dict]:
        """Прочитать таблицу рекордов (отсортирована по сокровищам)."""

    @abstractmethod
    def save_session(self, snapshot) -> None:
        """Сохранить текущую сессию (опционально)."""

    @abstractmethod
    def load_session(self):
        """Загрузить сохранённую сессию или None."""
