# 🌾 Clan Farm Bot

Bot Discord nông trại + minigame cho Clan, **chỉ dùng 4 lệnh**:

| Lệnh | Chức năng |
|---|---|
| `/farm` | Toàn bộ hệ thống nông trại (trồng, tưới, thu hoạch, bán, shop, bảo vệ, nâng cấp đất, trộm, BXH) — thao tác bằng nút bấm |
| `/game` | Sảnh 9 minigame, mở phòng và chơi bằng nút bấm |
| `/thongtin` | Hồ sơ người chơi (tiền, farm, thống kê, lượt còn lại trong ngày) |
| `/diemdanh` | Điểm danh nhận xu mỗi ngày, có chuỗi ngày liên tiếp |

Mọi thao tác con đều nằm trong nút/menu của `/farm` và `/game`, không thêm slash command nào khác.

## 🌱 Nông trại

- Mỗi thành viên có khu đất riêng trong nông trại chung của Clan, bắt đầu Lv.1 = 3 ô, tối đa Lv.10 = 35 ô.
- 4 loại cây: 🥕 Cà rốt (500 → 800, 5 phút), 🍓 Dâu (2.000 → 3.500, 15 phút), 🌻 Hướng dương (5.000 → 9.000, 30 phút), 🌳 Cây đặc biệt (15.000 → 30.000, 1 giờ).
- Tưới cây giảm 3 phút; giúp người khác nhận 100 🪙, tối đa 5 lượt/ngày. Nút "Tưới / Giúp" có thể random tặng thêm phân bón hoặc chút tiền cho người được giúp.
- Bán nông sản trích **10% vào quỹ Clan**.
- Trộm: 2 lần/ngày, mỗi người chỉ bị trộm 1 lần/ngày, không trộm cùng người liên tiếp, lấy 50% giá trị cây.
- Bảo vệ: 🔔 Chuông 10.000 (DM cảnh báo), 🪤 Bẫy 25.000 (40%, 1 lần), 🐶🐕🐕‍🦺🐺 Chó 50k–500k (60–95%, 7 ngày), 🏰 An ninh 1.000.000 (95%, 30 ngày — không cộng dồn với chó).
- Trộm thất bại: phạt 5.000 🪙, một nửa vào quỹ Clan.
- BXH: 💰 giàu nhất, 🌱 nông dân chăm chỉ, 🤝 người hỗ trợ, 🥷 đạo chích.

## 🎮 Minigame (`/game`)

💣 Bom hẹn giờ • 🧠 Đấu quiz • 🚢 Tàu đắm • 🏝️ Đảo kho báu • 🎯 Bắn bóng • 🪙 Đồng xu may rủi • 🧟 Zombie Clan • 🏃 Đua sinh tồn • 🃏 Lật bài

Mỗi ván thu phí tham gia, **đốt 10% phí hệ thống** để tránh lạm phát, phần còn lại là jackpot chia theo thứ hạng (50/25/15) hoặc theo điểm tùy game. Zombie Clan là game đồng đội: thắng thì 30% vào quỹ Clan, còn lại chia đều + chia theo đóng góp.

Một kênh chỉ chạy 1 ván tại một thời điểm.

## ⚙️ Cài đặt

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # điền DISCORD_TOKEN (và GUILD_ID nếu muốn sync lệnh ngay)
.venv/bin/python -m bot
```

Bot chạy được với intent mặc định, chỉ cần quyền `applications.commands` + gửi tin nhắn trong kênh. Nếu muốn bảng xếp hạng hiện tên thay vì mention: bật **Server Members Intent** (Discord Developer Portal → Bot → Privileged Gateway Intents) rồi đặt `MEMBERS_INTENT=true` trong `.env`.

Dữ liệu lưu ở SQLite `data/clanfarm.db` (tự tạo). Người chơi mới nhận 20.000 🪙 vốn ban đầu.

## 🧪 Kiểm thử

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```
