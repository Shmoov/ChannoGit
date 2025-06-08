import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
import random
import asyncio
import aiosqlite
import time
from pathlib import Path
from backup_db import backup_database

# Set up logging
LOG_DIR = Path('data/logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

# File handler with rotation
file_handler = RotatingFileHandler(
    LOG_DIR / 'channobot.log',
    maxBytes=1024 * 1024,  # 1MB
    backupCount=5
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Bot setup
intents = discord.Intents.default()  # Start with default intents
intents.members = True  # Needed to track member activity
intents.message_content = True  # Needed to read message content
intents.voice_states = True  # Needed for voice channel tracking
intents.guilds = True  # Needed for server access
intents.guild_messages = True  # Needed for commands
intents.guild_reactions = True  # Needed for reactions
intents.presences = True  # Needed for member status

# Blackjack game state
active_games = {}

class CustomHelpCommand(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = discord.Embed(
            title="🤖 ChannoBot Commands",
            description="Here are all the available commands:",
            color=discord.Color.blue()
        )

        # Points & Info
        embed.add_field(
            name="💰 Points & Info",
            value=(
                "`!points` - Check your current points\n"
                "`!leaderboard` - Show points leaderboard\n"
                "`!rewards` - Show available rewards"
            ),
            inline=False
        )

        # Games & Betting
        embed.add_field(
            name="🎮 Games & Betting",
            value=(
                "`!blackjack <amount>` - Play blackjack against the dealer\n"
                "`!flipbet @user <amount>` - Challenge someone to a coin flip\n"
                "`!custombet @player1 @player2 <amount> <description>` - Create a custom bet between two players"
            ),
            inline=False
        )

        # Voice Rewards
        embed.add_field(
            name="🎤 Voice Rewards",
            value=(
                "Join voice channels to earn points!\n"
                "• 1 point per minute in voice\n"
                "• Must be unmuted to earn points\n"
                "• AFK users don't earn points"
            ),
            inline=False
        )

        # Fun Commands
        embed.add_field(
            name="😈 Fun Commands",
            value=(
                "`!example` - Buy 2 minutes of auto-disconnect for a random person in your voice channel (Cost: 200000/number of people in call)"
            ),
            inline=False
        )

        await self.get_destination().send(embed=embed)

    async def send_command_help(self, command):
        embed = discord.Embed(
            title=f"Command: {command.name}",
            description=command.help or "No description available.",
            color=discord.Color.blue()
        )
        
        if command.aliases:
            embed.add_field(name="Aliases", value=", ".join(command.aliases), inline=False)
        
        usage = f"!{command.name}"
        if command.signature:
            usage += f" {command.signature}"
        embed.add_field(name="Usage", value=f"```\n{usage}\n```", inline=False)
        
        await self.get_destination().send(embed=embed)

# Initialize bot with custom help command
bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=CustomHelpCommand()
)
logger.info("Bot initialized with intents")

# SQLite setup
async def setup_database():
    try:
        # Backup existing database if it exists
        if Path(bot.db_path).exists():
            backup_database()
            logger.info("Created database backup")
        
        # Get absolute path to bot directory
        bot_dir = Path(__file__).parent.absolute()
        data_dir = bot_dir / "data"
        data_dir.mkdir(exist_ok=True)
        
        db_path = data_dir / "channobot.db"
        logger.info(f"Attempting to connect to database at: {db_path}")
        
        # Create database with correct schema if it doesn't exist
        async with aiosqlite.connect(db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER,
                    guild_id INTEGER,
                    points INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            await db.commit()
            logger.info("Database schema verified")
            
            # Only initialize default points if the table is empty
            async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                count = await cursor.fetchone()
                if count[0] == 0:
                    logger.info("New database detected, initializing with default points")
                    await db.execute('INSERT INTO users (user_id, guild_id, points) VALUES (?, ?, ?)', 
                                   (128712048790994945, 0, 1000))  # Default user with points
                    await db.commit()
                else:
                    logger.info(f"Using existing database with {count[0]} users")
                    
    except Exception as e:
        logger.error(f"Database setup error: {str(e)}")
        raise

# Make the database connection accessible to cogs
bot.db_path = Path(__file__).parent.absolute() / "data" / "channobot.db"

# Constants
POINTS_PER_MINUTE = 20
INACTIVE_THRESHOLD = 15  # minutes

# Voice state tracking
voice_time_tracker = {}
last_voice_activity = {}

def is_user_active(member_id):
    """Check if a user is currently active"""
    if member_id not in last_voice_activity:
        return False
    minutes_inactive = (datetime.now() - last_voice_activity[member_id]).total_seconds() / 60
    return minutes_inactive < INACTIVE_THRESHOLD

@tasks.loop(seconds=30)
async def check_voice_activity():
    """Monitor user activity status in voice channels"""
    current_time = datetime.now()
    
    for guild in bot.guilds:
        for voice_channel in guild.voice_channels:
            for member in voice_channel.members:
                if not member.bot and not member.voice.afk:
                    # Initialize activity if not present
                    if member.id not in last_voice_activity:
                        logger.info(f"Initializing tracking for {member.name} in {voice_channel.name}")
                        last_voice_activity[member.id] = current_time
                        voice_time_tracker[member.id] = current_time
                        continue

                    minutes_inactive = (current_time - last_voice_activity[member.id]).total_seconds() / 60
                    was_inactive = minutes_inactive >= INACTIVE_THRESHOLD

                    # Log only status changes
                    if was_inactive != (minutes_inactive >= INACTIVE_THRESHOLD):
                        logger.info(f"{member.name} is {'now inactive' if minutes_inactive >= INACTIVE_THRESHOLD else 'active again'} in {voice_channel.name}")

@tasks.loop(minutes=1)
async def check_and_award_points():
    """Award points to active users in voice channels"""
    for guild in bot.guilds:
        for voice_channel in guild.voice_channels:
            for member in voice_channel.members:
                if not member.bot and not member.voice.afk and is_user_active(member.id):
                    await award_voice_points(member)

@tasks.loop(hours=24)
async def backup_task():
    """Create daily database backup"""
    try:
        backup_database()
        logger.info("Daily database backup created")
    except Exception as e:
        logger.error(f"Error creating database backup: {str(e)}")

async def setup_hook():
    """Initialize the bot's background tasks"""
    check_and_award_points.start()
    backup_task.start()
    logger.info("Background tasks started")

class ExampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def example(self, ctx):
        """Buy 2 minutes of auto-disconnect for a random person in your voice channel"""
        if not ctx.author.voice:
            await ctx.send("You need to be in a voice channel to use this command!")
            return

        channel = ctx.author.voice.channel
        members = channel.members
        if len(members) <= 1:
            await ctx.send("You need at least one other person in your voice channel!")
            return

        cost = 200000 // len(members)
        user_points = await get_points(ctx.author.id, ctx.guild.id)

        if user_points < cost:
            await ctx.send(f"You need {cost} points to use this command!")
            return

        # Remove points from user
        await remove_points(ctx.author.id, ctx.guild.id, cost)

        # Choose random member (excluding the command user)
        other_members = [m for m in members if m != ctx.author]
        victim = random.choice(other_members)

        await ctx.send(f"Disconnecting {victim.name} in 2 minutes!")
        await asyncio.sleep(120)  # Wait 2 minutes
        try:
            await victim.move_to(None)  # Disconnect the member
            await ctx.send(f"{victim.name} has been disconnected!")
        except:
            await ctx.send(f"Failed to disconnect {victim.name}!")

async def setup(bot):
    try:
        logger.info("Starting bot setup...")
        
        # Setup database first
        await setup_database()
        logger.info("Database setup complete")

        # Add ExampleCog first
        bot.add_cog(ExampleCog(bot))
        logger.info("Added ExampleCog")
        
        # Load game extensions
        extensions = ['cogs.blackjack', 'cogs.betting', 'cogs.rewards', 'cogs.slots']
        for ext in extensions:
            try:
                logger.info(f"Attempting to load extension: {ext}")
                # Add sys.path modification to help find the cogs
                import sys
                sys.path.append(str(Path(__file__).parent.absolute()))
                await bot.load_extension(ext)
                logger.info(f"Successfully loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                import traceback
                logger.error(traceback.format_exc())
                # Don't raise here, try to load other extensions
                continue
        
        logger.info("Extension loading complete")
        logger.info(f"Loaded cogs: {[cog for cog in bot.cogs]}")
    except Exception as e:
        logger.error(f"Setup error: {str(e)}")
        raise

@bot.event
async def on_ready():
    logger.info("Bot on_ready event triggered")
    try:
        logger.info(f'{bot.user} has connected to Discord!')
        await setup(bot)
        logger.info("Setup complete!")
        
        # Start background tasks
        await setup_hook()
        logger.info("Background tasks started")
        
        # Log all loaded cogs
        loaded_cogs = [cog for cog in bot.cogs]
        logger.info(f"Currently loaded cogs: {loaded_cogs}")
    except Exception as e:
        logger.error(f"Error in on_ready: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(traceback.format_exc())

@bot.command()
async def whoami(ctx):
    """Test command to verify bot can see user info"""
    user = ctx.author
    voice_status = "in voice channel: " + user.voice.channel.name if user.voice else "not in voice"
    await ctx.send(f"I can see you, {user.name}! You are {voice_status}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    current_time = datetime.now()
    logger.info(f"\nVoice state update for {member.name}")
    logger.info(f"Before state: channel={before.channel}, mute={before.self_mute}, deaf={before.self_deaf}, afk={before.afk}")
    logger.info(f"After state: channel={after.channel}, mute={after.self_mute}, deaf={after.self_deaf}, afk={after.afk}")
    
    # Handle joining voice
    if before.channel is None and after.channel is not None:
        logger.info(f"{member.name} joined voice channel {after.channel.name}")
        voice_time_tracker[member.id] = current_time
        last_voice_activity[member.id] = current_time
    
    # Handle leaving voice
    elif before.channel is not None and after.channel is None:
        logger.info(f"{member.name} left voice channel {before.channel.name}")
        await update_points_on_leave(member)
        if member.id in last_voice_activity:
            del last_voice_activity[member.id]
            del voice_time_tracker[member.id]

    # Update activity for any voice state change while in a channel
    if after.channel is not None:
        # Always update activity when in a voice channel, unless AFK
        if not after.afk:
            logger.info(f"Updating activity for {member.name} in {after.channel.name}")
            last_voice_activity[member.id] = current_time
            if member.id not in voice_time_tracker:
                voice_time_tracker[member.id] = current_time
            logger.info(f"Activity timestamp updated to {current_time}")

async def award_voice_points(member):
    """Award points to a member for being in voice chat"""
    try:
        logger.info(f"Attempting to award {POINTS_PER_MINUTE} points to {member.name}")
        async with aiosqlite.connect(bot.db_path) as db:
            # First try to insert new user
            try:
                await db.execute('''
                    INSERT INTO users (user_id, guild_id, points)
                    VALUES (?, ?, ?)
                ''', (member.id, member.guild.id, POINTS_PER_MINUTE))
                await db.commit()
                logger.info(f"Created new user {member.name} with {POINTS_PER_MINUTE} points")
            except sqlite3.IntegrityError:
                # User exists, update points
                await db.execute('''
                    UPDATE users 
                    SET points = points + ?
                    WHERE user_id = ? AND guild_id = ?
                ''', (POINTS_PER_MINUTE, member.id, member.guild.id))
                await db.commit()
                logger.info(f"Updated points for existing user {member.name}")
            
            # Verify points were awarded
            async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', 
                               (member.id, member.guild.id)) as cursor:
                result = await cursor.fetchone()
                if result:
                    logger.info(f"{member.name} now has {result[0]} points")
                else:
                    logger.error(f"Failed to verify points for {member.name}")
    except Exception as e:
        logger.error(f"Error awarding points to {member.name}: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        raise

async def update_points_on_leave(member):
    """Update points when a member leaves voice chat"""
    if member.id in voice_time_tracker:
        start_time = voice_time_tracker[member.id]
        current_time = datetime.now()
        minutes = (current_time - start_time).total_seconds() / 60
        
        # Only award points if user has been active recently
        if is_user_active(member.id):
            points = int(minutes * POINTS_PER_MINUTE)
            try:
                async with aiosqlite.connect(bot.db_path) as db:
                    # First try to insert if user doesn't exist
                    try:
                        await db.execute('''
                            INSERT INTO users (user_id, guild_id, points)
                            VALUES (?, ?, ?)
                        ''', (member.id, member.guild.id, points))
                        await db.commit()
                        logger.info(f"Created new user {member.name} with {points} points on leave")
                    except sqlite3.IntegrityError:
                        # User exists, update points
                        await db.execute('''
                            UPDATE users SET points = points + ?
                            WHERE user_id = ? AND guild_id = ?
                        ''', (points, member.id, member.guild.id))
                        await db.commit()
                        logger.info(f"Updated points for {member.name} with {points} points on leave")
                    
                    # Verify points
                    async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', 
                                       (member.id, member.guild.id)) as cursor:
                        result = await cursor.fetchone()
                        if result:
                            logger.info(f"{member.name} now has {result[0]} points after leave")
                        else:
                            logger.error(f"Failed to verify points for {member.name} after leave")
            except Exception as e:
                logger.error(f"Error updating points for {member.name} on leave: {str(e)}")
                logger.error(f"Error type: {type(e)}")
        
        # Clean up tracking
        del voice_time_tracker[member.id]
        if member.id in last_voice_activity:
            del last_voice_activity[member.id]

@bot.command()
async def points(ctx, member: discord.Member = None):
    """Check your points or someone else's points"""
    target = member or ctx.author
    
    try:
        logger.info(f"Checking points for {target.name}")
        # Get voice status and point collection status
        is_in_voice = target.voice is not None
        is_collecting = False
        channel_name = None
        
        if is_in_voice:
            channel_name = target.voice.channel.name
            is_collecting = is_user_active(target.id)
            logger.info(f"Points command - {target.name} in {channel_name}, active: {is_collecting}")
        
        # Get points from database
        async with aiosqlite.connect(bot.db_path) as db:
            async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', (target.id, ctx.guild.id)) as cursor:
                result = await cursor.fetchone()
                points = result[0] if result else 0
                logger.info(f"Retrieved {points} points for {target.name}")
        
        # Create status message
        status_msg = ""
        if is_in_voice:
            if is_collecting:
                status_msg = f"\n🎙️ Currently collecting points in {channel_name}!"
            else:
                status_msg = f"\n⏰ In {channel_name} but inactive (no points collecting)"
                # If they're in voice but inactive, update their activity
                if not target.voice.afk:
                    last_voice_activity[target.id] = datetime.now()
                    logger.info(f"Updated activity for {target.name} due to points command")
        
        if member:
            await ctx.send(f"{target.name} has {points} points!{status_msg}")
        else:
            await ctx.send(f"You have {points} points!{status_msg}")
    except Exception as e:
        logger.error(f"Error checking points: {str(e)}")
        await ctx.send("Sorry, there was an error checking points. Please try again.")

@bot.command()
async def leaderboard(ctx):
    """Show the points leaderboard for this server"""
    async with aiosqlite.connect(bot.db_path) as db:
        async with db.execute('SELECT user_id, points FROM users WHERE guild_id = ? ORDER BY points DESC LIMIT 10', (ctx.guild.id,)) as cursor:
            results = await cursor.fetchall()
            
    if not results:
        await ctx.send("No points recorded yet in this server!")
        return
        
    embed = discord.Embed(
        title="🏆 Points Leaderboard",
        description=f"Top 10 Point Earners in {ctx.guild.name}",
        color=discord.Color.gold()
    )
    
    # Create leaderboard text
    for i, (user_id, points) in enumerate(results, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
        member = ctx.guild.get_member(user_id)
        name = member.name if member else f"User {user_id}"
        embed.add_field(
            name=f"{medal} #{i}",
            value=f"{name}: {points:,} points",
            inline=False
        )
        
    await ctx.send(embed=embed)

@bot.event
async def on_guild_join(guild):
    """Log when the bot joins a new guild"""
    logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
    logger.info(f"Guild owner: {guild.owner.name} (ID: {guild.owner.id})")
    logger.info(f"Total members: {guild.member_count}")

@bot.event
async def on_guild_remove(guild):
    """Log when the bot leaves a guild"""
    logger.info(f"Left guild: {guild.name} (ID: {guild.id})")

@bot.event
async def on_command(ctx):
    """Log when a command is attempted"""
    logger.info(f"Command '{ctx.command.name}' attempted by {ctx.author.name} in guild '{ctx.guild.name}' (ID: {ctx.guild.id})")

@bot.event
async def on_command_error(ctx, error):
    """Log command errors"""
    logger.error(f"Error executing command '{ctx.command}' in guild '{ctx.guild.name}' (ID: {ctx.guild.id})")
    logger.error(f"Error: {str(error)}")
    if isinstance(error, commands.errors.CommandNotFound):
        return
    await ctx.send(f"An error occurred: {str(error)}")

@bot.command()
async def test(ctx):
    """Simple test command that always responds"""
    try:
        server_info = f"Server: {ctx.guild.name} (ID: {ctx.guild.id})"
        channel_info = f"Channel: {ctx.channel.name} (ID: {ctx.channel.id})"
        permissions = ctx.guild.me.guild_permissions
        perm_list = [perm[0] for perm in permissions if perm[1]]
        
        response = f"```\nBot Test Response\n{server_info}\n{channel_info}\n\nMy Permissions:\n{', '.join(perm_list)}```"
        await ctx.send(response)
    except Exception as e:
        await ctx.send(f"Error: {str(e)}")

@bot.event
async def on_message(message):
    """Log messages and process commands"""
    if message.author.bot:
        return

    try:
        # Log all message details
        guild_info = f"Guild: {message.guild.name} (ID: {message.guild.id})"
        channel_info = f"Channel: {message.channel.name} (ID: {message.channel.id})"
        author_info = f"Author: {message.author.name}#{message.author.discriminator}"
        content_info = f"Content: {message.content}"
        bot_permissions = message.guild.me.guild_permissions
        bot_roles = [role.name for role in message.guild.me.roles]
        
        logger.info(f"\nMessage Details:\n{guild_info}\n{channel_info}\n{author_info}\n{content_info}")
        logger.info(f"Bot permissions in this guild: {bot_permissions}")
        logger.info(f"Bot roles in this guild: {bot_roles}")
        
        # If it starts with our prefix, log extra command debug info
        if message.content.startswith('!'):
            logger.info(f"Potential command detected: {message.content}")
            logger.info(f"Can bot send messages here: {message.channel.permissions_for(message.guild.me).send_messages}")
            logger.info(f"Can bot read messages here: {message.channel.permissions_for(message.guild.me).read_messages}")
            
        # Process commands
        await bot.process_commands(message)
        
    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}")
        logger.error(f"Message was: {message.content}")

@bot.command()
@commands.is_owner()
async def addpoints(ctx, user_id: int, amount: int):
    """Add points to a user (owner only)"""
    async with aiosqlite.connect('data/channobot.db') as db:
        await db.execute('UPDATE users SET points = points + ? WHERE user_id = ?', (amount, user_id))
        await db.commit()
        await ctx.send(f"Added {amount} points to user {user_id}")

def is_authorized_user():
    async def predicate(ctx):
        return ctx.author.id == 128712048790994945
    return commands.check(predicate)

@bot.command()
@is_authorized_user()
async def givepoints(ctx, user: discord.Member, amount: int):
    """Give points to a user (only authorized users can use this)"""
    try:
        async with aiosqlite.connect(bot.db_path) as db:
            # First try to insert if user doesn't exist
            try:
                await db.execute('''
                    INSERT INTO users (user_id, guild_id, points)
                    VALUES (?, ?, ?)
                ''', (user.id, ctx.guild.id, amount))
                await db.commit()
                current_points = amount
            except sqlite3.IntegrityError:
                # User exists, update points
                await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                               (amount, user.id, ctx.guild.id))
                await db.commit()
                
                # Get updated points
                async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', 
                                    (user.id, ctx.guild.id)) as cursor:
                    result = await cursor.fetchone()
                    current_points = result[0] if result else amount
            
            embed = discord.Embed(
                title="💰 Points Given!",
                description=f"Given {amount} points to {user.mention}\nTheir new balance: {current_points} points",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            logger.info(f"Given {amount} points to {user.name} (ID: {user.id}) in guild {ctx.guild.name} (ID: {ctx.guild.id})")
            
    except Exception as e:
        error_msg = f"Error giving points: {str(e)}"
        logger.error(error_msg)
        await ctx.send(error_msg)

# Run the bot
bot.run(os.getenv('DISCORD_TOKEN')) 