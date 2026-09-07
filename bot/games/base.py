"""Khung chung cho minigame: phòng chờ, thu phí, chia thưởng."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import discord

from ..config import GAME_TAX, GAMES, LOBBY_SECONDS, fmt
from ..db import Database

MAX_BET = 1_000_000


def parse_bet_amount(raw: str, minimum: int) -> int:
    """Parse a Vietnamese-friendly bet amount such as ``10.000``."""
    value = raw.strip().replace(".", "").replace(",", "")
    amount = int(value)
    if amount < minimum or amount > MAX_BET:
        raise ValueError
    return amount


class BaseGame:
    """Lớp cơ sở cho một ván minigame."""

    key: str = ""

    def __init__(
        self,
        db: Database,
        channel: discord.abc.Messageable,
        guild: discord.Guild,
        players: list[discord.Member],
        fee: int,
    ) -> None:
        self.db = db
        self.channel = channel
        self.guild = guild
        self.players = players
        self.fee = fee
        self.pot = 0
        self.burn = 0

    # ---------- tiền ----------
    def collect_fees(self) -> None:
        total = self.fee * len(self.players)
        for p in self.players:
            self.db.add_coins(self.guild.id, p.id, -self.fee)
        self.burn = int(total * GAME_TAX)
        self.pot = total - self.burn

    def award(self, member: discord.Member, amount: int) -> None:
        self.db.add_coins(self.guild.id, member.id, amount)

    def declare_winner(self, member: discord.Member, amount: int) -> None:
        self.award(member, amount)
        self.db.bump(self.guild.id, member.id, "game_wins")

    def payout_ranking(self, ranking: Sequence[discord.Member]) -> list[tuple[discord.Member, int]]:
        """Chia jackpot 50/25/15 (+10% còn lại vào quỹ clan) theo thứ hạng."""
        shares = [0.5, 0.25, 0.15]
        results: list[tuple[discord.Member, int]] = []
        paid = 0
        for member, share in zip(ranking, shares, strict=False):
            amount = int(self.pot * share)
            paid += amount
            self.award(member, amount)
            results.append((member, amount))
        if ranking:
            self.db.bump(self.guild.id, ranking[0].id, "game_wins")
        rest = self.pot - paid
        if rest > 0:
            self.db.add_fund(self.guild.id, rest)
        return results

    async def play(self) -> None:  # pragma: no cover - override
        raise NotImplementedError

    # ---------- tiện ích ----------
    async def send(self, content: str | None = None, **kwargs) -> discord.Message:
        return await self.channel.send(content, **kwargs)

    def pot_line(self) -> str:
        return f"🏦 Jackpot: {fmt(self.pot)} 🪙 (đã đốt {fmt(self.burn)} 🪙 phí hệ thống)"


class Lobby(discord.ui.View):
    """Phòng chờ chung cho mọi minigame."""

    def __init__(
        self,
        db: Database,
        game_key: str,
        host: discord.Member,
        fee: int | None = None,
    ) -> None:
        super().__init__(timeout=LOBBY_SECONDS)
        self.db = db
        self.game_key = game_key
        self.host = host
        emoji, name, default_fee, minp, maxp = GAMES[game_key]
        self.emoji, self.name, self.min_fee, self.min_players, self.max_players = (
            emoji,
            name,
            default_fee,
            minp,
            maxp,
        )
        self.fee = fee if fee is not None else default_fee
        self.players: list[discord.Member] = [host]
        self.message: discord.Message | None = None
        self.started = asyncio.Event()
        self.cancelled = False

    def embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"{self.emoji} {self.name.upper()}",
            description=(
                f"💰 Phí tham gia: **{fmt(self.fee)}** 🪙\n"
                f"👥 Người chơi: **{len(self.players)}/{self.max_players}** "
                f"(cần tối thiểu {self.min_players})\n"
                f"🏦 Tổng cược: {fmt(self.fee * len(self.players))} 🪙\n"
                f"⏳ Phòng bắt đầu sau tối đa {LOBBY_SECONDS} giây..."
            ),
            color=0x5865F2,
        )
        embed.add_field(
            name="Danh sách",
            value="\n".join(f"• {p.display_name}" for p in self.players) or "_trống_",
        )
        embed.set_footer(text=f"Chủ phòng: {self.host.display_name}")
        return embed

    async def update(self) -> None:
        if self.message:
            await self.message.edit(embed=self.embed(), view=self)

    @discord.ui.button(label="Đặt cược", emoji="💰", style=discord.ButtonStyle.secondary)
    async def bet(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ Chỉ chủ phòng đổi cược được.", ephemeral=True)
            return
        if len(self.players) > 1:
            await interaction.response.send_message(
                "❌ Không thể đổi cược sau khi đã có người tham gia. Hủy phòng và tạo lại nhé.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(LobbyBetModal(self))

    @discord.ui.button(label="THAM GIA", emoji="🎮", style=discord.ButtonStyle.success)
    async def join(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        member = interaction.user
        assert isinstance(member, discord.Member)
        if member in self.players:
            await interaction.response.send_message("Bạn đã ở trong phòng rồi.", ephemeral=True)
            return
        if len(self.players) >= self.max_players:
            await interaction.response.send_message("❌ Phòng đã đầy.", ephemeral=True)
            return
        if self.db.coins(self.guild_id(interaction), member.id) < self.fee:
            await interaction.response.send_message(
                f"❌ Bạn cần {fmt(self.fee)} 🪙 để tham gia.", ephemeral=True
            )
            return
        self.players.append(member)
        await interaction.response.defer()
        await self.update()
        if len(self.players) >= self.max_players:
            self.started.set()
            self.stop()

    @discord.ui.button(label="Rời phòng", emoji="🚪", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        member = interaction.user
        assert isinstance(member, discord.Member)
        if member == self.host:
            await interaction.response.send_message(
                "Chủ phòng không rời được, dùng nút ❌ Hủy phòng.", ephemeral=True
            )
            return
        if member not in self.players:
            await interaction.response.send_message("Bạn chưa tham gia.", ephemeral=True)
            return
        self.players.remove(member)
        await interaction.response.defer()
        await self.update()

    @discord.ui.button(label="BẮT ĐẦU", emoji="▶️", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ Chỉ chủ phòng bắt đầu được.", ephemeral=True)
            return
        if len(self.players) < self.min_players:
            await interaction.response.send_message(
                f"❌ Cần tối thiểu {self.min_players} người.", ephemeral=True
            )
            return
        await interaction.response.defer()
        self.started.set()
        self.stop()

    @discord.ui.button(label="Hủy phòng", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.user.id != self.host.id:
            await interaction.response.send_message("❌ Chỉ chủ phòng hủy được.", ephemeral=True)
            return
        self.cancelled = True
        await interaction.response.defer()
        self.started.set()
        self.stop()

    @staticmethod
    def guild_id(interaction: discord.Interaction) -> int:
        assert interaction.guild is not None
        return interaction.guild.id


class LobbyBetModal(discord.ui.Modal):
    def __init__(self, lobby: Lobby) -> None:
        super().__init__(title="Đặt cược cho phòng")
        self.lobby = lobby
        self.amount: discord.ui.TextInput = discord.ui.TextInput(
            label=f"Mức cược (tối thiểu {fmt(lobby.min_fee)} 🪙)",
            placeholder="Ví dụ: 10.000",
            default=str(lobby.fee),
            max_length=10,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = parse_bet_amount(str(self.amount.value), self.lobby.min_fee)
        except (TypeError, ValueError):
            await interaction.response.send_message(
                f"❌ Cược phải từ {fmt(self.lobby.min_fee)} đến {fmt(MAX_BET)} 🪙.",
                ephemeral=True,
            )
            return
        if self.lobby.db.coins(self.lobby.guild_id(interaction), self.lobby.host.id) < amount:
            await interaction.response.send_message(
                f"❌ Chủ phòng cần {fmt(amount)} 🪙 để mở phòng.", ephemeral=True
            )
            return
        self.lobby.fee = amount
        await interaction.response.send_message(
            f"✅ Đã đặt cược **{fmt(amount)} 🪙** cho phòng.", ephemeral=True
        )
        await self.lobby.update()


class ChoiceView(discord.ui.View):
    """View thu thập lựa chọn của nhiều người chơi trong một vòng."""

    def __init__(self, players: list[discord.Member], timeout: float) -> None:
        super().__init__(timeout=timeout)
        self.players = players
        self.choices: dict[int, str] = {}

    def allowed(self, user: discord.abc.User) -> bool:
        return any(p.id == user.id for p in self.players)

    async def record(self, interaction: discord.Interaction, value: str, label: str) -> None:
        if not self.allowed(interaction.user):
            await interaction.response.send_message("❌ Bạn không ở trong ván này.", ephemeral=True)
            return
        self.choices[interaction.user.id] = value
        await interaction.response.send_message(f"✅ Bạn đã chọn **{label}**.", ephemeral=True)
        if len(self.choices) >= len(self.players):
            self.stop()


class ChoiceButton(discord.ui.Button):
    def __init__(self, value: str, label: str, emoji: str | None = None, row: int | None = None):
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.primary, row=row)
        self.value = value

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        assert isinstance(view, ChoiceView)
        await view.record(interaction, self.value, self.label or self.value)
