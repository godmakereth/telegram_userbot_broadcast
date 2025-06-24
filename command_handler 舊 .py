from telethon import events
from datetime import datetime, timedelta
import json

class CommandHandler:
    """
    處理所有來自 Telegram 的使用者指令 (最終完整功能版)。
    """
    def __init__(self, client, config, broadcast_manager, scheduler, message_manager):
        self.client = client
        self.config = config
        self.broadcast_manager = broadcast_manager
        self.scheduler = scheduler
        self.message_manager = message_manager

    def register_handlers(self):
        # --- 管理員與群組成員管理 ---
        self.client.add_event_handler(self.list_admins, events.NewMessage(pattern='/list_admins', func=self._is_admin))
        self.client.add_event_handler(self.add_admin, events.NewMessage(pattern=r'/add_admin (.+)', func=self._is_admin))
        self.client.add_event_handler(self.remove_admin, events.NewMessage(pattern=r'/remove_admin (.+)', func=self._is_admin))
        self.client.add_event_handler(self.list_members, events.NewMessage(pattern='/list_members', func=self._is_admin))

        # --- 時間排程管理 ---
        self.client.add_event_handler(self.add_time, events.NewMessage(pattern=r'/add_time (\d{2}:\d{2})', func=self._is_admin))
        self.client.add_event_handler(self.remove_time, events.NewMessage(pattern=r'/remove_time (\d{2}:\d{2})', func=self._is_admin))
        self.client.add_event_handler(self.list_times, events.NewMessage(pattern='/list_times', func=self._is_admin))
        self.client.add_event_handler(self.clear_times, events.NewMessage(pattern='/clear_times', func=self._is_admin))
        
        # --- 廣播群組管理 ---
        self.client.add_event_handler(self.add_group, events.NewMessage(pattern='/add', func=self._is_admin))
        self.client.add_event_handler(self.list_groups, events.NewMessage(pattern='/list', func=self._is_admin))
        self.client.add_event_handler(self.remove_group, events.NewMessage(pattern=r'/remove (\d+)', func=self._is_admin))
        self.client.add_event_handler(self.my_groups, events.NewMessage(pattern='/my_groups', func=self._is_admin))
        self.client.add_event_handler(self.add_by_id, events.NewMessage(pattern=r'/add_by_id (-?\d+)', func=self._is_admin))

        # --- 其他指令 ---
        self.client.add_event_handler(self.show_schedule, events.NewMessage(pattern='/schedule', func=self._is_admin))
        self.client.add_event_handler(self.show_history, events.NewMessage(pattern='/history', func=self._is_admin))
        self.client.add_event_handler(self.enable_broadcast, events.NewMessage(pattern='/enable', func=self._is_admin))
        self.client.add_event_handler(self.disable_broadcast, events.NewMessage(pattern='/disable', func=self._is_admin))
        self.client.add_event_handler(self.list_files, events.NewMessage(pattern='/files', func=self._is_admin))
        self.client.add_event_handler(self.preview_message, events.NewMessage(pattern=r'/preview(?:\s+(.+))?', func=self._is_admin))
        self.client.add_event_handler(self.test_broadcast, events.NewMessage(pattern=r'/test(?:\s+(.+))?', func=self._is_admin))
        self.client.add_event_handler(self.show_status, events.NewMessage(pattern='/status', func=self._is_admin))
        self.client.add_event_handler(self.show_help, events.NewMessage(pattern='/help', func=self._is_admin))
        print("🦾 所有指令處理常式已註冊 (最終完整版)。")

    def _is_admin(self, event):
        return self.config.is_admin(event.sender_id)

    # --- 完整指令實作 ---

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

    async def add_admin(self, event):
        identifier = event.pattern_match.group(1).strip()
        try:
            user = await self.client.get_entity(identifier)
            if self.config.is_admin(user.id):
                await event.reply(f"ℹ️ **{user.first_name}** 已經是管理員了。")
                return

            new_admin = {"id": user.id, "name": user.first_name, "username": user.username or ""}
            self.config.admins.append(new_admin)
            self.config.save_admins()
            await event.reply(f"✅ 成功新增管理員: **{user.first_name}** (ID: `{user.id}`)")
        except Exception as e:
            await event.reply(f"❌ 新增失敗: 無法找到用戶 '{identifier}'。\n錯誤: {e}")

    async def remove_admin(self, event):
        identifier = event.pattern_match.group(1).strip()
        if len(self.config.admins) <= 1:
            await event.reply("❌ 無法移除最後一位管理員！")
            return

        try:
            user_to_remove = await self.client.get_entity(identifier)
            admin_found = next((admin for admin in self.config.admins if admin['id'] == user_to_remove.id), None)
            
            if admin_found:
                self.config.admins.remove(admin_found)
                self.config.save_admins()
                await event.reply(f"✅ 成功移除管理員: **{admin_found.get('name', '未知名稱')}** (ID: `{admin_found['id']}`)")
            else:
                await event.reply(f"❌ **{user_to_remove.first_name}** 不在管理員列表中。")
        except Exception as e:
            await event.reply(f"❌ 移除失敗: 無法找到用戶 '{identifier}'。\n錯誤: {e}")

    async def list_members(self, event):
        if not self.config.control_group:
            await event.reply("❌ 未設定控制群組。")
            return
        
        await event.reply("⏳ 正在獲取群組成員列表...")
        try:
            group = await self.client.get_entity(self.config.control_group)
            message = f"👥 **'{group.title}' 群組成員:**\n\n"
            count = 0
            async for member in self.client.iter_participants(group):
                count += 1
                admin_marker = "👑 (管理員)" if self.config.is_admin(member.id) else ""
                name = member.first_name or "無名稱"
                username_str = f"(@{member.username})" if member.username else ""
                message += f"• {name} {username_str} {admin_marker}\n  ID: `{member.id}`\n"
            
            message += f"\n總計: {count} 位成員。"
            await event.reply(message, parse_mode='md')
        except Exception as e:
            await event.reply(f"❌ 獲取成員列表失敗: {e}")

    async def add_time(self, event):
        time_input = event.pattern_match.group(1)
        if time_input in self.config.broadcast_times:
            await event.reply(f"ℹ️ 時間 `{time_input}` 已在排程中。")
            return
        
        self.config.broadcast_times.append(time_input)
        self.config.broadcast_times.sort()
        self.config.save_settings()
        self.scheduler.setup_schedule()
        await event.reply(f"✅ 已新增廣播時間: `{time_input}`。")

    async def remove_time(self, event):
        time_input = event.pattern_match.group(1)
        if time_input not in self.config.broadcast_times:
            await event.reply(f"❌ 找不到要移除的時間: `{time_input}`。")
            return
            
        self.config.broadcast_times.remove(time_input)
        self.config.save_settings()
        self.scheduler.setup_schedule()
        await event.reply(f"✅ 已移除廣播時間: `{time_input}`。")

    async def list_times(self, event):
        if not self.config.broadcast_times:
            await event.reply("⏰ 無廣播時間。\n💡 使用 `/add_time HH:MM` 新增。")
            return
        
        message = "⏰ **廣播時間列表:**\n\n" + "\n".join([f" - `{t}`" for t in self.config.broadcast_times])
        await event.reply(message)

    async def clear_times(self, event):
        self.config.broadcast_times = []
        self.config.enabled = False
        self.config.save_settings()
        self.scheduler.setup_schedule()
        await event.reply("🗑️ 已清除所有廣播時間並停用。")

    async def show_schedule(self, event):
        status = "✅ 啟用" if self.config.enabled else "⏸️ 停用"
        msg = f"📅 **排程資訊**\n\n🔄 狀態: **{status}**\n"

        if not self.config.broadcast_times:
            msg += "\n⏰ 無排程。\n💡 使用 `/add_time HH:MM` 新增。"
            await event.reply(msg)
            return

        msg += "\n⏰ **排程時間點:**\n" + "\n".join([f" - `{t}`" for t in self.config.broadcast_times])

        if self.config.enabled:
            now = datetime.now()
            # 處理沒有排程的邊界情況
            if not self.config.broadcast_times:
                 await event.reply(msg)
                 return
            
            next_broadcast = min(
                (now.replace(hour=int(t.split(':')[0]), minute=int(t.split(':')[1]), second=0) + timedelta(days=1)
                if now.replace(hour=int(t.split(':')[0]), minute=int(t.split(':')[1]), second=0) <= now else
                now.replace(hour=int(t.split(':')[0]), minute=int(t.split(':')[1]), second=0))
                for t in self.config.broadcast_times
            )
            countdown = next_broadcast - now
            hours, rem = divmod(countdown.seconds, 3600)
            minutes, _ = divmod(rem, 60)
            msg += f"\n\n🕐 **下個廣播:** {next_broadcast:%Y-%m-%d %H:%M}\n"
            msg += f"⏱️ **倒數:** {hours} 小時 {minutes} 分鐘"
        await event.reply(msg)

    async def add_group(self, event):
        chat = await event.get_chat()
        chat_info = {'id': chat.id, 'title': getattr(chat, 'title', f'對話 {chat.id}'), 'type': 'group'}
        if not any(g['id'] == chat_info['id'] for g in self.config.target_groups):
            self.config.target_groups.append(chat_info)
            self.config.save_settings()
            await event.reply(f"✅ 已新增廣播目標: 「{chat_info['title']}」")
        else:
            await event.reply(f"ℹ️ 「{chat_info['title']}」已在目標中。")

    async def list_groups(self, event):
        if not self.config.target_groups:
            await event.reply("📋 無廣播目標。")
            return
        message = "📋 **廣播目標列表:**\n\n" + "\n".join([f"{i}. {g['title']}\n   ID: `{g['id']}`\n" for i, g in enumerate(self.config.target_groups, 1)])
        await event.reply(message)

    async def remove_group(self, event):
        try:
            index = int(event.pattern_match.group(1)) - 1
            if 0 <= index < len(self.config.target_groups):
                removed = self.config.target_groups.pop(index)
                self.config.save_settings()
                await event.reply(f"✅ 已移除: 「{removed['title']}」")
            else:
                await event.reply("❌ 無效編號。")
        except ValueError:
            await event.reply("❌ 請輸入數字。")

    async def my_groups(self, event):
        await event.reply("⏳ 正在掃描群組...")
        groups = [f"• {d.title}\n  ID: `{d.id}`" async for d in self.client.iter_dialogs() if d.is_group or d.is_channel]
        response = "您所在的群組/頻道:\n\n" + "\n".join(groups) if groups else "找不到群組。"
        await event.reply(response)

    async def add_by_id(self, event):
        try:
            group_id = int(event.pattern_match.group(1))
            entity = await self.client.get_entity(group_id)
            chat_info = {'id': entity.id, 'title': getattr(entity, 'title', f'ID {entity.id}'), 'type': 'group'}
            if not any(g['id'] == chat_info['id'] for g in self.config.target_groups):
                self.config.target_groups.append(chat_info)
                self.config.save_settings()
                await event.reply(f"✅ 已新增目標: 「{chat_info['title']}」")
            else:
                await event.reply(f"ℹ️ 「{chat_info['title']}」已在目標中。")
        except Exception as e:
            await event.reply(f"❌ 新增失敗: {e}")

    async def show_history(self, event):
        try:
            with open('broadcast_history.json', 'r', encoding='utf-8') as f:
                history = json.load(f)
            if not history:
                await event.reply("📊 無廣播歷史。")
                return
            msg = "📊 **最近10次廣播歷史:**\n\n" + "\n".join([f"• **{r['time']}** ({'定時' if r.get('scheduled') else '手動'})\n  結果: {r['success_count']}/{r['total_count']} ({r['success_rate']})\n" for r in reversed(history[-10:])])
            await event.reply(msg)
        except FileNotFoundError:
            await event.reply("📊 找不到歷史檔案。")

    async def enable_broadcast(self, event):
        if not self.config.broadcast_times:
            await event.reply("❌ 請先用 `/add_time` 新增時間。")
            return
        self.config.enabled = True
        self.config.save_settings()
        self.scheduler.setup_schedule()
        await event.reply("✅ 所有排程已啟用。")

    async def disable_broadcast(self, event):
        self.config.enabled = False
        self.config.save_settings()
        self.scheduler.setup_schedule()
        await event.reply("⏸️ 所有排程已停用。")

    async def list_files(self, event):
        files = self.message_manager.list_message_files()
        default = self.config.default_message_file
        if not files:
            await event.reply("📁 找不到文案檔案。")
            return
        msg = "📁 **可用文案檔:**\n\n" + "\n".join([f"• `{f}` {'⭐' if f == default else ''}" for f in files])
        await event.reply(msg)

    async def preview_message(self, event):
        fn_input = event.pattern_match.group(1)
        fn = (fn_input.strip() if fn_input else self.config.default_message_file)
        if not fn.endswith('.txt'): fn += '.txt'
        content = self.message_manager.load_message(fn)
        await event.reply(f"📄 **預覽: `{fn}`**\n\n---\n\n{content}")

    async def test_broadcast(self, event):
        fn_input = event.pattern_match.group(1)
        fn = (fn_input.strip() if fn_input else self.config.default_message_file)
        if not fn.endswith('.txt'): fn += '.txt'
        await event.reply(f"🧪 正在測試廣播 `{fn}`...")
        await self.broadcast_manager.send_broadcast(fn)

    async def show_status(self, event):
        me = await self.client.get_me()
        await event.reply(f"""📊 **狀態報告**
👤 用戶: {me.first_name}
- 目標: {len(self.config.target_groups)} 個
- 排程: {len(self.config.broadcast_times)} 個
- 狀態: {'啟用' if self.config.enabled else '停用'}""")

    async def show_help(self, event):
        await event.reply("""🤖 **指令說明**

**👑 管理與成員**
- `/list_admins`: 列出管理員
- `/add_admin <ID/@用戶名>`: 新增管理員
- `/remove_admin <ID/@用戶名>`: 移除管理員
- `/list_members`: 列出控制群組成員

**⏰ 多時間排程**
- `/add_time HH:MM`: 新增廣播時間
- `/remove_time HH:MM`: 移除廣播時間
- `/list_times`: 查看時間列表
- `/clear_times`: 清除所有時間
- `/enable` / `/disable`: 啟用/停用排程
- `/schedule`: 查看排程狀態

**🏢 廣播目標**
- `/add`: 新增目前群組
- `/list`: 查看目標列表
- `/remove <編號>`: 移除目標

**📝 文案與測試**
- `/files`: 列出文案檔
- `/preview [檔名]`: 預覽文案
- `/test [檔名]`: 測試廣播

**ℹ️ 系統**
- `/status`: 查看狀態
- `/history`: 查看歷史""")
