import schedule
import asyncio
import threading
import time
from datetime import datetime
import pytz
import logging
import os # Import os module

class Scheduler:
    """
    管理定時廣播排程，支援多個廣播時間點與時區。
    """
    def __init__(self, config, broadcast_manager, loop, message_manager): # Add message_manager
        self.config = config
        self.broadcast_manager = broadcast_manager
        self.loop = loop
        self.message_manager = message_manager # Store message_manager
        try:
            self.tz = pytz.timezone(self.config.timezone)
        except pytz.UnknownTimeZoneError:
            print(f"⚠️ 時區 '{self.config.timezone}' 無效，將使用 UTC。")
            self.tz = pytz.utc

    def setup_schedule(self):
        """根據設定中的時間列表，建立或清除所有排程。"""
        schedule.clear()
        if self.config.enabled and self.config.schedules: 
            print(f"📅 正在設定 {len(self.config.schedules)} 個每日自動廣播排程 (時區: {self.config.timezone})...")
            
            for task in self.config.schedules: 
                broadcast_time = task.get("time")
                campaign_name = task.get("campaign")
                
                if not broadcast_time or not campaign_name:
                    print(f"  -> ❌ 無效的排程設定: {task} (缺少 'time' 或 'campaign')")
                    continue

                try:
                    # 使用指定的時區來設定排程
                    schedule.every().day.at(broadcast_time, self.config.timezone).do(
                        self.run_scheduled_broadcast, campaign_name=campaign_name 
                    )
                    print(f"  -> 已設定排程: {broadcast_time} (活動: {campaign_name})")
                except Exception as e:
                    print(f"  -> ❌ 設定排程 {broadcast_time} 失敗: {e}")
        else:
            print("⏸️ 自動廣播未啟用或未設定時間，已清除所有排程。")

    def run_scheduled_broadcast(self, campaign_name: str): 
        """將排定的廣播任務安全地提交到主事件循環中執行。"""
        print(f"[DEBUG] enabled={self.config.enabled}, loop_running={self.loop.is_running() if self.loop else None}")
        # 增加診斷日誌，確認排程已被觸發
        print(f"⏰ 排程時間已到 (時間: {datetime.now(self.tz).strftime('%H:%M:%S')})，準備執行廣播任務...")
        
        if self.config.enabled and self.loop and self.loop.is_running():
            # Load content from the specified campaign
            content = self.message_manager.load_campaign_content(campaign_name)
            asyncio.run_coroutine_threadsafe(
                self.broadcast_manager.send_campaign_broadcast(content, campaign_name), self.loop 
            )
        else:
            print("⚠️ 廣播任務被取消，原因：自動廣播未啟用或事件循環未運行。")

    def start_background_runner(self):
        """在一個獨立的背景執行緒中啟動排程檢查器，並加入錯誤處理。"""
        def schedule_checker():
            while True:
                try:
                    # 執行待處理的任務
                    schedule.run_pending()
                except Exception as e:
                    # 如果排程執行緒發生任何錯誤，印出日誌而不是讓執行緒崩潰
                    print(f"❌ 排程檢查器發生嚴重錯誤: {e}")
                
                # 每秒檢查一次，確保準時
                time.sleep(1)

        thread = threading.Thread(target=schedule_checker, daemon=True)
        thread.start()
        print("🚀 排程檢查器已在背景啟動 (含錯誤防護)。")