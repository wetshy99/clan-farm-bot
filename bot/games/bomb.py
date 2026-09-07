"""💣 Bom hẹn giờ."""

from __future__ import annotations

import asyncio
import random
import time

import discord

from ..config import fmt
from .base import BaseGame


class PassView(discord.ui.View):
    def __init__(self, holder: discord.Member, alive: list[discord.Member], timeout: float) -> None:
        super().__init__(timeout=timeout)
        self.holder = holder
        self.target: discord.Member | None = None
        for member in alive:
            if member.id != holder.id:
                self.add_item(PassButton(member))


class PassButton(discord.ui.Button):
    def __init__(self, member: discord.Member) -> None:
        super().__init__(label=member.display_name[:20], style=discord.ButtonStyle.danger, emoji="💣")
        self.member = member

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        assert isinstance(view, PassView)
        if interaction.user.id != view.holder.id:
            await interaction.response.send_message(
                "❌ Bom không ở trong tay bạn!", ephemeral=True
            )
            return
        view.target = self.member
        await interaction.response.defer()
        view.stop()


class BombGame(BaseGame):
    key = "bom"

    async def play(self) -> None:
        alive = list(self.players)
        round_no = 0
        while len(alive) > 1:
            round_no += 1
            holder = random.choice(alive)
            fuse = random.randint(10, 20)
            deadline = time.time() + fuse
            await self.send(
                f"💣 **VÒNG {round_no}** — {self.pot_line()}\n"
                f"👥 Còn lại: {len(alive)} người\n"
                f"💣 Bom được trao cho {holder.mention}\n⏰ ??? giây — chuyền ngay!"
            )
            while True:
                left = deadline - time.time()
                if left <= 0:
                    break
                view = PassView(holder, alive, timeout=left)
                msg = await self.send(
                    f"💣 Bom đang ở **{holder.display_name}** — chọn người để chuyền!", view=view
                )
                await view.wait()
                await msg.edit(view=None)
                if view.target is None:
                    break
                await self.send(f"💣 **CHUYỀN BOM!** {holder.mention} ➡️ {view.target.mention}")
                holder = view.target

            alive.remove(holder)
            await self.send(
                f"💥💥💥 **BOOM!!!**\n☠️ {holder.mention} đã bị bom nổ!\n"
                f"💸 Mất {fmt(self.fee)} 🪙\n👥 Người còn lại: {len(alive)}"
            )
            await asyncio.sleep(2)

        winner = alive[0]
        self.declare_winner(winner, self.pot)
        await self.send(
            f"🎉🎉🎉 **KẾT THÚC!**\n🏆 Người sống sót cuối cùng: 👑 {winner.mention}\n"
            f"💰 Nhận thưởng: **{fmt(self.pot)}** 🪙\n"
            f"🌾 Cảm ơn mọi người đã tham gia Bom Hẹn Giờ!"
        )
