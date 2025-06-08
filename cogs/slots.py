import discord
from discord.ext import commands
import random
import aiosqlite
import asyncio

class Slots(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Symbols with their emojis and multipliers
        self.symbols = [
            ("🍒", 2),    # Cherry - 2x
            ("🍋", 3),    # Lemon - 3x
            ("🍊", 4),    # Orange - 4x
            ("🍇", 5),    # Grapes - 5x
            ("💎", 10),   # Diamond - 10x
            ("🎰", 25),   # Jackpot - 25x
            ("👑", 50),   # Crown - 50x
        ]
        
    @commands.command()
    async def slots(self, ctx, bet: int):
        """Play the slot machine! Different symbols have different multipliers."""
        if bet < 1:
            await ctx.send("Bet amount must be at least 1 point!")
            return
            
        # Check if player has enough points
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', 
                               (ctx.author.id, ctx.guild.id)) as cursor:
                result = await cursor.fetchone()
                current_points = result[0] if result else 0
                
        if current_points < bet:
            await ctx.send(f"You don't have enough points! You have {current_points} points but tried to bet {bet}.")
            return
            
        # Deduct bet
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points - ? WHERE user_id = ? AND guild_id = ?', 
                           (bet, ctx.author.id, ctx.guild.id))
            await db.commit()
        
        # Create initial embed
        embed = discord.Embed(
            title="🎰 Slot Machine",
            description="Spinning...",
            color=discord.Color.blue()
        )
        message = await ctx.send(embed=embed)
        
        # Spin animation
        for _ in range(3):
            embed.description = "Spinning...\n" + " ".join(random.choice(self.symbols)[0] for _ in range(3))
            await message.edit(embed=embed)
            await asyncio.sleep(0.5)
        
        # Final spin
        result = [random.choice(self.symbols) for _ in range(3)]
        symbols = [r[0] for r in result]
        
        # Check for wins
        if symbols[0] == symbols[1] == symbols[2]:
            # Jackpot! All three match
            multiplier = next(m for s, m in self.symbols if s == symbols[0])
            winnings = bet * multiplier
            result_text = f"🎉 **JACKPOT!** All {symbols[0]} - {multiplier}x multiplier!"
        elif symbols[0] == symbols[1] or symbols[1] == symbols[2]:
            # Small win - two adjacent symbols match
            matching_symbol = symbols[1]  # The middle symbol that matches one of its neighbors
            multiplier = next(m for s, m in self.symbols if s == matching_symbol)
            winnings = bet * (multiplier // 2)  # Half the normal multiplier for two matches
            result_text = f"🎉 Two matches! {matching_symbol} - {multiplier//2}x multiplier!"
        else:
            # Loss
            winnings = 0
            result_text = "❌ No matches. Better luck next time!"
            
        # Award winnings if any
        if winnings > 0:
            async with aiosqlite.connect(self.bot.db_path) as db:
                await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                               (winnings, ctx.author.id, ctx.guild.id))
                await db.commit()
                
        # Show final result
        embed = discord.Embed(
            title="🎰 Slot Machine Results",
            description=f"**[ {' '.join(symbols)} ]**\n\n{result_text}",
            color=discord.Color.green() if winnings > 0 else discord.Color.red()
        )
        embed.add_field(
            name="Summary",
            value=f"Bet: {bet} points\nWinnings: {winnings} points\nNet: {winnings - bet:+} points"
        )
        await message.edit(embed=embed)
        
    @commands.command()
    async def slotinfo(self, ctx):
        """Show information about slot machine symbols and multipliers."""
        embed = discord.Embed(
            title="🎰 Slot Machine Info",
            description="Match 3 symbols for full multiplier, 2 adjacent symbols for half multiplier!",
            color=discord.Color.blue()
        )
        
        # Sort symbols by multiplier for display
        sorted_symbols = sorted(self.symbols, key=lambda x: x[1])
        
        for symbol, multiplier in sorted_symbols:
            embed.add_field(
                name=f"{symbol} {multiplier}x",
                value=f"3 matches: {multiplier}x bet\n2 matches: {multiplier//2}x bet",
                inline=True
            )
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Slots(bot)) 