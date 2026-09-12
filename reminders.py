import asyncio
import discord
from database import get_due_reminders, mark_reminder_delivered

async def start_reminder_loop(bot):
    """Background task that delivers due reminders every 30 seconds"""
    print("Starting reminder loop...")
    while True:
        try:
            due_reminders = get_due_reminders()
            for reminder_id, user_id, title, note, remind_at in due_reminders:
                try:
                    user = await bot.fetch_user(user_id)
                    content = f"⏰ **Reminder: {title}**"
                    if note:
                        content += f"\n{note}"
                    await user.send(content)
                    mark_reminder_delivered(reminder_id)
                    print(f"  -> Delivered reminder #{reminder_id} to {user.name}")
                except discord.Forbidden:
                    print(f"  -> Could not DM user {user_id} for reminder #{reminder_id} (DMs disabled), dropping")
                    mark_reminder_delivered(reminder_id)
                except Exception as e:
                    print(f"  -> Error delivering reminder #{reminder_id}: {e}")
        except Exception as e:
            print(f"Error in reminder loop: {e}")
        await asyncio.sleep(30)