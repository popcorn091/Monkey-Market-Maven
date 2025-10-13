# cogs/profit.py
"""
Profit/Loss tracking Cog - Handles profit and profitclear commands
"""

import discord
from discord.ext import commands

# Import from parent directory
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import TradingDatabase

class ProfitCog(commands.Cog):
    """
    Handles profit/loss tracking and management.
    All P&L data stored in profit_loss TABLE.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = TradingDatabase()
    
    @commands.command(name="profit")
    async def show_profit(self, ctx: commands.Context):
        """
        Display total realized profit/loss.
        
        Data Flow:
        1. Query profit_loss TABLE
        2. Sum all profit_loss values
        3. Display result
        """
        user_id = str(ctx.author.id)
        
        # Get total P&L from database
        total_profit = await self.db.get_total_profit_loss(user_id)
        
        if total_profit == 0:
            await ctx.send("📊 目前沒有任何已實現的損益紀錄，或總損益為 0。")
            return
        
        # Color based on profit/loss
        color = discord.Color.green() if total_profit >= 0 else discord.Color.red()
        title = "📈 總已實現損益" if total_profit >= 0 else "📉 總已實現損益"
        
        embed = discord.Embed(title=title, color=color)
        embed.add_field(
            name=f"{ctx.author.display_name} 的總損益為：",
            value=f"**${total_profit:,.2f}**",
            inline=False
        )
        
        # Optional: Add some statistics
        cursor = await self.db.db.execute("""
            SELECT COUNT(*) as count,
                   SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses
            FROM profit_loss
            WHERE user_id = ?
        """, (user_id,))
        stats = await cursor.fetchone()
        
        if stats and stats['count'] > 0:
            win_rate = (stats['wins'] / stats['count'] * 100) if stats['count'] > 0 else 0
            embed.add_field(
                name="交易統計",
                value=(
                    f"總交易次數: {stats['count']}\n"
                    f"獲利次數: {stats['wins']}\n"
                    f"虧損次數: {stats['losses']}\n"
                    f"勝率: {win_rate:.1f}%"
                ),
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="profitclear")
    async def clear_profit(self, ctx: commands.Context):
        """
        Clear all profit/loss records by adding offsetting entry.
        
        Data Flow:
        1. Query profit_loss TABLE for total
        2. Add offsetting entry to zero out total
        3. Confirm to user
        """
        user_id = str(ctx.author.id)
        
        # Get current total
        total_profit = await self.db.get_total_profit_loss(user_id)
        
        if total_profit == 0:
            await ctx.send("✅ 您的總損益已經是 0，無需歸零。")
            return
        
        # Clear P&L (adds offsetting entry)
        cleared_amount = await self.db.clear_profit_loss(user_id)
        
        await ctx.send(
            f"✅ **損益已歸零！** 已新增一筆 ${-cleared_amount:,.2f} 的紀錄來平衡您的總損益。\n"
            f"原始總損益：${cleared_amount:,.2f}\n"
            f"新總損益：$0.00"
        )

async def setup(bot: commands.Bot):
    """Required function to load the cog."""
    await bot.add_cog(ProfitCog(bot))