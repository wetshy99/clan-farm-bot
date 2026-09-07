# Chạy bot 24/7

## bot-hosting.net (free, không cần thẻ)

1. Vào https://bot-hosting.net → **Login with Discord** → nhận coins free hằng ngày.
2. **Create Server** → chọn loại **Python**.
3. Vào tab **Files** → upload thư mục `bot/` và file `requirements.txt` (hoặc upload zip rồi Unarchive).
4. Tab **Startup**:
   - App py file / Startup command: `python -m bot`
   - Additional packages (nếu có ô này): `discord.py python-dotenv`
   - Nếu panel không tự cài, mở tab **Console** chạy: `pip install -r requirements.txt`
5. Tab **Startup** hoặc **Variables** → thêm biến môi trường:
   - `DISCORD_TOKEN` = token bot
   - `GUILD_ID` = ID server (tuỳ chọn, sync lệnh nhanh hơn)
6. Bấm **Start**. Console hiện `Đăng nhập với tên ...` là chạy được.

Lưu ý: dữ liệu SQLite nằm ở `data/clanfarm.db` trên server đó — đừng xoá thư mục `data/`.

## Docker (VPS bất kỳ)

```bash
docker build -t clan-farm-bot .
docker run -d --restart=always \
  -e DISCORD_TOKEN=xxx \
  -v $PWD/data:/app/data \
  --name clan-farm-bot clan-farm-bot
```

## systemd (VPS Ubuntu, không dùng Docker)

```ini
# /etc/systemd/system/clan-farm-bot.service
[Unit]
Description=Clan Farm Bot
After=network.target

[Service]
WorkingDirectory=/opt/clan-farm-bot
Environment=DISCORD_TOKEN=xxx
ExecStart=/opt/clan-farm-bot/.venv/bin/python -m bot
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now clan-farm-bot
```

## Fly.io

```bash
fly launch --no-deploy   # dùng fly.toml sẵn có
fly volumes create clanfarm_data --size 1
fly secrets set DISCORD_TOKEN=xxx
fly deploy
```
