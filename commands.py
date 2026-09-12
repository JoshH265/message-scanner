import discord
from discord import app_commands
import re
from datetime import datetime, timezone, timedelta
from database import (
    add_trigger_word,
    remove_trigger_word,
    get_user_triggers,
    toggle_notifications,
    add_reminder,
    get_user_reminders,
    cancel_reminder
)
from ui import AddMultipleWordsModal

def parse_duration(duration: str):
    """Parse a duration string like '1h30m', '2h', '45m', '1d 4h' into a timedelta."""
    duration = duration.strip().lower().replace(' ', '')
    if not duration:
        return None
    pattern = r'^(\d+d)?(\d+h)?(\d+m)?(\d+s)?$'
    match = re.match(pattern, duration)
    if not match or not any(match.groups()):
        return None
    days = int(match.group(1)[:-1]) if match.group(1) else 0
    hours = int(match.group(2)[:-1]) if match.group(2) else 0
    minutes = int(match.group(3)[:-1]) if match.group(3) else 0
    seconds = int(match.group(4)[:-1]) if match.group(4) else 0
    total = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    if total <= timedelta(0):
        return None
    return total

def setup_commands(bot):
    """Register all slash commands with the bot"""

    # Slash Commands
    @bot.tree.command(name="watch", description="Add a single word to monitor")
    @app_commands.describe(word="The word you want to watch for")
    async def watch_command(interaction: discord.Interaction, word: str):
        """Add a word to your monitoring list"""
        
        # Clean the word
        word = word.strip().lower()
        
        if not word:
            await interaction.response.send_message("Please provide a valid word!", ephemeral=True)
            return
        
        # Only take first word if multiple provided
        word = word.split()[0]
        
        success = add_trigger_word(interaction.user.id, word)
        
        if success:
            await interaction.response.send_message(f"Now watching for: **{word}**", ephemeral=True)
            print(f"User {interaction.user.name} added trigger word: {word}")
        else:
            await interaction.response.send_message(f"You're already watching **{word}**", ephemeral=True)

    #### 
    @bot.tree.command(name="watch-multiple", description="Add multiple words to monitor at once")
    async def watch_multiple_command(interaction: discord.Interaction):
        """Open a modal to add multiple words"""
        modal = AddMultipleWordsModal()
        await interaction.response.send_modal(modal)

    ####
    @bot.tree.command(name="unwatch", description="Remove a word from monitoring")
    @app_commands.describe(word="The word you want to stop watching")
    async def unwatch_command(interaction: discord.Interaction, word: str):
        """Remove a word from your monitoring list"""
        
        word = word.strip().lower().split()[0]
        
        removed = remove_trigger_word(interaction.user.id, word)
        
        if removed:
            await interaction.response.send_message(f"No longer watching: **{word}**", ephemeral=True)
            print(f"User {interaction.user.name} removed trigger word: {word}")
        else:
            await interaction.response.send_message(f"You weren't watching **{word}**", ephemeral=True)


    ####
    @bot.tree.command(name="mywords", description="List all words you're currently monitoring")
    async def mywords_command(interaction: discord.Interaction):
        """List all words you're currently monitoring"""
        
        triggers = get_user_triggers(interaction.user.id)
        
        if triggers:
            word_list = ', '.join(f"**{word}**" for word in triggers)
            await interaction.response.send_message(
                f"**You're currently watching ({len(triggers)} word(s)):**\n{word_list}", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "You're not watching any words yet. Use `/watch` or `/watch-multiple` to start monitoring!", 
                ephemeral=True
            )

    ####
    @bot.tree.command(name="toggle", description="Toggle notifications on/off")
    async def toggle_command(interaction: discord.Interaction):
        """Toggle notifications on/off"""
        
        enabled = toggle_notifications(interaction.user.id)
        
        if enabled:
            await interaction.response.send_message("Notifications **enabled**", ephemeral=True)
        else:
            await interaction.response.send_message("Notifications **disabled**", ephemeral=True)

    ####
    @bot.tree.command(name="remind", description="Set a reminder that will DM you later")
    @app_commands.describe(
        duration="How long until the reminder (e.g. 1h, 30m, 2h30m, 1d 4h)",
        title="A short title for the reminder",
        note="Optional extra details (optional)"
    )
    async def remind_command(interaction: discord.Interaction, duration: str, title: str, note: str = None):
        """Set a reminder for the user"""
        delta = parse_duration(duration)
        if not delta:
            await interaction.response.send_message(
                "Invalid duration! Use a format like `1h`, `30m`, `2h30m`, `1d 4h`, or `45s`.",
                ephemeral=True
            )
            return
        
        title = title.strip()
        if not title:
            await interaction.response.send_message("Please provide a title for the reminder!", ephemeral=True)
            return
        
        remind_at = datetime.now(timezone.utc) + delta
        reminder_id = add_reminder(interaction.user.id, remind_at, title, note)
        
        timestamp = int(remind_at.timestamp())
        response = f"✅ Reminder **#{reminder_id}** set — **{title}** — <t:{timestamp}:R> (<t:{timestamp}:f>)"
        if note:
            response += f"\n*Note: {note}*"
        await interaction.response.send_message(response, ephemeral=True)
        print(f"User {interaction.user.name} set reminder #{reminder_id}: {title} in {duration}")

    ####
    @bot.tree.command(name="reminders", description="List your upcoming reminders")
    async def reminders_command(interaction: discord.Interaction):
        """List all upcoming reminders for the user"""
        reminders = get_user_reminders(interaction.user.id)
        
        if not reminders:
            await interaction.response.send_message(
                "You have no upcoming reminders. Use `/remind <duration> <title>` to set one!",
                ephemeral=True
            )
            return
        
        lines = []
        for reminder_id, title, note, remind_at in reminders:
            timestamp = int(remind_at.timestamp())
            line = f"**#{reminder_id}** — {title} — <t:{timestamp}:R>"
            if note:
                line += f"\n    *{note}*"
            lines.append(line)
        
        await interaction.response.send_message(
            f"**Your reminders ({len(reminders)}):**\n" + "\n".join(lines),
            ephemeral=True
        )

    ####
    @bot.tree.command(name="cancelreminder", description="Cancel one of your reminders")
    @app_commands.describe(reminder_id="The reminder ID (from /remind or /reminders)")
    async def cancelreminder_command(interaction: discord.Interaction, reminder_id: int):
        """Cancel a reminder by ID"""
        removed = cancel_reminder(interaction.user.id, reminder_id)
        
        if removed:
            await interaction.response.send_message(f"✅ Reminder **#{reminder_id}** cancelled.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ Couldn't find reminder **#{reminder_id}** (or it's not yours).",
                ephemeral=True
            )

    ####

    @bot.tree.command(name="help", description="Show information about the bot and its commands")
    async def help_command(interaction: discord.Interaction):
        """Show all available commands"""
        
        embed = discord.Embed(
            title="Discord Monitor Bot",
            description="Track keywords across servers and set reminders!",
            colour=discord.Colour.blue()
        )
        
        embed.add_field(
            name="Message Monitoring Commands",
            value=(
                "`/watch <word>` - Add a single word to monitor\n"
                "`/watch-multiple` - Add multiple words at once\n"
                "`/unwatch <word>` - Remove a word from monitoring\n"
                "`/mywords` - List your monitored words\n"
                "`/toggle` - Enable/disable notifications"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Reminder Commands",
            value=(
                "`/remind <duration> <title> [note]` - Set a reminder\n"
                "`/reminders` - List your upcoming reminders\n"
                "`/cancelreminder <id>` - Cancel a reminder"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Other Commands",
            value=(
                "`/help` - Show this help message"
            ),
            inline=False
        )
        
        embed.add_field(
            name="How it works",
            value="When someone mentions one of your watched words, you'll receive a DM with the message details!",
            inline=False
        )
        
        embed.add_field(
            name="Privacy",
            value="You'll only be notified for messages in servers you're a member of and channels you can see.",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)