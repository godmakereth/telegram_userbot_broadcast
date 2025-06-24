import asyncio
import json
import os
from datetime import datetime, time, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat, PeerUser
import schedule
import threading
from typing import Dict, List, Union
from dotenv import load_dotenv
import time as sync_time

# 載入環境變數
load_dotenv()

class JobBroadcaster:
    def __init__(self):
        # 從 .env 檔案讀取配置
        self.api_id = int(os.getenv('API_ID', '23170409'))
        self.api_hash = os.getenv('API_HASH', '0c79dc8fa92bd26461a819a3fa72129c')
        self.phone = os.getenv('PHONE_NUMBER', '+886958364330')
        self.password = os.getenv('PASSWORD', '')
        self.session_name = os.getenv('SESSION_NAME', 'userbot')

        # 控制群組和管理員設定
        self.control_group = int(os.getenv('CONTROL_GROUP', '-1002512140773'))
        admin_users_str = os.getenv('ADMIN_USERS', '7248981754,6457224485')
        self.admin_users = [int(uid.strip()) for uid in admin_users_str.split(',') if uid.strip()]

        # 廣播設定
        self.broadcast_delay = int(os.getenv('BROADCAST_DELAY', '2'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '10'))
        self.timezone = os.getenv('TIMEZONE', 'Asia/Taipei')

        # 初始化 Telegram 客戶端
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        self.loop = None

        # [MODIFIED] 初始化設定變數
        self.target_groups: List[Dict] = []
        self.broadcast_times: List[str] = [] # 從單一時間改為時間列表
        self.enabled: bool = False
        
        # 載入保存的設定與配置
        self.load_settings()
        self.load_broadcast_config()

    # [MODIFIED] 修改載入設定以支援多重時間並確保向下相容
    def load_settings(self):
        """載入保存的設定，並處理舊格式的相容性"""
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.target_groups = settings.get('target_groups', [])
                self.enabled = settings.get('enabled', False)

                # --- 向下相容處理 ---
                # 檢查是新的 'broadcast_times' (列表) 還是舊的 'broadcast_time' (字串)
                if 'broadcast_times' in settings:
                    self.broadcast_times = settings.get('broadcast_times', [])
                elif 'broadcast_time' in settings and settings['broadcast_time']:
                    # 如果找到舊的單一時間設定，將其轉換為列表格式
                    self.broadcast_times = [settings['broadcast_time']]
                    print("🔄 偵測到舊版時間設定，已自動轉換為新版多重時間格式。")
                else:
                    self.broadcast_times = []
                # --- 相容處理結束 ---

                print("📂 載入已保存設定:")
                print(f"   廣播時間: {', '.join(self.broadcast_times) if self.broadcast_times else '未設定'}")
                print(f"   啟用狀態: {'是' if self.enabled else '否'}")
                print(f"   目標群組: {len(self.target_groups)} 個")

        except FileNotFoundError:
            self.target_groups = []
            self.broadcast_times = [] # 初始為空列表
            self.enabled = False
            self.save_settings()
            print("📂 建立新的設定檔")

    # [MODIFIED] 修改儲存設定以使用新的 broadcast_times 列表
    def save_settings(self):
        """保存設定到檔案"""
        settings = {
            'target_groups': self.target_groups,
            'broadcast_times': self.broadcast_times, # 儲存時間列表
            'enabled': self.enabled,
            'last_updated': datetime.now().isoformat(),
        }
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        print(f"💾 設定已保存: 時間={self.broadcast_times}, 啟用={self.enabled}")
        
    def load_broadcast_config(self):
        """載入廣播配置檔案"""
        try:
            with open('broadcast_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.default_message_file = config.get('default_message_file', 'message.txt')
                self.last_startup = config.get('last_startup', None)
                self.total_restarts = config.get('total_restarts', 0)
            print(f"📋 載入廣播配置: 預設文案='{self.default_message_file}', 重啟次數={self.total_restarts}")
        except FileNotFoundError:
            self.default_message_file = 'message.txt'
            self.last_startup = None
            self.total_restarts = 0
            self.update_broadcast_config(is_startup=True)
            print("📋 建立新的廣播配置檔")

    def update_broadcast_config(self, is_startup=False):
        """更新並保存廣播配置"""
        if is_startup:
            self.total_restarts += 1
        
        config = {
            'default_message_file': self.default_message_file,
            'last_startup': datetime.now().isoformat(),
            'total_restarts': self.total_restarts,
        }
        with open('broadcast_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print("💾 廣播配置已更新")

    def load_message(self, message_file='message.txt'):
        """載入廣播訊息"""
        try:
            with open(message_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                print(f"📄 載入文案檔案: {message_file} ({len(content)} 字符)")
                return content
        except FileNotFoundError:
            if message_file == 'message.txt':
                default_message = "🔍 **最新求職機會** 🔍\n\n📍 **職位:** 請在 message.txt 中設定您的廣播內容"
                with open('message.txt', 'w', encoding='utf-8') as f:
                    f.write(default_message)
                print(f"📄 建立預設文案檔案: {message_file}")
                return default_message
            else:
                return f"❌ 找不到檔案：{message_file}"

    def list_message_files(self):
        """列出所有訊息檔案"""
        import glob
        return glob.glob('message*.txt')

    def is_admin(self, user_id):
        """檢查是否為管理員"""
        return user_id in self.admin_users

    def save_broadcast_history(self, start_time, success_count, total_count, message_file, success_rate):
        """保存廣播歷史記錄"""
        try:
            try:
                with open('broadcast_history.json', 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except FileNotFoundError:
                history = []
            
            record = {
                'time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'success_count': success_count,
                'total_count': total_count,
                'message_file': message_file,
                'success_rate': success_rate,
                'scheduled': self.enabled,
                'restart_count': self.total_restarts
            }
            history.append(record)
            history = history[-100:] # 只保留最近100次
            
            with open('broadcast_history.json', 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
            print(f"📊 廣播歷史已保存: {success_count}/{total_count} ({success_rate})")
        except Exception as e:
            print(f"❌ 保存廣播歷史失敗: {e}")

    # [MODIFIED] 更新啟動訊息以反映新功能
    async def send_startup_message(self):
        """發送啟動通知和指令說明到控制群組"""
        if not self.control_group: return
        try:
            me = await self.client.get_me()
            
            # 組裝時間字串
            times_str = ', '.join(self.broadcast_times) if self.broadcast_times else '未設定'
            status_str = '✅ 已啟用' if self.enabled and self.broadcast_times else '⏸️ 已停用'

            startup_msg = f"""🤖 **廣播機器人已啟動** V2.0 🚀

🔄 **第 {self.total_restarts} 次啟動**
👤 **用戶:** {me.first_name} {me.last_name or ''}
- 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📊 **當前設定:**
- 廣播時間: **{times_str}** ({status_str})
- 目標群組: {len(self.target_groups)} 個
- 預設文案: {self.default_message_file}

📝 **指令更新:**
- **/info**: 顯示所有時間、文案和群組的完整資訊。
- **/time HH:MM**: 新增廣播時間。
- **/time remove HH:MM**: 移除廣播時間。
- **/help**: 查看所有指令。

💡 所有設定已自動載入，重啟後不會遺失！"""
            await self.client.send_message(self.control_group, startup_msg)
            print("📤 已發送啟動通知到控制群組")
        except Exception as e:
            print(f"❌ 發送啟動通知失敗: {e}")

    async def start(self):
        """啟動客戶端"""
        await self.client.start(phone=self.phone, password=self.password)
        print("✅ Telegram 客戶端已連接")

        me = await self.client.get_me()
        print(f"👤 登入用戶: {me.first_name} {me.last_name or ''} (@{me.username or 'N/A'})")

        self.loop = asyncio.get_running_loop()
        
        self.update_broadcast_config(is_startup=True)
        self.setup_handlers()

        if self.enabled and self.broadcast_times:
            self.setup_schedule()
            print(f"🔄 已從保存的設定恢復排程: {self.broadcast_times}")
        else:
            print("⏸️ 未啟用自動廣播或未設定時間")

        await self.send_startup_message()

    def setup_handlers(self):
        """設定所有指令的處理器"""
        
        # --- 全新 /info 指令 ---
        @self.client.on(events.NewMessage(pattern='/info', from_users=self.admin_users))
        async def show_info(event):
            """顯示所有時間、推文和群組的完整資訊"""
            
            # 1. 廣播時間資訊
            times_str = ""
            if not self.broadcast_times:
                times_str = "未設定任何廣播時間"
            else:
                for t in sorted(self.broadcast_times):
                    times_str += f"- `{t}`\n"
            
            status_str = '✅ 已啟用' if self.enabled and self.broadcast_times else '⏸️ 已停用'
            
            info_msg = f"📊 **機器人完整資訊**\n\n"
            info_msg += f"⏰ **廣播時間設定** ({status_str})\n{times_str}\n"
            
            # 2. 預設文案預覽
            message_content = self.load_message(self.default_message_file)
            info_msg += f"📄 **預設廣播文案 (`{self.default_message_file}`)**\n"
            info_msg += "```\n"
            info_msg += message_content[:500] + ('...' if len(message_content) > 500 else '')
            info_msg += "\n```\n"

            # 3. 廣播群組清單
            groups_str = ""
            if not self.target_groups:
                groups_str = "未加入任何廣播群組"
            else:
                for i, group in enumerate(self.target_groups, 1):
                    groups_str += f"{i}. {group['title']} (`{group['id']}`)\n"
            
            info_msg += f"📋 **廣播群組清單 ({len(self.target_groups)}個)**\n{groups_str}"

            if len(info_msg) > 4096:
                info_msg = info_msg[:4090] + "\n..."
                
            await event.reply(info_msg)

        # --- 時間管理指令 (重構) ---
        @self.client.on(events.NewMessage(pattern=r'/time(?:\s+(.+))?', from_users=self.admin_users))
        async def set_time(event):
            """管理廣播時間（新增、移除、查看、清除）"""
            args = (event.pattern_match.group(1) or "").strip().lower().split()
            
            # 指令: /time (無參數) -> 列表
            if not args:
                if not self.broadcast_times:
                    await event.reply("⏰ 目前沒有設定廣播時間。\n💡 使用 `/time 09:00` 來新增一個。")
                    return
                
                times_list = "\n".join([f"- `{t}`" for t in sorted(self.broadcast_times)])
                status = "✅ 已啟用" if self.enabled else "⏸️ 已停用"
                await event.reply(f"⏰ **已設定的廣播時間:**\n{times_list}\n\n狀態: {status}")
                return

            command = args[0]
            
            # 指令: /time clear
            if command == 'clear':
                self.broadcast_times.clear()
                self.enabled = False
                schedule.clear()
                self.save_settings()
                await event.reply("✅ 已清除所有廣播時間，並停用自動廣播。")
                return
            
            # 指令: /time remove HH:MM
            if command == 'remove':
                if len(args) < 2:
                    await event.reply("❌ 格式錯誤。請使用 `/time remove HH:MM`。")
                    return
                time_to_remove = args[1]
                if time_to_remove in self.broadcast_times:
                    self.broadcast_times.remove(time_to_remove)
                    self.save_settings()
                    self.setup_schedule() # 重新整理排程
                    await event.reply(f"✅ 已移除時間: `{time_to_remove}`。")
                else:
                    await event.reply(f"❌ 找不到要移除的時間: `{time_to_remove}`。")
                return

            # 指令: /time HH:MM (新增)
            time_to_add = command
            try:
                datetime.strptime(time_to_add, '%H:%M')
                if time_to_add in self.broadcast_times:
                    await event.reply(f"ℹ️ 時間 `{time_to_add}` 已經在排程中了。")
                    return
                
                self.broadcast_times.append(time_to_add)
                self.save_settings()
                if self.enabled:
                    self.setup_schedule()
                
                msg = f"✅ 已新增廣播時間: `{time_to_add}`。\n💾 設定已保存。"
                if not self.enabled:
                    msg += "\n💡 目前廣播為停用狀態，請記得使用 `/enable` 來啟用。"
                await event.reply(msg)

            except ValueError:
                await event.reply("❌ 時間格式錯誤，請使用 `HH:MM` 格式 (例如: 09:30 或 21:00)。")

        # --- /enable 和 /disable ---
        @self.client.on(events.NewMessage(pattern='/enable', from_users=self.admin_users))
        async def enable_broadcast(event):
            if not self.broadcast_times:
                await event.reply("❌ 請至少設定一個廣播時間後再啟用。\n💡 使用 `/time HH:MM`。")
                return
            self.enabled = True
            self.save_settings()
            self.setup_schedule()
            await event.reply(f"✅ 自動廣播已啟用。\n⏰ 將在每天的 {', '.join(sorted(self.broadcast_times))} 進行廣播。")

        @self.client.on(events.NewMessage(pattern='/disable', from_users=self.admin_users))
        async def disable_broadcast(event):
            self.enabled = False
            self.save_settings()
            schedule.clear()
            await event.reply("⏸️ 自動廣播已停用，所有排程已清除。")
            
        # --- 其他指令 (保持不變或微調) ---
        @self.client.on(events.NewMessage(pattern='/add', from_users=self.admin_users))
        async def add_group(event):
            chat = await event.get_chat()
            chat_info = {'id': chat.id, 'title': getattr(chat, 'title', f'私人對話 {chat.id}')}
            if chat.id not in [g['id'] for g in self.target_groups]:
                self.target_groups.append(chat_info)
                self.save_settings()
                await event.reply(f"✅ 已將「{chat_info['title']}」加入廣播清單。")
            else:
                await event.reply(f"ℹ️ 「{chat_info['title']}」已在清單中。")

        @self.client.on(events.NewMessage(pattern='/list', from_users=self.admin_users))
        async def list_groups(event):
            if not self.target_groups:
                await event.reply("📋 廣播清單為空。")
                return
            message = "📋 **廣播群組清單:**\n\n"
            for i, group in enumerate(self.target_groups, 1):
                message += f"{i}. {group['title']}\n   ID: `{group['id']}`\n"
            await event.reply(message)

        @self.client.on(events.NewMessage(pattern=r'/remove (\d+)', from_users=self.admin_users))
        async def remove_group(event):
            try:
                index = int(event.pattern_match.group(1)) - 1
                if 0 <= index < len(self.target_groups):
                    removed_group = self.target_groups.pop(index)
                    self.save_settings()
                    await event.reply(f"✅ 已移除「{removed_group['title']}」。")
                else:
                    await event.reply("❌ 無效的編號。")
            except ValueError:
                await event.reply("❌ 請輸入有效的數字。")

        @self.client.on(events.NewMessage(pattern=r'/test(?:\s+(.+))?', from_users=self.admin_users))
        async def test_broadcast(event):
            filename = event.pattern_match.group(1)
            filename = f"{filename.replace('.txt', '')}.txt" if filename else self.default_message_file
            
            await event.reply(f"🧪 開始測試廣播 (檔案: {filename})...")
            success, total = await self.send_broadcast(filename)
            await event.reply(f"✅ 測試完成: {success}/{total} 成功。")

        # [MODIFIED] 更新 schedule 指令以顯示更詳細的資訊
        @self.client.on(events.NewMessage(pattern='/schedule', from_users=self.admin_users))
        async def show_schedule(event):
            schedule_msg = "📅 **廣播排程資訊**\n\n"
            status_emoji = "✅" if self.enabled else "⏸️"
            status_text = "已啟用" if self.enabled and self.broadcast_times else "已停用"
            
            schedule_msg += f"🔄 **狀態:** {status_emoji} {status_text}\n"
            
            if not self.broadcast_times:
                schedule_msg += "⏰ **廣播時間:** 未設定\n"
            else:
                schedule_msg += f"⏰ **廣播時間列表:**\n"
                for t in sorted(self.broadcast_times):
                    schedule_msg += f"   - `{t}`\n"
                
                # 計算下一次廣播
                if self.enabled:
                    now = datetime.now()
                    next_run_time = None
                    
                    for t_str in sorted(self.broadcast_times):
                        h, m = map(int, t_str.split(':'))
                        today_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
                        
                        potential_next = today_run
                        if today_run <= now:
                            potential_next += timedelta(days=1)
                        
                        if next_run_time is None or potential_next < next_run_time:
                            next_run_time = potential_next
                    
                    if next_run_time:
                        time_diff = next_run_time - now
                        hours, rem = divmod(time_diff.total_seconds(), 3600)
                        minutes, _ = divmod(rem, 60)
                        schedule_msg += f"\n⏳ **下次廣播倒數:** {int(hours)} 小時 {int(minutes)} 分鐘 (在 `{next_run_time.strftime('%H:%M')}`)\n"

            schedule_msg += f"\n💡 使用 `/info` 查看完整設定。"
            await event.reply(schedule_msg)

        # [MODIFIED] 更新 help 指令
        @self.client.on(events.NewMessage(pattern='/help', from_users=self.admin_users))
        async def show_help(event):
            help_text = """🤖 **廣播機器人指令說明 V2.0**

**🆕 核心指令**
- `/info` - 顯示時間/文案/群組等所有資訊 (推薦)

**⏰ 時間管理**
- `/time` - 列出所有廣播時間
- `/time HH:MM` - 新增一個廣播時間
- `/time remove HH:MM` - 移除指定時間
- `/time clear` - 清除所有時間
- `/schedule` - 查看排程狀態與下次廣播倒數
- `/enable` - 啟用所有定時廣播
- `/disable` - 停用所有定時廣播

**🏢 群組管理**
- `/add` - 將當前群組加入清單
- `/add_by_id <ID>` - 透過ID添加
- `/list` - 查看廣播群組清單
- `/remove <編號>` - 移除指定群組

**📝 文案與測試**
- `/test [檔名]` - 立即測試廣播 (預設用 message.txt)
- `/preview [檔名]` - 預覽文案內容
- `/files` - 列出所有可用的文案檔 (message*.txt)

**📊 系統**
- `/history` - 查看最近10次廣播歷史
- `/status` - 查看機器人簡要狀態
- `/help` - 顯示此說明
"""
            await event.reply(help_text)

    # [MODIFIED] 設定多個排程
    def setup_schedule(self):
        """根據 broadcast_times 列表設定多個排程"""
        schedule.clear()
        if self.enabled and self.broadcast_times:
            print(f"📅 正在設定 {len(self.broadcast_times)} 個每日排程...")
            for time_str in self.broadcast_times:
                schedule.every().day.at(time_str).do(self.schedule_broadcast_job)
                print(f"   - 已設定每日 {time_str} 自動廣播")
        else:
            print("排程未啟用或無時間設定，清除所有任務。")

    def schedule_broadcast_job(self):
        """排程觸發的任務，它會在主事件循環中安全地運行異步廣播函數"""
        if self.enabled and self.loop:
            print(f"⏰ 排程觸發 ({datetime.now().strftime('%H:%M')})! 準備廣播...")
            # 使用預設文案檔進行排程廣播
            asyncio.run_coroutine_threadsafe(self.send_broadcast(self.default_message_file), self.loop)

    async def send_broadcast(self, message_file: str):
        """執行廣播的核心異步函數"""
        message = self.load_message(message_file)
        if message.startswith("❌"): # 檢查文案是否載入失敗
             if self.control_group:
                await self.client.send_message(self.control_group, f"📊 **廣播失敗**\n\n原因: {message}")
             return 0, len(self.target_groups)

        success_count = 0
        total_count = len(self.target_groups)
        broadcast_start = datetime.now()
        
        print(f"📢 開始廣播到 {total_count} 個目標... (檔案: {message_file})")

        for i, group in enumerate(self.target_groups, 1):
            for attempt in range(self.max_retries):
                try:
                    await self.client.send_message(group['id'], message)
                    success_count += 1
                    print(f"✅ [{i}/{total_count}] 已發送到: {group['title']}")
                    break # 成功後跳出重試循環
                except Exception as e:
                    print(f"❌ [{i}/{total_count}] 發送失敗: {group['title']} (重試 {attempt+1}/{self.max_retries}): {e}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2) # 重試前稍作等待
            await asyncio.sleep(self.broadcast_delay)
            
        success_rate = f"{(success_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        print(f"📊 廣播完成: {success_count}/{total_count} ({success_rate})")
        
        self.save_broadcast_history(broadcast_start, success_count, total_count, message_file, success_rate)
        
        if self.control_group:
            result_msg = f"📊 **廣播完成報告**\n\n✅ 成功: {success_count}\n❌ 失敗: {total_count - success_count}\n📈 成功率: {success_rate}\n📁 檔案: {message_file}"
            await self.client.send_message(self.control_group, result_msg)
        
        return success_count, total_count

    def run_schedule_checker(self):
        """在獨立線程中運行排程檢查"""
        while True:
            try:
                schedule.run_pending()
                sync_time.sleep(1) # 每秒檢查一次以提高精準度
            except Exception as e:
                print(f"❌ 排程檢查線程錯誤: {e}")
                sync_time.sleep(60)

    async def run(self):
        """主運行函數"""
        await self.start()
        
        schedule_thread = threading.Thread(target=self.run_schedule_checker, daemon=True)
        schedule_thread.start()
        
        print("🚀 機器人正在運行中...")
        await self.client.run_until_disconnected()

# 主程式入口
if __name__ == '__main__':
    try:
        broadcaster = JobBroadcaster()
        asyncio.run(broadcaster.run())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 機器人已停止")
    except Exception as e:
        print(f"❌ 程式發生致命錯誤: {e}")
        input("按 Enter 鍵結束...")