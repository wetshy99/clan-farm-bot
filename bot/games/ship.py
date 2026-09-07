"""🚢 Tàu đắm."""

from __future__ import annotations

import asyncio
import random

import discord

from ..config import fmt
from .base import BaseGame, ChoiceButton, ChoiceView

ROOMS = ["A", "B", "C", "D", "E", "F"]
ROOM_EMOJI = {"A": "1️⃣", "B": "2️⃣", "C": "3️⃣", "D": "4️⃣", "E": "5️⃣", "F": "6️⃣"}
LIFEBOAT_COST = 20_000


class LifeboatView(discord.ui.View):
    def __init__(self, doomed: list[discord.Member], timeout: float = 8) -> None:
        super().__init__(timeout=timeout)
        self.doomed = doomed
        self.used: set[int] = set()

    @discord.ui.button(label="XUỒNG CỨU HỘ (20.000 🪙)", emoji="🛟", style=discord.ButtonStyle.success)
    async def rescue(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not any(p.id == interaction.user.id for p in self.doomed):
            await interaction.response.send_message(
                "❌ Khoang của bạn không chìm (hoặc bạn không trong ván).", ephemeral=True
            )
            return
        if interaction.user.id in self.used:
            await interaction.response.send_message("❌ Bạn đã dùng xuồng rồi.", ephemeral=True)
            return
        self.used.add(interaction.user.id)
        await interaction.response.send_message(
            "🛟 Bạn nhảy lên xuồng cứu hộ và thoát chết! (-20.000 🪙)", ephemeral=True
        )


class ShipGame(BaseGame):
    key = "tau"

    async def play(self) -> None:
        alive = list(self.players)
        rooms = list(ROOMS)
        used_boat: set[int] = set()
        round_no = 0

        while len(alive) > 1 and len(rooms) > 1:
            round_no += 1
            view = ChoiceView(alive, timeout=10)
            for i, room in enumerate(rooms):
                view.add_item(ChoiceButton(room, f"Khoang {room}", ROOM_EMOJI[room], row=i // 3))
            msg = await self.send(
                f"🚢 **VÒNG {round_no}** — {len(alive)} người sống\n{self.pot_line()}\n"
                f"Khoang còn hoạt động: {' '.join(ROOM_EMOJI[r] + r for r in rooms)}\n"
                "⏱️ 10 giây để chọn khoang!",
                view=view,
            )
            await view.wait()
            await msg.edit(view=None)

            positions = {p.id: view.choices.get(p.id, random.choice(rooms)) for p in alive}
            sink_count = 2 if len(rooms) > 3 and len(alive) > 3 else 1
            sinking = random.sample(rooms, min(sink_count, len(rooms) - 1))
            doomed = [p for p in alive if positions[p.id] in sinking]

            await self.send(
                "🌊 **NƯỚC ĐANG TRÀN VÀO!**\n"
                f"💥 Khoang {' + '.join(sinking)} đã bị chìm!"
                + (
                    f"\n⚠️ Nguy hiểm: {', '.join(p.display_name for p in doomed)}"
                    if doomed
                    else "\n😮 Không ai ở trong khoang chìm!"
                )
            )

            eligible = [p for p in doomed if p.id not in used_boat]
            if eligible:
                boat = LifeboatView(eligible)
                bmsg = await self.send(
                    "🛟 Còn 8 giây để dùng **Xuồng cứu hộ** (20.000 🪙, mỗi ván 1 lần)!", view=boat
                )
                await asyncio.sleep(8)
                boat.stop()
                await bmsg.edit(view=None)
                for uid in boat.used:
                    used_boat.add(uid)
                    self.db.add_coins(self.guild.id, uid, -LIFEBOAT_COST)
                doomed = [p for p in doomed if p.id not in boat.used]

            for p in doomed:
                alive.remove(p)
            rooms = [r for r in rooms if r not in sinking]
            if doomed:
                await self.send(
                    f"☠️ Bị loại: {', '.join(p.display_name for p in doomed)}\n"
                    f"👥 Còn lại: {len(alive)} người"
                )
            if len(alive) <= 1:
                break
            if len(rooms) < 2:
                rooms = random.sample(ROOMS, 3)
                await self.send("🚨 Tàu vỡ thêm — các khoang mới được mở: " + " ".join(rooms))
            await asyncio.sleep(2)

        if not alive:
            self.db.add_fund(self.guild.id, self.pot)
            await self.send(
                f"🌊 Tất cả đều chìm! {fmt(self.pot)} 🪙 được chuyển vào 🏦 quỹ Clan."
            )
            return
        winner = alive[0]
        self.declare_winner(winner, self.pot)
        await self.send(
            f"🏆 **NGƯỜI SỐNG SÓT CUỐI CÙNG!**\n👑 {winner.mention}\n💰 Nhận {fmt(self.pot)} 🪙"
        )
