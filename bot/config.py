"""Cấu hình game: cây trồng, bảo vệ, nâng cấp đất, tỉ lệ..."""

from dataclasses import dataclass

COIN = "🪙"
CLAN_TAX = 0.10  # % tiền bán nông sản vào quỹ clan
GAME_TAX = 0.10  # % phí hệ thống của minigame (đốt)


@dataclass(frozen=True)
class Crop:
    key: str
    name: str
    emoji: str
    seed_price: int
    grow_seconds: int
    sell_price: int


CROPS: dict[str, Crop] = {
    c.key: c
    for c in (
        Crop("carrot", "Cà rốt", "🥕", 500, 5 * 60, 800),
        Crop("strawberry", "Dâu", "🍓", 2_000, 15 * 60, 3_500),
        Crop("sunflower", "Hoa hướng dương", "🌻", 5_000, 30 * 60, 9_000),
        Crop("special", "Cây đặc biệt", "🌳", 15_000, 60 * 60, 30_000),
    )
}

WATER_BONUS_SECONDS = 3 * 60
HELP_REWARD = 100
MAX_HELPS_PER_DAY = 5
MAX_STEALS_PER_DAY = 2
MAX_TIMES_STOLEN_PER_DAY = 1
STEAL_RATIO = 0.5
STEAL_PENALTY = 5_000

DAILY_REWARD = 5_000
DAILY_STREAK_BONUS = 1_000
DAILY_STREAK_MAX_BONUS = 10_000

STARTING_COINS = 20_000

# Cấp đất: level -> (số ô, giá nâng cấp lên cấp này)
PLOT_LEVELS: dict[int, tuple[int, int]] = {
    1: (3, 0),
    2: (5, 20_000),
    3: (7, 60_000),
    4: (10, 150_000),
    5: (13, 350_000),
    6: (17, 700_000),
    7: (21, 1_500_000),
    8: (25, 3_000_000),
    9: (30, 6_000_000),
    10: (35, 12_000_000),
}
MAX_PLOT_LEVEL = 10

LEVEL_EMOJI = {1: "🌱", 2: "🌿", 3: "🌿", 4: "🌳", 5: "🌳", 6: "🏡", 7: "🏡", 8: "🏰", 9: "👑", 10: "💎"}


@dataclass(frozen=True)
class Dog:
    tier: int
    name: str
    emoji: str
    price: int
    detect: float
    days: int


DOGS: dict[int, Dog] = {
    d.tier: d
    for d in (
        Dog(1, "Chó canh", "🐶", 50_000, 0.60, 7),
        Dog(2, "Chó bảo vệ", "🐕", 100_000, 0.75, 7),
        Dog(3, "Chó nghiệp vụ", "🐕‍🦺", 200_000, 0.90, 7),
        Dog(4, "Chó sói", "🐺", 500_000, 0.95, 7),
    )
}

ALARM_PRICE = 10_000
TRAP_PRICE = 25_000
TRAP_CHANCE = 0.40
TRAP_FINE = 5_000
SECURITY_PRICE = 1_000_000
SECURITY_DETECT = 0.95
SECURITY_DAYS = 30

# Minigame
GAMES: dict[str, tuple[str, str, int, int, int]] = {
    # key: (emoji, tên, phí tham gia, min người, max người)
    "bom": ("💣", "Bom hẹn giờ", 10_000, 3, 10),
    "quiz": ("🧠", "Đấu quiz", 10_000, 2, 20),
    "tau": ("🚢", "Tàu đắm", 10_000, 4, 15),
    "dao": ("🏝️", "Đảo kho báu", 10_000, 2, 10),
    "banbong": ("🎯", "Bắn bóng", 10_000, 2, 10),
    "xu": ("🪙", "Đồng xu may rủi", 10_000, 2, 20),
    "zombie": ("🧟", "Zombie Clan", 5_000, 2, 20),
    "dua": ("🏃", "Đua sinh tồn", 10_000, 3, 15),
    "bai": ("🃏", "Lật bài", 10_000, 2, 10),
}

LOBBY_SECONDS = 60


def fmt(n: float) -> str:
    """Định dạng tiền: 1234567 -> 1.234.567"""
    return f"{int(n):,}".replace(",", ".")
