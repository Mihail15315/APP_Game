# -*- coding: utf-8 -*-
"""Файловая реализация репозитория (JSON).

Хранит:
  - highscores.json — таблица лидеров (сортировка по сокровищам), с полной
    статистикой попытки;
  - session.json — полная сохранённая сессия для продолжения.
"""
from __future__ import annotations

import json
from pathlib import Path

from rogue.domain.repository import GameRepository


class FileGameRepository(GameRepository):
    def __init__(self, base_dir: str = ".rogue") -> None:
        self._dir = Path(base_dir)
        self._highscores_file = self._dir / "highscores.json"
        self._session_file = self._dir / "session.json"
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_highscore(self, record: dict) -> None:
        hs = self.load_highscores()
        hs.append(record)
        hs.sort(key=lambda r: r.get("treasures", 0), reverse=True)
        self._highscores_file.write_text(
            json.dumps(hs, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_highscores(self) -> list[dict]:
        if not self._highscores_file.exists():
            return []
        try:
            return json.loads(self._highscores_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def save_session(self, data: dict) -> None:
        self._session_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def load_session(self) -> dict | None:
        if not self._session_file.exists():
            return None
        try:
            return json.loads(self._session_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def clear_session(self) -> None:
        if self._session_file.exists():
            self._session_file.unlink()
