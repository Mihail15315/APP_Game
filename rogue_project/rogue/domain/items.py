# -*- coding: utf-8 -*-
"""Предметы: фабрики, применение эффектов на игрока.

Каждое применение возвращает текст события и флаг, тратится ли предмет.
Статистику (food_eaten/potions_drunk/scrolls_read) обновляет Game, тут —
только эффект.
"""
from __future__ import annotations

import random

from rogue.domain.entities import Item, ItemType, ItemSubType, Player


_NAMES = {
    ItemType.FOOD: ["яблоко", "хлеб", "сыр", "мясо"],
    ItemType.POTION: {"agility": "эликсир ловкости", "strength": "эликсир силы",
                      "max": "эликсир здоровья"},
    ItemType.SCROLL: {"agility": "свиток ловкости", "strength": "свиток силы",
                      "max": "свиток здоровья"},
    ItemType.WEAPON: ["кинжал", "меч", "топор", "булава", "копьё"],
}

_KIND_TO_NAME = {
    ItemSubType.AGILITY: "agility",
    ItemSubType.STRENGTH: "strength",
    ItemSubType.MAX_HP: "max",
}


def make_food(rng):
    amt = rng.randint(5, 15)
    return Item(ItemType.FOOD, ItemSubType.NONE, health=amt,
                name=rng.choice(_NAMES[ItemType.FOOD]))


def make_treasure(rng, base_cost=10):
    cost = base_cost + rng.randint(0, 20)
    return Item(ItemType.TREASURE, ItemSubType.NONE, cost=cost,
                name=f"сокровище ({cost})")


def make_potion(rng):
    kind = rng.choice([ItemSubType.AGILITY, ItemSubType.STRENGTH, ItemSubType.MAX_HP])
    amt = rng.randint(2, 5)
    dur = rng.randint(15, 40)
    name = _NAMES[ItemType.POTION][_KIND_TO_NAME[kind]]
    return Item(ItemType.POTION, kind,
                agility=(amt if kind == ItemSubType.AGILITY else 0),
                strength=(amt if kind == ItemSubType.STRENGTH else 0),
                max_health=(amt if kind == ItemSubType.MAX_HP else 0),
                duration=dur, name=name)


def make_scroll(rng):
    kind = rng.choice([ItemSubType.AGILITY, ItemSubType.STRENGTH, ItemSubType.MAX_HP])
    amt = rng.randint(1, 3)
    name = _NAMES[ItemType.SCROLL][_KIND_TO_NAME[kind]]
    return Item(ItemType.SCROLL, kind,
                agility=(amt if kind == ItemSubType.AGILITY else 0),
                strength=(amt if kind == ItemSubType.STRENGTH else 0),
                max_health=(amt if kind == ItemSubType.MAX_HP else 0),
                name=name)


def make_weapon(rng):
    bonus = rng.randint(2, 8)
    return Item(ItemType.WEAPON, ItemSubType.WEAPON, strength=bonus,
                name=f"{rng.choice(_NAMES[ItemType.WEAPON])} +{bonus}")


def make_random(rng, level_index: int):
    r = rng.random()
    if r < 0.30:
        return make_food(rng)
    if r < 0.55:
        return make_weapon(rng)
    if r < 0.80:
        return make_scroll(rng)
    return make_potion(rng)


# ====== Применение по типам ======
def apply_food(player: Player, item: Item) -> str:
    """Еда: восстановление здоровья (до текущего max)."""
    cap = player.effective_max_health
    heal = min(item.health, cap - player.health)
    if heal <= 0:
        return f"Вы сыты — {item.name} не помогает."
    player.health += heal
    return f"Съеден {item.name}: +{heal} HP"


def apply_potion(player: Player, item: Item, current_turn: int) -> str:
    """Эликсир: временный эффект. health/max растут на время действия."""
    ag, st, mh = item.agility, item.strength, item.max_health
    player.effects.append([current_turn + item.duration, ag, st, mh, mh])
    if mh:
        player.health += mh
    what = {"agility": ag, "strength": st, "max": mh}
    raised = next(v for v in (ag, st, mh) if v)
    return f"Выпит {item.name}: +{raised} на {item.duration} ходов"


def apply_scroll(player: Player, item: Item) -> str:
    """Свиток: постоянное повышение характеристики."""
    if item.sub_type == ItemSubType.AGILITY:
        player.agility += item.agility
        return f"Свиток: +{item.agility} ловкости (навсегда)"
    if item.sub_type == ItemSubType.STRENGTH:
        player.strength += item.strength
        return f"Свиток: +{item.strength} силы (навсегда)"
    if item.sub_type == ItemSubType.MAX_HP:
        player.max_health += item.max_health
        player.health += item.max_health
        return f"Свиток: +{item.max_health} макс. здоровья"
    return "Свиток непонятен."


def equip_weapon(player: Player, item: Item) -> str:
    """Экипировать оружие. Старое нужно бросить отдельно (вызывает Game)."""
    player.weapon = item
    return f"Взято оружие: {item.name}"


def tick_effects(player: Player, current_turn: int) -> str | None:
    """Обновить временные эффекты в конце хода."""
    msg = None
    alive = []
    for end, ag, st, mh, total in player.effects:
        if current_turn >= end:
            if mh:
                player.health -= total
                if player.health <= 0:
                    player.health = 1
                    msg = "Действие эликсира закончилось: вы еле выжили!"
        else:
            alive.append([end, ag, st, mh, total])
    player.effects = alive
    return msg
