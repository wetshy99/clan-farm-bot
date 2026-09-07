"""Điểm chạy cho các panel hosting (Pterodactyl/Katabump): python main.py"""

from __future__ import annotations

import asyncio

from bot.__main__ import main

if __name__ == "__main__":
    asyncio.run(main())
