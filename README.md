# Telegram 廣播機器人 (含自動備份)

本專案是一套基於 Python 的 Telegram 使用者機器人，支援多群組/頻道廣播、定時排程、管理員權限、文案管理、自動本地備份等功能，適合社群經營、公告推播、行銷等多種用途。

---

## 主要功能
- 支援多群組/頻道自動廣播
- 多時段定時排程
- 管理員權限控管
- 文案多檔管理、預覽、測試
- 廣播歷史查詢、狀態查詢
- 本地自動備份所有設定檔
- 完整指令操作說明，適合新手

---

## 安裝與啟動
1. 下載或 clone 專案：
   ```bash
   git clone https://github.com/godmakereth/RG_Tai_Telegram_User_bot.git
   cd RG_Tai_Telegram_User_bot
   ```
2. 安裝依賴：
   ```bash
   pip install -r requirements.txt
   ```
3. 複製 `.env.example` 為 `.env`，填入 Telegram API 資訊。
4. 執行 `start.bat` 或 `python main.py` 啟動機器人。
5. 首次啟動會要求登入 Telegram 帳號，依指示完成。

---

## 常用指令
- `/add`：將當前群組加入廣播清單
- `/add_by_id <ID>`：透過 ID 加入群組
- `/list`：查看所有廣播群組
- `/remove <編號>`：移除指定群組
- `/my_groups`：快速查看所在群組
- `/time HH:MM`：新增每日廣播時間
- `/time remove HH:MM`：移除指定時間
- `/time clear`：清除所有時間
- `/enable` / `/disable`：啟用/停用排程
- `/files`：列出所有文案檔
- `/preview [檔名]`：預覽文案內容
- `/test [檔名]`：測試廣播
- `/status`：查看機器人狀態
- `/history`：查詢廣播歷史
- `/help`：顯示所有指令說明

> 更多完整指令與說明，請參考 `完整指令操作說明.txt`。

---

## 自動備份說明
- 機器人啟動時與每日自動將 `settings.json`、`admins.json`、`broadcast_config.json`、`broadcast_history.json` 備份到 `backup/` 資料夾，檔名加上時間戳記。
- 請定期備份 `backup/` 內容，必要時可用於還原設定。

---

## 注意事項
- 請勿上傳 `.env`、`userbot.session`、`__pycache__`、`backup/*.bak` 等敏感或暫存檔案。
- 管理員指令僅限授權帳號使用，請妥善保管管理員名單。
- 所有設定皆自動保存，重啟後自動恢復。

---

## 授權
本專案採用 MIT License，歡迎自由使用與二次開發。

## 檔案結構說明

```
rg_thelegram_user_bot/
├── main.py                  # 主程式
├── config.py                # 設定管理
├── telegram_client.py       # Telegram 連線
├── message_manager.py       # 文案管理
├── broadcast_manager.py     # 廣播發送
├── scheduler.py             # 排程管理
├── command_handler.py       # 指令處理
├── requirements.txt         # 依賴套件
├── settings.json            # 目標/排程設定
├── admins.json              # 管理員設定
├── broadcast_config.json    # 廣播設定
├── broadcast_history.json   # 廣播歷史
├── message 1.txt            # 文案檔案
├── ...（其他檔案）
``` 