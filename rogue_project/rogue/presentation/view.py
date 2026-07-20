# -*- coding: utf-8 -*-
"""Отрисовка состояния игры через curses.

View работает только со Snapshot. Имеет: заставку, игровой мир с камерой,
строку статуса, message-bar, экран инвентаря и таблицу рекордов.
"""
from __future__ import annotations

import curses

from rogue.domain.snapshot import Snapshot
from rogue.domain.entities import TileType, ItemType

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
        if snap.show_title:
            self._render_title()
        elif snap.show_highscores:
            self._render_highscores(snap)
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
            "   21 уровень подземелья, 5 типов монстров, сокровища...",
            "",
            "   Управление:  стрелки или h j k l — движение",
            "                . — ждать    i — рюкзак",
            "                u — использовать   w — экипировать оружие",
            "                r — таблица рекордов   q — выход",
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

    # ---- мир ----
    def _render_world(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        m = snap.level.map
        p = snap.player
        # камера: держим игрока в центре, clamp по границам карты
        cam_x = max(0, min(p.pos.x - w // 2, m.width - w))
        cam_y = max(0, min(p.pos.y - (h - 3) // 2, m.height - (h - 3)))
        # тайлы
        for ry in range(h - 3):
            my = ry + cam_y
            if my >= m.height:
                break
            for rx in range(w - 1):
                mx = rx + cam_x
                if mx >= m.width:
                    break
                t = m.tiles[my][mx]
                ch, col = self._tile_visual(t)
                try:
                    self._s.addch(ry, rx, ch, curses.color_pair(col))
                except curses.error:
                    pass
        # предметы
        for (ix, iy), item in snap.level.item_positions.items():
            rx, ry = ix - cam_x, iy - cam_y
            if 0 <= rx < w - 1 and 0 <= ry < h - 3:
                try:
                    self._s.addch(ry, rx, item.display_char, curses.color_pair(C_ITEM))
                except curses.error:
                    pass
        # противники
        for e in snap.visible_enemies:
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
                self._s.addch(pry, prx, "@",
                              curses.color_pair(C_PLAYER) | curses.A_BOLD)
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

    # ---- инвентарь ----
    def _render_inventory(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        self._safe(0, 0, "=== Рюкзак ===", C_TITLE)
        self._safe(1, 0, "(u — использовать, w — экипировать, q — закрыть)", C_DEFAULT)
        bp = snap.player.backpack
        if not bp:
            self._safe(3, 0, "Пусто.", C_DEFAULT)
        for i, item in enumerate(bp):
            mark = ">" if i == snap.inv_cursor else " "
            line = f"{mark} {item.display_char} {item.name} [{item.item_type.value}]"
            self._safe(3 + i, 0, line[:w - 1], C_DEFAULT)
        wname = snap.player.weapon.name if snap.player.weapon else "нет"
        self._safe(3 + len(bp) + 1, 0, f"Оружие: {wname}", C_DEFAULT)
        self._safe(h - 2, 0, snap.message[:w - 1] or " ", C_MSG)

    # ---- рекорды ----
    def _render_highscores(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        self._safe(0, 0, "=== Таблица рекордов ===", C_TITLE)
        self._safe(1, 0, "Уровень   Сокровища   Результат", C_DEFAULT)
        for i, rec in enumerate(snap.highscores[:h - 5]):
            line = f"  {rec.get('floor', 0):<7}  {rec.get('treasures', 0):<9}   {rec.get('result', '')}"
            self._safe(2 + i, 0, line[:w - 1], C_DEFAULT)
        self._safe(h - 2, 0, "Нажмите любую клавишу для возврата.", C_MSG)

    # ---- конец игры ----
    def _render_game_over(self, snap: Snapshot) -> None:
        h, w = self._s.getmaxyx()
        title = "ПОБЕДА!" if snap.won else "ИГРА ОКОНЧЕНА"
        self._safe(h // 2 - 1, max(0, (w - len(title)) // 2), title, C_TITLE)
        sub = (f"Достигнут уровень {snap.floor}, сокровищ: {snap.player.treasures}")
        self._safe(h // 2 + 1, max(0, (w - len(sub)) // 2), sub, C_DEFAULT)
        self._safe(h // 2 + 3, 0, "Enter — новая игра, q — выход.", C_MSG)

    def _safe(self, y, x, text, color):
        h, w = self._s.getmaxyx()
        if 0 <= y < h and 0 <= x < w:
            try:
                self._s.addstr(y, x, text[:w - x], curses.color_pair(color))
            except curses.error:
                pass
