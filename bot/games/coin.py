"""🪙 Đồng xu may rủi."""

from __future__ import annotations

import asyncio
import random

from ..config import fmt
from .base import BaseGame, ChoiceButton, ChoiceView


class CoinGame(BaseGame):
    key = "xu"

    async def play(self) -> None:
        alive = list(self.players)
        round_no = 0
        while len(alive) > 1:
            round_no += 1
            view = ChoiceView(alive, timeout=10)
            view.add_item(ChoiceButton("ngua", "NGỬA", "🟡"))
            view.add_item(ChoiceButton("sap", "SẤP", "⚪"))
            msg = await self.send(
                f"🪙 **VÒNG {round_no}** — {len(alive)} người còn sống\n"
                f"{self.pot_line()}\n"
                "🟡 NGỬA hay ⚪ SẤP? ⏱️ 10 giây (bấm lại để đổi mặt)",
                view=view,
            )
            await view.wait()
            await msg.edit(view=None)

            result = random.choice(["ngua", "sap"])
            label = "🟡 NGỬA" if result == "ngua" else "⚪ SẤP"
            survivors = [
                p for p in alive if view.choices.get(p.id, random.choice(["ngua", "sap"])) == result
            ]
            if not survivors:  # tất cả sai -> chơi lại vòng này
                await self.send(f"🪙 ĐANG TUNG... **{label}**!\n😱 Tất cả đều sai — tung lại!")
                await asyncio.sleep(2)
                continue
            out = [p for p in alive if p not in survivors]
            alive = survivors
            await self.send(
                f"🪙 ĐANG TUNG... **{label}**!\n"
                + (f"☠️ Bị loại: {', '.join(p.display_name for p in out)}\n" if out else "")
                + f"👥 Còn lại: {len(alive)} người"
            )
            await asyncio.sleep(2)

        winner = alive[0]
        self.declare_winner(winner, self.pot)
        await self.send(
            f"🏆 **NGƯỜI CUỐI CÙNG SỐNG SÓT!**\n👑 {winner.mention}\n"
            f"💰 Nhận {fmt(self.pot)} 🪙"
        )
