# -*- coding: utf-8 -*-
"""Ядро игры — бизнес-логика игрового процесса.

Game принимает доменные Command, мутирует состояние и отдаёт Snapshot.
Не зависит от curses и от конкретного хранилища (работает через
абстрактный GameRepository).

Ключевые правила (по заданию):
  - 21 уровень (индексы 0..20).
  - Пошаговый режим: ход игрока запускает ход всех противников.
  - Смерть → сброс сессии и возврат к началу.
  - Переход на следующий уровень по лестнице (>) автоматически.
  - Результат каждой партии пишется в таблицу рекордов.
"""
from __future__ import annotations

import random

from rogue.domain.commands import Command
from rogue.domain.entities import (
    Player, Level, Position, Enemy, Item, ItemType, ItemSubType,
    TileType, UP, DOWN, LEFT, RIGHT, UPLEFT, UPRIGHT, DOWNLEFT, DOWNRIGHT,
    DIRECTIONS_8,
)
from rogue.domain.repository import GameRepository
from rogue.domain.snapshot import Snapshot
from rogue.domain.dungeon import generate_level
from rogue.domain import combat
from rogue.domain import ai
from rogue.domain import items as itf
from rogue.domain import enemies as en


TOTAL_LEVELS = 21
BACKPACK_MAX_PER_TYPE = 9


class Game:
    def __init__(self, repository: GameRepository | None = None,
                 seed: int | None = None) -> None:
        self._repository = repository
        self._rng = random.Random(seed)
        self._player: Player | None = None
        self._level: Level | None = None
        self._floor: int = 0
        self._message: str = ""
        self._game_over: bool = False
        self._show_title: bool = True
        self._show_inventory: bool = False
        self._show_highscores: bool = False
        self._inv_cursor: int = 0
        self._won: bool = False
        self._new_game()

    # ====== Жизненный цикл ======
    def _new_game(self) -> None:
        """Начать новую партию с 1-го уровня."""
        self._player = Player(
            pos=Position(0, 0), max_health=50, health=50,
            agility=8, strength=6, experience=0, treasures=0,
            weapon=None, backpack=[], effects=[],
        )
        self._floor = 0
        self._won = False
        self._game_over = False
        self._show_inventory = False
        self._show_highscores = False
        self._enter_level(0)
        self._message = "Добро пожаловать в подземелье! (q — выход, i — рюкзак)"
        self._show_title = True

    def _enter_level(self, index: int) -> None:
        self._floor = index
        self._level = generate_level(index, self._rng)
        self._player.pos = self._level.start

    def _reset_to_start(self) -> None:
        """После смерти — полный сброс к началу."""
        self._new_game()
        self._show_title = False
        self._message = "Вы погибли... Новая попытка с 1-го уровня."

    # ====== Обработка команд ======
    def handle(self, command: Command) -> None:
        if self._show_title:
            if command == Command.CONFIRM:
                self._show_title = False
            elif command == Command.QUIT:
                self._finish(result="quit")
            return

        if self._show_inventory:
            self._handle_inventory(command)
            return

        if self._show_highscores:
            if command in (Command.CONFIRM, Command.QUIT, Command.IGNORE):
                self._show_highscores = False
            return

        if self._game_over:
            if command == Command.QUIT:
                self._finish(result="quit")
            elif command == Command.CONFIRM:
                self._reset_to_start()
            return

        match command:
            case Command.QUIT:
                self._finish(result="quit")
            case Command.CONFIRM:
                pass
            case Command.SHOW_INVENTORY:
                self._show_inventory = True
                self._inv_cursor = 0
            case Command.SHOW_HIGHSCORES:
                self._show_highscores = True
            case Command.MOVE_UP:
                self._player_step(UP)
            case Command.MOVE_DOWN:
                self._player_step(DOWN)
            case Command.MOVE_LEFT:
                self._player_step(LEFT)
            case Command.MOVE_RIGHT:
                self._player_step(RIGHT)
            case Command.WAIT:
                self._end_player_turn("Вы ждёте.")
            case Command.IGNORE:
                pass

    # ====== Движение игрока ======
    def _player_step(self, delta: Position) -> None:
        target = self._player.pos + delta
        # Если на цели противник — атакуем
        enemy = self._enemy_at(target)
        if enemy is not None:
            self._player_attacks(enemy)
            return
        # Иначе — движение
        if self._level.map.is_walkable(target):
            self._player.pos = target
            # Лестница?
            if self._level.map.tile_at(target) == TileType.STAIRS_DOWN:
                self._descend()
                return
            # Подбираем предмет автоматически
            self._auto_pickup()
            self._end_player_turn("")
        else:
            self._message = "Там стена."

    def _enemy_at(self, pos: Position) -> Enemy | None:
        for e in self._level.enemies:
            if e.is_alive() and e.visible and e.pos == pos:
                return e
        return None

    # ====== Бой ======
    def _player_attacks(self, enemy: Enemy) -> None:
        res = combat.attack(self._player, enemy, self._rng)
        if res.get("vampire_first_miss"):
            self._message = "Первый удар по вампиру прошел мимо!"
        elif res["hit"]:
            self._message = f"Вы бьёте {enemy.type_name}: -{res['damage']} HP"
            if res["killed"]:
                self._player_kills(enemy)
                self._end_player_turn("")
                return
        else:
            self._message = f"Вы промахнулись по {enemy.type_name}."
        self._end_player_turn("")

    def _player_kills(self, enemy: Enemy) -> None:
        enemy.health = 0
        # выпадают сокровища
        gained = enemy.treasures
        self._player.treasures += gained
        # изымаем из уровня
        self._level.enemies = [e for e in self._level.enemies if e.is_alive()]
        self._message = f"{enemy.type_name} повержен! +{gained} сокровищ."
        self._player.experience += 5

    def _enemy_attacks(self, enemy: Enemy, target=None) -> None:
        target = target or self._player
        res = combat.attack(enemy, target, self._rng)
        if res["hit"]:
            # спец-эффекты от типа противника
            self._apply_enemy_specials(enemy, res["damage"])
            if not self._player.is_alive():
                self._on_player_death()
                return
        # Огр: после атаки отдыхает, затем гарантированно бьёт
        if enemy.type_name == en.OGRE:
            enemy.rest = 1

    def _apply_enemy_specials(self, enemy: Enemy, dmg: int) -> None:
        self._player.health -= dmg
        if enemy.type_name == en.VAMPIRE:
            drain = 2
            self._player.max_health = max(5, self._player.max_health - drain)
            self._player.max_hp_drain += drain
            self._message = f"Вампир высасывает {dmg} HP и -{drain} макс. здоровья!"
            return
        if enemy.type_name == en.SERPENT:
            if self._rng.random() < 0.35:
                self._player.sleeping = 1
                self._message = f"Змей усыпляет вас! +{dmg} HP урона."
                return
        self._message = f"{enemy.type_name} бьёт вас: -{dmg} HP"

    # ====== Конец хода игрока → ход противников ======
    def _end_player_turn(self, msg: str) -> None:
        if msg:
            self._message = msg
        if self._player.sleeping > 0:
            self._player.sleeping -= 1
            self._message = "Вы спите и пропускаете ход!"
            # противники получают дополнительный темп
        # обновляем временные эффекты
        m = itf.tick_effects(self._player, 0)
        if m and not self._message:
            self._message = m
        # фаза для периодических эффектов привидения
        for e in self._level.enemies:
            e.phase += 1
            if e.type_name == en.GHOST and not e.engaged:
                # каждые 3 хода меняет видимость
                e.visible = (e.phase % 6 < 3)
        # ход противников
        self._enemies_turn()
        if not self._player.is_alive():
            self._on_player_death()

    def _enemies_turn(self) -> None:
        occupied = {self._player.pos}
        for e in self._level.enemies:
            if not e.is_alive() or not e.visible:
                continue
            other_pos = {o.pos for o in self._level.enemies
                         if o is not e and o.is_alive()}
            # если спит — соседняя клетка игрока недоступна для атаки через ход
            newpos = ai.move_enemy(e, self._player, self._level.map, other_pos, self._rng)
            # если шаг приводит на клетку игрока — атака, не движение
            if newpos == self._player.pos:
                self._enemy_attacks(e)
                occupied.add(e.pos)
                if not self._player.is_alive():
                    return
            else:
                e.pos = newpos
                occupied.add(newpos)

    # ====== Предметы ======
    def _auto_pickup(self) -> None:
        key = (self._player.pos.x, self._player.pos.y)
        item = self._level.item_positions.get(key)
        if item is None:
            return
        if item.item_type == ItemType.TREASURE:
            self._player.treasures += item.cost
            self._message = f"Подобрано сокровище (+{item.cost})."
        else:
            if self._can_add_to_backpack(item):
                self._player.backpack.append(item)
                self._message = f"В рюкзак: {item.name}."
            else:
                self._message = "Рюкзак полон для этого типа предметов!"
                return
        self._level.item_positions.pop(key, None)
        self._level.items = [i for i in self._level.items
                             if (i is item) is False]

    def _can_add_to_backpack(self, item: Item) -> bool:
        same = sum(1 for i in self._player.backpack
                   if i.item_type == item.item_type)
        return same < BACKPACK_MAX_PER_TYPE

    def _handle_inventory(self, command: Command) -> None:
        bp = self._player.backpack
        if command == Command.QUIT:
            self._show_inventory = False
            return
        if command == Command.NEXT_ITEM:
            self._inv_cursor = min(len(bp), self._inv_cursor + 1)
            return
        if command == Command.PREV_ITEM:
            self._inv_cursor = max(0, self._inv_cursor - 1)
            return
        if command == Command.USE and bp:
            idx = min(self._inv_cursor, len(bp) - 1)
            item = bp[idx]
            msg = itf.apply_item(self._player, item, 0)
            # еда/эликсиры/свитки тратятся; оружие не тратится (экипировка отдельно)
            if item.item_type in (ItemType.FOOD, ItemType.POTION, ItemType.SCROLL):
                bp.pop(idx)
                self._inv_cursor = min(self._inv_cursor, max(0, len(bp) - 1))
            self._message = msg
            # обновляем эффекты сразу
            itf.tick_effects(self._player, 0)
            self._end_player_turn("")
            return
        if command == Command.EQUIP and bp:
            idx = min(self._inv_cursor, len(bp) - 1)
            item = bp[idx]
            if item.item_type != ItemType.WEAPON:
                self._message = "Это не оружие."
                return
            # старое оружие падает на соседнюю клетку
            if self._player.weapon is not None:
                drop_pos = self._free_adjacent(self._player.pos)
                if drop_pos is not None:
                    old = self._player.weapon
                    old.name = old.name + " (брошено)"
                    self._level.item_positions[(drop_pos.x, drop_pos.y)] = old
                    self._level.items.append(old)
                else:
                    self._message = "Некуда бросить старое оружие!"
                    return
            bp.pop(idx)
            self._player.weapon = item
            self._message = f"Экипировано: {item.name}."
            self._end_player_turn("")
            return

    def _free_adjacent(self, pos: Position) -> Position | None:
        for d in [UP, DOWN, LEFT, RIGHT]:
            cand = pos + d
            if (self._level.map.is_walkable(cand)
                    and (cand.x, cand.y) not in self._level.item_positions):
                return cand
        return None

    # ====== Смена уровня ======
    def _descend(self) -> None:
        if self._floor + 1 >= TOTAL_LEVELS:
            self._won = True
            self._finish(result="win")
            return
        self._enter_level(self._floor + 1)
        self._message = f"Спуск на уровень {self._floor + 1}."

    # ====== Смерть ======
    def _on_player_death(self) -> None:
        self._message = "Вы погибли!"
        self._finish(result="death")

    def _finish(self, result: str) -> None:
        """Завершить партию: записать рекорд и показать экран конца."""
        record = {
            "result": result,
            "floor": self._floor + 1,
            "treasures": self._player.treasures,
            "won": self._won,
        }
        if self._repository is not None:
            self._repository.save_highscore(record)
        self._game_over = True
        if result == "win":
            self._message = "ПОБЕДА! Вы прошли все 21 уровней подземелья!"

    # ====== Внешний интерфейс ======
    def snapshot(self) -> Snapshot:
        hs = (self._repository.load_highscores()
              if self._repository is not None else [])
        visible = [e for e in self._level.enemies if e.is_alive() and e.visible]
        return Snapshot(
            level=self._level,
            player=self._player,
            floor=self._floor + 1,
            total_levels=TOTAL_LEVELS,
            message=self._message,
            game_over=self._game_over,
            show_title=self._show_title,
            show_inventory=self._show_inventory,
            show_highscores=self._show_highscores,
            inv_cursor=self._inv_cursor,
            highscores=hs,
            won=self._won,
            visible_enemies=visible,
        )

    def is_over(self) -> bool:
        # «над» считает только когда игра закрыта окончательно (QUIT на экране конца)
        return False

    def should_exit(self) -> bool:
        return self._game_over and self._message == "Игра завершена."
