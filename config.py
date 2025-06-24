import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    集中管理所有設定，包括從環境變數和 JSON 檔案載入。
    """
    ADMINS_FILE = 'admins.json'

    def __init__(self, client=None):
        self.client = client
        # 從 .env 檔案或環境變數讀取 Telegram API 設定
        self.api_id = int(os.getenv('API_ID', 'default_api_id'))
        self.api_hash = os.getenv('API_HASH', 'default_api_hash')
        self.phone = os.getenv('PHONE_NUMBER', 'default_phone')
        self.password = os.getenv('PASSWORD', '')
        self.session_name = os.getenv('SESSION_NAME', 'userbot')

        # 控制群組設定
        self.control_group = int(os.getenv('CONTROL_GROUP', '0'))
        
        # 廣播參數設定
        self.broadcast_delay = int(os.getenv('BROADCAST_DELAY', '2'))
        self.max_retries = int(os.getenv('MAX_RETRIES', '3'))
        
        # --- 新增: 時區設定 ---
        # 從 .env 讀取時區，如果沒有則預設為 'Asia/Taipei'
        self.timezone = os.getenv('TIMEZONE', 'Asia/Taipei')

        # 從 JSON 檔案載入動態設定
        self.load_settings()
        self.load_broadcast_config()
        self.load_admins()

    def load_settings(self):
        """從 settings.json 載入設定，並處理多時間排程的向後相容性。"""
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                settings = json.load(f)
            self.target_groups = settings.get('target_groups', [])
            self.enabled = settings.get('enabled', False)

            if 'broadcast_times' in settings and isinstance(settings['broadcast_times'], list):
                self.broadcast_times = settings['broadcast_times']
            elif 'broadcast_time' in settings and settings.get('broadcast_time'):
                self.broadcast_times = [settings['broadcast_time']]
                self.save_settings()
            else:
                self.broadcast_times = []
            
        except (FileNotFoundError, json.JSONDecodeError):
            self.target_groups = []
            self.broadcast_times = []
            self.enabled = False
            self.save_settings()

    def save_settings(self):
        """將目前設定保存到 settings.json，使用新的多時間格式。"""
        settings = {
            'target_groups': self.target_groups,
            'broadcast_times': self.broadcast_times,
            'enabled': self.enabled,
            'last_updated': datetime.now().isoformat()
        }
        settings.pop('broadcast_time', None)
        
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    def load_admins(self):
        """從 admins.json 載入管理員列表。"""
        if os.path.exists(self.ADMINS_FILE):
            try:
                with open(self.ADMINS_FILE, 'r', encoding='utf-8') as f:
                    self.admins = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.admins = []
        else:
            self.admins = []
            self.save_admins()

    async def migrate_admins_from_env(self):
        """首次啟動時從 .env 遷移管理員。"""
        if self.admins: return
        admin_users_str = os.getenv('ADMIN_USERS', '')
        if not admin_users_str: return

        admin_ids = [int(uid.strip()) for uid in admin_users_str.split(',') if uid.strip()]
        for admin_id in admin_ids:
            try:
                user = await self.client.get_entity(admin_id)
                self.admins.append({"id": user.id, "name": user.first_name, "username": user.username or ""})
            except Exception as e:
                print(f"  ❌ 無法遷移 ID {admin_id}: {e}")
        self.save_admins()

    def save_admins(self):
        """將管理員列表保存到 admins.json。"""
        with open(self.ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.admins, f, ensure_ascii=False, indent=2)

    def is_admin(self, user_id: int) -> bool:
        """檢查使用者 ID 是否為管理員。"""
        return any(admin['id'] == user_id for admin in self.admins)

    def load_broadcast_config(self):
        try:
            with open('broadcast_config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.default_message_file = config.get('default_message_file', 'message.txt')
            self.total_restarts = config.get('total_restarts', 0)
        except (FileNotFoundError, json.JSONDecodeError):
            self.default_message_file = 'message.txt'
            self.total_restarts = 0
            self.save_broadcast_config(is_startup=False)

    def save_broadcast_config(self, is_startup=True):
        if is_startup: self.total_restarts += 1
        config = {
            'schedules': [], 
            'default_message_file': self.default_message_file,
            'last_startup': datetime.now().isoformat(), 
            'total_restarts': self.total_restarts
        }
        with open('broadcast_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
