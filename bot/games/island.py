"""🏝️ Đảo kho báu."""

from __future__ import annotations

import asyncio
import random

import discord

from ..config import fmt
from .base import BaseGame

ROWS = "ABCDE"
COLS = "12345"
ROUNDS = 5
# số ô còn lại sau mỗi vòng
SHRINK = [25, 20, 15, 10, 5]


class CellSelect(discord.ui.Select):
    def __init__(self, cells: list[str], players: list[discord.Member]) -> None:
        self.players = players
        self.picks: dict[int, str] = {}
        options = [discord.SelectOption(label=c, emoji="🟦") for c in cells[:25]]
        super().__init__(placeholder="Chọn ô để đào...", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        if not any(p.id == interaction.user.id for p in self.players):
            await interaction.response.send_message("❌ Bạn không ở trong ván này.", ephemeral=True)
            return
        self.picks[interaction.user.id] = self.values[0]
        await interaction.response.send_message(f"⛏️ Bạn sẽ đào ô **{self.values[0]}**.", ephemeral=True)
        if len(self.picks) >= len(self.players) and self.view is not None:
            self.view.stop()


class DigView(discord.ui.View):
    def __init__(self, cells: list[str], players: list[discord.Member], timeout: float = 15) -> None:
        super().__init__(timeout=timeout)
        self.select = CellSelect(cells, players)
        self.add_item(self.select)


class IslandGame(BaseGame):
    key = "dao"

    def _make_map(self) -> dict[str, tuple[str, int]]:
        cells = [f"{r}{c}" for r in ROWS for c in COLS]
        random.shuffle(cells)
        contents: list[tuple[str, int]] = [
            ("👑 Kho báu hoàng gia", 500),
            ("💎 Kho báu lớn", 250),
            ("💰 Kho báu", 150),
            ("💰 Kho báu", 150),
            ("🪙 Tiền xu", 80),
            ("🪙 Tiền xu", 80),
            ("🪙 Tiền xu", 80),
            ("🗺️ Bản đồ", 40),
            ("🛟 Xuồng cứu hộ", 30),
            ("🪤 Bẫy", -50),
            ("🪤 Bẫy", -50),
            ("💣 Bom", -120),
            ("🏴‍☠️ Hải tặc", 0),
            ("🏴‍☠️ Hải tặc", 0),
        ]
        while len(contents) < 25:
            contents.append(("🏖️ Cát trống", 0))
        random.shuffle(contents)
        return dict(zip(cells, contents, strict=False))

    async def play(self) -> None:
        island = self._make_map()
        cells = list(island)
        points: dict[int, int] = {p.id: 0 for p in self.players}

        for rnd in range(1, ROUNDS + 1):
            available = cells[: SHRINK[rnd - 1]]
            view = DigView(available, self.players)
            grid = " ".join(f"🟦{c}" for c in available)
            msg = await self.send(
                f"🏝️ **VÒNG {rnd}/{ROUNDS}** — {self.pot_line()}\n"
                f"Ô còn đào được ({len(available)}): {grid}\n⏱️ 15 giây để chọn!",
                view=view,
            )
            await view.wait()
            await msg.edit(view=None)

            lines = []
            for p in self.players:
                cell = view.select.picks.get(p.id) or random.choice(available)
                name, value = island[cell]
                if name.startswith("🏴‍☠️"):
                    leader = max(points, key=lambda uid: points[uid])
                    if leader != p.id and points[leader] > 0:
                        loot = int(points[leader] * 0.3)
                        points[leader] -= loot
                        points[p.id] += loot
                        lm = self.guild.get_member(leader)
                        lines.append(
                            f"🏴‍☠️ {p.display_name} đào ô {cell} — cướp {loot} điểm kho báu của "
                            f"{lm.display_name if lm else f'<@{leader}>'}!"
                        )
                        continue
                    lines.append(f"🏴‍☠️ {p.display_name} đào ô {cell} — hải tặc bỏ đi tay không.")
                    continue
                points[p.id] = max(0, points[p.id] + value)
                lines.append(
                    f"⛏️ {p.display_name} đào ô {cell} → {name} ({value:+d} điểm, tổng {points[p.id]})"
                )
            await self.send("\n".join(lines))
            if rnd < ROUNDS:
                await self.send("🌊 **NƯỚC ĐANG DÂNG!** Hòn đảo thu nhỏ lại...")
            await asyncio.sleep(2)

        total_points = sum(points.values())
        ranking = sorted(self.players, key=lambda p: points[p.id], reverse=True)
        lines = []
        if total_points <= 0:
            self.db.add_fund(self.guild.id, self.pot)
            await self.send(f"😵 Không ai đào được gì! {fmt(self.pot)} 🪙 vào 🏦 quỹ Clan.")
            return
        for p in ranking:
            share = int(self.pot * points[p.id] / total_points)
            self.award(p, share)
            lines.append(f"• {p.display_name} — {points[p.id]} điểm → +{fmt(share)} 🪙")
        self.db.bump(self.guild.id, ranking[0].id, "game_wins")
        await self.send(
            f"👑 **KẾT THÚC ĐẢO KHO BÁU**\n🏆 Vua kho báu: {ranking[0].mention}\n" + "\n".join(lines)
        )
