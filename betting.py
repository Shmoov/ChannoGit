import discord
from discord.ext import commands
import random
import aiosqlite
import asyncio
from typing import Dict, Set, Optional, Union
from league_api import LeagueAPI
import os

class Betting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_bets: Dict[str, dict] = {}  # message_id -> bet_data
        self.league_api = LeagueAPI(os.getenv('RIOT_API_KEY', ''))
        
    def cog_help(self) -> discord.Embed:
        """Custom help command for the betting cog"""
        embed = discord.Embed(
            title="🎲 Betting Commands",
            description="Challenge your friends to bets and win points!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="!flip @opponent amount [description]",
            value="Start a coin flip bet with another user.\n"
                  "• Both players must have enough points\n"
                  "• Both players must react with 👍 to start\n"
                  "• Winner gets double their bet\n"
                  "Example: `!flip @Friend 100 Movie night bet`",
            inline=False
        )
        
        embed.add_field(
            name="!leaguebet @opponent outcome amount summoner_name",
            value="Bet on whether you'll win/lose your next League game.\n"
                  "• outcome: 'w' or 'l' for win/loss\n"
                  "• Both players must have enough points\n"
                  "• Opponent must react with 👍 to accept\n"
                  "Example: `!leaguebet @Friend w 100 SummonerName`",
            inline=False
        )
        
        embed.add_field(
            name="!resolve_league bet_id outcome",
            value="Resolve a League bet after the game.\n"
                  "• bet_id: The ID shown in the bet message\n"
                  "• outcome: 'w' or 'l' for win/loss\n"
                  "• Only the person who made the prediction can resolve\n"
                  "Example: `!resolve_league 123456789 w`",
            inline=False
        )
        
        embed.add_field(
            name="Points System",
            value="• New users start with 1000 points\n"
                  "• Points are deducted when both players accept\n"
                  "• Winner gets double their original bet",
            inline=False
        )
        
        embed.set_footer(text="💡 Tip: You can add a custom description to make your bets more interesting!")
        return embed

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize database tables if they don't exist"""
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT,
                    guild_id TEXT,
                    points INTEGER DEFAULT 1000,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            await db.commit()

    @commands.command(name="flip")
    async def flip(self, ctx, opponent: discord.Member, amount: int, *, description: str = None):
        """Create a coin flip bet with another user"""
        if amount <= 0:
            await ctx.send("❌ Bet amount must be positive!")
            return

        # Check if users have enough points
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute("SELECT points FROM users WHERE user_id = ? AND guild_id = ?",
                                (str(ctx.author.id), str(ctx.guild.id))) as cursor:
                author_points = await cursor.fetchone()
                if not author_points:
                    await db.execute("INSERT INTO users (user_id, guild_id) VALUES (?, ?)",
                                   (str(ctx.author.id), str(ctx.guild.id)))
                    author_points = (1000,)
                    await db.commit()

            async with db.execute("SELECT points FROM users WHERE user_id = ? AND guild_id = ?",
                                (str(opponent.id), str(ctx.guild.id))) as cursor:
                opponent_points = await cursor.fetchone()
                if not opponent_points:
                    await db.execute("INSERT INTO users (user_id, guild_id) VALUES (?, ?)",
                                   (str(opponent.id), str(ctx.guild.id)))
                    opponent_points = (1000,)
                    await db.commit()

        if author_points[0] < amount:
            await ctx.send(f"❌ You don't have enough points! You have {author_points[0]} points.")
            return

        if opponent_points[0] < amount:
            await ctx.send(f"❌ {opponent.display_name} doesn't have enough points! They have {opponent_points[0]} points.")
            return

        description = description or f"{ctx.author.display_name} vs {opponent.display_name} - {amount} points"
        embed = discord.Embed(
            title="🎲 New Coin Flip Bet!",
            description=f"**What's at stake:** {description}\n**Amount:** {amount} points\n\nBoth players must react with 👍 to start!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Players", value=f"{ctx.author.mention} vs {opponent.mention}")

        bet_message = await ctx.send(embed=embed)
        await bet_message.add_reaction("👍")

        # Store bet info
        bet_id = str(bet_message.id)
        self.active_bets[bet_id] = {
            "type": "flip",
            "message_id": bet_id,
            "player1": ctx.author.id,
            "player2": opponent.id,
            "amount": amount,
            "description": description,
            "guild_id": str(ctx.guild.id),
            "status": "pending_consent",
            "consented": set(),
            "auto_resolve": True
        }
        print(f"[DEBUG] Created new flip bet with ID: {bet_id}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle bet acceptance via reactions"""
        if user.bot:
            return

        message = reaction.message
        message_id = str(message.id)
        print(f"[DEBUG] Processing reaction on message {message_id}")
        
        if str(reaction.emoji) != "👍":
            return

        # Find the bet associated with this message
        bet_id = str(message.id)
        print(f"[DEBUG] Looking for bet with ID: {bet_id}")
        
        # Try to find the bet, being more lenient with ID matching
        found_bet = None
        for active_bet_id, bet_data in self.active_bets.items():
            if str(active_bet_id) == bet_id or str(bet_data.get("message_id")) == bet_id:
                found_bet = bet_data
                bet_id = active_bet_id
                break

        if not found_bet:
            print(f"[DEBUG] No bet found for message {message_id}")
            return

        bet = self.active_bets[bet_id]
        if bet["status"] != "pending_consent":
            return

        if user.id in [bet["player1"], bet["player2"]] or (bet.get("is_test") and user.id == bet["player1"]):
            # Check if players still have enough points
            async with aiosqlite.connect(self.bot.db_path) as db:
                # Check player1's points
                async with db.execute("SELECT points FROM users WHERE user_id = ? AND guild_id = ?",
                                    (str(bet["player1"]), bet["guild_id"])) as cursor:
                    player1_points = await cursor.fetchone()
                    if not player1_points or player1_points[0] < bet["amount"]:
                        player1 = await self.bot.fetch_user(bet["player1"])
                        await message.channel.send(f"❌ {player1.mention} no longer has enough points for this bet!")
                        del self.active_bets[bet_id]
                        return

                # Check player2's points
                async with db.execute("SELECT points FROM users WHERE user_id = ? AND guild_id = ?",
                                    (str(bet["player2"]), bet["guild_id"])) as cursor:
                    player2_points = await cursor.fetchone()
                    if not player2_points or player2_points[0] < bet["amount"]:
                        player2 = await self.bot.fetch_user(bet["player2"])
                        await message.channel.send(f"❌ {player2.mention} no longer has enough points for this bet!")
                        del self.active_bets[bet_id]
                        return

            bet["consented"].add(user.id)

            # If both players have consented (or if it's a test bet and the real player consented)
            consent_needed = 2 if not bet.get("is_test") else 1
            if len(bet["consented"]) >= consent_needed:
                bet["status"] = "active"

                # Deduct points from both players for flip bets
                if bet["type"] == "flip":
                    async with aiosqlite.connect(self.bot.db_path) as db:
                        await db.execute("UPDATE users SET points = points - ? WHERE user_id IN (?, ?) AND guild_id = ?",
                                       (bet["amount"], bet["player1"], bet["player2"], bet["guild_id"]))
                        await db.commit()

                embed = discord.Embed(
                    title="🎲 Bet Activated!",
                    description=f"{'Test bet' if bet.get('is_test') else 'Both players have'} accepted! The bet is now live.\n\n**What's at stake:** {bet['description']}\n**Amount:** {bet['amount']} points",
                    color=discord.Color.green()
                )
                await message.channel.send(embed=embed)

                # Auto-resolve flip bets
                if bet.get("auto_resolve"):
                    await asyncio.sleep(3)  # Add some suspense
                    await self.resolve_flip_bet(message.channel, bet_id)

    async def resolve_flip_bet(self, channel, bet_id):
        """Resolve a coin flip bet"""
        if bet_id not in self.active_bets:
            print(f"[DEBUG] Cannot resolve bet {bet_id} - not found in active bets")
            return

        bet = self.active_bets[bet_id]
        if bet["status"] != "active" or bet["type"] != "flip":
            return

        # Flip the coin
        result = random.choice(["heads", "tails"])
        winner_id = bet["player1"] if result == "heads" else bet["player2"]
        loser_id = bet["player2"] if result == "heads" else bet["player1"]

        # Calculate winnings (winner gets double their bet)
        winnings = bet["amount"] * 2

        # Update points in database
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute("UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?",
                           (winnings, str(winner_id), bet["guild_id"]))
            await db.commit()

        # Get user objects for mentions
        winner = await self.bot.fetch_user(winner_id)
        loser = await self.bot.fetch_user(loser_id)

        # Create result embed
        embed = discord.Embed(
            title="🎲 Coin Flip Results!",
            description=f"The coin landed on **{result}**!\n\n"
                      f"**Winner:** {winner.mention} (+{winnings} points)\n"
                      f"**Loser:** {loser.mention} (-{bet['amount']} points)",
            color=discord.Color.green()
        )

        await channel.send(embed=embed)
        
        # Remove the bet from active bets
        del self.active_bets[bet_id]
        print(f"[DEBUG] Resolved and removed bet {bet_id}")

    @commands.command(name="leaguebet")
    async def leaguebet(self, ctx, opponent: discord.Member, outcome: str, amount: int, summoner_name: str):
        """Create a bet on whether you'll win or lose your next League game
        
        Args:
            opponent: The person you're betting against
            outcome: Either 'w' or 'l' for win/loss
            amount: How many points to bet
            summoner_name: Your League of Legends summoner name
        """
        # Validate outcome
        outcome = outcome.lower()
        if outcome not in ['w', 'l', 'win', 'loss', 'lose']:
            await ctx.send("❌ Outcome must be 'w' or 'l' for win/loss!")
            return

        if amount <= 0:
            await ctx.send("❌ Bet amount must be positive!")
            return

        # Verify summoner exists
        summoner = self.league_api.get_summoner_by_name(summoner_name)
        if not summoner:
            await ctx.send("❌ Could not find that summoner name! Please check the spelling.")
            return

        # Check if users have enough points
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute("SELECT points FROM users WHERE user_id = ? AND guild_id = ?",
                                (str(ctx.author.id), str(ctx.guild.id))) as cursor:
                author_points = await cursor.fetchone()
                if not author_points:
                    await db.execute("INSERT INTO users (user_id, guild_id) VALUES (?, ?)",
                                   (str(ctx.author.id), str(ctx.guild.id)))
                    author_points = (1000,)
                    await db.commit()

            async with db.execute("SELECT points FROM users WHERE user_id = ? AND guild_id = ?",
                                (str(opponent.id), str(ctx.guild.id))) as cursor:
                opponent_points = await cursor.fetchone()
                if not opponent_points:
                    await db.execute("INSERT INTO users (user_id, guild_id) VALUES (?, ?)",
                                   (str(opponent.id), str(ctx.guild.id)))
                    opponent_points = (1000,)
                    await db.commit()

        if author_points[0] < amount:
            await ctx.send(f"❌ You don't have enough points! You have {author_points[0]} points.")
            return

        if opponent_points[0] < amount:
            await ctx.send(f"❌ {opponent.display_name} doesn't have enough points! They have {opponent_points[0]} points.")
            return

        # Format the outcome for display
        outcome_display = "win" if outcome.startswith('w') else "lose"
        description = f"{ctx.author.display_name} bets they will {outcome_display} their next League game"

        embed = discord.Embed(
            title="🎮 League Bet Created!",
            description=f"**What's at stake:** {description}\n**Amount:** {amount} points\n**Summoner:** {summoner_name}\n\n{opponent.mention}, do you accept this bet?\nReact with 👍 to accept!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Players", value=f"{ctx.author.mention} vs {opponent.mention}")
        embed.add_field(name="Prediction", value=f"{ctx.author.display_name} will {outcome_display}", inline=False)

        bet_message = await ctx.send(embed=embed)
        await bet_message.add_reaction("👍")

        # Store bet info
        bet_id = str(bet_message.id)
        self.active_bets[bet_id] = {
            "type": "league",
            "message_id": bet_id,
            "player1": ctx.author.id,  # The person making the prediction
            "player2": opponent.id,    # The person accepting the bet
            "amount": amount,
            "description": description,
            "guild_id": str(ctx.guild.id),
            "status": "pending_consent",
            "consented": set(),
            "auto_resolve": False,
            "predicted_outcome": outcome_display,
            "summoner_name": summoner_name,
            "summoner_puuid": summoner["puuid"]
        }
        print(f"[DEBUG] Created new league bet with ID: {bet_id}")

    @commands.command(name="verify_league")
    async def verify_league(self, ctx, bet_id: str):
        """Automatically verify a League bet result using the Riot API
        
        Args:
            bet_id: The ID of the bet to verify
        """
        if bet_id not in self.active_bets:
            await ctx.send("❌ This bet doesn't exist!")
            return

        bet = self.active_bets[bet_id]
        
        if bet["status"] != "active":
            await ctx.send("❌ This bet isn't active yet!")
            return

        if bet["type"] != "league":
            await ctx.send("❌ This isn't a League bet!")
            return

        # Get recent matches
        matches = self.league_api.get_match_history(bet["summoner_puuid"], count=1)
        if not matches:
            await ctx.send("❌ Could not find any recent matches for this summoner!")
            return

        # Get most recent match details
        match_details = self.league_api.get_match_details(matches[0])
        if not match_details:
            await ctx.send("❌ Could not fetch match details!")
            return

        # Find the participant info for the summoner
        actual_outcome = None
        for participant in match_details["info"]["participants"]:
            if participant["puuid"] == bet["summoner_puuid"]:
                actual_outcome = "win" if participant["win"] else "lose"
                break

        if actual_outcome is None:
            await ctx.send("❌ Could not find the summoner in the match!")
            return

        # Determine the winner
        prediction_correct = actual_outcome == bet["predicted_outcome"]
        winner_id = bet["player1"] if prediction_correct else bet["player2"]
        loser_id = bet["player2"] if prediction_correct else bet["player1"]

        # Calculate winnings (winner gets double their bet)
        winnings = bet["amount"] * 2

        # Update points in database
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute("UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?",
                           (winnings, str(winner_id), bet["guild_id"]))
            await db.commit()

        # Get user objects for mentions
        winner = await self.bot.fetch_user(winner_id)
        loser = await self.bot.fetch_user(loser_id)

        # Create result embed
        embed = discord.Embed(
            title="🎮 League Bet Results!",
            description=f"**The game was a {actual_outcome}!**\n\n"
                      f"**Winner:** {winner.mention} (+{winnings} points)\n"
                      f"**Loser:** {loser.mention} (-{bet['amount']} points)",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)
        
        # Remove the bet from active bets
        del self.active_bets[bet_id]
        print(f"[DEBUG] Resolved and removed league bet {bet_id}")

    @commands.command(name="resolve_league")
    async def resolve_league(self, ctx, bet_id: str, actual_outcome: str):
        """Resolve a League bet by specifying if it was a win or loss
        
        Args:
            bet_id: The ID of the bet to resolve (shown in footer of bet message)
            actual_outcome: 'w' or 'l' for win/loss
        """
        if bet_id not in self.active_bets:
            await ctx.send("❌ This bet doesn't exist!")
            return

        bet = self.active_bets[bet_id]
        
        # Only the person who made the prediction can resolve it
        if ctx.author.id != bet["player1"]:
            await ctx.send("❌ Only the person who made the prediction can resolve this bet!")
            return

        if bet["status"] != "active":
            await ctx.send("❌ This bet isn't active yet!")
            return

        if bet["type"] != "league":
            await ctx.send("❌ This isn't a League bet!")
            return

        # Validate and normalize the outcome
        actual_outcome = actual_outcome.lower()
        if actual_outcome not in ['w', 'l', 'win', 'loss', 'lose']:
            await ctx.send("❌ Outcome must be 'w' or 'l' for win/loss!")
            return
        
        actual_outcome = "win" if actual_outcome.startswith('w') else "lose"
        
        # Determine the winner
        prediction_correct = actual_outcome == bet["predicted_outcome"]
        winner_id = bet["player1"] if prediction_correct else bet["player2"]
        loser_id = bet["player2"] if prediction_correct else bet["player1"]

        # Calculate winnings (winner gets double their bet)
        winnings = bet["amount"] * 2

        # Update points in database
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute("UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?",
                           (winnings, str(winner_id), bet["guild_id"]))
            await db.commit()

        # Get user objects for mentions
        winner = await self.bot.fetch_user(winner_id)
        loser = await self.bot.fetch_user(loser_id)

        # Create result embed
        embed = discord.Embed(
            title="🎮 League Bet Results!",
            description=f"**The game was a {actual_outcome}!**\n\n"
                      f"**Winner:** {winner.mention} (+{winnings} points)\n"
                      f"**Loser:** {loser.mention} (-{bet['amount']} points)",
            color=discord.Color.green()
        )

        await ctx.send(embed=embed)
        
        # Remove the bet from active bets
        del self.active_bets[bet_id]
        print(f"[DEBUG] Resolved and removed league bet {bet_id}")

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        print("[DEBUG] Betting cog unloading - clearing active bets")
        self.active_bets.clear()

async def setup(bot):
    await bot.add_cog(Betting(bot)) 