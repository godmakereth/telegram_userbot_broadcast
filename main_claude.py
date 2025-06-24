import asyncio
import json
import os
from datetime import datetime, time, timedelta
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel, PeerChat, PeerUser
import schedule
import threading
from typing import Dict, List
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
        
        # 預設目標頻道
        target_channels_str = os.getenv('TARGET_CHANNELS', '-1002335227988,-4863847631')
        self.default_targets = [int(cid.strip()) for cid in target_channels_str.split(',') if cid.strip()]
        
        # 廣播設定
        self.broadcast_delay = int(os.getenv('BROADCAST_DELAY', '2'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        self.batch_size = int(os.getenv('BATCH_SIZE', '10'))
        self.timezone = os.getenv('TIMEZONE', 'Asia/Taipei')
        
        # 初始化 Telegram 客戶端
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        
        # 用於存儲主事件循環
        self.loop = None
        
        # 載入保存的設定
        self.load_settings()
        
        # 載入廣播排程配置
        self.load_broadcast_config()
        
    def load_settings(self):
        """載入保存的設定"""
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
                self.target_groups = settings.get('target_groups', [])
                self.broadcast_time = settings.get('broadcast_time', None)
                self.enabled = settings.get('enabled', False)
                
                print(f"📂 載入已保存設定:")
                print(f"   廣播時間: {self.broadcast_time if self.broadcast_time else '未設定'}")
                print(f"   啟用狀態: {'是' if self.enabled else '否'}")
                print(f"   目標群組: {len(self.target_groups)} 個")
                
        except FileNotFoundError:
            # 使用 .env 中的預設目標，但移除有問題的群組
            self.target_groups = []
            valid_targets = [-1002335227988, -4863847631]  # 移除有問題的 -4848522850
            for target_id in valid_targets:
                self.target_groups.append({
                    'id': target_id,
                    'title': f'頻道/群組 {target_id}',
                    'type': 'channel'
                })
            # 初始設定：不設定時間，不啟用
            self.broadcast_time = None
            self.enabled = False
            self.save_settings()
            print("📂 建立新的設定檔")
    
    def load_broadcast_config(self):
        """載入廣播配置檔案"""
        try:
            with open('broadcast_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.broadcast_schedules = config.get('schedules', [])
                self.default_message_file = config.get('default_message_file', 'message.txt')
                self.last_startup = config.get('last_startup', None)
                self.total_restarts = config.get('total_restarts', 0)
                
                print(f"📋 載入廣播配置:")
                print(f"   排程數量: {len(self.broadcast_schedules)} 個")
                print(f"   預設文案: {self.default_message_file}")
                print(f"   重啟次數: {self.total_restarts}")
                
        except FileNotFoundError:
            self.broadcast_schedules = []
            self.default_message_file = 'message.txt'
            self.last_startup = None
            self.total_restarts = 0
            self.save_broadcast_config()
            print("📋 建立新的廣播配置檔")
    
    def save_settings(self):
        """保存設定到檔案"""
        settings = {
            'target_groups': self.target_groups,
            'broadcast_time': self.broadcast_time,
            'enabled': self.enabled,
            'last_updated': datetime.now().isoformat(),
            'last_save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        print(f"💾 設定已保存: 時間={self.broadcast_time}, 啟用={self.enabled}")
    
    def save_broadcast_config(self):
        """保存廣播配置"""
        config = {
            'schedules': self.broadcast_schedules,
            'default_message_file': self.default_message_file,
            'last_startup': datetime.now().isoformat(),
            'total_restarts': self.total_restarts + 1,
            'last_save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        self.total_restarts = config['total_restarts']
        
        with open('broadcast_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"💾 廣播配置已保存")
    
    def load_message(self, message_file='message.txt'):
        """載入廣播訊息"""
        try:
            with open(message_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                print(f"📄 載入文案檔案: {message_file} ({len(content)} 字符)")
                return content
        except FileNotFoundError:
            if message_file == 'message.txt':
                default_message = """🔍 **最新求職機會** 🔍

📍 **職位:** 請在 message.txt 中設定您的廣播內容
💰 **薪資:** 面議
🏢 **公司:** 您的公司名稱
📧 **聯絡:** 您的聯絡方式

歡迎有興趣的朋友私訊詢問詳情！

#求職 #工作機會"""
                # 建立預設訊息檔案
                with open('message.txt', 'w', encoding='utf-8') as f:
                    f.write(default_message)
                print(f"📄 建立預設文案檔案: {message_file}")
                return default_message
            else:
                return f"❌ 找不到檔案：{message_file}"
    
    def list_message_files(self):
        """列出所有訊息檔案"""
        import glob
        message_files = glob.glob('message*.txt')
        return message_files
    
    def is_admin(self, user_id):
        """檢查是否為管理員"""
        return user_id in self.admin_users
    
    def save_broadcast_history(self, start_time, success_count, total_count, message_file, success_rate):
        """保存廣播歷史記錄"""
        try:
            # 讀取現有歷史
            try:
                with open('broadcast_history.json', 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except FileNotFoundError:
                history = []
            
            # 添加新記錄
            record = {
                'time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'success_count': success_count,
                'total_count': total_count,
                'message_file': message_file,
                'success_rate': success_rate,
                'scheduled': self.enabled,  # 是否為定時廣播
                'restart_count': self.total_restarts  # 記錄是第幾次重啟後的廣播
            }
            
            history.append(record)
            
            # 只保留最近100次記錄（增加保存數量）
            if len(history) > 100:
                history = history[-100:]
            
            # 保存歷史
            with open('broadcast_history.json', 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
                
            print(f"📊 廣播歷史已保存: {success_count}/{total_count} ({success_rate})")
                
        except Exception as e:
            print(f"❌ 保存廣播歷史失敗: {e}")
    
    async def send_startup_message(self):
        """發送啟動通知和指令說明到控制群組"""
        if not self.control_group:
            return
        
        try:
            # 獲取用戶資訊
            me = await self.client.get_me()
            
            # 統計訊息檔案
            files = self.list_message_files()
            
            # 檢查是否為重啟後首次啟動
            restart_info = ""
            if self.total_restarts > 0:
                restart_info = f"🔄 **第 {self.total_restarts} 次重啟**"
                if self.last_startup:
                    last_time = datetime.fromisoformat(self.last_startup).strftime('%Y-%m-%d %H:%M:%S')
                    restart_info += f"\n📅 上次啟動: {last_time}"
                restart_info += "\n"
            
            startup_msg = f"""🤖 **求職廣播機器人已啟動** 🚀

{restart_info}👤 **機器人資訊:**
- 用戶: {me.first_name} {me.last_name or ''} (@{me.username or 'N/A'})
- 啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 控制群組: {self.control_group}

📊 **保存的設定狀態:**
- 廣播時間: {self.broadcast_time if self.broadcast_time else '未設定'} ({'✅ 已啟用' if self.enabled and self.broadcast_time else '⏸️ 已停用'})
- 目標群組: {len(self.target_groups)} 個
- 訊息檔案: {len(files)} 個
- 預設文案: {self.default_message_file}
- 管理員: {len(self.admin_users)} 位
- 廣播延遲: {self.broadcast_delay} 秒
- 重試次數: {self.max_retries} 次

📋 **廣播群組清單:**"""

            # 添加群組詳細資訊
            if self.target_groups:
                for i, group in enumerate(self.target_groups, 1):
                    startup_msg += f"\n{i}. {group['title']}\n   ID: `{group['id']}`"
            else:
                startup_msg += "\n• 目前沒有設定廣播群組"

            # 顯示下次廣播時間（如果有設定且已啟用）
            if self.enabled and self.broadcast_time:
                now = datetime.now()
                broadcast_hour, broadcast_minute = map(int, self.broadcast_time.split(':'))
                today_broadcast = now.replace(hour=broadcast_hour, minute=broadcast_minute, second=0, microsecond=0)
                
                if today_broadcast <= now:
                    next_broadcast = today_broadcast + timedelta(days=1)
                else:
                    next_broadcast = today_broadcast
                
                time_diff = next_broadcast - now
                hours, remainder = divmod(time_diff.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                
                startup_msg += f"\n\n⏰ **下次自動廣播:**\n"
                startup_msg += f"🕐 時間: {next_broadcast.strftime('%Y-%m-%d %H:%M:%S')}\n"
                startup_msg += f"⏱️ 倒數: {int(hours)} 小時 {int(minutes)} 分鐘"

            startup_msg += f"""

📝 **可用指令說明:**

**🏢 群組管理**
- `/add` - 將當前群組加入廣播清單
- `/list` - 查看所有廣播群組
- `/remove 3` - 移除第3個群組

**🔍 群組掃描**
- `/my_groups` - 快速查看所在群組
- `/scan_groups` - 詳細掃描所有群組
- `/add_by_id <ID>` - 通過ID添加群組

**⏰ 時間管理**
- `/time` - 查看當前時間設定
- `/time 09:00` - 設定每日廣播時間
- `/time clear` - 清除時間設定
- `/schedule` - 查看廣播排程資訊
- `/history` - 查看廣播歷史記錄
- `/enable` - 啟用自動廣播
- `/disable` - 停用自動廣播
- `/reset_time` - 重置為預設時間

**📝 文案管理**
- `/files` - 查看所有訊息檔案
- `/preview message1` - 預覽文案內容
- `/test` - 立即測試廣播
- `/test message1` - 測試指定文案

**📊 系統狀態**
- `/status` - 查看機器人狀態
- `/help` - 顯示使用說明

💡 **所有設定已從檔案載入，無需重新設定！**
💾 **機器人會自動保存所有變更，重啟後不會遺失！**"""

            await self.client.send_message(self.control_group, startup_msg)
            print("📤 已發送啟動通知到控制群組")
            
        except Exception as e:
            print(f"❌ 發送啟動通知失敗: {e}")
    
    async def start(self):
        """啟動客戶端"""
        if self.password:
            await self.client.start(phone=self.phone, password=self.password)
        else:
            await self.client.start(phone=self.phone)
        
        print("✅ Telegram 客戶端已連接")
        
        # 獲取用戶資訊
        me = await self.client.get_me()
        print(f"👤 登入用戶: {me.first_name} {me.last_name or ''} (@{me.username or 'N/A'})")
        
        # 存儲主事件循環
        self.loop = asyncio.get_running_loop()
        
        # 更新啟動次數
        self.save_broadcast_config()
        
        # 設定指令處理
        self.setup_handlers()
        
        # 從保存的設定恢復排程
        if self.enabled and self.broadcast_time:
            self.setup_schedule()
            print(f"🔄 已從保存的設定恢復排程: {self.broadcast_time}")
        else:
            print("⏸️ 未啟用自動廣播或未設定時間")
        
        print(f"🤖 求職廣播機器人已啟動 (第 {self.total_restarts} 次)")
        print(f"📅 每日廣播時間: {self.broadcast_time if self.broadcast_time else '未設定'} ({'已啟用' if self.enabled and self.broadcast_time else '已停用'})")
        print(f"📋 目標群組數量: {len(self.target_groups)}")
        print(f"🎛️ 控制群組: {self.control_group}")
        print(f"👑 管理員: {len(self.admin_users)} 位")
        print("📝 可用指令:")
        print("  /add - 將當前群組加入廣播清單")
        print("  /list - 查看廣播清單")
        print("  /remove <編號> - 移除指定群組")
        print("  /my_groups - 快速查看所在群組")
        print("  /scan_groups - 詳細掃描所有群組")
        print("  /add_by_id <ID> - 通過ID添加群組")
        print("  /time [HH:MM|clear] - 管理廣播時間")
        print("  /schedule - 查看廣播排程")
        print("  /history - 查看廣播歷史")
        print("  /enable - 啟用自動廣播")
        print("  /disable - 停用自動廣播")
        print("  /clear_time - 清除排定時間")
        print("  /reset_time - 重置時間")
        print("  /test [檔案名] - 測試廣播")
        print("  /files - 查看所有訊息檔案")
        print("  /preview [檔案名] - 預覽訊息內容")
        print("  /status - 查看機器人狀態")
        print("  /help - 顯示說明")
        print("💾 所有設定已自動保存，重啟後會自動恢復！")
        
        # 發送啟動通知和指令說明到控制群組
        await self.send_startup_message()
    
    def setup_handlers(self):
        """設定指令處理器"""
        
        @self.client.on(events.NewMessage(pattern='/add'))
        async def add_group(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
                
            chat = await event.get_chat()
            chat_info = {
                'id': chat.id,
                'title': getattr(chat, 'title', f'私人對話 {chat.id}'),
                'type': 'group' if hasattr(chat, 'title') else 'private'
            }
            
            # 檢查是否已存在
            existing = next((g for g in self.target_groups if g['id'] == chat_info['id']), None)
            if not existing:
                self.target_groups.append(chat_info)
                self.save_settings()  # 立即保存
                await event.reply(f"✅ 已將「{chat_info['title']}」加入廣播清單\n💾 設定已自動保存")
            else:
                await event.reply(f"ℹ️ 「{chat_info['title']}」已在廣播清單中")
        
        @self.client.on(events.NewMessage(pattern='/list'))
        async def list_groups(event):
            if not self.is_admin(event.sender_id):
                return
                
            if not self.target_groups:
                await event.reply("📋 廣播清單為空")
                return
            
            message = "📋 **廣播清單:**\n\n"
            for i, group in enumerate(self.target_groups, 1):
                message += f"{i}. {group['title']}\n   ID: `{group['id']}`\n\n"
            
            message += f"⏰ **廣播時間:** {self.broadcast_time if self.broadcast_time else '未設定'}\n"
            message += f"🔄 **狀態:** {'啟用' if self.enabled and self.broadcast_time else '停用'}\n"
            message += f"⚙️ **延遲:** {self.broadcast_delay}秒\n"
            message += f"💾 **所有設定已保存** (重啟後會自動恢復)"
            
            await event.reply(message)
        
        @self.client.on(events.NewMessage(pattern=r'/remove (\d+)'))
        async def remove_group(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
                
            try:
                index = int(event.pattern_match.group(1)) - 1
                if 0 <= index < len(self.target_groups):
                    removed_group = self.target_groups.pop(index)
                    self.save_settings()  # 立即保存
                    await event.reply(f"✅ 已移除「{removed_group['title']}」\n💾 設定已自動保存")
                else:
                    await event.reply("❌ 無效的群組編號，請使用 /list 查看正確編號")
            except ValueError:
                await event.reply("❌ 請輸入有效的數字")
        
        @self.client.on(events.NewMessage(pattern='/my_groups'))
        async def my_groups(event):
            if not self.is_admin(event.sender_id):
                return
            
            await event.reply("🔍 正在獲取機器人所在群組的簡要清單...")
            
            try:
                dialogs = await self.client.get_dialogs()
                
                groups_count = 0
                channels_count = 0
                supergroups_count = 0
                
                simple_msg = ""
                
                for dialog in dialogs:
                    entity = dialog.entity
                    
                    if hasattr(entity, 'title'):  # 有標題的群組/頻道
                        if hasattr(entity, 'broadcast') and entity.broadcast:
                            channels_count += 1
                            simple_msg += f"📢 {entity.title}\n   ID: `{entity.id}`\n\n"
                        elif hasattr(entity, 'megagroup') and entity.megagroup:
                            supergroups_count += 1
                            simple_msg += f"🔊 {entity.title}\n   ID: `{entity.id}`\n\n"
                        else:
                            groups_count += 1
                            simple_msg += f"👥 {entity.title}\n   ID: `{entity.id}`\n\n"
                
                total = groups_count + channels_count + supergroups_count
                header = f"🔢 **總計:** {total} 個 (👥{groups_count} 🔊{supergroups_count} 📢{channels_count})\n\n"
                
                final_msg = "📋 **機器人所在群組簡要清單**\n\n" + header + simple_msg
                final_msg += "💡 使用 `/scan_groups` 查看詳細資訊\n💡 使用 `/add_by_id <ID>` 添加群組到廣播清單"
                
                if len(final_msg) > 4000:
                    await event.reply(f"📋 **機器人所在群組統計**\n\n{header}⚠️ 群組數量過多，請使用 `/scan_groups` 查看詳細清單")
                else:
                    await event.reply(final_msg)
                    
            except Exception as e:
                await event.reply(f"❌ 獲取群組清單時發生錯誤: {str(e)}")
        
        @self.client.on(events.NewMessage(pattern='/scan_groups'))
        async def scan_groups(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
            
            await event.reply("🔍 正在掃描機器人所在的群組...")
            
            try:
                # 獲取所有對話
                dialogs = await self.client.get_dialogs()
                
                groups = []
                channels = []
                supergroups = []
                
                for dialog in dialogs:
                    entity = dialog.entity
                    
                    # 分類不同類型的群組
                    if hasattr(entity, 'broadcast') and entity.broadcast:
                        # 頻道
                        channels.append({
                            'id': entity.id,
                            'title': entity.title,
                            'username': getattr(entity, 'username', None),
                            'participants_count': getattr(entity, 'participants_count', 'N/A')
                        })
                    elif hasattr(entity, 'megagroup') and entity.megagroup:
                        # 超級群組
                        supergroups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'username': getattr(entity, 'username', None),
                            'participants_count': getattr(entity, 'participants_count', 'N/A')
                        })
                    elif hasattr(entity, 'title'):
                        # 一般群組
                        groups.append({
                            'id': entity.id,
                            'title': entity.title,
                            'username': getattr(entity, 'username', None),
                            'participants_count': getattr(entity, 'participants_count', 'N/A')
                        })
                
                # 生成回覆訊息
                total_count = len(groups) + len(channels) + len(supergroups)
                scan_msg = f"📊 **機器人群組掃描結果**\n\n"
                scan_msg += f"🔢 **總計:** {total_count} 個群組/頻道\n"
                scan_msg += f"👥 一般群組: {len(groups)} 個\n"
                scan_msg += f"🔊 超級群組: {len(supergroups)} 個\n"
                scan_msg += f"📢 頻道: {len(channels)} 個\n\n"
                
                # 如果訊息過長，只顯示統計
                if total_count > 20:  # 如果群組太多，只顯示統計
                    scan_msg += "⚠️ 群組數量過多，僅顯示統計資訊\n"
                    scan_msg += "💡 使用 `/my_groups` 查看簡要清單\n"
                    scan_msg += "💡 使用 `/add_by_id <群組ID>` 添加群組到廣播清單"
                    await event.reply(scan_msg)
                    return
                
                # 添加群組詳細資訊
                for groups_list, emoji, type_name in [(groups, "👥", "一般群組"), (supergroups, "🔊", "超級群組"), (channels, "📢", "頻道")]:
                    if groups_list:
                        scan_msg += f"{emoji} **{type_name}:**\n"
                        for i, group in enumerate(groups_list, 1):
                            username_text = f"@{group['username']}" if group['username'] else "無用戶名"
                            scan_msg += f"{i}. {group['title']}\n"
                            scan_msg += f"   ID: `{group['id']}`\n"
                            scan_msg += f"   用戶名: {username_text}\n"
                            scan_msg += f"   成員數: {group['participants_count']}\n\n"
                
                scan_msg += "💡 **提示:** 使用 `/add_by_id <群組ID>` 可以直接添加群組到廣播清單"
                
                await event.reply(scan_msg)
                
            except Exception as e:
                await event.reply(f"❌ 掃描群組時發生錯誤: {str(e)}")

        @self.client.on(events.NewMessage(pattern=r'/add_by_id (-?\d+)'))
        async def add_by_id(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
            
            try:
                group_id = int(event.pattern_match.group(1))
                
                # 嘗試獲取群組資訊
                try:
                    entity = await self.client.get_entity(group_id)
                    chat_info = {
                        'id': entity.id,
                        'title': getattr(entity, 'title', f'群組/頻道 {entity.id}'),
                        'type': 'channel' if hasattr(entity, 'broadcast') else 'group'
                    }
                    
                    # 檢查是否已存在
                    existing = next((g for g in self.target_groups if g['id'] == chat_info['id']), None)
                    if not existing:
                        self.target_groups.append(chat_info)
                        self.save_settings()  # 立即保存
                        await event.reply(f"✅ 已將「{chat_info['title']}」加入廣播清單\nID: `{group_id}`\n💾 設定已自動保存")
                    else:
                        await event.reply(f"ℹ️ 「{chat_info['title']}」已在廣播清單中")
                        
                except Exception as e:
                    await event.reply(f"❌ 無法獲取群組資訊 (ID: {group_id}): {str(e)}")
                    
            except ValueError:
                await event.reply("❌ 請輸入有效的群組 ID")
        
        @self.client.on(events.NewMessage(pattern=r'/time(?:\s+(.+))?'))
        async def set_time(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
            
            time_input = event.pattern_match.group(1)
            
            if not time_input:
                # 顯示當前時間設定
                if self.broadcast_time:
                    await event.reply(f"⏰ 當前廣播時間: {self.broadcast_time}\n🔄 狀態: {'啟用' if self.enabled else '停用'}\n💾 設定已保存，重啟後會自動恢復")
                else:
                    await event.reply("⏰ 目前沒有設定廣播時間\n💡 使用 `/time 09:00` 設定時間")
                return
            
            time_input = time_input.strip().lower()
            
            # 支援清除時間
            if time_input in ['clear', 'delete', 'remove', '清除', '刪除']:
                old_time = self.broadcast_time
                self.broadcast_time = None
                self.enabled = False
                schedule.clear()
                self.save_settings()  # 立即保存
                await event.reply(f"✅ 已清除排定時間 ({old_time})\n⏸️ 自動廣播已停用\n💾 設定已自動保存")
                return
            
            # 驗證時間格式
            try:
                datetime.strptime(time_input, '%H:%M')
                old_time = self.broadcast_time
                self.broadcast_time = time_input
                self.save_settings()  # 立即保存
                if self.enabled:
                    self.setup_schedule()  # 重新設定排程
                
                change_msg = f"⏰ 廣播時間已設定為: {time_input}"
                if old_time:
                    change_msg += f" (原: {old_time})"
                change_msg += f"\n💾 設定已自動保存，重啟後會自動恢復"
                if not self.enabled:
                    change_msg += f"\n💡 使用 `/enable` 啟用自動廣播"
                
                await event.reply(change_msg)
            except ValueError:
                await event.reply("❌ 時間格式錯誤，請使用 HH:MM 格式（例如: 09:30）\n💡 使用 `/time clear` 清除時間設定")
        
        @self.client.on(events.NewMessage(pattern='/schedule'))
        async def show_schedule(event):
            if not self.is_admin(event.sender_id):
                return
            
            schedule_msg = "📅 **廣播排程資訊**\n\n"
            
            # 顯示當前設定
            if self.broadcast_time:
                status_emoji = "✅" if self.enabled else "⏸️"
                status_text = "已啟用" if self.enabled else "已停用"
                
                schedule_msg += f"⏰ **當前廣播時間:** {self.broadcast_time}\n"
                schedule_msg += f"🔄 **狀態:** {status_emoji} {status_text}\n"
                schedule_msg += f"📋 **目標群組:** {len(self.target_groups)} 個\n"
                schedule_msg += f"⚙️ **廣播延遲:** {self.broadcast_delay} 秒\n"
                schedule_msg += f"🔁 **重試次數:** {self.max_retries} 次\n"
                schedule_msg += f"🔄 **重啟次數:** {self.total_restarts} 次\n\n"
                
                # 計算下次廣播時間
                if self.enabled:
                    now = datetime.now()
                    broadcast_hour, broadcast_minute = map(int, self.broadcast_time.split(':'))
                    
                    # 計算今天的廣播時間
                    today_broadcast = now.replace(hour=broadcast_hour, minute=broadcast_minute, second=0, microsecond=0)
                    
                    # 如果今天的廣播時間已過，計算明天的
                    if today_broadcast <= now:
                        next_broadcast = today_broadcast + timedelta(days=1)
                    else:
                        next_broadcast = today_broadcast
                    
                    time_diff = next_broadcast - now
                    hours, remainder = divmod(time_diff.total_seconds(), 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    schedule_msg += f"🕐 **下次廣播:** {next_broadcast.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    schedule_msg += f"⏱️ **倒數時間:** {int(hours)} 小時 {int(minutes)} 分鐘\n\n"
                
                # 顯示廣播歷史統計（如果有的話）
                try:
                    with open('broadcast_history.json', 'r', encoding='utf-8') as f:
                        history = json.load(f)
                        total_broadcasts = len(history)
                        if total_broadcasts > 0:
                            last_broadcast = history[-1]
                            # 統計本次重啟後的廣播次數
                            current_restart_broadcasts = sum(1 for r in history if r.get('restart_count', 0) == self.total_restarts)
                            
                            schedule_msg += f"📊 **廣播統計:**\n"
                            schedule_msg += f"• 總廣播次數: {total_broadcasts} 次\n"
                            schedule_msg += f"• 本次重啟後: {current_restart_broadcasts} 次\n"
                            schedule_msg += f"• 最後廣播: {last_broadcast.get('time', 'N/A')}\n"
                            schedule_msg += f"• 最後成功率: {last_broadcast.get('success_rate', 'N/A')}\n\n"
                except FileNotFoundError:
                    pass
                
                schedule_msg += "💾 **持久化狀態:** 所有設定已保存，重啟後會自動恢復\n\n"
                schedule_msg += "💡 **管理指令:**\n"
                schedule_msg += "• `/time 14:30` - 修改廣播時間\n"
                schedule_msg += "• `/enable` - 啟用廣播\n"
                schedule_msg += "• `/disable` - 停用廣播\n"
                schedule_msg += "• `/time clear` - 清除時間設定"
                
            else:
                schedule_msg += "⏰ **目前沒有設定廣播時間**\n\n"
                schedule_msg += "💡 **快速設定:**\n"
                schedule_msg += "• `/time 09:00` - 設定上午9點廣播\n"
                schedule_msg += "• `/time 18:00` - 設定傍晚6點廣播\n"
                schedule_msg += "• `/enable` - 啟用自動廣播\n\n"
                schedule_msg += "💾 **注意:** 所有設定會自動保存，重啟後不會遺失"
            
            await event.reply(schedule_msg)
        
        @self.client.on(events.NewMessage(pattern='/history'))
        async def show_history(event):
            if not self.is_admin(event.sender_id):
                return
            
            try:
                with open('broadcast_history.json', 'r', encoding='utf-8') as f:
                    history = json.load(f)
                
                if not history:
                    await event.reply("📊 **廣播歷史**\n\n暫無廣播記錄")
                    return
                
                # 顯示最近10次記錄
                recent_history = history[-10:]
                
                history_msg = "📊 **廣播歷史記錄** (最近10次)\n\n"
                
                for i, record in enumerate(reversed(recent_history), 1):
                    broadcast_type = "🔄 定時" if record.get('scheduled', False) else "🧪 測試"
                    restart_info = f"R{record.get('restart_count', 0)}" if record.get('restart_count', 0) > 0 else ""
                    
                    history_msg += f"{i}. {broadcast_type} {record['time']} {restart_info}\n"
                    history_msg += f"   成功: {record['success_count']}/{record['total_count']} ({record['success_rate']})\n"
                    history_msg += f"   檔案: {record['message_file']}\n\n"
                
                # 統計資訊
                total_broadcasts = len(history)
                scheduled_broadcasts = sum(1 for r in history if r.get('scheduled', False))
                test_broadcasts = total_broadcasts - scheduled_broadcasts
                
                # 統計本次重啟後的廣播
                current_restart_broadcasts = sum(1 for r in history if r.get('restart_count', 0) == self.total_restarts)
                
                history_msg += f"📈 **統計資訊:**\n"
                history_msg += f"• 總廣播次數: {total_broadcasts} 次\n"
                history_msg += f"• 定時廣播: {scheduled_broadcasts} 次\n"
                history_msg += f"• 測試廣播: {test_broadcasts} 次\n"
                history_msg += f"• 本次重啟後: {current_restart_broadcasts} 次\n"
                
                # 計算平均成功率
                if history:
                    avg_success_rate = sum(float(r['success_rate'].rstrip('%')) for r in history) / len(history)
                    history_msg += f"• 平均成功率: {avg_success_rate:.1f}%\n\n"
                
                history_msg += "💾 **注意:** R數字表示重啟次數標記"
                
                await event.reply(history_msg)
                
            except FileNotFoundError:
                await event.reply("📊 **廣播歷史**\n\n暫無廣播記錄")
            except Exception as e:
                await event.reply(f"❌ 讀取廣播歷史失敗: {str(e)}")
        
        @self.client.on(events.NewMessage(pattern='/clear_time'))
        async def clear_time(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
            
            # 停用廣播並清除排程
            old_time = self.broadcast_time
            self.enabled = False
            self.broadcast_time = None
            schedule.clear()
            
            self.save_settings()  # 立即保存
            await event.reply(f"✅ 已清除排定時間 ({old_time})\n⏸️ 自動廣播已停用\n💾 設定已自動保存")

        @self.client.on(events.NewMessage(pattern='/reset_time'))
        async def reset_time(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
            
            # 重置為預設時間
            old_time = self.broadcast_time
            self.broadcast_time = '09:00'
            self.enabled = False
            schedule.clear()
            
            self.save_settings()  # 立即保存
            await event.reply(f"✅ 時間已重置為 09:00 (原: {old_time})\n⏸️ 自動廣播已停用\n💾 設定已自動保存\n💡 使用 `/enable` 重新啟用")
        
        @self.client.on(events.NewMessage(pattern='/enable'))
        async def enable_broadcast(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
            
            if not self.broadcast_time:
                await event.reply("❌ 請先設定廣播時間\n💡 使用 `/time 09:00` 設定時間")
                return
                
            self.enabled = True
            self.save_settings()  # 立即保存
            self.setup_schedule()
            await event.reply(f"✅ 自動廣播已啟用\n⏰ 廣播時間: {self.broadcast_time}\n💾 設定已自動保存，重啟後會自動恢復")
        
        @self.client.on(events.NewMessage(pattern='/disable'))
        async def disable_broadcast(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
                
            self.enabled = False
            self.save_settings()  # 立即保存
            schedule.clear()
            await event.reply(f"⏸️ 自動廣播已停用\n⏰ 排定時間: {self.broadcast_time if self.broadcast_time else '未設定'}\n💾 設定已自動保存")
        
        @self.client.on(events.NewMessage(pattern=r'/test(?:\s+(.+))?'))
        async def test_broadcast(event):
            if not self.is_admin(event.sender_id):
                await event.reply("❌ 您沒有權限執行此指令")
                return
            
            # 獲取檔案名參數
            filename = event.pattern_match.group(1)
            if filename:
                filename = filename.strip() + '.txt' if not filename.endswith('.txt') else filename.strip()
            else:
                filename = 'message.txt'
                
            await event.reply(f"🧪 開始測試廣播... (使用檔案: {filename})")
            success_count, total_count = await self.send_broadcast(filename)
            await event.reply(f"✅ 測試完成\n成功: {success_count}/{total_count} 個群組\n📊 結果已自動記錄到歷史")
        
        @self.client.on(events.NewMessage(pattern='/files'))
        async def list_files(event):
            if not self.is_admin(event.sender_id):
                return
                
            files = self.list_message_files()
            if not files:
                await event.reply("📁 沒有找到訊息檔案")
                return
            
            message = "📁 **可用的訊息檔案:**\n\n"
            for i, file in enumerate(files, 1):
                try:
                    file_size = os.path.getsize(file)
                    default_mark = " ⭐" if file == self.default_message_file else ""
                    message += f"{i}. `{file}` ({file_size} bytes){default_mark}\n"
                except:
                    message += f"{i}. `{file}` (無法讀取大小)\n"
            
            message += f"\n⭐ 預設文案: {self.default_message_file}"
            message += "\n💡 使用 `/test filename` 測試特定檔案"
            message += "\n💡 使用 `/preview filename` 預覽檔案內容"
            await event.reply(message)
        
        @self.client.on(events.NewMessage(pattern=r'/preview(?:\s+(.+))?'))
        async def preview_message(event):
            if not self.is_admin(event.sender_id):
                return
            
            # 獲取檔案名參數
            filename = event.pattern_match.group(1)
            if filename:
                filename = filename.strip() + '.txt' if not filename.endswith('.txt') else filename.strip()
            else:
                filename = 'message.txt'
            
            try:
                content = self.load_message(filename)
                preview_msg = f"📄 **預覽檔案: {filename}**"
                if filename == self.default_message_file:
                    preview_msg += " ⭐"
                preview_msg += "\n\n"
                preview_msg += "=" * 30 + "\n"
                preview_msg += content
                preview_msg += "\n" + "=" * 30
                
                if len(preview_msg) > 4000:
                    preview_msg = preview_msg[:4000] + "...\n\n⚠️ 內容過長，已截斷顯示"
                
                await event.reply(preview_msg)
            except Exception as e:
                await event.reply(f"❌ 無法讀取檔案 {filename}: {str(e)}")
        
        @self.client.on(events.NewMessage(pattern='/status'))
        async def show_status(event):
            if not self.is_admin(event.sender_id):
                return
                
            me = await self.client.get_me()
            
            # 統計訊息檔案
            files = self.list_message_files()
            
            # 讀取設定檔案時間
            try:
                settings_time = datetime.fromtimestamp(os.path.getmtime('settings.json')).strftime('%Y-%m-%d %H:%M:%S')
            except:
                settings_time = "未知"
            
            status_msg = f"""📊 **機器人狀態**

👤 **用戶:** {me.first_name} {me.last_name or ''}
📱 **電話:** {self.phone}
🎛️ **控制群組:** {self.control_group}

📋 **廣播設定:**
- 目標數量: {len(self.target_groups)} 個
- 廣播時間: {self.broadcast_time if self.broadcast_time else '未設定'}
- 狀態: {'✅ 啟用' if self.enabled and self.broadcast_time else '⏸️ 停用'}
- 延遲: {self.broadcast_delay} 秒
- 重試次數: {self.max_retries} 次

💾 **持久化資訊:**
- 重啟次數: {self.total_restarts} 次
- 設定檔更新: {settings_time}
- 預設文案: {self.default_message_file}

📁 **訊息檔案:** {len(files)} 個
⚙️ **管理員:** {len(self.admin_users)} 位
🕐 **當前時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

💡 **所有設定已自動保存，重啟後會自動恢復！**"""
            
            await event.reply(status_msg)
        
        @self.client.on(events.NewMessage(pattern='/help'))
        async def show_help(event):
            help_text = """🤖 **求職廣播機器人使用說明**

**群組管理:**
- `/add` - 將當前群組加入廣播清單
- `/list` - 查看廣播清單和設定
- `/remove <編號>` - 移除指定群組

**群組掃描:**
- `/my_groups` - 快速查看所在群組
- `/scan_groups` - 詳細掃描所有群組
- `/add_by_id <ID>` - 通過ID添加群組

**時間管理:**
- `/time` - 查看當前時間設定
- `/time HH:MM` - 設定每日廣播時間
- `/time clear` - 清除時間設定
- `/schedule` - 查看廣播排程資訊
- `/history` - 查看廣播歷史記錄
- `/enable` - 啟用自動廣播
- `/disable` - 停用自動廣播
- `/clear_time` - 清除排定時間
- `/reset_time` - 重置為預設時間

**訊息管理:**
- `/files` - 查看所有訊息檔案
- `/preview [檔案名]` - 預覽訊息內容
- `/test [檔案名]` - 測試廣播特定檔案

**系統功能:**
- `/status` - 查看機器人狀態
- `/help` - 顯示此說明

**使用方法:**
1. 使用 `/my_groups` 查看所在群組
2. 使用 `/add_by_id <ID>` 或在群組中 `/add` 添加廣播群組
3. 使用 `/time 09:00` 設定廣播時間
4. 編輯 `message.txt` 設定廣播內容
5. 使用 `/enable` 啟用自動廣播

**時間管理範例:**
- `/schedule` - 查看完整排程資訊
- `/time 09:00` - 設定上午9點
- `/enable` - 啟用廣播
- `/disable` - 停用廣播
- `/history` - 查看廣播歷史

**💾 持久化特性:**
- 所有設定自動保存到檔案
- 重啟後自動恢復廣播時間和狀態
- 群組清單永久保存
- 廣播歷史完整記錄
- 無需每次重新設定

**高級功能:**
- 支援多個訊息檔案 (message1.txt, message2.txt...)
- 使用 `/test message1` 測試特定檔案
- 重啟次數追蹤和廣播統計
- 自動記錄成功率和錯誤資訊

**注意事項:**
- 只有管理員可以操作機器人
- 建議先使用 `/test` 測試功能
- 所有變更都會立即保存
            """
            await event.reply(help_text)
    
    def setup_schedule(self):
        """設定排程"""
        schedule.clear()  # 清除舊排程
        if self.enabled and self.broadcast_time:
            schedule.every().day.at(self.broadcast_time).do(self.schedule_broadcast)
            print(f"📅 已設定每日 {self.broadcast_time} 自動廣播")
    
    def schedule_broadcast(self):
        """排程廣播任務 - 修正版本，使用正確的事件循環"""
        if self.enabled and self.broadcast_time and self.loop:
            # 在主事件循環中創建任務
            asyncio.run_coroutine_threadsafe(self.send_broadcast(), self.loop)
    
    async def send_broadcast(self, message_file='message.txt'):
        """發送廣播"""
        message = self.load_message(message_file)
        success_count = 0
        total_count = len(self.target_groups)
        
        # 記錄廣播開始時間
        broadcast_start = datetime.now()
        
        print(f"📢 開始廣播到 {total_count} 個目標... (使用檔案: {message_file})")
        
        for i, group in enumerate(self.target_groups, 1):
            retry_count = 0
            while retry_count < self.max_retries:
                try:
                    await self.client.send_message(group['id'], message)
                    success_count += 1
                    print(f"✅ [{i}/{total_count}] 已發送到: {group['title']}")
                    break
                except Exception as e:
                    retry_count += 1
                    print(f"❌ [{i}/{total_count}] 發送失敗 {group['title']} (重試 {retry_count}/{self.max_retries}): {e}")
                    if retry_count < self.max_retries:
                        await asyncio.sleep(1)
            
            # 延遲避免發送太快
            if i < total_count:
                await asyncio.sleep(self.broadcast_delay)
        
        # 計算成功率
        success_rate = f"{(success_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        
        print(f"📊 廣播完成: {success_count}/{total_count} 個群組 ({success_rate})")
        
        # 保存廣播歷史
        self.save_broadcast_history(broadcast_start, success_count, total_count, message_file, success_rate)
        
        # 如果有控制群組，發送廣播結果
        if self.control_group:
            try:
                result_msg = f"📊 **廣播完成報告**\n\n✅ 成功: {success_count}\n❌ 失敗: {total_count - success_count}\n📋 總計: {total_count}\n📁 檔案: {message_file}\n📈 成功率: {success_rate}\n🔄 重啟: R{self.total_restarts}\n🕐 時間: {broadcast_start.strftime('%Y-%m-%d %H:%M:%S')}"
                await self.client.send_message(self.control_group, result_msg)
            except:
                pass
        
        return success_count, total_count
    
    def run_schedule(self):
        """運行排程檢查"""
        while True:
            try:
                schedule.run_pending()
                sync_time.sleep(60)  # 每分鐘檢查一次
            except Exception as e:
                print(f"❌ 排程檢查錯誤: {e}")
                sync_time.sleep(60)
    
    async def run(self):
        """主運行函數"""
        await self.start()
        
        # 在背景運行排程檢查
        schedule_thread = threading.Thread(target=self.run_schedule, daemon=True)
        schedule_thread.start()
        
        print("🚀 機器人正在運行中...")
        print("💾 所有設定已自動保存，重啟後會自動恢復！")
        print("按 Ctrl+C 停止機器人")
        
        # 保持客戶端運行
        try:
            await self.client.run_until_disconnected()
        except KeyboardInterrupt:
            print("\n👋 機器人已停止")

# 主程式入口
if __name__ == '__main__':
    try:
        broadcaster = JobBroadcaster()
        asyncio.run(broadcaster.run())
    except KeyboardInterrupt:
        print("\n👋 程式已結束")
    except Exception as e:
        print(f"❌ 程式錯誤: {e}")
        input("按 Enter 鍵繼續...")