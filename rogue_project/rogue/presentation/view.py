# -*- coding: utf-8 -*-
"""Отрисовка игры через curses.

View работает только со Snapshot. Поддерживает туман войны (по сетке
visibility уровня), меню выбора предмета 0-9, инвентарь, статистику и
таблицу лидеров.
"""
from __future__ import annotations

import curses

from rogue.domain.snapshot import Snapshot
from rogue.domain.entities import TileType, Visibility, ItemType

# Цветовые пары
C_DEFAULT = 1
C_PLAYER = 2
C_WALL = 3
C_STATUS = 4
C_TITLE = 5
C_MSG = 6
C_FLOOR = 7
C_STAIRS = 8
C_ITEM = 9
C_ZOMBIE = 10
C_VAMPIRE = 11
C_GHOST = 12
C_OGRE = 13
C_SERPENT = 14


class GameView:
    def __init__(self, screen: curses.window) -> None:
        self._s = screen

    def render(self, snap: Snapshot) -> None:
        self._s.erase()
        if snap.show_continue_prompt:
            self._render_continue_prompt()
        elif snap.show_title:
            self._render_title()
        elif snap.show_highscores:
            self._render_highscores(snap)
        elif snap.show_statistics:
            self._render_statistics(snap)
        elif snap.show_selection:
            self._render_selection(snap)
        elif snap.show_inventory:
            self._render_inventory(snap)
        elif snap.game_over:
            self._render_game_over(snap)
        else:
            self._render_world(snap)
        self._s.refresh()

    # ---- заставка ----
    def _render_title(self) -> None:
        h, w = self._s.getmaxyx()
        lines = [
            "████████╗ ██████╗ ██╗   ██╗██████╗ ██╗███╗   ██╗",
            "╚══██╔══╝██╔────██╗██║   ██║██╔══██╗██║████╗  ██║",
            "   ██║   ██║     ██║██║   ██║██║  ██║██║██╔██╗ ██║",
            "   ╚═╝   ██║     ██║██║   ██║██║  ██║██║██║╚██╗██║",
            "        ╚██████╔╝╚██████╔╝██████╔╝██║██║ ╚████║",
            "         ╚═════╝  ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝",
            "",
            "   21 уровень подземелья • 5 типов монстров • сокровища",
            "",
            "   Управление:  WASD — движение    . — ждать",
            "                h — оружие  j — еда  k — эликсир  e — свиток",
            "                i — рюкзак  t — статистика  r — рекорды",
            "                выбор предмета: 0-9   q — выход",
            "",
            "   Нажмите Enter / пробел, чтобы войти в подземелье...",
        ]
        y0 = max(0, (h - len(lines)) // 2)
        for i, line in enumerate(lines):
            if 0 <= y0 + i < h:
                x = max(0, (w - len(line)) // 2)
                try:
                    self._s.addstr(y0 + i, x, line[:w - 1], curses.color_pair(C_TITLE))
                except curses.error:
                    pass

    def _render_continue_prompt(self) -> None:
        h, w = self._s.getmaxyx()
        title = "Найдено сохранение"
        self._safe(h // 2 - 1, max(0, (w - len(title)) // 2), title, C_TITLE)
        sub = "C — продолжить сессию      любая другая клавиша — новая игра"
        self._safe(h // 2 + 1, max(0, (w - len(sub)) // 2), sub, C_DEFAULT)

    # ---- мир с туманом войны ----
    def _render_world(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        m = snap.level.map
        p = snap.player
        vis = snap.level.visibility
        # камера
        cam_x = max(0, min(p.pos.x - w // 2, m.width - w))
        cam_y = max(0, min(p.pos.y - (h - 3) // 2, m.height - (h - 3)))
        for ry in range(h - 3):
            my = ry + cam_y
            if my >= m.height:
                break
            for rx in range(w - 1):
                mx = rx + cam_x
                if mx >= m.width:
                    break
                # туман войны
                if vis and vis[my][mx] == Visibility.UNKNOWN:
                    continue
                visible_now = (not vis) or vis[my][mx] == Visibility.VISIBLE
                t = m.tiles[my][mx]
                ch, col = self._tile_visual(t)
                # в EXPLORED рисуем только стены/пол, без «деталей»
                try:
                    attr = curses.color_pair(col)
                    if not visible_now and t == TileType.FLOOR:
                        attr = curses.color_pair(col) | curses.A_DIM
                    self._s.addch(ry, rx, ch, attr)
                except curses.error:
                    pass
        # предметы (только видимые)
        if vis:
            for (ix, iy), item in snap.level.item_positions.items():
                if vis[iy][ix] != Visibility.VISIBLE:
                    continue
                rx, ry = ix - cam_x, iy - cam_y
                if 0 <= rx < w - 1 and 0 <= ry < h - 3:
                    try:
                        self._s.addch(ry, rx, item.display_char, curses.color_pair(C_ITEM))
                    except curses.error:
                        pass
            # противники (только видимые)
            for e in snap.visible_enemies:
                if (0 <= e.pos.y < m.height and 0 <= e.pos.x < m.width
                        and vis[e.pos.y][e.pos.x] == Visibility.VISIBLE):
                    rx, ry = e.pos.x - cam_x, e.pos.y - cam_y
                    if 0 <= rx < w - 1 and 0 <= ry < h - 3:
                        try:
                            self._s.addch(ry, rx, e.display, curses.color_pair(e.color))
                        except curses.error:
                            pass
        # игрок
        prx, pry = p.pos.x - cam_x, p.pos.y - cam_y
        if 0 <= prx < w - 1 and 0 <= pry < h - 3:
            try:
                self._s.addch(pry, prx, "@", curses.color_pair(C_PLAYER) | curses.A_BOLD)
            except curses.error:
                pass
        # статус
        weapon = p.weapon.name if p.weapon else "без оружия"
        status = (f"Ур:{snap.floor}/{snap.total_levels} "
                  f"HP:{p.health}/{p.effective_max_health} "
                  f"Сила:{p.effective_strength} Лов:{p.effective_agility} "
                  f"Сокр:{p.treasures} | {weapon}")
        self._safe(h - 2, 0, status.ljust(w - 1), C_STATUS)
        self._safe(h - 1, 0, snap.message[:w - 1] or " ", C_MSG)

    def _tile_visual(self, t: TileType):
        if t == TileType.WALL:
            return "#", C_WALL
        if t == TileType.STAIRS_DOWN:
            return ">", C_STAIRS
        if t == TileType.DOOR:
            return "+", C_DEFAULT
        return ".", C_FLOOR

    # ---- выбор предмета ----
    def _render_selection(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        kind_ru = {"weapon": "оружие", "food": "еда", "potion": "эликсир",
                   "scroll": "свиток"}[snap.selection_kind]
        self._safe(0, 0, f"=== Выбор: {kind_ru} ===", C_TITLE)
        if snap.selection_kind == "weapon" and snap.selection_allow_zero:
            self._safe(1, 0, "0 — убрать оружие из рук (не выбрасывать)", C_DEFAULT)
        for i, item in enumerate(snap.selection_items[:9]):
            n = i if snap.selection_allow_zero else i + 1
            line = f"{n} — {item.display_char} {item.name}"
            self._safe(2 + i, 0, line[:w - 1], C_DEFAULT)
        self._safe(h - 2, 0, snap.message[:w - 1] or " ", C_MSG)
        self._safe(h - 1, 0, "Выберите 0-9. q — отмена.", C_MSG)

    # ---- инвентарь ----
    def _render_inventory(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        self._safe(0, 0, "=== Рюкзак ===", C_TITLE)
        bp = snap.player.backpack
        if not bp:
            self._safe(2, 0, "Пусто.", C_DEFAULT)
        for i, item in enumerate(bp):
            line = f"  {item.display_char} {item.name} [{item.item_type.value}]"
            self._safe(2 + i, 0, line[:w - 1], C_DEFAULT)
        wname = snap.player.weapon.name if snap.player.weapon else "нет"
        self._safe(2 + len(bp) + 1, 0, f"Оружие в руках: {wname}", C_DEFAULT)
        self._safe(h - 2, 0, snap.message[:w - 1] or " ", C_MSG)
        self._safe(h - 1, 0, "q — закрыть", C_MSG)

    # ---- статистика ----
    def _render_statistics(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        s = snap.statistics
        self._safe(0, 0, "=== Статистика текущей партии ===", C_TITLE)
        lines = [
            f"Сокровища:           {s.get('treasures', 0)}",
            f"Достигнут уровень:   {snap.floor} / {snap.total_levels}",
            f"Побеждено врагов:    {s.get('enemies_killed', 0)}",
            f"Съедено еды:         {s.get('food_eaten', 0)}",
            f"Выпито эликсиров:    {s.get('potions_drunk', 0)}",
            f"Прочитано свитков:   {s.get('scrolls_read', 0)}",
            f"Нанесено ударов:     {s.get('hits_dealt', 0)}",
            f"Пропущено ударов:    {s.get('hits_taken', 0)}",
            f"Пройдено клеток:     {s.get('steps', 0)}",
        ]
        for i, ln in enumerate(lines):
            self._safe(2 + i, 0, ln[:w - 1], C_DEFAULT)
        self._safe(h - 2, 0, "Любая клавиша — возврат.", C_MSG)

    # ---- рекорды ----
    def _render_highscores(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        self._safe(0, 0, "=== Таблица лидеров ===", C_TITLE)
        self._safe(1, 0, "Сокр  Ур  Враги  Результат", C_DEFAULT)
        for i, rec in enumerate(snap.highscores[:h - 5]):
            line = (f"{rec.get('treasures', 0):<4}  "
                    f"{rec.get('floor', 0):<2}  "
                    f"{rec.get('enemies_killed', 0):<5}  "
                    f"{rec.get('result', '')}")
            self._safe(2 + i, 0, line[:w - 1], C_DEFAULT)
        self._safe(h - 2, 0, "Любая клавиша — возврат.", C_MSG)

    # ---- конец игры ----
    def _render_game_over(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        title = "ПОБЕДА!" if snap.won else "ИГРА ОКОНЧЕНА"
        self._safe(h // 2 - 1, max(0, (w - len(title)) // 2), title, C_TITLE)
        sub = (f"Уровень {snap.floor}, сокровищ: {snap.player.treasures}, "
               f"врагов: {snap.statistics.get('enemies_killed', 0)}")
        self._safe(h // 2 + 1, max(0, (w - len(sub)) // 2), sub, C_DEFAULT)
        self._safe(h // 2 + 3, 0, "Enter — новая игра, q — выход.", C_MSG)

    def _safe(self, y, x, text, color):
        h, w = self._s.getmaxyx()
        if 0 <= y < h and 0 <= x < w:
            try:
                self._s.addstr(y, x, text[:w - x], curses.color_pair(color))
            except curses.error:
                pass
