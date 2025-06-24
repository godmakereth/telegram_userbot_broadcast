# Telegram 廣播機器人

一個基於 Python + Telethon 的多群組/頻道自動廣播機器人，支援多時段排程、目標管理、文案管理、完整指令與日誌，適合自動推播訊息到多個 Telegram 群組/頻道。

## 功能特色

- 多群組/頻道自動廣播
- 多時段排程
- 文案檔案管理、預覽、測試
- 管理員權限控管
- 詳細日誌記錄
- 設定自動保存，重啟自動恢復
- 完整 Telegram 指令操作

## 安裝與環境需求

- Python 3.8+
- pip

### 安裝依賴

```bash
pip install -r requirements.txt
```

## 快速開始

1. **申請 Telegram API ID & HASH**  
   前往 [my.telegram.org](https://my.telegram.org) 申請。

2. **建立 `.env` 檔案**  
   在專案根目錄建立 `.env`，內容範例：
   ```
   API_ID=你的API_ID
   API_HASH=你的API_HASH
   PHONE_NUMBER=你的手機號碼（含國碼）
   PASSWORD=（如有雙重驗證則填，否則留空）
   CONTROL_GROUP=控制群組ID（可選）
   TIMEZONE=Asia/Taipei
   ADMIN_USERS=123456789,987654321
   ```

3. **啟動機器人**
   ```bash
   python main.py
   ```
   或執行 `start.bat`（Windows）

## 常用指令

| 指令 | 說明 |
|------|------|
| `/add` 或 `/add <群組ID>` | 新增目前群組或指定ID為廣播目標 |
| `/list` | 查看所有已加入群組/頻道，標記廣播目標 |
| `/remove <編號>` | 移除目標群組 |
| `/add_time HH:MM` | 新增廣播時間 |
| `/remove_time HH:MM` | 移除廣播時間 |
| `/list_times` | 查看所有排程時間 |
| `/enable` / `/disable` | 啟用/停用自動廣播 |
| `/files` | 列出所有文案檔案 |
| `/preview [檔名]` | 預覽文案內容 |
| `/test [檔名]` | 測試廣播 |
| `/status` | 查看機器人狀態 |
| `/history` | 查看廣播歷史 |
| `/help` | 查看所有指令說明 |

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

## 授權

MIT License 