import asyncio
import json
from datetime import datetime
import logging

class BroadcastManager:
    """
    處理廣播發送的核心邏輯以及歷史記錄的保存。
    """
    def __init__(self, client, config, message_manager):
        self.client = client
        self.config = config
        self.message_manager = message_manager

    async def send_broadcast(self, message_file: str):
        """
        執行廣播任務，將訊息發送到所有目標群組。
        """
        message = self.message_manager.load_message(message_file)
        # 檢查訊息是否載入失敗
        if message.startswith("❌"):
             print(f"廣播中止，因為無法載入訊息：{message}")
             logging.info(f"廣播中止，因為無法載入訊息：{message}")
             if self.config.control_group:
                 await self.client.send_message(self.config.control_group, f"⚠️ 廣播任務中止\n原因: {message}")
             return 0, 0

        success_count = 0
        total_count = len(self.config.target_groups)
        broadcast_start = datetime.now()

        print(f"📢 開始廣播到 {total_count} 個目標... (使用檔案: {message_file})")
        logging.info(f"開始廣播到 {total_count} 個目標... (使用檔案: {message_file})")

        for i, group in enumerate(self.config.target_groups, 1):
            for attempt in range(self.config.max_retries):
                try:
                    await self.client.send_message(group['id'], message)
                    success_count += 1
                    print(f"✅ [{i}/{total_count}] 已發送到: {group['title']}")
                    logging.info(f"✅ [{i}/{total_count}] 已發送到: {group['title']}")
                    break  # 成功後跳出重試循環
                except Exception as e:
                    print(f"❌ [{i}/{total_count}] 發送失敗: {group['title']} (重試 {attempt + 1}/{self.config.max_retries}): {e}")
                    logging.error(f"❌ [{i}/{total_count}] 發送失敗: {group['title']} (重試 {attempt + 1}/{self.config.max_retries}): {e}")
                    if attempt < self.config.max_retries - 1:
                        await asyncio.sleep(2) # 重試前稍作等待
            
            # 每次發送後延遲，避免過於頻繁
            if i < total_count:
                await asyncio.sleep(self.config.broadcast_delay)

        success_rate = f"{(success_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        print(f"📊 廣播完成: {success_count}/{total_count} ({success_rate})")
        logging.info(f"廣播完成: {success_count}/{total_count} ({success_rate})")
        
        self.save_broadcast_history(broadcast_start, success_count, total_count, message_file, success_rate)

        # 向控制群組發送廣播報告
        if self.config.control_group:
            try:
                report_msg = (
                    f"📊 **廣播完成報告**\n\n"
                    f"✅ 成功: {success_count}\n"
                    f"❌ 失敗: {total_count - success_count}\n"
                    f"📋 總計: {total_count}\n"
                    f"📁 檔案: {message_file}\n"
                    f"📈 成功率: {success_rate}\n"
                    f"🔄 重啟: R{self.config.total_restarts}\n"
                    f"🕐 時間: {broadcast_start.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await self.client.send_message(self.config.control_group, report_msg)
            except Exception as e:
                print(f"❌ 發送廣播報告到控制群組失敗: {e}")
            
        return success_count, total_count

    def save_broadcast_history(self, start_time, success_count, total_count, message_file, success_rate):
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
                'message_file': message_file,
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

