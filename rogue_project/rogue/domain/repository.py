# -*- coding: utf-8 -*-
"""Порт доступа к данным (Dependency Inversion).

Определяется в домене, реализуется в data. Домен ничего не знает о файлах.
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
    def save_session(self, data: dict) -> None:
        """Сохранить полную игровую сессию для продолжения."""

    @abstractmethod
    def load_session(self) -> dict | None:
        """Загрузить сохранённую сессию или None."""

    @abstractmethod
    def clear_session(self) -> None:
        """Удалить сохранённую сессию (после провала/победы)."""
