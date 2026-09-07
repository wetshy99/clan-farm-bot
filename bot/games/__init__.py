"""Danh mục minigame."""

from .base import BaseGame, Lobby
from .bomb import BombGame
from .cards import CardsGame
from .coin import CoinGame
from .island import IslandGame
from .quiz import QuizGame
from .race import RaceGame
from .ship import ShipGame
from .shooting import ShootingGame
from .zombie import ZombieGame

GAME_CLASSES: dict[str, type[BaseGame]] = {
    "bom": BombGame,
    "quiz": QuizGame,
    "tau": ShipGame,
    "dao": IslandGame,
    "banbong": ShootingGame,
    "xu": CoinGame,
    "zombie": ZombieGame,
    "dua": RaceGame,
    "bai": CardsGame,
}

__all__ = ["GAME_CLASSES", "BaseGame", "Lobby"]
