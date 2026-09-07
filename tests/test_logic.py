import time
from pathlib import Path

import pytest

from bot.cogs.farm import parse_plant_quantity
from bot.config import CROPS, PLOT_LEVELS, STARTING_COINS
from bot.db import Database


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    return Database(tmp_path / "test.db")


def test_new_player_gets_starting_coins(db: Database) -> None:
    assert db.coins(1, 100) == STARTING_COINS
    assert db.plot_count(1, 100) == PLOT_LEVELS[1][0]


def test_plant_harvest_sell_flow(db: Database) -> None:
    crop = CROPS["carrot"]
    db.add_coins(1, 100, -crop.seed_price)
    db.plant(1, 100, "carrot", int(time.time()) - 1)
    plants = db.plants(1, 100)
    assert len(plants) == 1

    db.remove_plant(int(plants[0]["id"]))
    db.add_item(1, 100, "carrot", 1)
    gain, to_clan, inv = db.sell_all(1, 100)

    assert inv == {"carrot": 1}
    assert gain + to_clan == crop.sell_price
    assert to_clan == int(crop.sell_price * 0.10)
    assert db.fund(1) == to_clan
    assert db.coins(1, 100) == STARTING_COINS - crop.seed_price + gain


@pytest.mark.parametrize("value", ["all", "ALL", "tất cả", "tat ca", "*"])
def test_plant_quantity_all_uses_available_slots(value: str) -> None:
    assert parse_plant_quantity(value, 7) == 7


def test_plant_quantity_accepts_number() -> None:
    assert parse_plant_quantity(" 3 ", 7) == 3


def test_watering_reduces_ready_time(db: Database) -> None:
    ready_at = int(time.time()) + 600
    db.plant(1, 100, "strawberry", ready_at)
    plant = db.plants(1, 100)[0]
    db.water_plant(int(plant["id"]), 180)
    updated = db.plants(1, 100)[0]
    assert int(updated["ready_at"]) == ready_at - 180
    assert updated["watered"] == 1


def test_daily_checkin_once_per_day(db: Database) -> None:
    ok, reward, streak = db.claim_daily(1, 100)
    assert ok and reward > 0 and streak == 1
    ok2, reward2, _ = db.claim_daily(1, 100)
    assert not ok2 and reward2 == 0


def test_daily_counters_are_per_day(db: Database) -> None:
    db.bump_counter(1, 100, "steals")
    db.bump_counter(1, 100, "steals")
    assert int(db.counters(1, 100)["steals"]) == 2
    db.set_last_target(1, 100, 200)
    assert int(db.counters(1, 100)["last_target"]) == 200


def test_coins_never_negative(db: Database) -> None:
    db.add_coins(1, 100, -10 * STARTING_COINS)
    assert db.coins(1, 100) == 0


def test_leaderboard_sorted(db: Database) -> None:
    db.add_coins(1, 100, 1_000)
    db.add_coins(1, 200, 5_000)
    top = db.top(1, "coins", 2)
    assert [int(r["user_id"]) for r in top] == [200, 100]


def test_invalid_field_rejected(db: Database) -> None:
    with pytest.raises(ValueError):
        db.bump(1, 100, "coins; DROP TABLE players")
