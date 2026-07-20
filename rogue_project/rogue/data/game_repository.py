# -*- coding: utf-8 -*-
"""Файловая реализация репозитория (JSON).

Хранит таблицу рекордов (историю игр) и опционально текущую сессию в
каталоге .rogue/. Таблица рекордов сортируется по количеству сокровищ.
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
        # сортировка по сокровищам (убывание)
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

    def save_session(self, snapshot) -> None:
        # Полное сохранение/загрузка сессии оставлено на будущие задания.
        pass

    def load_session(self):
        return None
