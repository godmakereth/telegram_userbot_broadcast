import asyncio
from datetime import datetime
import logging
import os
import shutil

from config import Config
from telegram_client import TelegramClientManager
from message_manager import MessageManager
from broadcast_manager import BroadcastManager
from command_handler import CommandHandler
from scheduler import Scheduler

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename='bot.log',
    encoding='utf-8'
)

class JobBot:
    """
    應用程式主類別，負責整合所有模組並啟動機器人。
    """
    def __init__(self):
        """
        應用程式主類別，負責整合所有模組並啟動機器人。
        """
        # 1. 建立唯一的 Config 實例
        self.config = Config()

        # 2. 使用此 Config 實例初始化 Client Manager
        self.client_manager = TelegramClientManager(self.config)
        self.client = self.client_manager.get_client()

        # 3. 將 client 實例回寫到 config 中，供需要 client 的功能使用
        self.config.client = self.client

        # 4. 使用唯一的 Config 實例初始化其他管理員
        self.message_manager = MessageManager()
        self.broadcast_manager = BroadcastManager(self.client, self.config, self.message_manager)
        
        # 5. 初始化 Scheduler 和 CommandHandler (在 run 方法中進行)
        self.scheduler = None
        self.command_handler = None

    async def send_startup_message(self):
        """在啟動時向控制群組發送通知訊息。"""
        if self.config.control_group == 0:
            print("⚠️ 未設定控制群組，將不會發送啟動通知。")
            return
        
        try:
            admin_list_lines = ["\n- (尚無管理員)"]
            if self.config.admins:
                admin_list_lines = []
                for admin in self.config.admins:
                    username_part = f" (@{admin['username']})" if admin.get('username') else ''
                    admin_list_lines.append(f"\n- {admin.get('name', 'N/A')} (`{admin['id']}`){username_part}")
            admin_list_str = "".join(admin_list_lines)

            me = await self.client.get_me()
            startup_msg = f"""🤖 **廣播機器人已啟動**

👑 **偵測到的機器人管理員:**{admin_list_str}

- **狀態:** {'啟用' if self.config.enabled else '停用'}
            - **排程數量:** {len(self.config.schedules)} 個
- **目標群組:** {len(self.config.target_groups)} 個
- **重啟次數:** {self.config.total_restarts}

使用 `/help` 取得指令說明。
"""
            await self.client.send_message(self.config.control_group, startup_msg)
        except Exception as e:
            print(f"❌ 發送啟動訊息失敗: {e}")

    async def list_all_groups(self, send_to_control_group=True):
        """列出所有已加入的群組/頻道，標記已設定/未設定廣播。"""
        dialogs = []
        try:
            async for dialog in self.client.iter_dialogs():
                if dialog.is_group or dialog.is_channel:
                    dialogs.append({
                        'id': dialog.id,
                        'title': dialog.name,
                        'type': 'group' if dialog.is_group else 'channel'
                    })
        except Exception as e:
            print(f"❌ 取得群組/頻道名單失敗: {e}")
            logging.error(f"❌ 取得群組/頻道名單失敗: {e}")
            return
        broadcast_ids = set(g['id'] for g in self.config.target_groups)
        lines = ["[群組/頻道偵測結果]"]
        for idx, g in enumerate(dialogs, 1):
            mark = "[設定廣播]" if g['id'] in broadcast_ids else "[未設定廣播]"
            lines.append(f"{idx}. {g['title']} ({g['id']}) {mark}")
        result = "\n".join(lines)
        print(result)
        logging.info(result)
        if send_to_control_group and self.config.control_group:
            try:
                await self.client.send_message(self.config.control_group, f"<pre>{result}</pre>", parse_mode="html")
            except Exception as e:
                print(f"❌ 發送群組/頻道名單到控制群組失敗: {e}")
                logging.error(f"❌ 發送群組/頻道名單到控制群組失敗: {e}")

    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.scheduler = Scheduler(self.config, self.broadcast_manager, self.loop, self.message_manager)
        self.command_handler = CommandHandler(
            self, self.client, self.config, self.broadcast_manager, self.scheduler, self.message_manager
        )
        await self.client_manager.start()
        await self.config.migrate_admins_from_env()
        self.command_handler.register_handlers()
        self.config.save_broadcast_config(is_startup=True)
        self.scheduler.setup_schedule()
        self.scheduler.start_background_runner()
        await self.list_all_groups(send_to_control_group=True)  # 開機時自動列印
        await self.send_startup_message()
        print("✅ 機器人已準備就緒，正在等待指令...")
        logging.info("✅ 機器人已準備就緒，正在等待指令...")
        await self.client.run_until_disconnected()

def backup_files():
    os.makedirs('backup', exist_ok=True)
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    for f in ['settings.json', 'admins.json', 'broadcast_config.json', 'broadcast_history.json']:
        if os.path.exists(f):
            shutil.copy(f, f'backup/{f}.{now}.bak')

if __name__ == '__main__':
    # 啟動時建立備份資料夾
    os.makedirs('backup', exist_ok=True)
    # 啟動時立即備份一次
    backup_files()
    # 啟動每小時定時備份
    import threading
    def hourly_backup():
        backup_files()
        # 每1小時（3600秒）執行一次
        threading.Timer(3600, hourly_backup).start()
    hourly_backup()
    try:
        bot = JobBot()
        asyncio.run(bot.run())
    except Exception as e:
        print(f"❌ 程式發生嚴重錯誤: {e}")
    finally:
        print("\n👋 程式已停止。")
