"""Lớp dữ liệu SQLite cho bot."""

from __future__ import annotations

import datetime as dt
import sqlite3
import time
from pathlib import Path

from .config import CLAN_TAX, PLOT_LEVELS, STARTING_COINS

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "clanfarm.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    guild_id     INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    coins        INTEGER NOT NULL DEFAULT 0,
    plot_level   INTEGER NOT NULL DEFAULT 1,
    harvested    INTEGER NOT NULL DEFAULT 0,
    helped       INTEGER NOT NULL DEFAULT 0,
    steals       INTEGER NOT NULL DEFAULT 0,
    game_wins    INTEGER NOT NULL DEFAULT 0,
    daily_date   TEXT NOT NULL DEFAULT '',
    daily_streak INTEGER NOT NULL DEFAULT 0,
    created_at   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS plants (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    crop       TEXT    NOT NULL,
    ready_at   INTEGER NOT NULL,
    watered    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS inventory (
    guild_id INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    crop     TEXT    NOT NULL,
    qty      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, crop)
);

CREATE TABLE IF NOT EXISTS protections (
    guild_id          INTEGER NOT NULL,
    user_id           INTEGER NOT NULL,
    alarm             INTEGER NOT NULL DEFAULT 0,
    trap              INTEGER NOT NULL DEFAULT 0,
    dog_tier          INTEGER NOT NULL DEFAULT 0,
    dog_expires       INTEGER NOT NULL DEFAULT 0,
    security_expires  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS daily_counters (
    guild_id     INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    day          TEXT    NOT NULL,
    helps        INTEGER NOT NULL DEFAULT 0,
    steals       INTEGER NOT NULL DEFAULT 0,
    times_stolen INTEGER NOT NULL DEFAULT 0,
    last_target  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, day)
);

CREATE TABLE IF NOT EXISTS clans (
    guild_id INTEGER PRIMARY KEY,
    fund     INTEGER NOT NULL DEFAULT 0
);
"""


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- helpers ----------
    @staticmethod
    def today() -> str:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    def commit(self) -> None:
        self.conn.commit()

    # ---------- player ----------
    def get_player(self, guild_id: int, user_id: int) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT * FROM players WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO players (guild_id, user_id, coins, created_at) VALUES (?,?,?,?)",
                (guild_id, user_id, STARTING_COINS, int(time.time())),
            )
            self.conn.execute(
                "INSERT OR IGNORE INTO protections (guild_id, user_id) VALUES (?,?)",
                (guild_id, user_id),
            )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT * FROM players WHERE guild_id=? AND user_id=?", (guild_id, user_id)
            ).fetchone()
        return row

    def coins(self, guild_id: int, user_id: int) -> int:
        return int(self.get_player(guild_id, user_id)["coins"])

    def add_coins(self, guild_id: int, user_id: int, amount: int) -> int:
        self.get_player(guild_id, user_id)
        self.conn.execute(
            "UPDATE players SET coins = MAX(0, coins + ?) WHERE guild_id=? AND user_id=?",
            (amount, guild_id, user_id),
        )
        self.conn.commit()
        return self.coins(guild_id, user_id)

    def bump(self, guild_id: int, user_id: int, field: str, amount: int = 1) -> None:
        if field not in {"harvested", "helped", "steals", "game_wins"}:
            raise ValueError(field)
        self.get_player(guild_id, user_id)
        self.conn.execute(
            f"UPDATE players SET {field} = {field} + ? WHERE guild_id=? AND user_id=?",
            (amount, guild_id, user_id),
        )
        self.conn.commit()

    def plot_count(self, guild_id: int, user_id: int) -> int:
        return PLOT_LEVELS[int(self.get_player(guild_id, user_id)["plot_level"])][0]

    def set_plot_level(self, guild_id: int, user_id: int, level: int) -> None:
        self.conn.execute(
            "UPDATE players SET plot_level=? WHERE guild_id=? AND user_id=?",
            (level, guild_id, user_id),
        )
        self.conn.commit()

    # ---------- clan fund ----------
    def fund(self, guild_id: int) -> int:
        row = self.conn.execute("SELECT fund FROM clans WHERE guild_id=?", (guild_id,)).fetchone()
        if row is None:
            self.conn.execute("INSERT INTO clans (guild_id, fund) VALUES (?, 0)", (guild_id,))
            self.conn.commit()
            return 0
        return int(row["fund"])

    def add_fund(self, guild_id: int, amount: int) -> int:
        self.fund(guild_id)
        self.conn.execute(
            "UPDATE clans SET fund = MAX(0, fund + ?) WHERE guild_id=?", (amount, guild_id)
        )
        self.conn.commit()
        return self.fund(guild_id)

    # ---------- plants ----------
    def plants(self, guild_id: int, user_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM plants WHERE guild_id=? AND user_id=? ORDER BY ready_at",
                (guild_id, user_id),
            )
        )

    def plant(self, guild_id: int, user_id: int, crop: str, ready_at: int) -> None:
        self.conn.execute(
            "INSERT INTO plants (guild_id, user_id, crop, ready_at) VALUES (?,?,?,?)",
            (guild_id, user_id, crop, ready_at),
        )
        self.conn.commit()

    def remove_plant(self, plant_id: int) -> None:
        self.conn.execute("DELETE FROM plants WHERE id=?", (plant_id,))
        self.conn.commit()

    def water_plant(self, plant_id: int, seconds: int) -> None:
        self.conn.execute(
            "UPDATE plants SET watered=1, ready_at = MAX(?, ready_at - ?) WHERE id=?",
            (int(time.time()), seconds, plant_id),
        )
        self.conn.commit()

    def all_plants(self, guild_id: int) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM plants WHERE guild_id=?", (guild_id,)))

    # ---------- inventory ----------
    def inventory(self, guild_id: int, user_id: int) -> dict[str, int]:
        rows = self.conn.execute(
            "SELECT crop, qty FROM inventory WHERE guild_id=? AND user_id=? AND qty > 0",
            (guild_id, user_id),
        )
        return {r["crop"]: int(r["qty"]) for r in rows}

    def add_item(self, guild_id: int, user_id: int, crop: str, qty: int) -> None:
        self.conn.execute(
            "INSERT INTO inventory (guild_id, user_id, crop, qty) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id, user_id, crop) DO UPDATE SET qty = MAX(0, qty + ?)",
            (guild_id, user_id, crop, max(0, qty), qty),
        )
        self.conn.commit()

    def clear_inventory(self, guild_id: int, user_id: int) -> None:
        self.conn.execute(
            "DELETE FROM inventory WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )
        self.conn.commit()

    def sell_all(self, guild_id: int, user_id: int) -> tuple[int, int, dict[str, int]]:
        """Bán toàn bộ kho. Trả về (tiền người chơi nhận, tiền vào quỹ clan, chi tiết)."""
        from .config import CROPS

        inv = self.inventory(guild_id, user_id)
        total = sum(CROPS[c].sell_price * q for c, q in inv.items() if c in CROPS)
        if total <= 0:
            return 0, 0, {}
        to_clan = int(total * CLAN_TAX)
        gain = total - to_clan
        self.clear_inventory(guild_id, user_id)
        self.add_coins(guild_id, user_id, gain)
        self.add_fund(guild_id, to_clan)
        return gain, to_clan, inv

    # ---------- protections ----------
    def protection(self, guild_id: int, user_id: int) -> sqlite3.Row:
        self.get_player(guild_id, user_id)
        row = self.conn.execute(
            "SELECT * FROM protections WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO protections (guild_id, user_id) VALUES (?,?)", (guild_id, user_id)
            )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT * FROM protections WHERE guild_id=? AND user_id=?", (guild_id, user_id)
            ).fetchone()
        return row

    def set_protection(self, guild_id: int, user_id: int, field: str, value: int) -> None:
        if field not in {"alarm", "trap", "dog_tier", "dog_expires", "security_expires"}:
            raise ValueError(field)
        self.protection(guild_id, user_id)
        self.conn.execute(
            f"UPDATE protections SET {field}=? WHERE guild_id=? AND user_id=?",
            (value, guild_id, user_id),
        )
        self.conn.commit()

    # ---------- daily counters ----------
    def counters(self, guild_id: int, user_id: int) -> sqlite3.Row:
        day = self.today()
        row = self.conn.execute(
            "SELECT * FROM daily_counters WHERE guild_id=? AND user_id=? AND day=?",
            (guild_id, user_id, day),
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO daily_counters (guild_id, user_id, day) VALUES (?,?,?)",
                (guild_id, user_id, day),
            )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT * FROM daily_counters WHERE guild_id=? AND user_id=? AND day=?",
                (guild_id, user_id, day),
            ).fetchone()
        return row

    def bump_counter(self, guild_id: int, user_id: int, field: str, amount: int = 1) -> None:
        if field not in {"helps", "steals", "times_stolen"}:
            raise ValueError(field)
        self.counters(guild_id, user_id)
        self.conn.execute(
            f"UPDATE daily_counters SET {field} = {field} + ? "
            "WHERE guild_id=? AND user_id=? AND day=?",
            (amount, guild_id, user_id, self.today()),
        )
        self.conn.commit()

    def set_last_target(self, guild_id: int, user_id: int, target_id: int) -> None:
        self.counters(guild_id, user_id)
        self.conn.execute(
            "UPDATE daily_counters SET last_target=? WHERE guild_id=? AND user_id=? AND day=?",
            (target_id, guild_id, user_id, self.today()),
        )
        self.conn.commit()

    # ---------- daily check-in ----------
    def claim_daily(self, guild_id: int, user_id: int) -> tuple[bool, int, int]:
        """Trả về (thành công, tiền nhận, streak)."""
        from .config import DAILY_REWARD, DAILY_STREAK_BONUS, DAILY_STREAK_MAX_BONUS

        p = self.get_player(guild_id, user_id)
        today = self.today()
        if p["daily_date"] == today:
            return False, 0, int(p["daily_streak"])
        yesterday = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%d")
        streak = int(p["daily_streak"]) + 1 if p["daily_date"] == yesterday else 1
        bonus = min(DAILY_STREAK_BONUS * (streak - 1), DAILY_STREAK_MAX_BONUS)
        reward = DAILY_REWARD + bonus
        self.conn.execute(
            "UPDATE players SET daily_date=?, daily_streak=?, coins = coins + ? "
            "WHERE guild_id=? AND user_id=?",
            (today, streak, reward, guild_id, user_id),
        )
        self.conn.commit()
        return True, reward, streak

    # ---------- leaderboards ----------
    def top(self, guild_id: int, field: str, limit: int = 10) -> list[sqlite3.Row]:
        if field not in {"coins", "harvested", "helped", "steals", "game_wins"}:
            raise ValueError(field)
        return list(
            self.conn.execute(
                f"SELECT user_id, {field} AS value FROM players WHERE guild_id=? "
                f"ORDER BY {field} DESC LIMIT ?",
                (guild_id, limit),
            )
        )
