import os
import glob

class MessageManager:
    """
    管理廣播訊息檔案的相關操作，如載入、列出檔案等。
    """
    def load_message(self, message_file: str) -> str:
        """
        從指定檔案載入廣播訊息。
        如果檔案不存在，會回傳錯誤訊息，或建立預設檔案。
        """
        try:
            with open(message_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                print(f"📄 已載入文案檔案: {message_file} ({len(content)} 字符)")
                return content
        except FileNotFoundError:
            # 如果是預設的 message.txt 不存在，則自動建立一個
            if message_file == 'message.txt':
                default_message = """🔍 **最新求職機會** 🔍

📍 **職位:** 請在 message.txt 中設定您的廣播內容
💰 **薪資:** 面議
🏢 **公司:** 您的公司名稱
📧 **聯絡:** 您的聯絡方式

歡迎有興趣的朋友私訊詢問詳情！

#求職 #工作機會"""
                with open('message.txt', 'w', encoding='utf-8') as f:
                    f.write(default_message)
                print(f"📄 找不到 message.txt，已建立預設檔案。")
                return default_message
            else:
                error_msg = f"❌ 找不到指定的文案檔案：{message_file}"
                print(error_msg)
                return error_msg

    def list_message_files(self) -> list:
        """列出當前目錄下所有符合 message*.txt 格式的檔案。"""
        return glob.glob('message*.txt')
