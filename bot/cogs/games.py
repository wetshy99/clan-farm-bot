"""Lệnh /game — sảnh chọn minigame."""

from __future__ import annotations

import asyncio
import logging
import traceback

import discord
from discord import app_commands
from discord.ext import commands

from ..config import GAMES, LOBBY_SECONDS, fmt
from ..db import Database
from ..games import GAME_CLASSES, Lobby

log = logging.getLogger(__name__)


class GameSelect(discord.ui.Select):
    def __init__(self, cog: GameCog, owner_id: int) -> None:
        self.cog = cog
        self.owner_id = owner_id
        options = [
            discord.SelectOption(
                label=name,
                value=key,
                emoji=emoji,
                description=f"{fmt(fee)} 🪙 • {minp}-{maxp} người",
            )
            for key, (emoji, name, fee, minp, maxp) in GAMES.items()
        ]
        super().__init__(placeholder="Chọn minigame để mở phòng...", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Menu này của người khác, gõ `/game` để mở của bạn.", ephemeral=True
            )
            return
        await self.cog.open_lobby(interaction, self.values[0])


class GameMenu(discord.ui.View):
    def __init__(self, cog: GameCog, owner_id: int) -> None:
        super().__init__(timeout=120)
        self.add_item(GameSelect(cog, owner_id))


class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db
        self.active: set[int] = set()  # channel_id đang có ván

    async def open_lobby(self, interaction: discord.Interaction, key: str) -> None:
        assert interaction.guild is not None and interaction.channel is not None
        member = interaction.user
        assert isinstance(member, discord.Member)
        channel = interaction.channel

        game_config = GAMES.get(key)
        game_class = GAME_CLASSES.get(key)
        if game_config is None or game_class is None:
            message = "❌ Game này không còn khả dụng. Gõ `/game` để tải lại danh sách."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return

        if channel.id in self.active:
            await interaction.response.send_message(
                "❌ Kênh này đang có một ván đang diễn ra, chờ xong đã!", ephemeral=True
            )
            return
        emoji, name, fee, _minp, _maxp = game_config
        if self.db.coins(interaction.guild.id, member.id) < fee:
            await interaction.response.send_message(
                f"❌ Bạn cần {fmt(fee)} 🪙 để mở phòng {name}.", ephemeral=True
            )
            return

        lobby = Lobby(self.db, key, member)
        await interaction.response.send_message(f"{emoji} Đã mở phòng **{name}**!", ephemeral=True)
        lobby.message = await channel.send(embed=lobby.embed(), view=lobby)
        self.active.add(channel.id)
        try:
            try:
                await asyncio.wait_for(lobby.started.wait(), timeout=LOBBY_SECONDS)
            except TimeoutError:
                pass
            lobby.stop()
            await lobby.message.edit(view=None)

            if lobby.cancelled:
                await channel.send("❌ Phòng đã bị hủy.")
                return
            players = [p for p in lobby.players if self.db.coins(interaction.guild.id, p.id) >= fee]
            if len(players) < lobby.min_players:
                await channel.send(
                    f"😕 Không đủ người chơi ({len(players)}/{lobby.min_players}), phòng đóng."
                )
                return

            game = game_class(self.db, channel, interaction.guild, players, fee)
            game.collect_fees()
            await channel.send(
                f"{emoji} **{name.upper()} BẮT ĐẦU!**\n"
                f"👥 {len(players)} người chơi • {game.pot_line()}"
            )
            await game.play()
        except Exception:  # pragma: no cover - báo lỗi trong Discord
            log.exception("Minigame %s failed in channel %s", key, channel.id)
            traceback.print_exc()
            if interaction.response.is_done():
                await channel.send("💥 Ván đấu gặp lỗi và đã dừng lại. Hãy thử mở phòng mới.")
            else:
                await interaction.response.send_message(
                    "💥 Không thể mở ván đấu lúc này. Hãy thử lại.", ephemeral=True
                )
        finally:
            self.active.discard(channel.id)

    @app_commands.guild_only()
    @app_commands.command(name="game", description="🎮 Mở sảnh minigame của Clan")
    async def game(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="🎮 SẢNH MINIGAME CLAN",
            description="Chọn một game bên dưới để mở phòng. Mọi người bấm 🎮 THAM GIA để vào.",
            color=0xEB459E,
        )
        for emoji, name, fee, minp, maxp in GAMES.values():
            embed.add_field(
                name=f"{emoji} {name}",
                value=f"💰 {fmt(fee)} 🪙 • 👥 {minp}-{maxp} người",
                inline=True,
            )
        embed.set_footer(text="Phí hệ thống 10% mỗi ván bị đốt để tránh lạm phát")
        await interaction.response.send_message(
            embed=embed, view=GameMenu(self, interaction.user.id)
        )


async def setup(bot: commands.Bot) -> None:  # pragma: no cover - discord entrypoint
    await bot.add_cog(GameCog(bot, bot.db))  # type: ignore[attr-defined]
