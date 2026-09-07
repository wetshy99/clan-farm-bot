"""🃏 Lật bài."""

from __future__ import annotations

import asyncio
import random

import discord

from ..config import fmt
from .base import BaseGame

DECK: list[tuple[str, str, int]] = (
    [("🪙 Xu nhỏ", "coin", 30)] * 4
    + [("💰 Xu vừa", "coin", 70)] * 3
    + [("💎 Xu lớn", "coin", 120)] * 2
    + [("👑 Kho báu", "coin", 250)]
    + [("🛡️ Khiên", "shield", 0)] * 2
    + [("🔄 Đảo lượt", "reverse", 0)]
    + [("🏴‍☠️ Cướp", "rob", 0)]
    + [("💣 Bom", "bomb", -100)] * 2
)


class CardButton(discord.ui.Button):
    def __init__(self, index: int) -> None:
        super().__init__(label=str(index + 1), emoji="🂠", style=discord.ButtonStyle.secondary, row=index // 4)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        assert isinstance(view, TableView)
        if interaction.user.id != view.current.id:
            await interaction.response.send_message("❌ Chưa tới lượt bạn!", ephemeral=True)
            return
        view.picked = self.index
        await interaction.response.defer()
        view.stop()


class TableView(discord.ui.View):
    def __init__(self, current: discord.Member, remaining: list[int], timeout: float = 20) -> None:
        super().__init__(timeout=timeout)
        self.current = current
        self.picked: int | None = None
        for i in remaining:
            self.add_item(CardButton(i))


class CardsGame(BaseGame):
    key = "bai"

    async def play(self) -> None:
        deck = random.sample(DECK, len(DECK))
        while len(deck) < 16:
            deck.append(("🪙 Xu nhỏ", "coin", 30))
        remaining = list(range(16))
        points: dict[int, int] = {p.id: 0 for p in self.players}
        shields: dict[int, int] = {p.id: 0 for p in self.players}
        order = list(self.players)
        turn = 0

        while remaining:
            player = order[turn % len(order)]
            view = TableView(player, remaining)
            msg = await self.send(
                f"🃏 **Lượt của {player.mention}** — còn {len(remaining)} lá\n"
                f"{self.pot_line()}\n⏱️ 20 giây để chọn một lá!",
                view=view,
            )
            await view.wait()
            await msg.edit(view=None)
            index = view.picked if view.picked is not None else random.choice(remaining)
            remaining.remove(index)
            name, kind, value = deck[index]

            if kind == "coin":
                points[player.id] += value
                text = f"🃏 Lá {index + 1}: **{name}** → {player.display_name} +{value} điểm"
            elif kind == "shield":
                shields[player.id] += 1
                text = f"🛡️ Lá {index + 1}: **{name}** → {player.display_name} có khiên chặn 1 lá bom"
            elif kind == "reverse":
                order.reverse()
                turn = order.index(player)
                text = f"🔄 Lá {index + 1}: **{name}** → thứ tự lượt bị đảo ngược!"
            elif kind == "rob":
                victims = [p for p in self.players if p.id != player.id and points[p.id] > 0]
                if victims:
                    victim = max(victims, key=lambda p: points[p.id])
                    loot = max(1, int(points[victim.id] * 0.2))
                    points[victim.id] -= loot
                    points[player.id] += loot
                    text = (
                        f"🏴‍☠️ Lá {index + 1}: **{name}** → {player.display_name} cướp {loot} điểm "
                        f"của {victim.display_name}!"
                    )
                else:
                    text = f"🏴‍☠️ Lá {index + 1}: **{name}** → không có ai để cướp."
            else:  # bomb
                if shields[player.id] > 0:
                    shields[player.id] -= 1
                    text = f"💣 Lá {index + 1}: **{name}** → 🛡️ Khiên đã chặn quả bom!"
                else:
                    lost = min(points[player.id], 100) if points[player.id] > 0 else 0
                    points[player.id] -= lost
                    text = f"💣 Lá {index + 1}: **{name}** → {player.display_name} mất {lost} điểm"
            await self.send(text)
            turn += 1
            await asyncio.sleep(1.5)

        total = sum(max(0, v) for v in points.values())
        ranking = sorted(self.players, key=lambda p: points[p.id], reverse=True)
        if total <= 0:
            self.db.add_fund(self.guild.id, self.pot)
            await self.send(f"😵 Không ai ghi điểm! {fmt(self.pot)} 🪙 vào 🏦 quỹ Clan.")
            return
        lines = []
        for p in ranking:
            share = int(self.pot * max(0, points[p.id]) / total)
            self.award(p, share)
            lines.append(f"• {p.display_name} — {points[p.id]} điểm → +{fmt(share)} 🪙")
        self.db.bump(self.guild.id, ranking[0].id, "game_wins")
        await self.send(f"🏆 **KẾT QUẢ LẬT BÀI**\n👑 {ranking[0].mention}\n" + "\n".join(lines))
