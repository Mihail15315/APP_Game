# -*- coding: utf-8 -*-
"""Логика боя: 3 этапа (попадание → урон → применение).

Атакующий и цель — любые Character (Player или Enemy). Формулы:
  - Попадание: вероятность = clamp(0.1 + 0.05*(atk_agility - def_agility), 0.05, 0.95)
  - Урон: attacker_strength (+ оружие для игрока) ± случайность
"""
from __future__ import annotations

import random

from rogue.domain.entities import Character, Player, Enemy


def hit_chance(atk_agility: int, def_agility: int) -> float:
    raw = 0.5 + 0.05 * (atk_agility - def_agility)
    return max(0.05, min(0.95, raw))


def compute_damage(strength: int, rng) -> int:
    base = strength
    return max(1, base + rng.randint(-2, 2))


def attack(attacker: Character, defender: Character, rng) -> dict:
    """Один удар attacker → defender. Возвращает словарь с результатом."""
    # Особый случай: первый удар игрока по вампиру всегда промах
    first_miss = (isinstance(attacker, Player)
                  and isinstance(defender, Enemy)
                  and defender.first_strike_miss)
    if first_miss:
        defender.first_strike_miss = False
        return {"hit": False, "damage": 0, "killed": False, "vampire_first_miss": True}

    atk_ag = attacker.agility
    def_ag = defender.agility
    if not hit_chance(atk_ag, def_ag) >= rng.random():
        return {"hit": False, "damage": 0, "killed": False}

    # Сила = эффективная сила игрока (с эликсирами) или базовая
    if isinstance(attacker, Player):
        base = attacker.effective_strength
        if attacker.weapon is not None:
            base += attacker.weapon.strength
    else:
        base = attacker.strength
    dmg = compute_damage(base, rng)
    defender.take_damage(dmg)
    killed = not defender.is_alive()
    return {"hit": True, "damage": dmg, "killed": killed}
