import os
import glob

class MessageManager:
    """
    管理廣播活動內容的相關操作，包括列出活動、載入活動內容（文字、圖片、影片、GIF）。
    """
    CONTENT_DB_PATH = "content_databases"

    def list_campaigns(self) -> list[str]:
        """
        列出 content_databases 目錄下所有可用的廣播活動（子資料夾名稱）。
        """
        if not os.path.isdir(self.CONTENT_DB_PATH):
            print(f"⚠️ 找不到內容資料庫目錄：{self.CONTENT_DB_PATH}")
            return []
        
        campaigns = [d for d in os.listdir(self.CONTENT_DB_PATH) if os.path.isdir(os.path.join(self.CONTENT_DB_PATH, d))]
        print(f"📂 已找到 {len(campaigns)} 個廣播活動：{', '.join(campaigns)}")
        return campaigns

    def load_campaign_content(self, campaign_name: str) -> dict:
        """
        從指定的廣播活動資料夾載入內容，包括文字、圖片、影片和GIF。
        """
        campaign_path = os.path.join(self.CONTENT_DB_PATH, campaign_name)
        content = {
            "text": "",
            "photo": None,
            "video": None,
            "gif": None
        }

        if not os.path.isdir(campaign_path):
            print(f"❌ 找不到指定的廣播活動資料夾：{campaign_path}")
            return content

        # 載入文字內容 (message.txt)
        message_file_path = os.path.join(campaign_path, "message.txt")
        if os.path.exists(message_file_path):
            try:
                with open(message_file_path, 'r', encoding='utf-8') as f:
                    content["text"] = f.read().strip()
                    print(f"📄 已載入活動文案: {message_file_path} ({len(content['text'])} 字符)")
            except Exception as e:
                print(f"❌ 載入活動文案檔案失敗: {message_file_path} - {e}")

        # 搜尋圖片、影片和GIF
        # 優先順序：圖片 -> 影片 -> GIF
        for ext in ["jpg", "jpeg", "png"]:
            files = glob.glob(os.path.join(campaign_path, f"*.{ext}"))
            if files:
                content["photo"] = files[0] # 只取第一個找到的圖片
                print(f"🖼️ 已找到圖片: {content['photo']}")
                break

        if not content["photo"]:
            for ext in ["mp4", "mov", "avi"]:
                files = glob.glob(os.path.join(campaign_path, f"*.{ext}"))
                if files:
                    content["video"] = files[0] # 只取第一個找到的影片
                    print(f"🎬 已找到影片: {content['video']}")
                    break

        if not content["photo"] and not content["video"]:
            files = glob.glob(os.path.join(campaign_path, "*.gif"))
            if files:
                content["gif"] = files[0] # 只取第一個找到的GIF
                print(f"✨ 已找到GIF: {content['gif']}")

        return content
