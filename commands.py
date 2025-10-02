import discord
from discord import app_commands
from database import (
    add_trigger_word,
    remove_trigger_word,
    get_user_triggers,
    toggle_notifications
)
from ui import AddMultipleWordsModal

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

    @bot.tree.command(name="help", description="Show information about the bot and its commands")
    async def help_command(interaction: discord.Interaction):
        """Show all available commands"""
        
        embed = discord.Embed(
            title="Discord Monitor Bot",
            description="Track keywords across servers you're in!",
            colour=discord.Colour.blue()
        )
        
        embed.add_field(
            name="Commands",
            value=(
                "`/watch <word>` - Add a single word to monitor\n"
                "`/watch-multiple` - Add multiple words at once\n"
                "`/unwatch <word>` - Remove a word from monitoring\n"
                "`/mywords` - List your monitored words\n"
                "`/toggle` - Enable/disable notifications\n"
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