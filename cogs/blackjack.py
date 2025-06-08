import discord
from discord.ext import commands
import random
import asyncio
import aiosqlite
from datetime import datetime

class Card:
    def __init__(self, suit, value):
        self.suit = suit
        self.value = value
        
    def __str__(self):
        return f"{self.value}{self.suit}"
        
    def get_blackjack_value(self):
        if self.value in ['J', 'Q', 'K']:
            return 10
        elif self.value == 'A':
            return 11
        else:
            return int(self.value)

class Deck:
    def __init__(self):
        self.cards = []
        suits = ['♠', '♥', '♦', '♣']
        values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        for suit in suits:
            for value in values:
                self.cards.append(Card(suit, value))
        random.shuffle(self.cards)
        
    def draw(self):
        if not self.cards:
            # Reshuffle if deck is empty
            self.__init__()
        return self.cards.pop()

def calculate_hand(hand):
    """Calculate the value of a blackjack hand"""
    value = 0
    aces = 0
    
    for card in hand:
        if card.value == 'A':
            aces += 1
        else:
            value += card.get_blackjack_value()
    
    # Add aces
    for _ in range(aces):
        if value + 11 <= 21:
            value += 11
        else:
            value += 1
            
    return value

class BlackjackCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}
        self.deck = Deck()

    @commands.command(name="blackjack")
    async def blackjack(self, ctx, bet: str):
        """Play blackjack against the dealer"""
        # Validate bet amount is a clean integer
        if not bet.isdigit():
            await ctx.send("Bet amount must be a positive integer!")
            return
            
        bet = int(bet)
        if bet <= 0:
            await ctx.send("Bet amount must be a positive integer!")
            return
            
        if ctx.author.id in self.active_games:
            await ctx.send("You already have an active game!")
            return
            
        # Check if player has enough points for potential double/split
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', 
                               (ctx.author.id, ctx.guild.id)) as cursor:
                result = await cursor.fetchone()
                current_points = result[0] if result else 0
        
        if current_points < bet:
            await ctx.send(f"You don't have enough points! You have {current_points} points but tried to bet {bet}.")
            return
            
        # Deduct initial bet
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points - ? WHERE user_id = ? AND guild_id = ?', 
                           (bet, ctx.author.id, ctx.guild.id))
            await db.commit()
        
        # Initialize game
        player_hand = [self.deck.draw(), self.deck.draw()]
        dealer_hand = [self.deck.draw(), self.deck.draw()]
        
        # Debug print initial hand
        print(f"Initial hand: {[str(card) for card in player_hand]}")
        print(f"Can split: {self.can_split(player_hand)}")
        print(f"Card values: {[card.get_blackjack_value() for card in player_hand]}")
        
        self.active_games[ctx.author.id] = {
            'deck': self.deck,
            'player_hands': [player_hand],  # List of hands for splitting
            'current_hand': 0,  # Index of current hand being played
            'dealer_hand': dealer_hand,
            'bet': bet,
            'bets': [bet],  # List of bets for each hand
            'can_double': True,  # Track if player can still double down
            'can_split': self.can_split(player_hand)  # Track if player can split
        }
        
        # Create and send the game state embed
        await self.display_game(ctx)
        
        # Check for natural blackjack
        player_value = calculate_hand(player_hand)
        dealer_value = calculate_hand(dealer_hand)
        
        if player_value == 21:
            if dealer_value == 21:
                # Push - return bet
                async with aiosqlite.connect(self.bot.db_path) as db:
                    await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                                   (bet, ctx.author.id, ctx.guild.id))
                    await db.commit()
                await ctx.send("🤝 Both have Blackjack! Push - your bet is returned.")
            else:
                # Blackjack pays 3:2
                winnings = int(bet * 2.5)
                async with aiosqlite.connect(self.bot.db_path) as db:
                    await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                                   (winnings, ctx.author.id, ctx.guild.id))
                    await db.commit()
                await ctx.send(f"🎉 Blackjack! You won {winnings} points!")
            del self.active_games[ctx.author.id]
            return
            
        await self.show_options(ctx)

    def can_split(self, hand):
        """Check if a hand can be split"""
        if len(hand) != 2:
            return False
        return hand[0].get_blackjack_value() == hand[1].get_blackjack_value()

    async def display_game(self, ctx):
        """Display the current game state"""
        game = self.active_games[ctx.author.id]
        current_hand = game['player_hands'][game['current_hand']]
        
        # Create embed
        embed = discord.Embed(title="🎰 Blackjack", color=discord.Color.green())
        
        # Create dealer hand string
        dealer_hand = game['dealer_hand']
        # Show full hand if game is over or player has stood
        if (game.get('status') == 'complete' or 
            game.get('stood', False) or
            calculate_hand(current_hand) > 21 or 
            calculate_hand(current_hand) == 21):
            dealer_cards = [str(card) for card in dealer_hand]
            dealer_value = calculate_hand(dealer_hand)
            dealer_text = f"{' '.join(dealer_cards)} ({dealer_value})"
        else:  # Hide second card during initial player decision
            dealer_cards = [str(dealer_hand[0]), '??']
            dealer_value = dealer_hand[0].get_blackjack_value()
            dealer_text = f"{' '.join(dealer_cards)} ({dealer_value}+)"
        
        embed.add_field(name="Dealer's Hand", value=dealer_text, inline=False)
        
        # Create player hand string(s)
        for i, hand in enumerate(game['player_hands']):
            hand_str = ' '.join(str(card) for card in hand)
            hand_value = calculate_hand(hand)
            status = "🎮 Current" if i == game['current_hand'] else "✅ Done"
            embed.add_field(name=f"Your Hand {i+1}", value=f"{hand_str} ({hand_value}) - {status}", inline=False)
        
        # Add bet info
        current_bet = game['bets'][game['current_hand']]
        embed.add_field(name="Current Bet", value=f"{current_bet} points", inline=False)
        
        # Send embed and add reactions
        message = await ctx.send(embed=embed)
        
        # Only add reactions if game is still active
        if not game.get('status') == 'complete' and not game.get('stood', False):
            await message.add_reaction('👊')  # hit
            await message.add_reaction('🛑')  # stand
            if game['can_double']:
                await message.add_reaction('💰')  # double
            if game['can_split']:
                await message.add_reaction('✌️')  # split
        
        # Store message ID for reaction handling
        game['message_id'] = message.id

    async def show_options(self, ctx):
        """Show available options to the player"""
        game = self.active_games[ctx.author.id]
        current_hand = game['player_hands'][game['current_hand']]
        
        # Update last action time
        game['last_action'] = datetime.now()
        
        options = ["hit", "stand"]
        if game['can_double']:
            options.append("double")
        if game['can_split']:
            options.append("split")
            
        hand_value = calculate_hand(current_hand)
        if hand_value == 21:
            await self.stand(ctx)
        else:
            await ctx.send(f"```Available options: {', '.join(options)}```")

    async def hit(self, ctx):
        """Hit - draw another card"""
        game = self.active_games[ctx.author.id]
        current_hand = game['player_hands'][game['current_hand']]
        
        # Draw a card
        current_hand.append(self.deck.draw())
        await self.display_game(ctx)
        
        # Check for bust or 21
        hand_value = calculate_hand(current_hand)
        if hand_value > 21:
            if game['current_hand'] < len(game['player_hands']) - 1:
                # Move to next split hand
                game['current_hand'] += 1
                game['can_double'] = True
                game['can_split'] = self.can_split(game['player_hands'][game['current_hand']])
                await self.display_game(ctx)
            else:
                await self.stand(ctx)
        elif hand_value == 21:
            await self.stand(ctx)

    async def double_down(self, ctx):
        """Double the bet and take exactly one more card"""
        game = self.active_games[ctx.author.id]
        current_hand = game['player_hands'][game['current_hand']]
        current_bet = game['bets'][game['current_hand']]
        
        # Deduct additional bet
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points - ? WHERE user_id = ? AND guild_id = ?', 
                           (current_bet, ctx.author.id, ctx.guild.id))
            await db.commit()
        game['bets'][game['current_hand']] *= 2
        
        # Draw one card
        current_hand.append(self.deck.draw())
        await self.display_game(ctx)
        
        if calculate_hand(current_hand) > 21:
            if game['current_hand'] < len(game['player_hands']) - 1:
                # Move to next split hand
                game['current_hand'] += 1
                game['can_double'] = True
                game['can_split'] = self.can_split(game['player_hands'][game['current_hand']])
                await self.show_options(ctx)
            else:
                await self.end_game(ctx)
        else:
            # Automatically stand after doubling down
            await self.stand(ctx)

    async def split(self, ctx):
        """Split the current hand into two hands"""
        game = self.active_games[ctx.author.id]
        current_hand = game['player_hands'][game['current_hand']]
        current_bet = game['bets'][game['current_hand']]
        
        # Deduct bet for the new hand
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points - ? WHERE user_id = ? AND guild_id = ?', 
                           (current_bet, ctx.author.id, ctx.guild.id))
            await db.commit()
        
        # Create new hand from split
        new_hand = [current_hand.pop()]
        game['player_hands'].insert(game['current_hand'] + 1, new_hand)
        game['bets'].insert(game['current_hand'] + 1, current_bet)
        
        # Draw a card for each hand
        current_hand.append(self.deck.draw())
        new_hand.append(self.deck.draw())
        
        # Reset double/split flags for current hand
        game['can_double'] = True
        game['can_split'] = self.can_split(current_hand)
        
        await self.display_game(ctx)
        await self.show_options(ctx)

    async def stand(self, ctx):
        """Stand on the current hand"""
        game = self.active_games[ctx.author.id]
        
        if game['current_hand'] < len(game['player_hands']) - 1:
            # Move to next split hand
            game['current_hand'] += 1
            game['can_double'] = True
            game['can_split'] = self.can_split(game['player_hands'][game['current_hand']])
            await self.display_game(ctx)
        else:
            # Show dealer's full hand and play it out
            game['stood'] = True  # Mark that player has stood
            await self.display_game(ctx)  # Show dealer's full hand
            await asyncio.sleep(1)
            
            # Play out dealer's hand
            while calculate_hand(game['dealer_hand']) < 17:
                new_card = self.deck.draw()
                game['dealer_hand'].append(new_card)
                await self.display_game(ctx)  # Update display with new dealer card
                await asyncio.sleep(1)
            
            # Show final results
            dealer_value = calculate_hand(game['dealer_hand'])
            
            # Build results embed
            embed = discord.Embed(title="🎰 Game Over!", color=discord.Color.blue())
            
            # Process each hand
            for i, player_hand in enumerate(game['player_hands']):
                hand_str = ' '.join(str(card) for card in player_hand)
                hand_value = calculate_hand(player_hand)
                bet = game['bets'][i]
                
                # Determine winner
                if hand_value > 21:
                    result = f"Bust! Lost {bet} points"
                elif dealer_value > 21:
                    payout = bet * 2
                    await self.add_points(ctx.author.id, payout, ctx.guild.id)
                    result = f"Dealer bust! Won {payout} points"
                elif hand_value > dealer_value:
                    payout = bet * 2
                    await self.add_points(ctx.author.id, payout, ctx.guild.id)
                    result = f"Won {payout} points"
                elif hand_value < dealer_value:
                    result = f"Lost {bet} points"
                else:
                    await self.add_points(ctx.author.id, bet, ctx.guild.id)
                    result = f"Push! {bet} points returned"
                
                embed.add_field(name=f"Hand {i+1}", value=f"{hand_str} ({hand_value}) - {result}", inline=False)
            
            # Send final results
            await ctx.send(embed=embed)
            
            # Clean up game
            del self.active_games[ctx.author.id]

    def is_soft_hand(self, hand):
        """Check if a hand is a soft hand"""
        value = 0
        aces = 0
        
        for card in hand:
            if card.value == 'A':
                aces += 1
            else:
                value += card.get_blackjack_value()
        
        # Add aces
        for _ in range(aces):
            if value + 11 <= 21:
                value += 11
            else:
                value += 1
        
        return value <= 17 and aces > 0

    def determine_winner(self, player_hand, dealer_hand):
        """Determine the winner of the game"""
        player_value = calculate_hand(player_hand)
        dealer_value = calculate_hand(dealer_hand)
        
        if player_value > 21:
            return 'loss'
        elif dealer_value > 21:
            return 'win'
        elif player_value == 21:
            return 'blackjack'
        elif dealer_value == 21:
            return 'blackjack'
        elif player_value > dealer_value:
            return 'win'
        elif player_value < dealer_value:
            return 'loss'
        else:
            return 'push'

    async def add_points(self, user_id, points, guild_id):
        """Add points to the user's account"""
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                           (points, user_id, guild_id))
            await db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        """Check for game timeouts"""
        if message.author.bot:
            return
            
        # Check for active games that have timed out
        current_time = datetime.now()
        games_to_timeout = []
        
        for user_id, game in self.active_games.items():
            if 'last_action' not in game:
                game['last_action'] = current_time
            elif (current_time - game['last_action']).total_seconds() > 60:  # 60 second timeout
                games_to_timeout.append(user_id)
        
        for user_id in games_to_timeout:
            game = self.active_games[user_id]
            channel = message.channel  # Use the current channel
            
            # Get user from channel
            user = message.guild.get_member(user_id)
            if user:
                await channel.send("Game timed out! Standing automatically.")
                
                # Create a new context object for the timed out user
                ctx = await self.bot.get_context(message)
                ctx.author = user
                
                # Stand on the current hand
                await self.stand(ctx)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle game reactions"""
        # Ignore bot's own reactions
        if user.bot:
            return
            
        # Check if this is a game message
        if user.id not in self.active_games:
            return
            
        game = self.active_games[user.id]
        if reaction.message.id != game.get('message_id'):
            return
            
        # Create context for command execution
        ctx = await self.bot.get_context(reaction.message)
        ctx.author = user
        
        # Handle different reactions
        if str(reaction.emoji) == '👊':  # hit
            await self.hit(ctx)
        elif str(reaction.emoji) == '🛑':  # stand
            await self.stand(ctx)
        elif str(reaction.emoji) == '💰' and game['can_double']:  # double
            await self.double_down(ctx)
        elif str(reaction.emoji) == '✌️' and game['can_split']:  # split
            await self.split(ctx)
            
        # Try to remove the reaction
        try:
            await reaction.remove(user)
        except:
            pass  # Ignore if we can't remove the reaction

async def setup(bot):
    await bot.add_cog(BlackjackCog(bot)) 