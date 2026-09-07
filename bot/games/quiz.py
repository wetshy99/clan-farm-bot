"""🧠 Đấu quiz."""

from __future__ import annotations

import asyncio
import random
import time

import discord

from ..config import fmt
from .base import BaseGame

LETTERS = ["A", "B", "C", "D"]
LETTER_EMOJI = ["🇦", "🇧", "🇨", "🇩"]
QUESTION_COUNT = 10
ANSWER_SECONDS = 10

# (câu hỏi, [4 đáp án], chỉ số đáp án đúng)
QUESTIONS: list[tuple[str, list[str], int]] = [
    ("Loài nào được gọi là 'vua của muôn loài'?", ["Hổ", "Sư tử", "Voi", "Gấu"], 1),
    ("Thủ đô của Việt Nam là gì?", ["TP.HCM", "Đà Nẵng", "Hà Nội", "Huế"], 2),
    ("Hành tinh nào gần Mặt Trời nhất?", ["Kim tinh", "Thủy tinh", "Hỏa tinh", "Trái Đất"], 1),
    ("1 giờ có bao nhiêu giây?", ["360", "600", "3.600", "6.000"], 2),
    ("Nước nào có diện tích lớn nhất thế giới?", ["Canada", "Mỹ", "Trung Quốc", "Nga"], 3),
    ("Con vật nào lớn nhất đại dương?", ["Cá mập trắng", "Cá voi xanh", "Bạch tuộc", "Cá heo"], 1),
    ("Vịnh Hạ Long thuộc tỉnh nào?", ["Hải Phòng", "Quảng Ninh", "Nam Định", "Thanh Hóa"], 1),
    ("Ai là tác giả 'Truyện Kiều'?", ["Hồ Xuân Hương", "Nguyễn Du", "Nguyễn Trãi", "Tú Xương"], 1),
    ("Ngôn ngữ lập trình nào có logo con rắn?", ["Java", "Python", "Ruby", "Go"], 1),
    ("Kim loại nào lỏng ở nhiệt độ phòng?", ["Thủy ngân", "Chì", "Nhôm", "Sắt"], 0),
    ("Sông nào dài nhất thế giới?", ["Mekong", "Amazon", "Nile", "Trường Giang"], 2),
    ("Trái Đất quay quanh Mặt Trời hết bao lâu?", ["24 giờ", "1 tháng", "365 ngày", "10 năm"], 2),
    ("Việt Nam có bao nhiêu tỉnh thành trước 2025?", ["58", "61", "63", "65"], 2),
    ("Món phở nổi tiếng nhất của nước nào?", ["Thái Lan", "Việt Nam", "Hàn Quốc", "Nhật Bản"], 1),
    ("Màu nào không có trong cầu vồng?", ["Đỏ", "Lục", "Nâu", "Tím"], 2),
    ("Ai phát minh ra bóng đèn sợi đốt phổ biến?", ["Newton", "Edison", "Tesla", "Einstein"], 1),
    ("Đơn vị đo lực là gì?", ["Newton", "Joule", "Watt", "Pascal"], 0),
    ("Một đội bóng đá có mấy cầu thủ trên sân?", ["9", "10", "11", "12"], 2),
    ("Loài chim nào không biết bay?", ["Đại bàng", "Chim cánh cụt", "Bồ câu", "Én"], 1),
    ("Nước đóng băng ở bao nhiêu độ C?", ["-10", "0", "10", "100"], 1),
    ("Thành phố nào được gọi là 'thành phố ngàn hoa'?", ["Đà Lạt", "Sa Pa", "Vũng Tàu", "Cần Thơ"], 0),
    ("Ngày Quốc khánh Việt Nam là ngày nào?", ["30/4", "1/5", "2/9", "10/3"], 2),
    (
        "HTML là viết tắt của gì?",
        [
            "HyperText Markup Language",
            "High Tech Modern Language",
            "Home Tool Markup Language",
            "Hyperlink Text Mode Language",
        ],
        0,
    ),
    ("Loài vật nào ngủ đông?", ["Gấu", "Sư tử", "Ngựa", "Hươu"], 0),
    ("Đại dương lớn nhất là gì?", ["Đại Tây Dương", "Ấn Độ Dương", "Thái Bình Dương", "Bắc Băng Dương"], 2),
]


class AnswerView(discord.ui.View):
    def __init__(self, players: list[discord.Member], timeout: float) -> None:
        super().__init__(timeout=timeout)
        self.players = players
        self.answers: dict[int, tuple[int, float]] = {}
        for i in range(4):
            self.add_item(AnswerButton(i))


class AnswerButton(discord.ui.Button):
    def __init__(self, index: int) -> None:
        super().__init__(label=LETTERS[index], emoji=LETTER_EMOJI[index], style=discord.ButtonStyle.primary)
        self.index = index

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        assert isinstance(view, AnswerView)
        if not any(p.id == interaction.user.id for p in view.players):
            await interaction.response.send_message("❌ Bạn không ở trong ván này.", ephemeral=True)
            return
        if interaction.user.id in view.answers:
            await interaction.response.send_message("❌ Bạn đã trả lời rồi.", ephemeral=True)
            return
        view.answers[interaction.user.id] = (self.index, time.time())
        await interaction.response.send_message(f"✅ Đã chọn **{LETTERS[self.index]}**.", ephemeral=True)
        if len(view.answers) >= len(view.players):
            view.stop()


class QuizGame(BaseGame):
    key = "quiz"

    async def play(self) -> None:
        scores: dict[int, int] = {p.id: 0 for p in self.players}
        questions = random.sample(QUESTIONS, min(QUESTION_COUNT, len(QUESTIONS)))

        for idx, (question, options, correct) in enumerate(questions, start=1):
            special = ""
            if idx % 3 == 0:
                special = random.choice(["x2", "cuop"])
            header = f"🧠 **CÂU {idx}/{len(questions)}**"
            if special == "x2":
                header += "\n💀 **CÂU X2** — đúng +200, sai -100!"
            elif special == "cuop":
                header += "\n🎯 **CÂU CƯỚP ĐIỂM** — ai đúng nhanh nhất cướp 100 điểm của người dẫn đầu!"
            body = "\n".join(f"{LETTER_EMOJI[i]} {LETTERS[i]}. {o}" for i, o in enumerate(options))
            view = AnswerView(self.players, timeout=ANSWER_SECONDS)
            msg = await self.send(f"{header}\n{question}\n{body}\n⏱️ {ANSWER_SECONDS} giây!", view=view)
            await view.wait()
            await msg.edit(view=None)

            correct_players = sorted(
                [(uid, t) for uid, (ans, t) in view.answers.items() if ans == correct],
                key=lambda x: x[1],
            )
            fastest = correct_players[0][0] if correct_players else None
            lines = []
            for p in self.players:
                answer = view.answers.get(p.id)
                if answer is None:
                    lines.append(f"⏰ {p.display_name}: không trả lời")
                    continue
                if answer[0] == correct:
                    gain = 200 if special == "x2" else 100
                    if p.id == fastest:
                        gain += 50
                    scores[p.id] += gain
                    lines.append(f"✅ {p.display_name}: +{gain}")
                else:
                    loss = -100 if special == "x2" else 0
                    scores[p.id] += loss
                    lines.append(f"❌ {p.display_name}: {loss:+d}")

            steal_line = ""
            if special == "cuop" and fastest is not None:
                leader = max(scores, key=lambda uid: scores[uid])
                if leader != fastest:
                    scores[leader] -= 100
                    scores[fastest] += 100
                    lname = self.guild.get_member(leader)
                    fname = self.guild.get_member(fastest)
                    steal_line = (
                        f"\n🏴‍☠️ {fname.display_name if fname else leader} cướp 100 điểm của "
                        f"{lname.display_name if lname else leader}!"
                    )

            board = " • ".join(
                f"{p.display_name}: {scores[p.id]}"
                for p in sorted(self.players, key=lambda x: scores[x.id], reverse=True)
            )
            await self.send(
                f"✅ Đáp án đúng: **{LETTERS[correct]}. {options[correct]}**\n"
                + "\n".join(lines)
                + steal_line
                + f"\n📊 {board}"
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
        await self.send(f"🏆 **BẢNG XẾP HẠNG QUIZ**\n{board}\n\n💰 **Thưởng**\n{prize}")
