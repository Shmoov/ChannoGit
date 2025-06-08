import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import re
import random
import aiosqlite

class Betting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_bets = {}

    @commands.command()
    async def custombet(self, ctx, player1: discord.Member, player2: discord.Member, amount: int, *, description: str):
        """Create a custom 1v1 bet between two players"""
        print(f"[DEBUG] Custombet command triggered by {ctx.author.name}")
        print(f"[DEBUG] Arguments: player1={player1.name}, player2={player2.name}, amount={amount}, description={description}")
        try:
            await self._create_bet(ctx, player1, player2, amount, description, bet_type='custom')
            print("[DEBUG] _create_bet called successfully")
        except Exception as e:
            print(f"[DEBUG] Error in custombet: {str(e)}")
            await ctx.send(f"Error creating bet: {str(e)}")

    @commands.command()
    async def leaguebet(self, ctx, player1: discord.Member, player2: discord.Member, amount: int, summoner_name: str):
        """Create a bet on a League of Legends game result"""
        description = f"League of Legends game result for {summoner_name}"
        bet = await self._create_bet(ctx, player1, player2, amount, description, bet_type='league')
        if bet:
            bet_id = str(ctx.message.id)
            self.active_bets[bet_id]['summoner_name'] = summoner_name
            embed = discord.Embed(
                title="🎲 League Bet Created!",
                description=f"**Type:** League of Legends\n**What's at stake:** {description}\n**Amount:** {amount} points\n\n{player1.mention} vs {player2.mention}\n\nBoth players must react with 👍 to accept.",
                color=discord.Color.blue()
            )
            message = await ctx.send(embed=embed)
            await message.add_reaction('👍')

    @commands.command()
    async def testleaguebet(self, ctx, amount: int, summoner_name: str):
        """Test League bet against bot (for testing only)"""
        test_opponent = type('TestOpponent', (), {
            'bot': False, 
            'id': 999999,
            'name': 'TestBot',
            'mention': '<@999999>'
        })()

        description = f"Bet that {summoner_name} will WIN their next League game"
        bet = await self._create_bet(ctx, ctx.author, test_opponent, amount, description, bet_type='league', is_test=True)
        if bet:
            bet_id = str(ctx.message.id)
            self.active_bets[bet_id]['summoner_name'] = summoner_name
            # Auto-accept for test opponent
            self.active_bets[bet_id]['consented'].add(999999)
            # Only need the real player to accept now
            embed = discord.Embed(
                title="🎲 Test Bet Created!",
                description=f"**Type:** League of Legends (Test)\n**What's at stake:** {description}\n**Amount:** {amount} points\n\n**If {summoner_name} wins:** You win {amount * 2} points\n**If {summoner_name} loses:** You lose {amount} points\n\nReact with 👍 to accept.",
                color=discord.Color.blue()
            )
            embed.set_footer(text=f"Bet ID: {bet_id} | Test Mode")
            message = await ctx.send(embed=embed)
            await message.add_reaction('👍')

    @commands.command()
    async def flipbet(self, ctx, opponent: discord.Member, bet: str):
        """Create a coin flip bet with another user"""
        # Validate bet amount
        if not bet.isdigit():
            await ctx.send("Bet amount must be a positive integer!")
            return
            
        bet = int(bet)
        if bet <= 0:
            await ctx.send("Bet amount must be a positive integer!")
            return

        bet = await self._create_bet(
            ctx=ctx,
            player1=ctx.author,
            player2=opponent,
            amount=bet,
            description=f"Coin flip between {ctx.author.name} and {opponent.name}",
            bet_type='flip'
        )
        
        if bet:
            # Set auto_resolve flag for coin flips
            bet_id = str(ctx.message.id)
            self.active_bets[bet_id]['auto_resolve'] = True
            
            embed = discord.Embed(
                title="🎲 Coin Flip Bet Created!",
                description=f"{opponent.mention}, {ctx.author.mention} wants to bet {bet} points on a coin flip!\n\nReact with 👍 to accept.",
                color=discord.Color.blue()
            )
            message = await ctx.send(embed=embed)
            await message.add_reaction('👍')

    async def _create_bet(self, ctx, player1, player2, amount, description, bet_type, is_test=False):
        """Common bet creation logic"""
        print(f"[DEBUG] _create_bet called with type={bet_type}")
        print(f"[DEBUG] Current active bets before creation: {list(self.active_bets.keys())}")
        
        if not is_test:
            if player1.bot or player2.bot:
                print("[DEBUG] Rejected: Bot involved in bet")
                await ctx.send("You cannot create bets involving bots!")
                return None

            if player1 == player2:
                print("[DEBUG] Rejected: Same player")
                await ctx.send("You cannot create a bet between the same player!")
                return None

        if amount < 1:
            print("[DEBUG] Rejected: Invalid amount")
            await ctx.send("Bet amount must be at least 1 point!")
            return None

        # Check if player1 has enough points
        print(f"[DEBUG] Checking points for {player1.name}")
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', (player1.id, ctx.guild.id)) as cursor:
                result = await cursor.fetchone()
                current_points = result[0] if result else 0
                print(f"[DEBUG] Current points: {current_points}")

        if current_points < amount:
            print(f"[DEBUG] Rejected: Not enough points ({current_points} < {amount})")
            await ctx.send(f"You don't have enough points! You have {current_points} points but need {amount}.")
            return None

        # Create and send bet confirmation embed first to get the message ID
        embed = discord.Embed(
            title="🎲 Custom Bet Created!",
            description=f"**What's at stake:** {description}\n**Amount:** {amount} points\n\n{player1.mention} vs {player2.mention}\n\nBoth players must react with 👍 to accept.",
            color=discord.Color.blue()
        )
        message = await ctx.send(embed=embed)
        await message.add_reaction('👍')
        
        # Use message ID as bet ID
        bet_id = str(message.id)
        print(f"[DEBUG] Generated bet ID (message ID): {bet_id}")
        
        bet_data = {
            'announcer': ctx.author.id,
            'description': description,
            'amount': amount,
            'player1': player1.id,
            'player2': player2.id,
            'guild_id': ctx.guild.id,
            'consented': set(),
            'status': 'pending_consent',
            'type': bet_type,
            'is_test': is_test,
            'message_id': message.id
        }
        
        print(f"[DEBUG] Created bet data: {bet_data}")
        self.active_bets[bet_id] = bet_data
        print(f"[DEBUG] Current active bets after creation: {list(self.active_bets.keys())}")
        
        # Update the embed to include the bet ID
        embed.set_footer(text=f"Bet ID: {bet_id}")
        await message.edit(embed=embed)
        
        return bet_data

    async def check_league_game(self, summoner_name):
        """Check the most recent League game result for a summoner"""
        try:
            # Format the summoner name for the URL
            formatted_name = summoner_name.replace(' ', '%20')
            url = f"https://www.op.gg/summoners/na/{formatted_name}"
            print(f"Checking URL: {url}")  # Debug log
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            print(f"Response status: {response.status_code}")  # Debug log
            
            if response.status_code != 200:
                print(f"Error accessing op.gg: {response.status_code}")
                return None
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for game result in different possible elements
            game_result = None
            
            # Try different possible selectors
            selectors = [
                'div.game-result',
                'div[class*="game-result"]',
                'div[class*="result"]',
                'div[class*="win"]',
                'div[class*="lose"]'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    print(f"Found elements with selector {selector}: {elements}")  # Debug log
                    for element in elements:
                        text = element.get_text().lower()
                        if 'victory' in text or 'win' in text:
                            return True
                        elif 'defeat' in text or 'lose' in text:
                            return False
            
            # If we couldn't find a result, save the HTML for debugging
            with open('debug_opgg.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("Saved HTML to debug_opgg.html for inspection")
            
            return None
            
        except Exception as e:
            print(f"Error checking League game: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle bet acceptance via reactions"""
        print(f"[DEBUG] Reaction added: {reaction.emoji} by {user.name}")
        
        if user.bot:
            print("[DEBUG] Ignoring bot reaction")
            return
            
        message = reaction.message
        print(f"[DEBUG] Message ID: {message.id}")
        
        if str(reaction.emoji) != '👍':
            print("[DEBUG] Not a thumbs up reaction")
            return
            
        # Find the bet associated with this message
        bet_id = str(message.id)
        print(f"[DEBUG] Looking for bet with ID: {bet_id}")
        print(f"[DEBUG] Active bets: {list(self.active_bets.keys())}")
        
        if bet_id not in self.active_bets:
            print("[DEBUG] No bet found with this ID")
            return
            
        bet = self.active_bets[bet_id]
        print(f"[DEBUG] Found bet: {bet}")
        
        if bet['status'] != 'pending_consent':
            print(f"[DEBUG] Bet status is not pending_consent: {bet['status']}")
            return
            
        if user.id in [bet['player1'], bet['player2']] or (bet.get('is_test') and user.id == bet['player1']):
            print(f"[DEBUG] Valid player {user.name} reacted")
            bet['consented'].add(user.id)
            print(f"[DEBUG] Current consents: {bet['consented']}")
            
            # If both players have consented (or if it's a test bet and the real player consented)
            consent_needed = 2 if not bet.get('is_test') else 1
            if len(bet['consented']) >= consent_needed:
                print("[DEBUG] All required consents received")
                bet['status'] = 'active'
                
                # Deduct points from both players for flip bets
                if bet['type'] == 'flip':
                    print("[DEBUG] Processing flip bet deductions")
                    async with aiosqlite.connect(self.bot.db_path) as db:
                        await db.execute('UPDATE users SET points = points - ? WHERE user_id IN (?, ?) AND guild_id = ?', 
                                       (bet['amount'], bet['player1'], bet['player2'], bet['guild_id']))
                        await db.commit()
                else:
                    # Original deduction for other bet types
                    print("[DEBUG] Processing standard bet deduction")
                    async with aiosqlite.connect(self.bot.db_path) as db:
                        await db.execute('UPDATE users SET points = points - ? WHERE user_id = ? AND guild_id = ?', 
                                       (bet['amount'], bet['player1'], bet['guild_id']))
                        await db.commit()
                
                embed = discord.Embed(
                    title="🎲 Bet Activated!",
                    description=f"{'Test bet' if bet.get('is_test') else 'Both players have'} accepted! The bet is now live.\n\n**What's at stake:** {bet['description']}\n**Amount:** {bet['amount']} points",
                    color=discord.Color.green()
                )
                await message.channel.send(embed=embed)

                # Auto-resolve flip bets
                if bet.get('auto_resolve'):
                    print("[DEBUG] Auto-resolving flip bet")
                    await asyncio.sleep(3)  # Add some suspense
                    await self.resolve_flip_bet(message.channel, bet_id)
        else:
            print(f"[DEBUG] Invalid player {user.name} reacted")

    async def resolve_flip_bet(self, channel, bet_id):
        """Automatically resolve a coin flip bet"""
        bet = self.active_bets[bet_id]
        
        # Do the coin flip
        is_heads = random.choice([True, False])
        
        # Get the players
        player1 = channel.guild.get_member(bet['player1'])
        player2 = channel.guild.get_member(bet['player2'])
        
        # Randomly assign heads/tails to players
        heads_player = player1
        tails_player = player2
        
        # Determine winner
        winner = heads_player if is_heads else tails_player
        
        # Calculate winnings (both players bet, so winner gets double their bet)
        winnings = bet['amount'] * 2
        
        # Award points to winner
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                           (winnings, winner.id, bet['guild_id']))
            await db.commit()

        # Create results embed with coin flip animation
        flip_msg = await channel.send("Flipping coin...")
        await asyncio.sleep(1)
        await flip_msg.edit(content="Flipping coin..")
        await asyncio.sleep(1)
        await flip_msg.edit(content="Flipping coin...")
        await asyncio.sleep(1)
        
        result = "HEADS" if is_heads else "TAILS"
        loser = tails_player if is_heads else heads_player
        
        embed = discord.Embed(
            title="🎲 Coin Flip Results!",
            description=f"**The coin landed on:** {result}!\n\n"
                       f"**{heads_player.name}** was Heads\n"
                       f"**{tails_player.name}** was Tails\n\n"
                       f"🏆 **Winner:** {winner.mention}\n"
                       f"😢 **Loser:** {loser.mention}\n\n"
                       f"**Prize:** {winnings} points",
            color=discord.Color.gold()
        )
        
        await channel.send(embed=embed)
        del self.active_bets[bet_id]

    @commands.command()
    async def resolve(self, ctx, bet_id: str, winner: discord.Member = None):
        """Resolve a custom bet by declaring the winner"""
        print(f"[DEBUG] Resolve command called for bet {bet_id}")
        print(f"[DEBUG] Available bet IDs: {list(self.active_bets.keys())}")
        print(f"[DEBUG] Winner: {winner.name if winner else 'None'}")
        
        if bet_id not in self.active_bets:
            print(f"[DEBUG] Bet {bet_id} not found in active bets")
            await ctx.send(f"This bet doesn't exist! Available bets: {', '.join(list(self.active_bets.keys()))}")
            return
            
        bet = self.active_bets[bet_id]
        print(f"[DEBUG] Found bet: {bet}")
        
        # Only announcer can resolve
        if ctx.author.id != bet['announcer']:
            print(f"[DEBUG] Unauthorized resolve attempt by {ctx.author.name}")
            await ctx.send("Only the bet announcer can resolve this bet!")
            return
            
        if bet['status'] != 'active':
            print(f"[DEBUG] Invalid bet status: {bet['status']}")
            await ctx.send("This bet isn't active yet!")
            return
            
        # For custom bets, winner must be specified
        if bet['type'] == 'custom' and winner is None:
            print("[DEBUG] No winner specified for custom bet")
            await ctx.send("You must specify a winner for custom bets!")
            return
            
        # Validate winner is part of the bet
        if winner.id not in [bet['player1'], bet['player2']]:
            print(f"[DEBUG] Invalid winner {winner.name} - not part of bet")
            await ctx.send("The winner must be one of the players in the bet!")
            return
            
        print(f"[DEBUG] Processing win for {winner.name}")
        # Calculate winnings (winner gets their bet back plus the opponent's bet)
        winnings = bet['amount'] * 2
        
        # Award points to winner
        print(f"[DEBUG] Awarding {winnings} points to {winner.name}")
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                           (winnings, winner.id, bet['guild_id']))
            await db.commit()

        # Create results embed
        loser_id = bet['player1'] if winner.id == bet['player2'] else bet['player2']
        loser = ctx.guild.get_member(loser_id)
        
        embed = discord.Embed(
            title="🎲 Bet Results",
            description=f"**What was at stake:** {bet['description']}\n\n🏆 **Winner:** {winner.mention}\n😢 **Loser:** {loser.mention}\n\n**Prize:** {winnings} points",
            color=discord.Color.gold()
        )
        
        await ctx.send(embed=embed)
        print(f"[DEBUG] Bet {bet_id} resolved successfully")
        del self.active_bets[bet_id]

    @commands.command()
    async def cancel(self, ctx, bet_id: str):
        """Cancel a pending bet that hasn't been accepted yet"""
        if bet_id not in self.active_bets:
            await ctx.send("This bet doesn't exist!")
            return

        bet = self.active_bets[bet_id]
        
        # Only announcer can cancel
        if ctx.author.id != bet['announcer']:
            await ctx.send("Only the bet announcer can cancel this bet!")
            return

        if bet['status'] != 'pending_consent':
            await ctx.send("This bet can't be cancelled - it's already active!")
            return

        del self.active_bets[bet_id]
        await ctx.send("Bet has been cancelled!")

async def setup(bot):
    await bot.add_cog(Betting(bot)) 