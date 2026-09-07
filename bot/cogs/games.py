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
from ..games.base import MAX_BET, parse_bet_amount

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
        view = self.view
        assert isinstance(view, GameMenu)
        key = self.values[0]
        view.selected_key = key
        emoji, name, fee, _minp, _maxp = GAMES[key]
        await interaction.response.send_message(
            f"{emoji} Đã chọn **{name}** — cược từ **{fmt(fee)}** đến **{fmt(MAX_BET)}** 🪙.\n"
            "Bấm **➕ Tạo phòng** để mở sảnh.",
            ephemeral=True,
        )


class CreateLobbyButton(discord.ui.Button):
    def __init__(self, cog: GameCog) -> None:
        self.cog = cog
        super().__init__(label="Tạo phòng", emoji="➕", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        assert isinstance(view, GameMenu)
        if view.selected_key is None:
            await interaction.response.send_message(
                "❌ Chọn một minigame trước rồi bấm **Tạo phòng**.", ephemeral=True
            )
            return
        await interaction.response.send_modal(BetModal(self.cog, view.selected_key))


class GameMenu(discord.ui.View):
    def __init__(self, cog: GameCog, owner_id: int) -> None:
        super().__init__(timeout=120)
        self.owner_id = owner_id
        self.selected_key: str | None = None
        self.add_item(GameSelect(cog, owner_id))
        self.add_item(CreateLobbyButton(cog))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Menu này của người khác, gõ `/game` để mở menu của bạn.", ephemeral=True
            )
            return False
        return True


class BetModal(discord.ui.Modal):
    def __init__(self, cog: GameCog, game_key: str) -> None:
        _emoji, name, fee, _minp, _maxp = GAMES[game_key]
        super().__init__(title=f"Cược cho {name}")
        self.cog = cog
        self.game_key = game_key
        self.amount: discord.ui.TextInput = discord.ui.TextInput(
            label=f"Mức cược (tối thiểu {fmt(fee)} 🪙)",
            placeholder="Ví dụ: 10.000",
            default=str(fee),
            max_length=10,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        minimum = GAMES[self.game_key][2]
        try:
            fee = parse_bet_amount(str(self.amount.value), minimum)
        except (TypeError, ValueError):
            await interaction.response.send_message(
                f"❌ Cược phải từ {fmt(minimum)} đến {fmt(MAX_BET)} 🪙.",
                ephemeral=True,
            )
            return
        await self.cog.open_lobby(interaction, self.game_key, fee_override=fee)


class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db
        self.active: set[int] = set()  # channel_id đang có ván

    async def open_lobby(
        self,
        interaction: discord.Interaction,
        key: str,
        fee_override: int | None = None,
    ) -> None:
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
        emoji, name, configured_fee, _minp, _maxp = game_config
        fee = fee_override if fee_override is not None else configured_fee
        if fee < configured_fee or fee > MAX_BET:
            message = f"❌ Cược phải từ {fmt(configured_fee)} đến {fmt(MAX_BET)} 🪙."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return
        if self.db.coins(interaction.guild.id, member.id) < fee:
            await interaction.response.send_message(
                f"❌ Bạn cần {fmt(fee)} 🪙 để mở phòng {name}.", ephemeral=True
            )
            return

        lobby = Lobby(self.db, key, member, fee=fee)
        await interaction.response.send_message(
            f"{emoji} Đã mở phòng **{name}** với cược **{fmt(fee)} 🪙**!", ephemeral=True
        )
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
            description=(
                "Chọn game → bấm **➕ Tạo phòng** → nhập mức cược.\n"
                "Trong phòng có nút tham gia, đặt cược, bắt đầu và hủy phòng."
            ),
            color=0xEB459E,
        )
        for emoji, name, fee, minp, maxp in GAMES.values():
            embed.add_field(
                name=f"{emoji} {name}",
                value=f"💰 {fmt(fee)} 🪙 • 👥 {minp}-{maxp} người",
                inline=True,
            )
        embed.set_footer(text="Chủ phòng có thể đổi cược trước khi có người tham gia.")
        await interaction.response.send_message(
            embed=embed, view=GameMenu(self, interaction.user.id)
        )


async def setup(bot: commands.Bot) -> None:  # pragma: no cover - discord entrypoint
    await bot.add_cog(GameCog(bot, bot.db))  # type: ignore[attr-defined]
