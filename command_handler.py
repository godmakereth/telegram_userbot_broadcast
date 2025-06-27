from telethon import events
from telethon.tl.types import ChannelParticipantsAdmins
from datetime import datetime, timedelta
import json
import re
import os
import pytz
import logging

class CommandHandler:
    """
    處理所有來自 Telegram 的使用者指令 (最終完整版，包含所有功能)。
    """
    def __init__(self, bot_instance, client, config, broadcast_manager, scheduler, message_manager):
        self.bot_instance = bot_instance
        self.client = client
        self.config = config
        self.broadcast_manager = broadcast_manager
        self.scheduler = scheduler
        self.message_manager = message_manager

    def register_handlers(self):
        # --- 管理員與群組成員管理 ---
        self.client.add_event_handler(self.list_admins, events.NewMessage(pattern=r'^/list_admins$', func=self._is_admin))
        self.client.add_event_handler(self.add_admin, events.NewMessage(pattern=r'/add_admin (.+)', func=self._is_admin))
        self.client.add_event_handler(self.remove_admin, events.NewMessage(pattern=r'/remove_admin (.+)', func=self._is_admin))
        self.client.add_event_handler(self.list_members, events.NewMessage(pattern='/list_members', func=self._is_admin))
        self.client.add_event_handler(self.sync_admins, events.NewMessage(pattern='/sync_admins', func=self._is_admin))

        # --- 新排程管理 (以活動為中心) ---
        self.client.add_event_handler(self.add_schedule, events.NewMessage(pattern=r'/add_schedule (\d{2}:\d{2}) (.+)', func=self._is_admin))
        self.client.add_event_handler(self.remove_schedule, events.NewMessage(pattern=r'/remove_schedule (\d{2}:\d{2}) (.+)', func=self._is_admin))
        self.client.add_event_handler(self.list_schedules, events.NewMessage(pattern='/list_schedules', func=self._is_admin))
        
        # --- 廣播群組管理 ---
        @self.client.on(events.NewMessage(pattern=r'/add(?:\s+(-?\d+))?', func=self._is_admin))
        async def add_group(event):
            user_id = event.sender_id
            username = getattr(event.sender, 'username', None)
            print(f"[CMD] 收到指令: /add 來自 {user_id} ({username})")
            logging.info(f"[CMD] 收到指令: /add 來自 {user_id} ({username})")
            group_id_str = event.pattern_match.group(1)
            if group_id_str:
                # 指定群組ID
                try:
                    group_id = int(group_id_str)
                    entity = await self.client.get_entity(group_id)
                    chat_info = {'id': entity.id, 'title': getattr(entity, 'title', f'ID {entity.id}'), 'type': 'group'}
                    if not any(g['id'] == chat_info['id'] for g in self.config.target_groups):
                        self.config.target_groups.append(chat_info)
                        self.config.save_settings()
                        await event.reply(f"✅ 已新增廣播目標: 「{chat_info['title']}」 (ID: `{chat_info['id']}`)")
                    else:
                        await event.reply(f"ℹ️ 「{chat_info['title']}」已在目標中。")
                except Exception as e:
                    await event.reply(f"❌ 新增失敗: {e}")
            else:
                # 新增目前群組
                chat = await event.get_chat()
                chat_info = {'id': chat.id, 'title': getattr(chat, 'title', f'對話 {chat.id}'), 'type': 'group'}
                if not any(g['id'] == chat_info['id'] for g in self.config.target_groups):
                    self.config.target_groups.append(chat_info)
                    self.config.save_settings()
                    await event.reply(f"✅ 已新增廣播目標: 「{chat_info['title']}」")
                else:
                    await event.reply(f"ℹ️ 「{chat_info['title']}」已在目標中。")
        self.client.add_event_handler(self.list_groups, events.NewMessage(pattern=r'^/list_groups$', func=self._is_admin))
        self.client.add_event_handler(self.remove_group, events.NewMessage(pattern=r'/remove (\d+)', func=self._is_admin))
        self.client.add_event_handler(self.my_groups, events.NewMessage(pattern='/my_groups', func=self._is_admin))
        self.client.add_event_handler(self.add_by_id, events.NewMessage(pattern=r'/add_by_id (-?\d+)', func=self._is_admin))

        # --- 活動與測試指令 ---
        self.client.add_event_handler(self.list_campaigns, events.NewMessage(pattern='/campaigns', func=self._is_admin))
        self.client.add_event_handler(self.preview_campaign, events.NewMessage(pattern=r'/preview(?:\s+(.+))?', func=self._is_admin))
        self.client.add_event_handler(self.test_campaign_broadcast, events.NewMessage(pattern=r'/test(?:\s+(.+))?', func=self._is_admin))

        # --- 其他系統指令 ---
        self.client.add_event_handler(self.show_schedule, events.NewMessage(pattern='/schedule', func=self._is_admin))
        self.client.add_event_handler(self.show_history, events.NewMessage(pattern='/history', func=self._is_admin))
        self.client.add_event_handler(self.enable_broadcast, events.NewMessage(pattern='/enable', func=self._is_admin))
        self.client.add_event_handler(self.disable_broadcast, events.NewMessage(pattern='/disable', func=self._is_admin))
        self.client.add_event_handler(self.show_status, events.NewMessage(pattern='/status', func=self._is_admin))
        self.client.add_event_handler(self.show_help, events.NewMessage(pattern='/help'))
        self.client.add_event_handler(self.show_info, events.NewMessage(pattern='/info', func=self._is_admin))
        
        @self.client.on(events.NewMessage(pattern='/list'))
        async def handler_list(event):
            user_id = event.sender_id
            username = getattr(event.sender, 'username', None)
            print(f"[CMD] 收到指令: /list 來自 {user_id} ({username})")
            logging.info(f"[CMD] 收到指令: /list 來自 {user_id} ({username})")
            # 僅允許管理員查詢
            if not self.config.is_admin(user_id):
                await event.reply("你沒有權限使用此指令。"); return
            # 直接呼叫 list_all_groups
            await self.bot_instance.list_all_groups(send_to_control_group=True)

        @self.client.on(events.NewMessage(pattern=r'/add_groups (.+)', func=self._is_admin))
        async def add_groups(event):
            user_id = event.sender_id
            username = getattr(event.sender, 'username', None)
            print(f"[CMD] 收到指令: /add_groups 來自 {user_id} ({username})")
            logging.info(f"[CMD] 收到指令: /add_groups 來自 {user_id} ({username})")
            group_ids_str = event.pattern_match.group(1)
            group_ids = [gid.strip() for gid in group_ids_str.split(',') if gid.strip()]
            added = []
            failed = []
            for gid in group_ids:
                try:
                    group_id = int(gid)
                    entity = await self.client.get_entity(group_id)
                    chat_info = {'id': entity.id, 'title': getattr(entity, 'title', f'ID {entity.id}'), 'type': 'group'}
                    if not any(g['id'] == chat_info['id'] for g in self.config.target_groups):
                        self.config.target_groups.append(chat_info)
                        added.append(f"{chat_info['title']} (`{chat_info['id']}`)")
                    else:
                        failed.append(f"{chat_info['title']} (`{chat_info['id']}`) 已存在")
                except Exception as e:
                    failed.append(f"ID {gid} 新增失敗: {e}")
            self.config.save_settings()
            msg = ""
            if added:
                msg += f"✅ 已新增: {'、'.join(added)}\n"
            if failed:
                msg += f"⚠️ 未新增/已存在: {'、'.join(failed)}"
            await event.reply(msg or "沒有任何群組被新增。")

        print("🦾 所有指令處理常式已註冊 (最終完整版)。")

    async def _is_admin(self, event):
        is_admin = self.config.is_admin(event.sender_id)
        if not is_admin:
            await event.reply("❌ 您沒有權限執行此操作。")
        return is_admin

    def _is_control_group_member(self, event):
        # 僅允許主控制群組成員執行
        return event.chat_id == self.config.control_group

    async def _get_user_entity(self, identifier_raw: str):
        cleaned_str = re.sub(r'[<>@\s]', '', identifier_raw)
        try:
            entity_to_find = int(cleaned_str)
        except ValueError:
            entity_to_find = cleaned_str
        return await self.client.get_entity(entity_to_find)

    # --- 指令實作 ---

    async def sync_admins(self, event):
        if not self.config.control_group: await event.reply("❌ 未設定控制群組，無法同步。"); return
        await event.reply("⏳ 正在掃描控制群組的管理員並進行同步...")
        try:
            new_admins = []
            async for user in self.client.iter_participants(self.config.control_group, filter=ChannelParticipantsAdmins):
                if user.bot: continue
                new_admins.append({"id": user.id, "name": user.first_name, "username": user.username or ""})
            self.config.admins = new_admins
            self.config.save_admins()
            await event.reply(f"✅ 同步完成！已將 **{len(new_admins)}** 位控制群組的管理員設定為機器人管理員。")
        except Exception as e: await event.reply(f"❌ 同步失敗: {e}")

    async def add_admin(self, event):
        identifier_raw = event.pattern_match.group(1).strip()
        try:
            user = await self._get_user_entity(identifier_raw)
            if self.config.is_admin(user.id): await event.reply(f"ℹ️ **{user.first_name}** 已經是管理員了。"); return
            new_admin = {"id": user.id, "name": user.first_name, "username": user.username or ""}
            self.config.admins.append(new_admin); self.config.save_admins()
            await event.reply(f"✅ 成功新增管理員: **{user.first_name}** (ID: `{user.id}`)")
        except Exception as e: await event.reply(f"❌ 新增失敗: 無法找到用戶 '{identifier_raw}'.\n錯誤: {e}")

    async def remove_admin(self, event):
        identifier_raw = event.pattern_match.group(1).strip()
        if len(self.config.admins) <= 1: await event.reply("❌ 無法移除最後一位管理員！"); return
        try:
            user_to_remove = await self._get_user_entity(identifier_raw)
            admin_found = next((admin for admin in self.config.admins if admin['id'] == user_to_remove.id), None)
            if admin_found:
                self.config.admins.remove(admin_found); self.config.save_admins()
                await event.reply(f"✅ 成功移除管理員: **{admin_found.get('name', 'N/A')}** (ID: `{admin_found['id']}`)")
            else: await event.reply(f"❌ **{user_to_remove.first_name}** 不在管理員列表中。")
        except Exception as e: await event.reply(f"❌ 移除失敗: 無法找到用戶 '{identifier_raw}'.\n錯誤: {e}")

    async def list_admins(self, event):
        if not self.config.admins:
            await event.reply("👑 目前沒有設定任何管理員。")
            return
        message = "👑 **目前管理員列表:**\n\n"
        for i, admin in enumerate(self.config.admins, 1):
            name = admin.get('name', '未知名稱')
            username = admin.get('username')
            username_str = f"(@{username})" if username else ""
            message += f"{i}. {name} {username_str}\n   ID: `{admin['id']}`\n"
        await event.reply(message)

    async def list_members(self, event):
        if not self.config.control_group: await event.reply("❌ 未設定控制群組。"); return
        await event.reply("⏳ 正在獲取群組成員列表...")
        try:
            group = await self.client.get_entity(self.config.control_group)
            message = f"👥 **'{group.title}' 群組成員:**\n\n"
            count = 0
            async for member in self.client.iter_participants(group):
                count += 1
                admin_marker = "👑 (機器人管理員)" if self.config.is_admin(member.id) else ""
                name = member.first_name or "N/A"
                username_str = f"(@{member.username})" if member.username else ""
                message += f"• {name} {username_str} {admin_marker}\n  ID: `{member.id}`\n"
            message += f"\n總計: {count} 位成員。"
            await event.reply(message, parse_mode='md')
        except Exception as e: await event.reply(f"❌ 獲取成員列表失敗: {e}")

    async def list_campaigns(self, event):
        campaigns = self.message_manager.list_campaigns()
        if not campaigns:
            await event.reply("📁 找不到任何廣播活動。請確保 `content_databases` 資料夾中有子資料夾。")
            return
        
        message = "📁 **可用廣播活動:**\n\n"
        for i, campaign in enumerate(campaigns, 1):
            message += f"{i}. `{campaign}`\n"
        
        message += "\n💡 使用 `/preview <活動名稱>` 預覽活動內容。\n"
        message += "💡 使用 `/test <活動名稱>` 手動測試廣播。\n"
        message += "💡 使用 `/add_schedule HH:MM <活動名稱>` 設定排程。"
        await event.reply(message)

    async def preview_campaign(self, event):
        campaign_name = event.pattern_match.group(1)
        if not campaign_name:
            await event.reply("❌ 請提供要預覽的活動名稱。例如: `/preview campaign_A`")
            return

        content = self.message_manager.load_campaign_content(campaign_name)
        
        if not content["text"] and not content["photo"] and not content["video"] and not content["gif"]:
            await event.reply(f"❌ 活動 `{campaign_name}` 中沒有可預覽的內容 (文字、圖片、影片或GIF)。")
            return

        message = f"📄 **預覽活動: `{campaign_name}`**\n\n---\n\n"
        if content["text"]:
            message += f"**文字內容:**\n{content['text']}\n\n"
        if content["photo"]:
            message += f"**圖片:** `{content['photo']}`\n"
        if content["video"]:
            message += f"**影片:** `{content['video']}`\n"
        if content["gif"]:
            message += f"**GIF:** `{content['gif']}`\n"
        
        await event.reply(message)

    async def test_campaign_broadcast(self, event):
        campaign_name = event.pattern_match.group(1)
        if not campaign_name:
            await event.reply("❌ 請提供要測試廣播的活動名稱。例如: `/test campaign_A`")
            return

        # 檢查活動是否存在
        if campaign_name not in self.message_manager.list_campaigns():
            await event.reply(f"❌ 找不到活動 `{campaign_name}`。請使用 `/campaigns` 查看可用活動。")
            return

        await event.reply(f"🧪 正在測試廣播活動 `{campaign_name}`...")
        
        # 載入活動內容
        content = self.message_manager.load_campaign_content(campaign_name)
        
        # 執行廣播
        success_count, total_count = await self.broadcast_manager.send_campaign_broadcast(content, campaign_name)
        
        if success_count > 0:
            await event.reply(f"✅ 測試廣播完成！成功發送 {success_count}/{total_count} 個。")
        else:
            await event.reply(f"❌ 測試廣播失敗。請檢查日誌。")

    async def show_schedule(self, event):
        status = "✅ 啟用" if self.config.enabled else "⏸️ 停用"
        msg = f"📅 **排程資訊**\n\n🔄 狀態: **{status}**\n"
        
        if not self.config.schedules:
            msg += "\n⏰ 無排程。"
            await event.reply(msg)
            return
        
        msg += "\n⏰ **排程時間點:**\n"
        for s in self.config.schedules:
            msg += f" - `{s['time']}` (活動: `{s['campaign']}`)\n"

        if self.config.enabled and self.config.schedules:
            now = datetime.now(pytz.timezone(self.config.timezone))
            
            # 尋找下一個最近的排程
            next_broadcast_time = None
            next_campaign = None
            min_diff = timedelta(days=365) # 初始化一個很大的時間差

            for s in self.config.schedules:
                schedule_time_today = now.replace(hour=int(s['time'].split(':')[0]), 
                                                  minute=int(s['time'].split(':')[1]), 
                                                  second=0, microsecond=0)
                
                # 如果排程時間已過，則考慮明天的時間
                if schedule_time_today <= now:
                    schedule_time_today += timedelta(days=1)
                
                diff = schedule_time_today - now
                
                if diff < min_diff:
                    min_diff = diff
                    next_broadcast_time = schedule_time_today
                    next_campaign = s['campaign']

            if next_broadcast_time:
                hours, rem = divmod(min_diff.seconds, 3600)
                minutes, _ = divmod(rem, 60)
                msg += f"\n\n🕐 **下個廣播:** {next_broadcast_time:%Y-%m-%d %H:%M} (活動: `{next_campaign}`)\n"
                msg += f"⏱️ **倒數:** {hours} 小時 {minutes} 分鐘"
            else:
                msg += "\n\n⚠️ 無法計算下一個廣播時間。"
        await event.reply(msg)

    async def list_groups(self, event):
        if not self.config.target_groups:
            await event.reply("📋 無廣播目標。"); return
            
        # 嘗試更新群組名稱
        updated = False
        for group in self.config.target_groups:
            if group['title'].startswith('頻道/群組 ') or group['title'].startswith('ID '):
                try:
                    entity = await self.client.get_entity(group['id'])
                    if hasattr(entity, 'title'):
                        group['title'] = entity.title
                        updated = True
                except Exception as e:
                    print(f"無法更新群組 {group['id']} 的名稱: {e}")
        
        if updated:
            self.config.save_settings()
            
        message = "📋 廣播目標列表:\n\n" + "\n".join([
            f"{i}. {g['title']}\n   ID: `{g['id']}`\n" for i, g in enumerate(self.config.target_groups, 1)
        ])
        await event.reply(message)

    async def remove_group(self, event):
        try:
            index = int(event.pattern_match.group(1)) - 1
            if 0 <= index < len(self.config.target_groups):
                removed = self.config.target_groups.pop(index); self.config.save_settings()
                await event.reply(f"✅ 已移除: 「{removed['title']}」")
            else: await event.reply("❌ 無效編號。")
        except ValueError: await event.reply("❌ 請輸入數字。")

    async def my_groups(self, event):
        await event.reply("⏳ 正在掃描群組..."); groups = [f"• {d.title}\n  ID: `{d.id}`" async for d in self.client.iter_dialogs() if d.is_group or d.is_channel]
        response = "您所在的群組/頻道:\n\n" + "\n".join(groups) if groups else "找不到群組。"
        await event.reply(response)

    async def add_by_id(self, event):
        try:
            group_id = int(event.pattern_match.group(1)); entity = await self.client.get_entity(group_id)
            chat_info = {'id': entity.id, 'title': getattr(entity, 'title', f'ID {entity.id}'), 'type': 'group'}
            if not any(g['id'] == chat_info['id'] for g in self.config.target_groups):
                self.config.target_groups.append(chat_info); self.config.save_settings()
                await event.reply(f"✅ 已新增目標: 「{chat_info['title']}」")
            else: await event.reply(f"ℹ️ 「{chat_info['title']}」已在目標中。")
        except Exception as e: await event.reply(f"❌ 新增失敗: {e}")

    async def show_history(self, event):
        try:
            with open('broadcast_history.json', 'r', encoding='utf-8') as f: history = json.load(f)
            if not history: await event.reply("📊 無廣播歷史。"); return
            msg = "📊 **最近10次廣播歷史:**\n\n" + "\n".join([f"• **{r['time']}** ({'定時' if r.get('scheduled') else '手動'})\n  結果: {r['success_count']}/{r['total_count']} ({r['success_rate']})\n" for r in reversed(history[-10:])])
            await event.reply(msg)
        except FileNotFoundError: await event.reply("📊 找不到歷史檔案。")

    async def enable_broadcast(self, event):
        if not self.config.schedules: await event.reply("❌ 請先用 `/add_schedule` 新增排程。"); return
        self.config.enabled = True; self.config.save_settings(); self.scheduler.setup_schedule()
        await event.reply("✅ 所有排程已啟用。")

    async def disable_broadcast(self, event):
        self.config.enabled = False; self.config.save_settings(); self.scheduler.setup_schedule()
        await event.reply("⏸️ 所有排程已停用。")

    async def add_schedule(self, event):
        match = re.match(r'/add_schedule (\d{2}:\d{2}) (.+)', event.raw_text)
        if not match:
            await event.reply("❌ 用法錯誤。請使用 `/add_schedule HH:MM <活動名稱>`")
            return
        
        time_str = match.group(1)
        campaign_name = match.group(2).strip()

        # 檢查活動是否存在
        if campaign_name not in self.message_manager.list_campaigns():
            await event.reply(f"❌ 找不到活動 `{campaign_name}`。請使用 `/campaigns` 查看可用活動。")
            return

        # 檢查時間格式
        try:
            datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            await event.reply("❌ 時間格式錯誤。請使用 HH:MM (例如 10:30)。")
            return

        # 檢查是否已存在相同的時間和活動組合
        for s in self.config.schedules:
            if s['time'] == time_str and s['campaign'] == campaign_name:
                await event.reply(f"ℹ️ 排程 `{time_str}` 執行活動 `{campaign_name}` 已存在。")
                return

        self.config.schedules.append({'time': time_str, 'campaign': campaign_name})
        self.config.schedules.sort(key=lambda x: x['time']) # 依時間排序
        self.config.save_broadcast_config(is_startup=False)
        self.scheduler.setup_schedule() # 重新設定排程

        await event.reply(f"✅ 已新增排程: `{time_str}` 執行活動 `{campaign_name}`。")

    async def remove_schedule(self, event):
        match = re.match(r'/remove_schedule (\d{2}:\d{2}) (.+)', event.raw_text)
        if not match:
            await event.reply("❌ 用法錯誤。請使用 `/remove_schedule HH:MM <活動名稱>`")
            return
        
        time_str = match.group(1)
        campaign_name = match.group(2).strip()

        original_len = len(self.config.schedules)
        self.config.schedules = [s for s in self.config.schedules if not (s['time'] == time_str and s['campaign'] == campaign_name)]
        
        if len(self.config.schedules) < original_len:
            self.config.save_broadcast_config(is_startup=False)
            self.scheduler.setup_schedule() # 重新設定排程
            await event.reply(f"✅ 已移除排程: `{time_str}` 執行活動 `{campaign_name}`。")
        else:
            await event.reply(f"❌ 找不到排程 `{time_str}` 執行活動 `{campaign_name}`。")

    async def list_schedules(self, event):
        if not self.config.schedules:
            await event.reply("⏰ 目前沒有設定任何排程。")
            return
        
        message = "⏰ **目前排程列表:**\n\n"
        for i, s in enumerate(self.config.schedules, 1):
            message += f"{i}. 時間: `{s['time']}`, 活動: `{s['campaign']}`\n"
        
        message += "\n💡 使用 `/add_schedule HH:MM <活動名稱>` 新增排程。\n"
        message += "💡 使用 `/remove_schedule HH:MM <活動名稱>` 移除排程。"
        await event.reply(message)

    async def show_status(self, event):
        me = await self.client.get_me()
        await event.reply(f"""📊 **狀態報告**\n👤 用戶: {me.first_name}\n- 目標: {len(self.config.target_groups)} 個\n- 排程: {len(self.config.schedules)} 個\n- 狀態: {'啟用' if self.config.enabled else '停用'}盡""")

    async def show_info(self, event):
        """顯示所有設定資訊"""
        # 廣播目標
        target_groups_str = "\n".join([f"- `{g['title']}` (`{g['id']}`)" for g in self.config.target_groups]) or "未設定"
        
        # 廣播排程
        schedules_str = "\n".join([f"- `{s['time']}` (活動: `{s['campaign']}`)" for s in self.config.schedules]) or "未設定"
        
        # 排程狀態
        schedule_status = "✅ 啟用" if self.config.enabled else "⏸️ 停用"
        
        info_message = f"""ℹ️ **機器人完整資訊**\n\n**🎯 廣播目標:**\n{target_groups_str}\n\n**⏰ 廣播排程:**\n{schedules_str}\n\n**📅 排程狀態:** {schedule_status}\n"""
        await event.reply(info_message)

    async def show_help(self, event):
        await event.reply("""🤖 **指令說明**\n\n**👑 管理與成員**\n- `/list_admins`: 列出機器人管理員\n- `/add_admin <ID/@用戶名>`: 新增機器人管理員\n- `/remove_admin <ID/@用戶名>`: 移除機器人管理員\n- `/sync_admins`: **從控制群組同步管理員**\n- `/list_members`: 列出控制群組成員\n\n**⏰ 多任務排程**\n- `/add_schedule HH:MM <活動名稱>`: 新增排程\n- `/remove_schedule HH:MM <活動名稱>`: 移除排程\n- `/list_schedules`: 查看排程列表\n- `/enable` / `/disable`: 啟用/停用排程\n- `/schedule`: 查看排程狀態\n\n**🏢 廣播目標**\n- `/add`: 新增目前群組\n- `/add_by_id <ID>`: 透過 ID 新增群組\n- `/add_groups <ID1,ID2,...>`: 批量新增多個群組/頻道（用逗號分隔多個 ID）\n- `/list_groups`: 查看目標列表\n- `/remove <編號>`: 移除目標\n\n**📝 活動與測試**\n- `/campaigns`: 列出所有可用活動\n- `/preview <活動名稱>`: 預覽活動內容\n- `/test <活動名稱>`: 手動測試廣播\n\n**ℹ️ 系統**\n- `/status`: 查看狀態\n- `/history`: 查看歷史\n- `/info`: 顯示所有設定資訊""")