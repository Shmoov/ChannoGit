import discord
from discord.ext import commands
import asyncio
import aiosqlite

class Rewards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rewards = {
            'disconnect': {
                'cost': 1200,  # 1 hour worth of points (20 points/min × 60 minutes)
                'description': 'Disconnect a user from voice channel once'
            },
            'mute': {
                'cost': 3000,  # 2 hours worth of points (20 points/min × 120 minutes)
                'description': 'Mute a user for 1 minute'
            }
        }

    @commands.command()
    async def rewards(self, ctx):
        """Show available rewards"""
        embed = discord.Embed(
            title="🎁 Available Rewards",
            description="Here are the rewards you can redeem with your points:",
            color=discord.Color.purple()
        )
        
        for reward_id, reward in self.rewards.items():
            embed.add_field(
                name=f"{reward_id.title()} ({reward['cost']} points)",
                value=reward['description'],
                inline=False
            )
            
        await ctx.send(embed=embed)

    @commands.command()
    async def redeem(self, ctx, reward: str, member: discord.Member):
        """Redeem a reward to use on another member"""
        reward = reward.lower()
        
        if reward not in self.rewards:
            await ctx.send("Invalid reward! Use !rewards to see available rewards.")
            return
            
        if member.bot:
            await ctx.send("You cannot use rewards on bots!")
            return
            
        if member.id == ctx.author.id:
            await ctx.send("You cannot use rewards on yourself!")
            return

        # Check if target is in a voice channel (for voice-related rewards)
        if reward in ['disconnect', 'mute'] and not member.voice:
            await ctx.send(f"{member.name} is not in a voice channel!")
            return

        # Check if user has enough points
        async with aiosqlite.connect(self.bot.db_path) as db:
            async with db.execute('SELECT points FROM users WHERE user_id = ? AND guild_id = ?', (ctx.author.id, ctx.guild.id)) as cursor:
                result = await cursor.fetchone()
                current_points = result[0] if result else 0

        cost = self.rewards[reward]['cost']

        if current_points < cost:
            await ctx.send(f"You don't have enough points! You need {cost} points but have {current_points}.")
            return

        # Deduct points
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('UPDATE users SET points = points - ? WHERE user_id = ? AND guild_id = ?', 
                           (cost, ctx.author.id, ctx.guild.id))
            await db.commit()

        # Apply the reward effect
        if reward == 'disconnect':
            await self.disconnect_user(ctx, member)
        elif reward == 'mute':
            await self.mute_user(ctx, member)

    async def disconnect_user(self, ctx, member: discord.Member):
        """Disconnect a user from voice channel"""
        if member.voice and member.voice.channel:
            await member.move_to(None)
            await ctx.send(f"👋 {member.name} has been disconnected from voice!")
        else:
            await ctx.send(f"{member.name} is not in a voice channel!")
            # Refund points if action couldn't be completed
            async with aiosqlite.connect(self.bot.db_path) as db:
                await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                               (self.rewards['disconnect']['cost'], ctx.author.id, ctx.guild.id))
                await db.commit()

    async def mute_user(self, ctx, member: discord.Member):
        """Temporarily mute a user"""
        if member.voice:
            await member.edit(mute=True)
            await ctx.send(f"🤐 {member.name} has been muted for 1 minute!")
            
            # Schedule unmute
            await asyncio.sleep(60)
            try:
                await member.edit(mute=False)
                await ctx.send(f"🔊 {member.name} has been unmuted!")
            except discord.HTTPException:
                pass
        else:
            await ctx.send(f"{member.name} is not in a voice channel!")
            # Refund points if action couldn't be completed
            async with aiosqlite.connect(self.bot.db_path) as db:
                await db.execute('UPDATE users SET points = points + ? WHERE user_id = ? AND guild_id = ?', 
                               (self.rewards['mute']['cost'], ctx.author.id, ctx.guild.id))
                await db.commit()

async def setup(bot):
    await bot.add_cog(Rewards(bot)) 