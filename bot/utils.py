"""Tiện ích chung."""

from __future__ import annotations

import time

import discord

from .config import CROPS, DOGS, LEVEL_EMOJI, PLOT_LEVELS, fmt
from .db import Database


def remaining(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} giờ {minutes} phút"
    if minutes:
        return f"{minutes} phút {sec} giây"
    return f"{sec} giây"


def plot_display(db: Database, guild_id: int, user_id: int) -> str:
    now = int(time.time())
    plants = db.plants(guild_id, user_id)
    total = PLOT_LEVELS[int(db.get_player(guild_id, user_id)["plot_level"])][0]
    cells: list[str] = []
    for p in plants[:total]:
        crop = CROPS[p["crop"]]
        cells.append(crop.emoji if p["ready_at"] <= now else f"{crop.emoji}⏳")
    cells += ["🟫"] * (total - len(cells))
    return " ".join(cells)


def protection_display(db: Database, guild_id: int, user_id: int) -> str:
    now = int(time.time())
    pr = db.protection(guild_id, user_id)
    parts: list[str] = []
    if pr["alarm"]:
        parts.append("🔔 Chuông")
    if pr["trap"]:
        parts.append("🪤 Bẫy")
    if pr["dog_tier"] and pr["dog_expires"] > now:
        dog = DOGS[int(pr["dog_tier"])]
        parts.append(f"{dog.emoji} {dog.name} ({remaining(pr['dog_expires'] - now)})")
    if pr["security_expires"] > now:
        parts.append(f"🏰 An ninh ({remaining(pr['security_expires'] - now)})")
    return " • ".join(parts) if parts else "Không có 😶"


def farm_embed(db: Database, guild: discord.Guild, member: discord.Member) -> discord.Embed:
    now = int(time.time())
    p = db.get_player(guild.id, member.id)
    level = int(p["plot_level"])
    plots, _ = PLOT_LEVELS[level]
    plants = db.plants(guild.id, member.id)
    ready = sum(1 for pl in plants if pl["ready_at"] <= now)

    embed = discord.Embed(
        title=f"🌾 NÔNG TRẠI CỦA {member.display_name.upper()}",
        color=0x57F287,
    )
    embed.add_field(
        name=f"{LEVEL_EMOJI[level]} Đất Lv.{level} — {len(plants)}/{plots} ô",
        value=plot_display(db, guild.id, member.id),
        inline=False,
    )
    if plants:
        lines = []
        for pl in plants[:10]:
            crop = CROPS[pl["crop"]]
            if pl["ready_at"] <= now:
                lines.append(f"{crop.emoji} {crop.name} — ✅ sẵn sàng thu hoạch")
            else:
                water = "" if pl["watered"] else " (chưa tưới 💧)"
                lines.append(
                    f"{crop.emoji} {crop.name} — còn {remaining(pl['ready_at'] - now)}{water}"
                )
        embed.add_field(name="🌱 Cây đang trồng", value="\n".join(lines), inline=False)

    inv = db.inventory(guild.id, member.id)
    if inv:
        value = " • ".join(f"{CROPS[c].emoji} ×{q}" for c, q in inv.items() if c in CROPS)
        total = sum(CROPS[c].sell_price * q for c, q in inv.items() if c in CROPS)
        embed.add_field(name=f"📦 Kho (≈ {fmt(total)} 🪙)", value=value, inline=False)

    embed.add_field(name="💰 Tiền", value=f"{fmt(p['coins'])} 🪙", inline=True)
    embed.add_field(name="🏦 Quỹ Clan", value=f"{fmt(db.fund(guild.id))} 🪙", inline=True)
    embed.add_field(name="🌾 Sẵn sàng", value=f"{ready} cây", inline=True)
    embed.add_field(
        name="🛡️ Bảo vệ", value=protection_display(db, guild.id, member.id), inline=False
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Dùng các nút bên dưới để chơi • /thongtin • /diemdanh")
    return embed
