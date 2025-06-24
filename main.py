import asyncio
from datetime import datetime
import logging

from config import Config
from telegram_client import TelegramClientManager
from message_manager import MessageManager
from broadcast_manager import BroadcastManager
from command_handler import CommandHandler
from scheduler import Scheduler

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class JobBot:
    """
    應用程式主類別，負責整合所有模組並啟動機器人。
    """
    def __init__(self):
        self.message_manager = MessageManager()
        self.client_manager = TelegramClientManager(Config()) 
        self.client = self.client_manager.get_client()
        
        self.config = Config(client=self.client)
        self.client_manager.config = self.config

        self.broadcast_manager = BroadcastManager(self.client, self.config, self.message_manager)
        self.scheduler = None
        self.command_handler = None

    async def send_startup_message(self):
        """在啟動時向控制群組發送通知訊息。"""
        if self.config.control_group == 0:
            print("⚠️ 未設定控制群組，將不會發送啟動通知。")
            return
        
        try:
            admin_list_str = "\n- (尚無管理員)"
            if self.config.admins:
                admin_list_str = "".join([f"\n- {admin.get('name', 'N/A')} (`{admin['id']}`)" for admin in self.config.admins])

            me = await self.client.get_me()
            startup_msg = f"""🤖 **廣播機器人已啟動**

👑 **偵測到的機器人管理員:**{admin_list_str}

- **狀態:** {'啟用' if self.config.enabled else '停用'}
- **排程數量:** {len(self.config.broadcast_times)} 個
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
        # 取得已設定廣播的ID集合
        broadcast_ids = set(g['id'] for g in self.config.target_groups)
        lines = ["[群組/頻道偵測結果]"]
        for idx, g in enumerate(dialogs, 1):
            mark = "[已設定廣播]" if g['id'] in broadcast_ids else "[未設定廣播]"
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
        self.scheduler = Scheduler(self.config, self.broadcast_manager, self.loop)
        self.command_handler = CommandHandler(
            self.client, self.config, self.broadcast_manager, self.scheduler, self.message_manager
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

if __name__ == '__main__':
    try:
        bot = JobBot()
        asyncio.run(bot.run())
    except Exception as e:
        print(f"❌ 程式發生嚴重錯誤: {e}")
    finally:
        print("\n👋 程式已停止。")
