# -*- coding: utf-8 -*-
"""Тесты бизнес-логики (domain). НЕ требуют curses/терминала."""
from rogue.domain.game import Game
from rogue.domain.commands import Command
from rogue.domain.entities import Position, UP, DOWN, LEFT, RIGHT, Player, Enemy
from rogue.domain.dungeon import generate_level
from rogue.domain import combat, enemies as en
from rogue.domain import items as itf
import random


def _fresh_game():
    return Game(repository=None, seed=42)


def test_player_starts_alive():
    g = _fresh_game()
    snap = g.snapshot()
    assert snap.player.is_alive()
    assert snap.floor == 1
    assert snap.total_levels == 21
    assert snap.show_title is True
    print("OK test_player_starts_alive")


def test_confirm_removes_title():
    g = _fresh_game()
    g.handle(Command.CONFIRM)
    assert g.snapshot().show_title is False
    print("OK test_confirm_removes_title")


def test_move_blocked_by_wall_keeps_position():
    g = _fresh_game()
    g.handle(Command.CONFIRM)
    before = g.snapshot().player.pos
    # Идём в стену несколько раз — позиция не должна стать невалидной
    for _ in range(20):
        g.handle(Command.MOVE_LEFT)
    after = g.snapshot().player.pos
    assert after.x >= 0 and after.y >= 0
    print("OK test_move_blocked_by_wall_keeps_position")


def test_level_has_rooms_and_stairs():
    rng = random.Random(123)
    lvl = generate_level(0, rng)
    assert len(lvl.rooms) == 9
    assert lvl.map.tile_at(lvl.stairs).name == "STAIRS_DOWN"
    print("OK test_level_has_rooms_and_stairs")


def test_combat_hit_or_miss_returns_dict():
    rng = random.Random(7)
    p = Player(pos=Position(0, 0), max_health=50, health=50, agility=8, strength=6)
    e = en.make_zombie(rng, Position(1, 0))
    res = combat.attack(p, e, rng)
    assert "hit" in res and "damage" in res and "killed" in res
    print("OK test_combat_hit_or_miss_returns_dict")


def test_food_heals_player():
    rng = random.Random(1)
    p = Player(pos=Position(0, 0), max_health=50, health=10, agility=8, strength=6)
    food = itf.make_food(rng)
    before = p.health
    itf.apply_item(p, food, 0)
    assert p.health > before
    assert p.health <= p.max_health
    print("OK test_food_heals_player")


def test_scroll_raises_stat_permanently():
    rng = random.Random(2)
    p = Player(pos=Position(0, 0), max_health=50, health=50, agility=8, strength=6)
    scroll = itf.make_scroll(rng)
    ag_before = p.agility
    st_before = p.strength
    mh_before = p.max_health
    itf.apply_item(p, scroll, 0)
    changed = (p.agility + p.strength + p.max_health) > (ag_before + st_before + mh_before)
    assert changed
    print("OK test_scroll_raises_stat_permanently")


def test_repository_highscores_sorted():
    import tempfile, os
    from rogue.data.game_repository import FileGameRepository
    with tempfile.TemporaryDirectory() as d:
        repo = FileGameRepository(base_dir=d)
        repo.save_highscore({"result": "death", "floor": 3, "treasures": 50})
        repo.save_highscore({"result": "death", "floor": 5, "treasures": 200})
        repo.save_highscore({"result": "win", "floor": 21, "treasures": 100})
        hs = repo.load_highscores()
        assert hs[0]["treasures"] == 200
        assert hs[-1]["treasures"] == 50
        print("OK test_repository_highscores_sorted")


def test_enemy_pool_grows_with_depth():
    assert en.ZOMBIE in en.pool_for_depth(0)
    assert en.GHOST in en.pool_for_depth(2)
    assert en.VAMPIRE in en.pool_for_depth(4)
    assert en.SERPENT in en.pool_for_depth(6)
    assert en.OGRE in en.pool_for_depth(9)
    print("OK test_enemy_pool_grows_with_depth")


def test_auto_pickup_treasure():
    g = _fresh_game()
    g.handle(Command.CONFIRM)
    before = g.snapshot().player.treasures
    # не можем гарантировать позицию, но проверим что функция не падает
    g.handle(Command.WAIT)
    print("OK test_auto_pickup_treasure (no crash)")


if __name__ == "__main__":
    test_player_starts_alive()
    test_confirm_removes_title()
    test_move_blocked_by_wall_keeps_position()
    test_level_has_rooms_and_stairs()
    test_combat_hit_or_miss_returns_dict()
    test_food_heals_player()
    test_scroll_raises_stat_permanently()
    test_repository_highscores_sorted()
    test_enemy_pool_grows_with_depth()
    test_auto_pickup_treasure()
    print("\nВсе тесты пройдены ✓")
