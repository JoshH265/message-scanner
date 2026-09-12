
import discord
from discord.ext import commands
import logging
import os
import asyncio

# Import our modules
from database import (
    init_connection_pool,
    init_db,
    get_all_users_monitoring,
    is_notifications_enabled
)
from commands import setup_commands

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Get configuration from environment variables
TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')

print("Starting bot...")
print(f"DATABASE_URL exists: {DATABASE_URL is not None}")

if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)

async def wait_for_database(max_attempts=10, delay=5):
    """Retry DB connection until it succeeds so transient startup failures don't kill the bot."""
    for attempt in range(1, max_attempts + 1):
        try:
            init_connection_pool()
            init_db()
            print("Database ready")
            return True
        except Exception as e:
            print(f"Database not ready (attempt {attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                await asyncio.sleep(delay)
    return False

@bot.event
async def on_ready():
    """Called when the bot successfully connects to Discord"""
    # Register and sync slash commands first so they work even if the DB is down
    setup_commands(bot)
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Connected to {len(bot.guilds)} server(s)')
    for guild in bot.guilds:
        print(f'  - {guild.name} (ID: {guild.id})')
    
    await wait_for_database()

@bot.event
async def on_message(message):
    """Called whenever a message is sent in a channel the bot can see"""
    
    # Ignore messages from bots
    if message.author.bot:
        return
    
    print(f"Message received from {message.author}: {message.content}")
    
    notifications = {}
    try:
        # Convert message to lowercase for checking
        message_lower = message.content.lower()
        
        # Extract all words from the message
        words_in_message = message_lower.split()
        
        # Check each word in the message
        for word in words_in_message:
            # Clean the word (remove punctuation)
            clean_word = ''.join(char for char in word if char.isalnum())
            if not clean_word:
                continue
                
            # Find all users monitoring this word
            monitoring_users = get_all_users_monitoring(clean_word)
            
            for user_id in monitoring_users:
                # Check if they have notifications enabled
                if not is_notifications_enabled(user_id):
                    continue
                
                if user_id not in notifications:
                    notifications[user_id] = []
                notifications[user_id].append(clean_word)
    except Exception as e:
        print(f"Error checking triggers for message: {e}")
    
    # Send notifications
    for user_id, triggered_words in notifications.items():
        try:
            # Check if the message is in a server (guild)
            if message.guild:
                # Check if the user is a member of this server
                member = message.guild.get_member(user_id)
                if not member:
                    print(f"  -> User {user_id} not in server {message.guild.name}, skipping notification")
                    continue
                
                # Check if the user can see the channel where the message was sent
                channel_permissions = message.channel.permissions_for(member)
                if not channel_permissions.read_messages:
                    print(f"  -> User {member.name} cannot see channel {message.channel.name}, skipping notification")
                    continue
            
            user = await bot.fetch_user(user_id)
            
            # Create the DM message
            dm_message = (
                f"**Alert!**\n\n"
                f"**From:** {message.author.name} ({message.author.mention})\n"
                f"**Server:** {message.guild.name if message.guild else 'DM'}\n"
                f"**Channel:** {message.channel.mention if hasattr(message.channel, 'mention') else 'DM'}\n"
                f"**Message:** {message.content[:200]}\n\n"
                f"[Jump to message]({message.jump_url})"
            )
            
            await user.send(dm_message)
            print(f"  -> Sent alert to {user.name} for words: {triggered_words}")
            
        except discord.Forbidden:
            print(f"  -> Could not DM user {user_id} (DMs disabled or bot blocked)")
        except Exception as e:
            print(f"  -> Error sending DM to {user_id}: {e}")
    
    # Allow commands to work
    await bot.process_commands(message)

# Run the bot
print("\nAttempting to connect to Discord...")
try:
    bot.run(TOKEN)
except discord.LoginFailure:
    print("\nERROR: Invalid token. Please check your bot token is correct.")
except Exception as e:
    print(f"\nERROR: {e}")