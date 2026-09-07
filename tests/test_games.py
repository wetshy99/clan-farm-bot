from pathlib import Path
from types import SimpleNamespace

import pytest
from bot.config import GAME_TAX, GAMES, STARTING_COINS
from bot.db import Database
from bot.games import GAME_CLASSES
from bot.games.base import BaseGame, parse_bet_amount


class FakeMember(SimpleNamespace):
    pass


@pytest.fixture()
def game(tmp_path: Path) -> BaseGame:
    db = Database(tmp_path / "game.db")
    guild = SimpleNamespace(id=1)
    players = [FakeMember(id=100 + i, display_name=f"P{i}") for i in range(4)]
    return BaseGame(db, channel=None, guild=guild, players=players, fee=10_000)


def test_fees_and_burn(game: BaseGame) -> None:
    game.collect_fees()
    total = game.fee * len(game.players)
    assert game.burn == int(total * GAME_TAX)
    assert game.pot == total - game.burn
    for p in game.players:
        assert game.db.coins(1, p.id) == STARTING_COINS - game.fee


def test_ranking_payout_leaves_nothing_unassigned(game: BaseGame) -> None:
    game.collect_fees()
    results = game.payout_ranking(game.players)
    paid = sum(a for _, a in results)
    assert [a for _, a in results] == [
        int(game.pot * 0.5),
        int(game.pot * 0.25),
        int(game.pot * 0.15),
    ]
    assert game.db.fund(1) == game.pot - paid
    assert game.db.get_player(1, game.players[0].id)["game_wins"] == 1


def test_every_configured_game_has_a_matching_implementation() -> None:
    assert set(GAMES) == set(GAME_CLASSES)
    assert all(GAME_CLASSES[key].key == key for key in GAMES)


@pytest.mark.parametrize("value", ["10.000", "10,000", "10000"])
def test_bet_amount_accepts_common_number_formats(value: str) -> None:
    assert parse_bet_amount(value, 10_000) == 10_000
