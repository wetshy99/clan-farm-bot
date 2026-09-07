"""Điểm khởi chạy bot: python -m bot"""

from __future__ import annotations

import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from .db import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("clanfarm")

COGS = ["bot.cogs.farm", "bot.cogs.games", "bot.cogs.profile"]


class ClanFarmBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = os.getenv("MEMBERS_INTENT", "").lower() in {"1", "true", "yes"}
        super().__init__(command_prefix="!cf ", intents=intents, help_command=None)
        self.db = Database()

    async def setup_hook(self) -> None:
        for cog in COGS:
            await self.load_extension(cog)
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        log.info("Đã đồng bộ %d lệnh: %s", len(synced), ", ".join(c.name for c in synced))

    async def on_ready(self) -> None:
        log.info("Đăng nhập với tên %s (%s)", self.user, getattr(self.user, "id", "?"))
        await self.change_presence(
            activity=discord.Game(name="/farm • /game • /thongtin • /diemdanh")
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        """Always acknowledge command failures instead of showing Discord's timeout."""
        log.exception("Slash command failed: %s", error)
        message = "⚠️ Bot gặp lỗi khi mở lệnh. Thử lại sau vài giây."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except discord.HTTPException:
            log.exception("Không thể gửi thông báo lỗi slash command")


async def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Thiếu DISCORD_TOKEN — tạo file .env từ .env.example.")
    async with ClanFarmBot() as bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
