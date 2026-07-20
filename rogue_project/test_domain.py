# -*- coding: utf-8 -*-
"""Тесты бизнес-логики (domain). НЕ требуют curses/терминала."""
from rogue.domain.game import Game
from rogue.domain.commands import Command, select_to_index
from rogue.domain.entities import Position, Player, PlayerStats, Visibility
from rogue.domain.dungeon import generate_level, _is_connected
from rogue.domain.entities import Corridor
from rogue.domain import combat, enemies as en, fog
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


def test_level_has_rooms_stairs_and_visibility():
    rng = random.Random(123)
    lvl = generate_level(0, rng)
    assert len(lvl.rooms) == 9
    assert lvl.map.tile_at(lvl.stairs).name == "STAIRS_DOWN"
    assert lvl.rooms[0].is_start
    assert lvl.rooms[8].is_end
    # visibility инициализирована
    assert len(lvl.visibility) == lvl.map.height
    print("OK test_level_has_rooms_stairs_and_visibility")


def test_graph_is_connected():
    rng = random.Random(7)
    for _ in range(10):
        lvl = generate_level(rng.randint(0, 20), rng)
        assert _is_connected(9, lvl.corridors)
    print("OK test_graph_is_connected (10 уровней)")


def test_fog_visibility_grows():
    rng = random.Random(99)
    lvl = generate_level(0, rng)
    fog.init_visibility(lvl)
    fog.update_visibility(lvl, lvl.start)
    # в стартовой комнате должны быть VISIBLE клетки
    vis_count = sum(1 for row in lvl.visibility for v in row if v == Visibility.VISIBLE)
    assert vis_count > 0
    print("OK test_fog_visibility_grows")


def test_combat_returns_dict():
    rng = random.Random(7)
    p = Player(pos=Position(0, 0), max_health=50, health=50, agility=8, strength=6)
    e = en.make_zombie(rng, Position(1, 0))
    res = combat.attack(p, e, rng)
    assert "hit" in res and "damage" in res and "killed" in res
    print("OK test_combat_returns_dict")


def test_food_heals_player():
    rng = random.Random(1)
    p = Player(pos=Position(0, 0), max_health=50, health=10, agility=8, strength=6)
    food = itf.make_food(rng)
    before = p.health
    itf.apply_food(p, food)
    assert p.health > before
    assert p.health <= p.max_health
    print("OK test_food_heals_player")


def test_scroll_permanent():
    rng = random.Random(2)
    p = Player(pos=Position(0, 0), max_health=50, health=50, agility=8, strength=6)
    scroll = itf.make_scroll(rng)
    before = p.agility + p.strength + p.max_health
    itf.apply_scroll(p, scroll)
    assert (p.agility + p.strength + p.max_health) > before
    print("OK test_scroll_permanent")


def test_select_to_index():
    assert select_to_index(Command.SELECT_0) == 0
    assert select_to_index(Command.SELECT_9) == 9
    assert select_to_index(Command.CONFIRM) is None
    print("OK test_select_to_index")


def test_repository_highscores_and_session():
    import tempfile
    from rogue.data.game_repository import FileGameRepository
    with tempfile.TemporaryDirectory() as d:
        repo = FileGameRepository(base_dir=d)
        repo.save_highscore({"result": "death", "floor": 3, "treasures": 50,
                             "enemies_killed": 2})
        repo.save_highscore({"result": "win", "floor": 21, "treasures": 200,
                             "enemies_killed": 30})
        hs = repo.load_highscores()
        assert hs[0]["treasures"] == 200
        # сохранение/загрузка сессии
        repo.save_session({"floor": 5, "player": {"x": 1, "y": 1}})
        s = repo.load_session()
        assert s["floor"] == 5
        repo.clear_session()
        assert repo.load_session() is None
        print("OK test_repository_highscores_and_session")


def test_enemy_pool_grows_with_depth():
    assert en.ZOMBIE in en.pool_for_depth(0)
    assert en.GHOST in en.pool_for_depth(2)
    assert en.VAMPIRE in en.pool_for_depth(4)
    assert en.SERPENT in en.pool_for_depth(6)
    assert en.OGRE in en.pool_for_depth(9)
    print("OK test_enemy_pool_grows_with_depth")


def test_21_levels_generate():
    rng = random.Random(55)
    for i in range(21):
        lvl = generate_level(i, rng)
        assert len(lvl.rooms) == 9
        assert _is_connected(9, lvl.corridors)
    print("OK test_21_levels_generate")


if __name__ == "__main__":
    test_player_starts_alive()
    test_confirm_removes_title()
    test_level_has_rooms_stairs_and_visibility()
    test_graph_is_connected()
    test_fog_visibility_grows()
    test_combat_returns_dict()
    test_food_heals_player()
    test_scroll_permanent()
    test_select_to_index()
    test_repository_highscores_and_session()
    test_enemy_pool_grows_with_depth()
    test_21_levels_generate()
    print("\nВсе тесты пройдены ✓")
