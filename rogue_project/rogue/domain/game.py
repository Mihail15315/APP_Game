# -*- coding: utf-8 -*-
"""Ядро игры — бизнес-логика игрового процесса.

Game принимает доменные Command, мутирует состояние, отдаёт Snapshot.
Не зависит от curses и от конкретного хранилища.

Поток выбора предмета (по заданию 4): h/j/k/e открывает меню со списком
предметов этого типа, игрок выбирает 1-9 (для оружия — 0-9, где 0 = убрать
оружие из рук, не выбрасывая).
"""
from __future__ import annotations

import random

from rogue.domain.commands import Command, select_to_index
from rogue.domain.entities import (
    Player, PlayerStats, Level, Position, Enemy, Item, ItemType, ItemSubType,
    TileType, UP, DOWN, LEFT, RIGHT, DIRECTIONS_8, Visibility,
)
from rogue.domain.repository import GameRepository
from rogue.domain.snapshot import Snapshot
from rogue.domain.dungeon import generate_level
from rogue.domain import combat
from rogue.domain import ai
from rogue.domain import fog
from rogue.domain import items as itf
from rogue.domain import enemies as en


TOTAL_LEVELS = 21
BACKPACK_MAX_PER_TYPE = 9
EFFECT_TICK = 0  # упрощённый таймер эффекта (растёт с числом ходов)


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
        self._show_statistics: bool = False
        self._show_highscores: bool = False
        # меню выбора предмета
        self._sel_items: list[Item] = []
        self._sel_kind: str = ""
        self._sel_allow_zero: bool = False
        self._inv_cursor: int = 0
        self._won: bool = False
        self._show_continue_prompt: bool = False
        self._stats_total: PlayerStats = PlayerStats()
        self._seed: int | None = seed
        # продолжаем сохранённую сессию?
        self._can_continue = (repository is not None
                              and repository.load_session() is not None)
        if self._can_continue:
            self._show_title = False
            self._show_continue_prompt = True
        self._new_game()

    # ====== Жизненный цикл ======
    def _new_game(self) -> None:
        self._player = Player(
            pos=Position(0, 0), max_health=50, health=50,
            agility=8, strength=6, experience=0, treasures=0,
            weapon=None, backpack=[], effects=[],
            stats=PlayerStats(),
        )
        self._floor = 0
        self._won = False
        self._game_over = False
        self._stats_total = PlayerStats()
        self._enter_level(0)
        if not self._show_continue_prompt:
            self._message = "Добро пожаловать в подземелье! (q — выход, r — рекорды, t — статистика)"
            self._show_title = True

    def _enter_level(self, index: int) -> None:
        self._floor = index
        self._level = generate_level(index, self._rng)
        self._player.pos = self._level.start
        fog.update_visibility(self._level, self._player.pos)
        self._save_current_session()

    def _reset_to_start(self) -> None:
        """После смерти — полный сброс к началу."""
        self._rng = random.Random()  # новый случайный сид
        if self._repository is not None:
            self._repository.clear_session()
        self._show_continue_prompt = False
        self._new_game()
        self._show_title = False
        self._message = "Вы погибли... Новая попытка с 1-го уровня."

    # ====== Обработка команд ======
    def handle(self, command: Command) -> None:
        # Стартовый вопрос о продолжении
        if self._show_continue_prompt:
            if command == Command.CONTINUE_SESSION:
                self._continue_session()
            else:
                self._show_continue_prompt = False
                self._new_game()
            return

        if self._show_title:
            if command == Command.CONFIRM:
                self._show_title = False
            elif command == Command.QUIT:
                self._finish(result="quit")
            return

        if self._sel_items:
            self._handle_selection(command)
            return

        if self._show_inventory:
            if command == Command.QUIT:
                self._show_inventory = False
            return

        if self._show_statistics:
            if command in (Command.CONFIRM, Command.QUIT, Command.IGNORE):
                self._show_statistics = False
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
            case Command.SHOW_STATISTICS:
                self._show_statistics = True
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
            case Command.USE_WEAPON:
                self._open_selection("weapon")
            case Command.USE_FOOD:
                self._open_selection("food")
            case Command.USE_POTION:
                self._open_selection("potion")
            case Command.USE_SCROLL:
                self._open_selection("scroll")
            case Command.IGNORE:
                pass

    # ====== Меню выбора предмета ======
    _KIND_TO_TYPE = {
        "weapon": ItemType.WEAPON,
        "food": ItemType.FOOD,
        "potion": ItemType.POTION,
        "scroll": ItemType.SCROLL,
    }

    def _open_selection(self, kind: str) -> None:
        itype = self._KIND_TO_TYPE[kind]
        items = [i for i in self._player.backpack if i.item_type == itype]
        if kind == "weapon":
            # оружие: показать также экипированное как вариант 0 (убрать из рук)
            items = [self._player.weapon] + items if self._player.weapon else items
            self._sel_allow_zero = True
        else:
            self._sel_allow_zero = False
        if not items:
            self._message = f"В рюкзаке нет {self._kind_ru(kind)}."
            return
        self._sel_items = items
        self._sel_kind = kind
        self._message = f"Выберите {self._kind_ru(kind)} (0-9):"

    @staticmethod
    def _kind_ru(kind: str) -> str:
        return {"weapon": "оружие", "food": "еду", "potion": "эликсир",
                "scroll": "свиток"}[kind]

    def _handle_selection(self, command: Command) -> None:
        if command == Command.QUIT:
            self._sel_items = []
            self._sel_kind = ""
            self._message = ""
            return
        idx = select_to_index(command)
        if idx is None:
            self._message = "Нажмите 0-9 или q для отмены."
            return
        # для оружия разрешён 0 (если есть allow_zero) — означает "убрать из рук"
        if idx == 0:
            if self._sel_kind == "weapon" and self._sel_allow_zero and self._player.weapon:
                w = self._player.weapon
                self._player.backpack.append(w)
                self._player.weapon = None
                self._message = f"Убрано из рук: {w.name}"
                self._sel_items = []
                return
            if not self._sel_allow_zero:
                self._message = "Нужно выбрать 1-9."
                return
        # индекс в списке: с учётом сдвига для оружия
        list_idx = idx - 1 if self._sel_kind == "weapon" and self._sel_allow_zero else idx
        if list_idx < 0 or list_idx >= len(self._sel_items):
            self._message = "Нет такого предмета."
            return
        item = self._sel_items[list_idx]
        kind = self._sel_kind
        self._sel_items = []
        self._apply_selected(kind, item)

    def _apply_selected(self, kind: str, item: Item) -> None:
        p = self._player
        if kind == "food":
            msg = itf.apply_food(p, item)
            p.backpack.remove(item)
            p.stats.food_eaten += 1
        elif kind == "potion":
            msg = itf.apply_potion(p, item, self._turn_count())
            p.backpack.remove(item)
            p.stats.potions_drunk += 1
        elif kind == "scroll":
            msg = itf.apply_scroll(p, item)
            p.backpack.remove(item)
            p.stats.scrolls_read += 1
        elif kind == "weapon":
            # оружие: сначала выбросить старое на соседнюю клетку
            if p.weapon is not None and p.weapon is not item:
                self._drop_adjacent(p.weapon)
            if item in p.backpack:
                p.backpack.remove(item)
            msg = itf.equip_weapon(p, item)
        else:
            msg = "Не получается."
        self._message = msg
        if kind in ("food", "potion", "scroll"):
            self._end_player_turn(msg)
        else:
            self._save_current_session()

    def _turn_count(self) -> int:
        return self._stats_total.steps  # эффекты тикают по ходам

    # ====== Движение игрока ======
    def _player_step(self, delta: Position) -> None:
        target = self._player.pos + delta
        enemy = self._enemy_at(target)
        if enemy is not None:
            self._player_attacks(enemy)
            return
        if self._level.map.is_walkable(target):
            self._player.pos = target
            self._stats_total.steps += 1
            self._player.stats.steps += 1
            if self._level.map.tile_at(target) == TileType.STAIRS_DOWN:
                self._descend()
                return
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
            self._end_player_turn("")
            return
        if res["hit"]:
            self._message = f"Вы бьёте {enemy.type_name}: -{res['damage']} HP"
            self._stats_total.hits_dealt += 1
            self._player.stats.hits_dealt += 1
            if res["killed"]:
                self._player_kills(enemy)
                self._end_player_turn("")
                return
        else:
            self._message = f"Вы промахнулись по {enemy.type_name}."
        self._end_player_turn("")

    def _player_kills(self, enemy: Enemy) -> None:
        enemy.health = 0
        gained = enemy.treasures
        self._player.treasures += gained
        self._stats_total.treasures += gained
        self._stats_total.enemies_killed += 1
        self._player.stats.enemies_killed += 1
        self._level.enemies = [e for e in self._level.enemies if e.is_alive()]
        self._message = f"{enemy.type_name} повержен! +{gained} сокровищ."
        self._player.experience += 5

    def _enemy_attacks(self, enemy: Enemy, target=None) -> None:
        target = target or self._player
        res = combat.attack(enemy, target, self._rng)
        if res["hit"]:
            self._apply_enemy_specials(enemy, res["damage"])
            self._stats_total.hits_taken += 1
            self._player.stats.hits_taken += 1
            if not self._player.is_alive():
                self._on_player_death()
                return
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
                self._message = f"Змей усыпляет вас! -{dmg} HP."
                return
        self._message = f"{enemy.type_name} бьёт вас: -{dmg} HP"

    def _end_player_turn(self, msg: str) -> None:
        if msg:
            self._message = msg
        if self._player.sleeping > 0:
            self._player.sleeping -= 1
            self._message = "Вы спите и пропускаете ход!"
        m = itf.tick_effects(self._player, self._turn_count())
        if m and not self._message:
            self._message = m
        # фаза для периодических эффектов привидения
        for e in self._level.enemies:
            e.phase += 1
            if e.type_name == en.GHOST and not e.engaged:
                e.visible = (e.phase % 6 < 3)
        self._enemies_turn()
        fog.update_visibility(self._level, self._player.pos)
        if not self._player.is_alive():
            self._on_player_death()
        else:
            self._save_current_session()

    def _enemies_turn(self) -> None:
        occupied = {self._player.pos}
        for e in list(self._level.enemies):
            if not e.is_alive() or not e.visible:
                continue
            other_pos = {o.pos for o in self._level.enemies
                         if o is not e and o.is_alive()}
            newpos = ai.move_enemy(e, self._player, self._level.map, other_pos, self._rng)
            if newpos == self._player.pos:
                self._enemy_attacks(e)
                occupied.add(e.pos)
                if not self._player.is_alive():
                    return
            else:
                e.pos = newpos
                occupied.add(newpos)

    # ====== Предметы (подбор, сброс) ======
    def _auto_pickup(self) -> None:
        key = (self._player.pos.x, self._player.pos.y)
        item = self._level.item_positions.get(key)
        if item is None:
            return
        if item.item_type == ItemType.TREASURE:
            self._player.treasures += item.cost
            self._stats_total.treasures += item.cost
            self._message = f"Подобрано сокровище (+{item.cost})."
        else:
            if self._can_add_to_backpack(item):
                self._player.backpack.append(item)
                self._message = f"В рюкзак: {item.name}."
            else:
                self._message = "Рюкзак полон для этого типа предметов!"
                return
        self._level.item_positions.pop(key, None)
        self._level.items = [i for i in self._level.items if i is not item]

    def _can_add_to_backpack(self, item: Item) -> bool:
        same = sum(1 for i in self._player.backpack
                   if i.item_type == item.item_type)
        return same < BACKPACK_MAX_PER_TYPE

    def _drop_adjacent(self, item: Item) -> None:
        pos = self._free_adjacent(self._player.pos)
        if pos is None:
            return
        item.name = item.name + " (брошено)"
        self._level.item_positions[(pos.x, pos.y)] = item
        self._level.items.append(item)

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

    # ====== Смерть / финал ======
    def _on_player_death(self) -> None:
        self._message = "Вы погибли!"
        self._finish(result="death")

    def _finish(self, result: str) -> None:
        record = {
            "result": result,
            "floor": self._floor + 1,
            "treasures": self._player.treasures,
            "won": self._won,
            "enemies_killed": self._stats_total.enemies_killed,
            "food_eaten": self._stats_total.food_eaten,
            "potions_drunk": self._stats_total.potions_drunk,
            "scrolls_read": self._stats_total.scrolls_read,
            "hits_dealt": self._stats_total.hits_dealt,
            "hits_taken": self._stats_total.hits_taken,
            "steps": self._stats_total.steps,
        }
        if self._repository is not None:
            self._repository.save_highscore(record)
            if result in ("death", "win"):
                self._repository.clear_session()
        self._game_over = True
        if result == "win":
            self._message = "ПОБЕДА! Вы прошли все 21 уровней подземелья!"

    # ====== Сохранение / загрузка ======
    def _save_current_session(self) -> None:
        if self._repository is None:
            return
        p = self._player
        data = {
            "floor": self._floor,
            "player": {
                "x": p.pos.x, "y": p.pos.y,
                "health": p.health, "max_health": p.max_health,
                "agility": p.agility, "strength": p.strength,
                "treasures": p.treasures, "experience": p.experience,
            },
            "stats": {
                "treasures": self._stats_total.treasures,
                "enemies_killed": self._stats_total.enemies_killed,
                "food_eaten": self._stats_total.food_eaten,
                "potions_drunk": self._stats_total.potions_drunk,
                "scrolls_read": self._stats_total.scrolls_read,
                "hits_dealt": self._stats_total.hits_dealt,
                "hits_taken": self._stats_total.hits_taken,
                "steps": self._stats_total.steps,
            },
        }
        self._repository.save_session(data)

    def _continue_session(self) -> None:
        data = self._repository.load_session()
        if data is None:
            self._new_game()
            return
        self._show_continue_prompt = False
        # восстановим игрока и сгенерируем уровень по индексу
        self._new_game()
        pd = data["player"]
        self._floor = data["floor"]
        self._level = generate_level(self._floor, self._rng)
        self._player.pos = Position(pd["x"], pd["y"])
        self._player.health = pd["health"]
        self._player.max_health = pd["max_health"]
        self._player.agility = pd["agility"]
        self._player.strength = pd["strength"]
        self._player.treasures = pd["treasures"]
        self._player.experience = pd["experience"]
        s = data["stats"]
        self._stats_total = PlayerStats(**s)
        fog.update_visibility(self._level, self._player.pos)
        self._message = f"Продолжаем с уровня {self._floor + 1}."

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
            show_statistics=self._show_statistics,
            show_highscores=self._show_highscores,
            show_selection=bool(self._sel_items),
            selection_items=self._sel_items,
            selection_kind=self._sel_kind,
            selection_allow_zero=self._sel_allow_zero,
            inv_cursor=self._inv_cursor,
            highscores=hs,
            statistics=self._stats_to_dict(),
            won=self._won,
            visible_enemies=visible,
            show_continue_prompt=self._show_continue_prompt,
        )

    def _stats_to_dict(self) -> dict:
        s = self._stats_total
        return {
            "treasures": s.treasures, "enemies_killed": s.enemies_killed,
            "food_eaten": s.food_eaten, "potions_drunk": s.potions_drunk,
            "scrolls_read": s.scrolls_read, "hits_dealt": s.hits_dealt,
            "hits_taken": s.hits_taken, "steps": s.steps,
        }

    def is_over(self) -> bool:
        return False

    def should_exit(self) -> bool:
        return self._game_over and self._message == "Игра завершена."
