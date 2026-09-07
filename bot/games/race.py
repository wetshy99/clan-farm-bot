"""🏃 Đua sinh tồn."""

from __future__ import annotations

import asyncio
import random

from ..config import fmt
from .base import BaseGame, ChoiceButton, ChoiceView

# tên: (emoji, an toàn, mất máu, đường tắt)
PATHS = {
    "rung": ("🌲", "Rừng", 0.70, 0.20, 0.10),
    "nui": ("🏔️", "Núi", 0.50, 0.30, 0.20),
    "song": ("🌊", "Sông", 0.60, 0.25, 0.15),
}
ITEMS = ["❤️ Thuốc", "🛡️ Khiên", "⚡ Giày", "🗺️ Bản đồ"]
MAX_ROUNDS = 12
GOAL = 5  # số bước đường tắt cần để về đích


class RaceGame(BaseGame):
    key = "dua"

    async def play(self) -> None:
        hp = {p.id: 3 for p in self.players}
        progress = {p.id: 0 for p in self.players}
        shield = {p.id: 0 for p in self.players}
        alive = list(self.players)

        for rnd in range(1, MAX_ROUNDS + 1):
            if len(alive) <= 1:
                break
            view = ChoiceView(alive, timeout=10)
            for key, (emoji, name, *_rest) in PATHS.items():
                view.add_item(ChoiceButton(key, name, emoji))
            status = " • ".join(
                f"{p.display_name} {'❤️' * hp[p.id]} ({progress[p.id]}/{GOAL})" for p in alive
            )
            msg = await self.send(
                f"🏃 **VÒNG {rnd}** — {self.pot_line()}\n{status}\n"
                "Chọn đường đi! ⏱️ 10 giây",
                view=view,
            )
            await view.wait()
            await msg.edit(view=None)

            lines = []
            for p in list(alive):
                key = view.choices.get(p.id, random.choice(list(PATHS)))
                emoji, name, safe, hurt, _short = PATHS[key]
                roll = random.random()
                if roll < safe:
                    progress[p.id] += 1
                    line = f"{emoji} {p.display_name} đi {name} an toàn (+1 bước)"
                elif roll < safe + hurt:
                    if shield[p.id] > 0:
                        shield[p.id] -= 1
                        line = f"{emoji} {p.display_name} gặp nguy hiểm nhưng 🛡️ khiên đã chặn!"
                    else:
                        hp[p.id] -= 1
                        line = f"{emoji} {p.display_name} gặp nguy hiểm ở {name} (-1 ❤️)"
                else:
                    progress[p.id] += 2
                    line = f"{emoji} {p.display_name} tìm được đường tắt ở {name} (+2 bước)"
                if random.random() < 0.20:
                    item = random.choice(ITEMS)
                    if item.startswith("❤️"):
                        hp[p.id] = min(3, hp[p.id] + 1)
                    elif item.startswith("🛡️"):
                        shield[p.id] += 1
                    else:
                        progress[p.id] += 1
                    line += f" • nhặt được {item}"
                if hp[p.id] <= 0:
                    alive.remove(p)
                    line += " ☠️ **BỊ LOẠI!**"
                lines.append(line)
            await self.send("\n".join(lines))

            finished = [p for p in alive if progress[p.id] >= GOAL]
            if finished:
                ranking = sorted(alive, key=lambda p: (progress[p.id], hp[p.id]), reverse=True)
                await self._finish(ranking)
                return
            await asyncio.sleep(2)

        ranking = sorted(
            self.players,
            key=lambda p: (p in alive, progress[p.id], hp[p.id]),
            reverse=True,
        )
        await self._finish(ranking)

    async def _finish(self, ranking: list) -> None:
        rewards = self.payout_ranking(ranking)
        medals = ["🥇", "🥈", "🥉"]
        board = "\n".join(
            f"{medals[i] if i < 3 else '•'} {p.display_name}" for i, p in enumerate(ranking)
        )
        prize = "\n".join(f"{medals[i]} {m.display_name}: +{fmt(a)} 🪙" for i, (m, a) in enumerate(rewards))
        await self.send(f"🏁 **VỀ ĐÍCH!**\n{board}\n\n💰 **Thưởng**\n{prize}")
