"""🧟 Zombie Clan — game đồng đội bảo vệ nông trại."""

from __future__ import annotations

import asyncio
import random

from ..config import fmt
from .base import BaseGame, ChoiceButton, ChoiceView

ROLES = {
    "xathu": ("🔫", "Xạ thủ", "Gây sát thương Zombie"),
    "kysu": ("🧱", "Kỹ sư", "Sửa tường"),
    "bacsi": ("💊", "Bác sĩ", "Hồi HP cho tường & đồng đội"),
    "baove": ("🌾", "Bảo vệ", "Giảm sát thương Zombie"),
    "bay": ("💣", "Đặt bẫy", "Tỉ lệ tiêu diệt nhiều Zombie"),
}
WAVES = [(1, 20), (2, 35), (3, 50), (4, 80), (5, 100)]
WALL_HP = 100


class ZombieGame(BaseGame):
    key = "zombie"

    async def play(self) -> None:
        wall = WALL_HP
        contribution: dict[int, int] = {p.id: 0 for p in self.players}

        for wave, zombies in WAVES:
            boss = wave == 5
            view = ChoiceView(self.players, timeout=12)
            for key, (emoji, name, _desc) in ROLES.items():
                view.add_item(ChoiceButton(key, name, emoji))
            msg = await self.send(
                f"🧟 **WAVE {wave}/5** — {zombies} zombie{' + 👹 BOSS' if boss else ''}\n"
                f"🧱 Tường: {wall}/{WALL_HP} HP\n{self.pot_line()}\n"
                "Chọn vai trò của bạn! ⏱️ 12 giây",
                view=view,
            )
            await view.wait()
            await msg.edit(view=None)

            killed = 0
            repair = 0
            reduce = 0.0
            lines = []
            for p in self.players:
                role = view.choices.get(p.id, random.choice(list(ROLES)))
                emoji, name, _ = ROLES[role]
                if role == "xathu":
                    dmg = random.randint(8, 16)
                    killed += dmg
                    contribution[p.id] += dmg
                    lines.append(f"{emoji} {p.display_name} bắn hạ {dmg} zombie")
                elif role == "bay":
                    if random.random() < 0.5:
                        dmg = random.randint(18, 30)
                        killed += dmg
                        contribution[p.id] += dmg
                        lines.append(f"{emoji} {p.display_name} kích bẫy, diệt {dmg} zombie!")
                    else:
                        lines.append(f"{emoji} {p.display_name} đặt bẫy nhưng zombie né mất")
                elif role == "kysu":
                    fix = random.randint(10, 20)
                    repair += fix
                    contribution[p.id] += fix // 2
                    lines.append(f"{emoji} {p.display_name} sửa tường +{fix} HP")
                elif role == "bacsi":
                    fix = random.randint(5, 12)
                    repair += fix
                    contribution[p.id] += fix // 2
                    lines.append(f"{emoji} {p.display_name} hồi máu đồng đội +{fix} HP")
                else:
                    reduce += 0.10
                    contribution[p.id] += 6
                    lines.append(f"{emoji} {p.display_name} phòng thủ, giảm 10% sát thương")

            leftover = max(0, zombies - killed)
            damage = int(leftover * (2 if boss else 1) * max(0.2, 1 - min(reduce, 0.6)))
            wall = min(WALL_HP, wall + repair) - damage
            await self.send(
                "\n".join(lines)
                + f"\n\n🧟 Còn lại {leftover} zombie → tường nhận {damage} sát thương "
                f"(+{repair} HP sửa chữa)\n🧱 Tường: {max(0, wall)}/{WALL_HP} HP"
            )
            if wall <= 0:
                total = self.pot
                self.db.add_fund(self.guild.id, total // 2)
                await self.send(
                    "💀 **TƯỜNG BỊ PHÁ — CLAN THẤT BẠI!**\n"
                    f"🏦 {fmt(total // 2)} 🪙 vào quỹ Clan, phần còn lại bị đốt."
                )
                return
            await asyncio.sleep(2)

        # thắng
        clan_share = int(self.pot * 0.30)
        even_share = int(self.pot * 0.40)
        contrib_share = self.pot - clan_share - even_share
        self.db.add_fund(self.guild.id, clan_share)
        per_player = even_share // len(self.players)
        for p in self.players:
            self.award(p, per_player)

        ranking = sorted(self.players, key=lambda p: contribution[p.id], reverse=True)
        weights = [0.25, 0.20, 0.15]
        paid = 0
        lines = []
        for i, p in enumerate(ranking[:3]):
            amount = int(contrib_share * weights[i])
            paid += amount
            self.award(p, amount)
            medal = ["🥇", "🥈", "🥉"][i]
            lines.append(
                f"{medal} {p.display_name} — {contribution[p.id]} đóng góp: "
                f"+{fmt(amount + per_player)} 🪙"
            )
        rest_players = ranking[3:]
        if rest_players:
            each = (contrib_share - paid) // len(rest_players)
            for p in rest_players:
                self.award(p, each)
                lines.append(
                    f"• {p.display_name} — {contribution[p.id]} đóng góp: "
                    f"+{fmt(each + per_player)} 🪙"
                )
        elif contrib_share - paid > 0:
            self.db.add_fund(self.guild.id, contrib_share - paid)
        self.db.bump(self.guild.id, ranking[0].id, "game_wins")

        await self.send(
            "🎉 **CLAN ĐÃ ĐẨY LÙI ĐÀN ZOMBIE!**\n"
            f"🏦 Quỹ Clan nhận {fmt(clan_share)} 🪙\n" + "\n".join(lines)
        )
