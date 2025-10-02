
import discord
from discord.ext import commands
from discord import app_commands
import psycopg2
from psycopg2 import pool
import logging
import os

# from dotenv import load_dotenv
import psycopg2.pool

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

TOKEN = os.environ.get('BOT_TOKEN')
DATBASE_URL = os.environ.get('DATABASE_URL')

print("Starting bot...")
# Not needed anymore shifting to a database and multiple users
# print(f"Monitoring for: {TRIGGER_WORDS}")
# print(f"Will ping user ID: {USER_ID}")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


bot = commands.Bot(command_prefix='/', intents=intents)

# Database connection pool
connection_pool = None

def init_connection_pool():
    """Initialise the database connection pool"""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            DATBASE_URL
        )
        print("Database connection pool created")

    except Exception as e:
        print(f"Error creating connection pool: {e}")
        raise

def get_db_connection():
    """Get a connection from the pool"""
    return connection_pool.getconn()


def return_db_connection(conn):
    """Return connection to the pool"""    
    connection_pool.putconn(conn)

def init_db():
    """Initialise the database with required tables"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_triggers (
                user_id BIGINT,
                trigger_word TEXT,
                PRIMARY KEY (user_id, trigger_word)
            )
        ''')
        
        # Create table for user settings
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id BIGINT PRIMARY KEY,
                notifications_enabled BOOLEAN DEFAULT TRUE
            )
        ''')
        
        # Create index for faster lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_trigger_word 
            ON user_triggers(trigger_word)
        ''')

        conn.commit()
        print("Database tables initialised")
    except Exception as e:
        print(f"Error initialising BB {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        return_db_connection(conn)

###################

def get_user_triggers(user_id):
    """Get all trigger words for a specific user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT trigger_word FROM user_triggers WHERE user_id = %s', (user_id,))
        triggers = [row[0] for row in cursor.fetchall()]
        return triggers
    finally:
        cursor.close()
        return_db_connection(conn)

def get_all_users_monitoring(word):
    """Get all users who are monitoring a specific word"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM user_triggers WHERE trigger_word = %s', (word.lower(),))
        users = [row[0] for row in cursor.fetchall()]
        return users
    finally:
        cursor.close()
        return_db_connection(conn)

def add_trigger_word(user_id, word):
    """Add a trigger word for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO user_triggers (user_id, trigger_word) VALUES (%s, %s)',
                          (user_id, word.lower()))
            conn.commit()
            return True
        except psycopg2.IntegrityError:
            conn.rollback()
            return False  # Word already exists
    finally:
        cursor.close()
        return_db_connection(conn)

def add_multiple_trigger_words(user_id, words):
    """Add multiple trigger words for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        added = []
        duplicates = []
        
        for word in words:
            word = word.strip().lower()
            if not word:
                continue
            try:
                cursor.execute('INSERT INTO user_triggers (user_id, trigger_word) VALUES (%s, %s)',
                              (user_id, word))
                added.append(word)
            except psycopg2.IntegrityError:
                duplicates.append(word)
                conn.rollback()
        
        conn.commit()
        return added, duplicates
    finally:
        cursor.close()
        return_db_connection(conn)
    

def remove_trigger_word(user_id, word):
    """Remove a trigger word for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_triggers WHERE user_id = %s AND trigger_word = %s',
                      (user_id, word.lower()))
        removed = cursor.rowcount > 0
        conn.commit()
        return removed
    finally:
        cursor.close()
        return_db_connection(conn)

def is_notifications_enabled(user_id):
    """Check if notifications are enabled for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT notifications_enabled FROM user_settings WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else True  # Default to enabled
    finally:
        cursor.close()
        return_db_connection(conn)

def toggle_notifications(user_id):
    """Toggle notifications on/off for a user"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Get current state
        cursor.execute('SELECT notifications_enabled FROM user_settings WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        
        if result:
            new_state = not result[0]
            cursor.execute('UPDATE user_settings SET notifications_enabled = %s WHERE user_id = %s',
                          (new_state, user_id))
        else:
            new_state = False  # If no record, they want to disable (default is enabled)
            cursor.execute('INSERT INTO user_settings (user_id, notifications_enabled) VALUES (%s, %s)',
                          (user_id, new_state))
        
        conn.commit()
        return new_state
    finally:
        cursor.close()
        return_db_connection(conn)

##########################



@bot.event
async def on_ready():
    """Called when the bot successfully connects to Discord"""
    init_connection_pool()
    init_db()

        # Sync slash commands (NEW!)
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

@bot.event
async def on_message(message):
    """Called whenever a message is sent in a channel the bot can see"""

    # print(f"Message received from {message.author}: {message.content}")

    # Ignores the bots messages and own users messages
    if message.author == bot.user:
        return
    # if message.author.id == USER_ID:
    #     return

    print(f"Message received from {message.author}: {message.content}")
    message_lower = message.content.lower()
    words_in_message = message_lower.split()

    # Track which users to notify and what words triggered
    notifications = {}  # {user_id: [list of triggered words]}

    for word in words_in_message:
        # Clean the word
        clean_word = ''.join(char for char in word if char.isalnum())
        if not clean_word:
            continue

        monitoring_users = get_all_users_monitoring(clean_word)
        for user_id in monitoring_users:
            # if user_id == message.author.id:
            #     continue

            if not is_notifications_enabled(user_id):
                continue
            if user_id not in notifications:
                notifications[user_id] = []
            notifications[user_id].append(clean_word)

    # Send notifaction for message 
    for user_id, trigger_words in notifications.items():
        try:
            # Check if the message is in a server
            if message.guild:
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
                # f"🔔 **Keyword Alert!**\n\n"
                # f"**Word(s) detected:** {', '.join(set(trigger_words))}\n"
                f"**From:** ({message.author.mention})\n" # {message.author.name} <- add this back in if i want it
                # f"**Server:** {message.guild.name if message.guild else 'DM'}\n"
                f"**Channel:** {message.channel.mention if hasattr(message.channel, 'mention') else 'DM'}\n"
                f"**Message:** {message.content[:200]}\n\n"
                f"[Link to message]({message.jump_url})"
            )
            
            await user.send(dm_message)
            print(f"  -> Sent alert to {user.name} for words: {trigger_words}")


        except discord.Forbidden:
            print(f" -> could not DM user {user_id} (DMs disabled)")
        except Exception as e:
            print(f" Error sending DM to {user_id}: {e}")

    await bot.process_commands(message)


# # Command: Add trigger words
# @bot.command(name='w')
# async def add_word(ctx, *, word: str):
#     """Add a word to monitoring list
#     Usage: !watch <word>
#     """
#     if not word:
#         await ctx.send("Please provide a word")
#         return
    
#     word = word.split()[0].lower()
#     success = add_trigger_word(ctx.author.id, word)

#     if success:
#         await ctx.send(f"Now watching for: {word}")
#         print(f"User {ctx.author.name} added trigger word: {word}")

#     else:
#         await ctx.send("Watching weord: **{word}**")

# # Command: Remove a trigger word
# @bot.command(name='uw')
# async def remove_word(ctx, *, word: str):
#     """Remove a word from your monitoring list
#     Usage: !unwatch <word>
#     """
#     if not word:
#         await ctx.send("Please provide a word to unwatch. Usage: `!unwatch <word>`")
#         return
    
#     word = word.split()[0].lower()
    
#     removed = remove_trigger_word(ctx.author.id, word)
    
#     if removed:
#         await ctx.send(f"✅ No longer watching: **{word}**")
#         print(f"User {ctx.author.name} removed trigger word: {word}")
#     else:
#         await ctx.send(f"You weren't watching **{word}**")

# # Command: List your trigger words
# @bot.command(name='mw')
# async def list_words(ctx):
#     """List all words you're currently monitoring
#     Usage: !mywords
#     """
#     triggers = get_user_triggers(ctx.author.id)
    
#     if triggers:
#         word_list = ', '.join(f"**{word}**" for word in triggers)
#         await ctx.send(f"📝 You're currently watching: {word_list}")
#     else:
#         await ctx.send("You're not watching any words yet. Use `!watch <word>` to start monitoring!")

# # Command: Toggle notifications
# @bot.command(name='toggle')
# async def toggle_notifs(ctx):
#     """Toggle notifications on/off
#     Usage: !toggle
#     """
#     enabled = toggle_notifications(ctx.author.id)
    
#     if enabled:
#         await ctx.send("🔔 Notifications **enabled**")
#     else:
#         await ctx.send("🔕 Notifications **disabled**")

# # Command: Help
# @bot.command(name='help')
# async def help_command(ctx):
#     """Show all available commands"""
#     embed = discord.Embed(
#         title="Discord Monitor Bot - Commands",
#         description="Track keywords across servers you're in!",
#         colour=discord.Colour.blue()
#     )
    
#     embed.add_field(
#         name="Commands",
#         value=(
#             "`!w <word>` - Add a word to monitor\n"
#             "`!uw<word>` - Remove a word from monitoring\n"
#             "`!mw` - List your monitored words\n"
#             "`!toggle` - Enable/disable notifications\n"
#             "`!help` - Show this help message"
#         ),
#         inline=False
#     )
    
#     embed.add_field(
#         name="How it works",
#         value="When someone mentions one of your watched words in a server you're in, you'll receive a DM with the message details!",
#         inline=False
#     )
    
#     await ctx.send(embed=embed)

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
        await interaction.response.send_message(f"✅ Now watching for: **{word}**", ephemeral=True)
        print(f"User {interaction.user.name} added trigger word: {word}")
    else:
        await interaction.response.send_message(f"⚠️ You're already watching **{word}**", ephemeral=True)

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
        await interaction.response.send_message(f"✅ No longer watching: **{word}**", ephemeral=True)
        print(f"User {interaction.user.name} removed trigger word: {word}")
    else:
        await interaction.response.send_message(f"⚠️ You weren't watching **{word}**", ephemeral=True)


####
@bot.tree.command(name="mywords", description="List all words you're currently monitoring")
async def mywords_command(interaction: discord.Interaction):
    """List all words you're currently monitoring"""
    
    triggers = get_user_triggers(interaction.user.id)
    
    if triggers:
        word_list = ', '.join(f"**{word}**" for word in triggers)
        await interaction.response.send_message(
            f"📝 **You're currently watching ({len(triggers)} word(s)):**\n{word_list}", 
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
        await interaction.response.send_message("🔔 Notifications **enabled**", ephemeral=True)
    else:
        await interaction.response.send_message("🔕 Notifications **disabled**", ephemeral=True)

####

@bot.tree.command(name="help", description="Show information about the bot and its commands")
async def help_command(interaction: discord.Interaction):
    """Show all available commands"""
    
    embed = discord.Embed(
        title="🔔 Discord Monitor Bot",
        description="Track keywords across servers you're in!",
        colour=discord.Colour.blue()
    )
    
    embed.add_field(
        name="📝 Commands",
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
        name="🔔 How it works",
        value="When someone mentions one of your watched words, you'll receive a DM with the message details!",
        inline=False
    )
    
    embed.add_field(
        name="🔒 Privacy",
        value="You'll only be notified for messages in servers you're a member of and channels you can see.",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)




# Run the bot
print("\nAttempting to connect to Discord...")
try:
    bot.run(TOKEN)
except discord.LoginFailure:
    print("\nERROR: Invalid token. Please check your bot token is correct.")
except Exception as e:
    print(f"\nERROR: {e}")
finally:
    # Close the connection pool when shutting down
    if connection_pool:
        connection_pool.closeall()
        print("Database connections closed")

        

class AddMultipleWordsModal(discord.ui.Modal, title='Add Multiple Words'):
    words_input = discord.ui.TextInput(
        label='Words to Watch',
        placeholder='Enter words separated by commas (e.g., meeting, urgent, help)',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Parse the input
        words_list = [word.strip() for word in self.words_input.value.split(',')]
        words_list = [w for w in words_list if w]  # Remove empty strings
        
        if not words_list:
            await interaction.response.send_message("No valid words provided!", ephemeral=True)
            return
        
        # Add words to database
        added, duplicates = add_multiple_trigger_words(interaction.user.id, words_list)
        
        # Build response message
        response_parts = []
        
        if added:
            response_parts.append(f"✅ **Added {len(added)} word(s):** {', '.join(f'`{w}`' for w in added)}")
        
        if duplicates:
            response_parts.append(f"⚠️ **Already watching:** {', '.join(f'`{w}`' for w in duplicates)}")
        
        if not added and not duplicates:
            response_parts.append("❌ No words were added.")
        
        await interaction.response.send_message('\n'.join(response_parts), ephemeral=True)
        print(f"User {interaction.user.name} added multiple words: {added}")


bot.run(TOKEN)