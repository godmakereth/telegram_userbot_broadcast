import getpass
from telethon import TelegramClient, errors

class TelegramClientManager:
    """
    管理 Telethon 客戶端的初始化、啟動和連接。
    """
    def __init__(self, config):
        self.config = config
        self.client = TelegramClient(
            config.session_name,
            config.api_id,
            config.api_hash
        )

    async def start(self):
        """
        啟動並連接 Telethon 客戶端。
        會根據設定處理 2FA 密碼。
        """
        print("⏳ 正在連接 Telegram...")
        await self.client.connect()

        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.config.phone)
            try:
                await self.client.sign_in(self.config.phone, input('請輸入 Telegram 驗證碼: '))
            except errors.SessionPasswordNeededError:
                password = self.config.password or getpass.getpass('請輸入您的兩步驟驗證密碼: ')
                await self.client.sign_in(password=password)
        
        me = await self.client.get_me()
        print(f"✅ Telegram 客戶端已連接")
        print(f"👤 登入用戶: {me.first_name} {me.last_name or ''} (@{me.username or 'N/A'})")


    def get_client(self) -> TelegramClient:
        """返回已初始化的 Telethon 客戶端實例。"""
        return self.client