import asyncio
import json
from datetime import datetime
import logging
import os # Import os module

class BroadcastManager:
    """
    處理廣播發送的核心邏輯以及歷史記錄的保存。
    """
    def __init__(self, client, config, message_manager):
        self.client = client
        self.config = config
        self.message_manager = message_manager

    async def send_campaign_broadcast(self, content: dict, campaign_name: str):
        """
        執行廣播任務，根據內容字典發送文字、圖片、影片或GIF。
        """
        message_text = content.get("text", "")
        photo_path = content.get("photo")
        video_path = content.get("video")
        gif_path = content.get("gif")

        # Determine the primary file for logging and history
        primary_content_type = "text_only"
        if photo_path: primary_content_type = "photo"
        elif video_path: primary_content_type = "video"
        elif gif_path: primary_content_type = "gif"

        if primary_content_type == "text_only" and not message_text:
            error_msg = f"❌ 廣播中止，因為活動 '{campaign_name}' 中沒有可發送的內容 (文字、圖片、影片或GIF)。"
            print(error_msg)
            logging.error(error_msg)
            if self.config.control_group:
                await self.client.send_message(self.config.control_group, f"⚠️ 廣播任務中止\n原因: {error_msg}")
            return 0, 0

        success_count = 0
        total_count = len(self.config.target_groups)
        broadcast_start = datetime.now()

        print(f"📢 開始廣播到 {total_count} 個目標... (內容來自活動: {campaign_name})")
        logging.info(f"開始廣播到 {total_count} 個目標... (內容來自活動: {campaign_name})")

        success_groups = []
        failed_groups = []
        for i, group in enumerate(self.config.target_groups, 1):
            for attempt in range(self.config.max_retries):
                try:
                    if photo_path:
                        await self.client.send_file(group['id'], photo_path, caption=message_text)
                    elif video_path:
                        await self.client.send_file(group['id'], video_path, caption=message_text)
                    elif gif_path:
                        await self.client.send_file(group['id'], gif_path, caption=message_text)
                    elif message_text:
                        await self.client.send_message(group['id'], message_text)
                    else:
                        # This case should ideally be caught earlier, but as a fallback
                        print(f"⚠️ 無法發送內容到 {group['title']}，因為沒有可用的內容。")
                        logging.warning(f"無法發送內容到 {group['title']}，因為沒有可用的內容。")
                        break # Skip to next group if no content

                    success_count += 1
                    success_groups.append(f"{group['title']} (`{group['id']}`)")
                    print(f"✅ [{i}/{total_count}] 已發送到: {group['title']}")
                    logging.info(f"✅ [{i}/{total_count}] 已發送到: {group['title']}")
                    break
                except Exception as e:
                    if attempt == self.config.max_retries - 1:
                        failed_groups.append(f"{group['title']} (`{group['id']}`)")
                    print(f"❌ [{i}/{total_count}] 發送失敗: {group['title']} (重試 {attempt + 1}/{self.config.max_retries}): {e}")
                    logging.error(f"❌ [{i}/{total_count}] 發送失敗: {group['title']} (重試 {attempt + 1}/{self.config.max_retries}): {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2)
            if i < total_count:
                await asyncio.sleep(self.config.broadcast_delay)

        success_rate = f"{(success_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        print(f"📊 廣播完成: {success_count}/{total_count} ({success_rate})")
        logging.info(f"廣播完成: {success_count}/{total_count} ({success_rate})")
        self.save_broadcast_history(broadcast_start, success_count, total_count, campaign_name, success_rate,
                                    is_photo=bool(photo_path), is_video=bool(video_path), is_gif=bool(gif_path))

        # 向控制群組發送廣播報告
        if self.config.control_group:
            try:
                report_msg = (
                    f"📊 **廣播完成報告**\n\n"
                    f"✅ 成功: {success_count}\n"
                    f"{chr(10).join(['  - ' + g for g in success_groups]) if success_groups else '  - 無'}\n"
                    f"❌ 失敗: {total_count - success_count}\n"
                    f"{chr(10).join(['  - ' + g for g in failed_groups]) if failed_groups else '  - 無'}\n"
                    f"📋 總計: {total_count}\n"
                    f"📁 內容活動: {campaign_name}\n"
                    f"📈 成功率: {success_rate}\n"
                    f"🔄 重啟: R{self.config.total_restarts}\n"
                    f"🕒 時間: {broadcast_start.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await self.client.send_message(self.config.control_group, report_msg)
            except Exception as e:
                print(f"❌ 發送廣播報告到控制群組失敗: {e}")
        return success_count, total_count

    def save_broadcast_history(self, start_time: datetime, success_count: int, total_count: int,
                               file_path: str, success_rate: str, is_photo: bool = False,
                               is_video: bool = False, is_gif: bool = False):
        """將本次廣播的結果保存到 broadcast_history.json。"""
        try:
            try:
                with open('broadcast_history.json', 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                history = []

            record = {
                'time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'success_count': success_count,
                'total_count': total_count,
                'content_source': file_path, # Changed from message_file to content_source
                'is_photo': is_photo,
                'is_video': is_video, # New field
                'is_gif': is_gif,     # New field
                'success_rate': success_rate,
                'scheduled': self.config.enabled,
                'restart_count': self.config.total_restarts
            }
            history.append(record)

            # 僅保留最新的 100 筆記錄
            history = history[-100:]

            with open('broadcast_history.json', 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            print("📊 廣播歷史已保存。")
        except Exception as e:
            print(f"❌ 保存廣播歷史時發生錯誤: {e}")