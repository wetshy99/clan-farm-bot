"""Lệnh /farm — toàn bộ hệ thống nông trại nằm trong 1 lệnh duy nhất."""

from __future__ import annotations

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from ..config import (
    ALARM_PRICE,
    CROPS,
    DOGS,
    HELP_REWARD,
    MAX_HELPS_PER_DAY,
    MAX_PLOT_LEVEL,
    MAX_STEALS_PER_DAY,
    MAX_TIMES_STOLEN_PER_DAY,
    PLOT_LEVELS,
    SECURITY_DAYS,
    SECURITY_DETECT,
    SECURITY_PRICE,
    STEAL_PENALTY,
    STEAL_RATIO,
    TRAP_CHANCE,
    TRAP_FINE,
    TRAP_PRICE,
    WATER_BONUS_SECONDS,
    fmt,
)
from ..db import Database
from ..utils import farm_embed, remaining


class PlantModal(discord.ui.Modal):
    def __init__(self, db: Database, crop_key: str, free_slots: int) -> None:
        crop = CROPS[crop_key]
        super().__init__(title=f"Trồng {crop.name}")
        self.db = db
        self.crop_key = crop_key
        self.free_slots = free_slots
        self.qty: discord.ui.TextInput = discord.ui.TextInput(
            label=f"Số lượng (còn {free_slots} ô trống)",
            placeholder="1",
            default="1",
            max_length=3,
            required=True,
        )
        self.add_item(self.qty)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        crop = CROPS[self.crop_key]
        try:
            qty = int(str(self.qty.value).strip())
        except ValueError:
            await interaction.response.send_message("❌ Số lượng không hợp lệ.", ephemeral=True)
            return
        if qty < 1:
            await interaction.response.send_message("❌ Số lượng phải ≥ 1.", ephemeral=True)
            return
        if qty > self.free_slots:
            await interaction.response.send_message(
                f"❌ Chỉ còn {self.free_slots} ô đất trống.", ephemeral=True
            )
            return
        cost = crop.seed_price * qty
        gid, uid = interaction.guild.id, interaction.user.id
        if self.db.coins(gid, uid) < cost:
            await interaction.response.send_message(
                f"❌ Không đủ tiền! Cần {fmt(cost)} 🪙.", ephemeral=True
            )
            return
        self.db.add_coins(gid, uid, -cost)
        ready = int(time.time()) + crop.grow_seconds
        for _ in range(qty):
            self.db.plant(gid, uid, self.crop_key, ready)
        await interaction.response.send_message(
            f"🌱 Đã trồng {crop.emoji} **{crop.name} ×{qty}** — mất {fmt(cost)} 🪙\n"
            f"⏳ Chín sau {remaining(crop.grow_seconds)} (tưới cây để nhanh hơn).",
            ephemeral=True,
        )


class PlantSelect(discord.ui.Select):
    def __init__(self, db: Database, free_slots: int) -> None:
        self.db = db
        self.free_slots = free_slots
        options = [
            discord.SelectOption(
                label=f"{c.name} — {fmt(c.seed_price)} 🪙",
                value=c.key,
                emoji=c.emoji,
                description=f"Lớn sau {remaining(c.grow_seconds)} • bán {fmt(c.sell_price)} 🪙",
            )
            for c in CROPS.values()
        ]
        super().__init__(placeholder="Chọn loại hạt giống...", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(
            PlantModal(self.db, self.values[0], self.free_slots)
        )


class ShopSelect(discord.ui.Select):
    """Mua bảo vệ."""

    def __init__(self, db: Database) -> None:
        self.db = db
        options = [
            discord.SelectOption(
                label=f"Chuông báo động — {fmt(ALARM_PRICE)} 🪙",
                value="alarm",
                emoji="🔔",
                description="Báo cho bạn khi có người cố trộm",
            ),
            discord.SelectOption(
                label=f"Bẫy — {fmt(TRAP_PRICE)} 🪙",
                value="trap",
                emoji="🪤",
                description=f"{int(TRAP_CHANCE * 100)}% bắt trộm, dùng 1 lần",
            ),
        ]
        options += [
            discord.SelectOption(
                label=f"{d.name} — {fmt(d.price)} 🪙",
                value=f"dog{d.tier}",
                emoji=d.emoji,
                description=f"Phát hiện {int(d.detect * 100)}% • {d.days} ngày",
            )
            for d in DOGS.values()
        ]
        options.append(
            discord.SelectOption(
                label=f"Hệ thống an ninh — {fmt(SECURITY_PRICE)} 🪙",
                value="security",
                emoji="🏰",
                description=f"{int(SECURITY_DETECT * 100)}% chống trộm • {SECURITY_DAYS} ngày",
            )
        )
        super().__init__(placeholder="Chọn món bảo vệ muốn mua...", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        gid, uid = interaction.guild.id, interaction.user.id
        choice = self.values[0]
        now = int(time.time())
        pr = self.db.protection(gid, uid)

        if choice == "alarm":
            price, ok_msg = ALARM_PRICE, "🔔 Đã lắp **Chuông báo động**!"
            if pr["alarm"]:
                await interaction.response.send_message("❌ Bạn đã có chuông rồi.", ephemeral=True)
                return
        elif choice == "trap":
            price, ok_msg = TRAP_PRICE, "🪤 Đã đặt **Bẫy** (dùng 1 lần)!"
            if pr["trap"]:
                await interaction.response.send_message(
                    "❌ Bẫy của bạn vẫn còn hiệu lực.", ephemeral=True
                )
                return
        elif choice == "security":
            if pr["dog_tier"] and pr["dog_expires"] > now:
                await interaction.response.send_message(
                    "❌ Hệ thống an ninh không cộng dồn với chó canh. "
                    "Chờ chó hết hạn hoặc chọn 1 trong 2.",
                    ephemeral=True,
                )
                return
            price = SECURITY_PRICE
            ok_msg = f"🏰 Đã kích hoạt **Hệ thống an ninh** trong {SECURITY_DAYS} ngày!"
        else:
            dog = DOGS[int(choice.removeprefix("dog"))]
            if pr["security_expires"] > now:
                await interaction.response.send_message(
                    "❌ Bạn đang dùng hệ thống an ninh, không nuôi chó cùng lúc được.",
                    ephemeral=True,
                )
                return
            price = dog.price
            ok_msg = f"{dog.emoji} Đã mua **{dog.name}** ({int(dog.detect * 100)}%) — {dog.days} ngày!"

        if self.db.coins(gid, uid) < price:
            await interaction.response.send_message(
                f"❌ Không đủ tiền! Cần {fmt(price)} 🪙.", ephemeral=True
            )
            return
        self.db.add_coins(gid, uid, -price)
        if choice == "alarm":
            self.db.set_protection(gid, uid, "alarm", 1)
        elif choice == "trap":
            self.db.set_protection(gid, uid, "trap", 1)
        elif choice == "security":
            self.db.set_protection(gid, uid, "security_expires", now + SECURITY_DAYS * 86400)
        else:
            tier = int(choice.removeprefix("dog"))
            self.db.set_protection(gid, uid, "dog_tier", tier)
            self.db.set_protection(gid, uid, "dog_expires", now + DOGS[tier].days * 86400)
        await interaction.response.send_message(ok_msg, ephemeral=True)


class TargetSelect(discord.ui.UserSelect):
    def __init__(self, action: str, cog: FarmCog) -> None:
        self.action = action
        self.cog = cog
        super().__init__(
            placeholder="Chọn thành viên..." if action == "water" else "Chọn mục tiêu để trộm...",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        target = self.values[0]
        if not isinstance(target, discord.Member):
            await interaction.response.send_message("❌ Người chơi không hợp lệ.", ephemeral=True)
            return
        if self.action == "water":
            await self.cog.do_water(interaction, target)
        else:
            await self.cog.do_steal(interaction, target)


class EphemeralView(discord.ui.View):
    def __init__(self, item: discord.ui.Item) -> None:
        super().__init__(timeout=120)
        self.add_item(item)


class FarmView(discord.ui.View):
    def __init__(self, cog: FarmCog, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "❌ Đây là bảng nông trại của người khác. Gõ `/farm` để mở của bạn.",
                ephemeral=True,
            )
            return False
        return True

    async def refresh(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        await interaction.message.edit(  # type: ignore[union-attr]
            embed=farm_embed(self.cog.db, interaction.guild, interaction.user), view=self
        )

    @discord.ui.button(label="Trồng", emoji="🌱", style=discord.ButtonStyle.success, row=0)
    async def plant(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        assert interaction.guild is not None
        db = self.cog.db
        gid, uid = interaction.guild.id, interaction.user.id
        free = db.plot_count(gid, uid) - len(db.plants(gid, uid))
        if free <= 0:
            await interaction.response.send_message(
                "❌ Hết ô đất trống! Thu hoạch hoặc nâng cấp đất đã.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "🌱 Chọn hạt giống muốn trồng:",
            view=EphemeralView(PlantSelect(db, free)),
            ephemeral=True,
        )

    @discord.ui.button(label="Tưới / Giúp", emoji="💧", style=discord.ButtonStyle.primary, row=0)
    async def water(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_message(
            f"💧 Chọn người muốn giúp (tối đa {MAX_HELPS_PER_DAY} lượt/ngày):",
            view=EphemeralView(TargetSelect("water", self.cog)),
            ephemeral=True,
        )

    @discord.ui.button(label="Thu hoạch", emoji="🌾", style=discord.ButtonStyle.success, row=0)
    async def harvest(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        assert interaction.guild is not None
        db = self.cog.db
        gid, uid = interaction.guild.id, interaction.user.id
        now = int(time.time())
        plants = db.plants(gid, uid)
        ready = [p for p in plants if p["ready_at"] <= now]
        if not ready:
            if plants:
                nxt = min(plants, key=lambda p: p["ready_at"])
                crop = CROPS[nxt["crop"]]
                msg = (
                    "⏳ Cây chưa trưởng thành!\n"
                    f"{crop.emoji} {crop.name} còn {remaining(nxt['ready_at'] - now)}."
                )
            else:
                msg = "🟫 Nông trại trống trơn, trồng cây đi đã!"
            await interaction.response.send_message(msg, ephemeral=True)
            return
        counts: dict[str, int] = {}
        for p in ready:
            counts[p["crop"]] = counts.get(p["crop"], 0) + 1
            db.remove_plant(int(p["id"]))
            db.add_item(gid, uid, p["crop"], 1)
        db.bump(gid, uid, "harvested", len(ready))
        lines = "\n".join(
            f"{CROPS[c].emoji} {CROPS[c].name} ×{n} (≈ {fmt(CROPS[c].sell_price * n)} 🪙)"
            for c, n in counts.items()
        )
        await interaction.response.send_message(
            f"🌾 **THU HOẠCH THÀNH CÔNG!**\n{lines}\n📦 Nông sản đã vào kho — bấm 💰 Bán để lấy tiền.",
            ephemeral=True,
        )
        await self.refresh(interaction)

    @discord.ui.button(label="Bán", emoji="💰", style=discord.ButtonStyle.secondary, row=0)
    async def sell(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        assert interaction.guild is not None
        db = self.cog.db
        gid, uid = interaction.guild.id, interaction.user.id
        gain, to_clan, inv = db.sell_all(gid, uid)
        if gain <= 0:
            await interaction.response.send_message("📦 Kho trống, không có gì để bán.", ephemeral=True)
            return
        detail = " • ".join(f"{CROPS[c].emoji} ×{q}" for c, q in inv.items() if c in CROPS)
        await interaction.response.send_message(
            f"💰 **ĐÃ BÁN**: {detail}\n"
            f"👤 Bạn nhận: {fmt(gain)} 🪙\n🏦 Quỹ Clan: +{fmt(to_clan)} 🪙",
            ephemeral=True,
        )
        await self.refresh(interaction)

    @discord.ui.button(label="Shop", emoji="🛒", style=discord.ButtonStyle.secondary, row=1)
    async def shop(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        embed = discord.Embed(title="🛒 CỬA HÀNG HẠT GIỐNG", color=0xFEE75C)
        for c in CROPS.values():
            embed.add_field(
                name=f"{c.emoji} {c.name}",
                value=(
                    f"Hạt: {fmt(c.seed_price)} 🪙\n"
                    f"Lớn: {remaining(c.grow_seconds)}\n"
                    f"Bán: {fmt(c.sell_price)} 🪙"
                ),
                inline=True,
            )
        embed.set_footer(text="Bán nông sản trích 10% vào quỹ Clan • Bấm 🌱 Trồng để mua hạt")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Bảo vệ", emoji="🛡️", style=discord.ButtonStyle.primary, row=1)
    async def defense(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_message(
            "🛡️ Mua bảo vệ cho nông trại:",
            view=EphemeralView(ShopSelect(self.cog.db)),
            ephemeral=True,
        )

    @discord.ui.button(label="Nâng cấp đất", emoji="⬆️", style=discord.ButtonStyle.success, row=1)
    async def upgrade(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        assert interaction.guild is not None
        db = self.cog.db
        gid, uid = interaction.guild.id, interaction.user.id
        level = int(db.get_player(gid, uid)["plot_level"])
        if level >= MAX_PLOT_LEVEL:
            await interaction.response.send_message(
                "💎 Nông trại của bạn đã đạt cấp tối đa (35 ô)!", ephemeral=True
            )
            return
        plots, price = PLOT_LEVELS[level + 1]
        if db.coins(gid, uid) < price:
            await interaction.response.send_message(
                f"❌ Nâng lên Lv.{level + 1} ({plots} ô) cần {fmt(price)} 🪙 — "
                f"bạn mới có {fmt(db.coins(gid, uid))} 🪙.",
                ephemeral=True,
            )
            return
        db.add_coins(gid, uid, -price)
        db.set_plot_level(gid, uid, level + 1)
        await interaction.response.send_message(
            f"🎉 Nâng cấp thành công! Nông trại lên **Lv.{level + 1}** — {plots} ô đất.",
            ephemeral=True,
        )
        await self.refresh(interaction)

    @discord.ui.button(label="Trộm", emoji="🥷", style=discord.ButtonStyle.danger, row=1)
    async def steal(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.send_message(
            f"🥷 Chọn nông trại muốn đột nhập (tối đa {MAX_STEALS_PER_DAY} lần/ngày):",
            view=EphemeralView(TargetSelect("steal", self.cog)),
            ephemeral=True,
        )

    @discord.ui.button(label="BXH", emoji="🏆", style=discord.ButtonStyle.secondary, row=2)
    async def top(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        assert interaction.guild is not None
        db = self.cog.db
        gid = interaction.guild.id
        embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG CLAN", color=0xEB459E)
        boards = [
            ("💰 Giàu nhất", "coins", "🪙"),
            ("🌱 Nông dân chăm chỉ", "harvested", "cây"),
            ("🤝 Người hỗ trợ", "helped", "lượt"),
            ("🥷 Đạo chích", "steals", "phi vụ"),
        ]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for title, field, unit in boards:
            rows = [r for r in db.top(gid, field, 5) if r["value"] > 0]
            if not rows:
                embed.add_field(name=title, value="_Chưa có ai_", inline=False)
                continue
            lines = []
            for i, r in enumerate(rows):
                member = interaction.guild.get_member(int(r["user_id"]))
                name = member.display_name if member else f"<@{r['user_id']}>"
                lines.append(f"{medals[i]} {name} — {fmt(r['value'])} {unit}")
            embed.add_field(name=title, value="\n".join(lines), inline=False)
        embed.add_field(name="🏦 Quỹ Clan", value=f"{fmt(db.fund(gid))} 🪙", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Làm mới", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_button(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        await interaction.response.edit_message(
            embed=farm_embed(self.cog.db, interaction.guild, interaction.user), view=self
        )


class FarmCog(commands.Cog):
    def __init__(self, bot: commands.Bot, db: Database) -> None:
        self.bot = bot
        self.db = db

    # ---------- hành động cần mục tiêu ----------
    async def do_water(self, interaction: discord.Interaction, target: discord.Member) -> None:
        assert interaction.guild is not None
        db = self.db
        gid, uid = interaction.guild.id, interaction.user.id
        counters = db.counters(gid, uid)
        if target.bot:
            await interaction.response.send_message("❌ Bot không có nông trại.", ephemeral=True)
            return
        if int(counters["helps"]) >= MAX_HELPS_PER_DAY and target.id != uid:
            await interaction.response.send_message(
                f"❌ Bạn đã dùng hết {MAX_HELPS_PER_DAY} lượt giúp hôm nay.", ephemeral=True
            )
            return
        now = int(time.time())
        plants = [
            p for p in db.plants(gid, target.id) if not p["watered"] and p["ready_at"] > now
        ]
        if not plants:
            await interaction.response.send_message(
                f"❌ {target.display_name} không có cây nào cần tưới.", ephemeral=True
            )
            return
        plant = plants[0]
        crop = CROPS[plant["crop"]]
        db.water_plant(int(plant["id"]), WATER_BONUS_SECONDS)

        if target.id == uid:
            await interaction.response.send_message(
                f"💧 Bạn đã tự tưới {crop.emoji} **{crop.name}** — giảm 3 phút thời gian sinh trưởng.",
                ephemeral=True,
            )
            return

        extra = random.choice(["water", "boost", "coin"])
        bonus_text = ""
        if extra == "boost":
            db.water_plant(int(plant["id"]), WATER_BONUS_SECONDS)
            bonus_text = "\n🌱 Bón thêm phân: giảm thêm 3 phút!"
        elif extra == "coin":
            gift = random.randint(50, 200)
            db.add_coins(gid, target.id, gift)
            bonus_text = f"\n🪙 Bạn tặng thêm {fmt(gift)} 🪙 cho {target.display_name}."

        db.add_coins(gid, uid, HELP_REWARD)
        db.bump(gid, uid, "helped")
        db.bump_counter(gid, uid, "helps")
        left = MAX_HELPS_PER_DAY - int(db.counters(gid, uid)["helps"])
        await interaction.response.send_message(
            f"💧 **{interaction.user.display_name} đã tưới cây cho {target.display_name}!**\n"
            f"{crop.emoji} {crop.name} được giảm 3 phút thời gian sinh trưởng.{bonus_text}\n"
            f"🤝 Bạn nhận {fmt(HELP_REWARD)} 🪙 tiền hỗ trợ. (còn {left} lượt hôm nay)",
            ephemeral=False,
        )

    async def do_steal(self, interaction: discord.Interaction, target: discord.Member) -> None:
        assert interaction.guild is not None
        db = self.db
        gid, uid = interaction.guild.id, interaction.user.id
        now = int(time.time())

        if target.id == uid:
            await interaction.response.send_message("❌ Không thể trộm chính mình.", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("❌ Bot không có nông trại.", ephemeral=True)
            return
        c = db.counters(gid, uid)
        if int(c["steals"]) >= MAX_STEALS_PER_DAY:
            await interaction.response.send_message(
                f"❌ Hết lượt trộm hôm nay ({MAX_STEALS_PER_DAY}/ngày).", ephemeral=True
            )
            return
        if int(c["last_target"]) == target.id:
            await interaction.response.send_message(
                "❌ Không thể trộm cùng một người liên tiếp.", ephemeral=True
            )
            return
        tc = db.counters(gid, target.id)
        if int(tc["times_stolen"]) >= MAX_TIMES_STOLEN_PER_DAY:
            await interaction.response.send_message(
                f"🛑 {target.display_name} đã bị trộm hôm nay rồi, tha cho người ta.", ephemeral=True
            )
            return
        ready = [p for p in db.plants(gid, target.id) if p["ready_at"] <= now]
        if not ready:
            await interaction.response.send_message(
                f"❌ {target.display_name} không có cây trưởng thành để trộm.", ephemeral=True
            )
            return

        db.bump_counter(gid, uid, "steals")
        db.set_last_target(gid, uid, target.id)
        pr = db.protection(gid, target.id)

        # chuông báo động
        if pr["alarm"]:
            try:
                await target.send(
                    f"🔔 **BÁO ĐỘNG!**\n🥷 {interaction.user.display_name} "
                    f"vừa cố đột nhập nông trại của bạn tại **{interaction.guild.name}**!"
                )
            except discord.HTTPException:
                pass

        # an ninh / chó canh
        detect = 0.0
        guard = ""
        if pr["security_expires"] > now:
            detect, guard = SECURITY_DETECT, "🏰 Hệ thống an ninh"
        elif pr["dog_tier"] and pr["dog_expires"] > now:
            dog = DOGS[int(pr["dog_tier"])]
            detect, guard = dog.detect, f"{dog.emoji} {dog.name}"

        if detect and random.random() < detect:
            fine = STEAL_PENALTY
            db.add_coins(gid, uid, -fine)
            db.add_fund(gid, fine // 2)
            await interaction.response.send_message(
                f"🚨 **BỊ BẮT!**\n🥷 {interaction.user.mention} cố trộm nông trại của "
                f"{target.mention} nhưng bị phát hiện!\n{guard} đã bắt được kẻ trộm.\n"
                f"💸 Bị phạt {fmt(fine)} 🪙 (một nửa vào 🏦 quỹ Clan).",
                ephemeral=False,
            )
            return

        # bẫy
        if pr["trap"]:
            db.set_protection(gid, target.id, "trap", 0)
            if random.random() < TRAP_CHANCE:
                db.add_coins(gid, uid, -TRAP_FINE)
                db.add_coins(gid, target.id, TRAP_FINE // 2)
                db.add_fund(gid, TRAP_FINE // 2)
                await interaction.response.send_message(
                    f"🪤 **BẪY ĐÃ KÍCH HOẠT!**\n{interaction.user.mention} bị bắt khi cố trộm "
                    f"nông trại của {target.mention}.\n💸 Mất {fmt(TRAP_FINE)} 🪙.",
                    ephemeral=False,
                )
                return

        # trộm thành công
        stolen = random.choice(ready)
        crop = CROPS[stolen["crop"]]
        loot = int(crop.sell_price * STEAL_RATIO)
        db.remove_plant(int(stolen["id"]))
        db.add_coins(gid, uid, loot)
        db.add_coins(gid, target.id, -loot)
        db.bump(gid, uid, "steals")
        db.bump_counter(gid, target.id, "times_stolen")
        await interaction.response.send_message(
            f"🚨 **ĐỘT NHẬP THÀNH CÔNG!**\n"
            f"🥷 {interaction.user.mention} đã lẻn vào nông trại của {target.mention}.\n"
            f"{crop.emoji} Lấy trộm 1 {crop.name}\n"
            f"💰 Nhận: {fmt(loot)} 🪙\n😡 {target.display_name} mất: {fmt(loot)} 🪙",
            ephemeral=False,
        )

    @app_commands.guild_only()
    @app_commands.command(name="farm", description="🌾 Mở nông trại Clan của bạn")
    async def farm(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None and isinstance(interaction.user, discord.Member)
        self.db.get_player(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            embed=farm_embed(self.db, interaction.guild, interaction.user),
            view=FarmView(self, interaction.user.id),
        )


async def setup(bot: commands.Bot) -> None:  # pragma: no cover - discord entrypoint
    await bot.add_cog(FarmCog(bot, bot.db))  # type: ignore[attr-defined]
