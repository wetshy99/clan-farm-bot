"""Lệnh /thongtin và /diemdanh."""

from __future__ import annotations

import time

import discord
from discord import app_commands
from discord.ext import commands

from ..config import (
    CROPS,
    DAILY_REWARD,
    LEVEL_EMOJI,
    MAX_HELPS_PER_DAY,
    MAX_STEALS_PER_DAY,
    PLOT_LEVELS,
    fmt,
)
from ..db import Database
from ..utils import plot_display, protection_display


class ProfileCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    @app_commands.guild_only()
    @app_commands.command(name="thongtin", description="📊 Xem thông tin người chơi")
    @app_commands.describe(nguoi_choi="Người muốn xem (bỏ trống = chính bạn)")
    async def thongtin(
        self, interaction: discord.Interaction, nguoi_choi: discord.Member | None = None
    ) -> None:
        assert interaction.guild is not None
        member = nguoi_choi or interaction.user
        assert isinstance(member, discord.Member)
        gid = interaction.guild.id
        p = self.db.get_player(gid, member.id)
        c = self.db.counters(gid, member.id)
        level = int(p["plot_level"])
        plots, _ = PLOT_LEVELS[level]
        plants = self.db.plants(gid, member.id)
        now = int(time.time())
        ready = sum(1 for pl in plants if pl["ready_at"] <= now)
        inv = self.db.inventory(gid, member.id)
        inv_value = sum(CROPS[k].sell_price * q for k, q in inv.items() if k in CROPS)

        embed = discord.Embed(title=f"📊 HỒ SƠ — {member.display_name}", color=0x5865F2)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💰 Tiền", value=f"{fmt(p['coins'])} 🪙", inline=True)
        embed.add_field(name="📦 Giá trị kho", value=f"{fmt(inv_value)} 🪙", inline=True)
        embed.add_field(name="🏦 Quỹ Clan", value=f"{fmt(self.db.fund(gid))} 🪙", inline=True)
        embed.add_field(
            name=f"{LEVEL_EMOJI[level]} Nông trại",
            value=f"Lv.{level} • {len(plants)}/{plots} ô • {ready} cây sẵn sàng\n"
            + plot_display(self.db, gid, member.id),
            inline=False,
        )
        embed.add_field(name="🌾 Đã thu hoạch", value=f"{fmt(p['harvested'])} cây", inline=True)
        embed.add_field(name="🤝 Đã giúp", value=f"{fmt(p['helped'])} lượt", inline=True)
        embed.add_field(name="🥷 Trộm thành công", value=f"{fmt(p['steals'])} lần", inline=True)
        embed.add_field(name="🎮 Thắng minigame", value=f"{fmt(p['game_wins'])} ván", inline=True)
        embed.add_field(name="🔥 Chuỗi điểm danh", value=f"{p['daily_streak']} ngày", inline=True)
        embed.add_field(
            name="⏳ Lượt hôm nay",
            value=(
                f"💧 Giúp: {int(c['helps'])}/{MAX_HELPS_PER_DAY} • "
                f"🥷 Trộm: {int(c['steals'])}/{MAX_STEALS_PER_DAY}"
            ),
            inline=False,
        )
        embed.add_field(
            name="🛡️ Bảo vệ", value=protection_display(self.db, gid, member.id), inline=False
        )
        embed.set_footer(text="/farm để chơi nông trại • /game để chơi minigame")
        await interaction.response.send_message(embed=embed)

    @app_commands.guild_only()
    @app_commands.command(name="diemdanh", description="📅 Điểm danh nhận xu mỗi ngày")
    async def diemdanh(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        gid, uid = interaction.guild.id, interaction.user.id
        ok, reward, streak = self.db.claim_daily(gid, uid)
        if not ok:
            await interaction.response.send_message(
                f"📅 Hôm nay bạn điểm danh rồi! Chuỗi hiện tại: **{streak} ngày** 🔥\n"
                "Quay lại vào ngày mai nhé.",
                ephemeral=True,
            )
            return
        bonus = reward - DAILY_REWARD
        await interaction.response.send_message(
            f"📅 **ĐIỂM DANH THÀNH CÔNG!**\n"
            f"💰 Nhận {fmt(reward)} 🪙"
            + (f" (thưởng chuỗi +{fmt(bonus)} 🪙)" if bonus else "")
            + f"\n🔥 Chuỗi: **{streak} ngày**\n"
            f"💵 Số dư: {fmt(self.db.coins(gid, uid))} 🪙"
        )


async def setup(bot: commands.Bot) -> None:  # pragma: no cover - discord entrypoint
    await bot.add_cog(ProfileCog(bot, bot.db))  # type: ignore[attr-defined]
