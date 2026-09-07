"""🎯 Bắn bóng."""

from __future__ import annotations

import asyncio
import random

from ..config import fmt
from .base import BaseGame, ChoiceButton, ChoiceView

NUM_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
POOL = [
    ("🟥", -50),
    ("🟨", 50),
    ("🟩", 100),
    ("💎", 200),
    ("🎁", 300),
    ("💣", -100),
]
ROUNDS = 5


class ShootingGame(BaseGame):
    key = "banbong"

    def _targets(self) -> list[tuple[str, int]]:
        targets = [random.choice(POOL) for _ in range(8)]
        if random.random() < 0.10:
            targets[random.randrange(8)] = ("🎯", 500)  # hồng tâm
        return targets

    async def play(self) -> None:
        scores: dict[int, int] = {p.id: 0 for p in self.players}
        for rnd in range(1, ROUNDS + 1):
            targets = self._targets()
            view = ChoiceView(self.players, timeout=12)
            for i in range(8):
                view.add_item(ChoiceButton(str(i), f"Bắn {i + 1}", NUM_EMOJI[i], row=i // 4))
            board = "\n".join(f"{NUM_EMOJI[i]} ❓" for i in range(8))
            msg = await self.send(
                f"🎯 **LƯỢT {rnd}/{ROUNDS}** — {self.pot_line()}\n"
                f"Bảng mục tiêu (điểm bị giấu):\n{board}\n⏱️ 12 giây để bắn!",
                view=view,
            )
            await view.wait()
            await msg.edit(view=None)

            lines = []
            for i, (emoji, point) in enumerate(targets):
                lines.append(f"{NUM_EMOJI[i]} {emoji} {point:+d}")
            result_lines = []
            for p in self.players:
                pick = int(view.choices.get(p.id, str(random.randrange(8))))
                emoji, point = targets[pick]
                scores[p.id] += point
                result_lines.append(
                    f"• {p.display_name} bắn {NUM_EMOJI[pick]} → {emoji} {point:+d} "
                    f"(tổng {scores[p.id]})"
                )
            await self.send(
                "🎯 **KẾT QUẢ LƯỢT " + str(rnd) + "**\n" + "\n".join(lines) + "\n\n" + "\n".join(result_lines)
            )
            await asyncio.sleep(2)

        ranking = sorted(self.players, key=lambda p: scores[p.id], reverse=True)
        rewards = self.payout_ranking(ranking)
        medals = ["🥇", "🥈", "🥉"]
        board = "\n".join(
            f"{medals[i] if i < 3 else '•'} {p.display_name} — {scores[p.id]} điểm"
            for i, p in enumerate(ranking)
        )
        prize = "\n".join(f"{medals[i]} {m.display_name}: +{fmt(a)} 🪙" for i, (m, a) in enumerate(rewards))
        await self.send(f"🏆 **KẾT QUẢ CHUNG CUỘC**\n{board}\n\n💰 **Thưởng**\n{prize}")
