# cogs/settings.py
"""
User settings Cog - Manages monkey trading preferences
"""

import discord
from discord.ext import commands

# Import from parent directory
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import TradingDatabase

class SettingsCog(commands.Cog):
    """
    Manages user-specific settings for monkey trading.
    All settings stored in user_settings TABLE.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = TradingDatabase()
    
    @commands.command(name="usersetting")
    async def user_setting(self, ctx: commands.Context, setting_type: str = None, 
                          *values):
        """
        Configure monkey trading settings.
        
        Usage:
        !usersetting - Show current settings
        !usersetting amount <min> <max> - Set trade amount range
        !usersetting weights <buy> <sell> <hold> - Set action weights
        
        Examples:
        !usersetting amount 10000 80000
        !usersetting weights 40 35 25
        """
        user_id = str(ctx.author.id)
        
        # Get current settings
        settings = await self.db.get_user_settings(user_id)
        
        # Display current settings if no parameters
        if setting_type is None:
            await self._show_settings(ctx, settings)
            return
        
        setting_type = setting_type.lower()
        
        # Update amount range
        if setting_type in ["amount", "金額", "範圍"]:
            if len(values) != 2:
                await ctx.send("❌ 用法: `!usersetting amount <最小金額> <最大金額>`")
                return
            
            try:
                min_amt = int(values[0])
                max_amt = int(values[1])
                
                if min_amt < 1000 or max_amt < 1000:
                    await ctx.send("❌ 金額必須至少 1000 元。")
                    return
                
                if min_amt >= max_amt:
                    await ctx.send("❌ 最小金額必須小於最大金額。")
                    return
                
                if (max_amt - min_amt) < 1000:
                    await ctx.send("❌ 金額範圍至少需要 1000 元的差距。")
                    return
                
                await self.db.update_user_settings(
                    user_id,
                    monkey_min_amount=min_amt,
                    monkey_max_amount=max_amt
                )
                
                await ctx.send(
                    f"✅ 已更新金額範圍：${min_amt:,} ~ ${max_amt:,}"
                )
                
            except ValueError:
                await ctx.send("❌ 請輸入有效的數字。")
                return
        
        # Update action weights
        elif setting_type in ["weights", "權重", "weight"]:
            if len(values) != 3:
                await ctx.send("❌ 用法: `!usersetting weights <買入權重> <賣出權重> <持有權重>`")
                return
            
            try:
                buy_w = int(values[0])
                sell_w = int(values[1])
                hold_w = int(values[2])
                
                if any(w < 0 for w in [buy_w, sell_w, hold_w]):
                    await ctx.send("❌ 權重不能為負數。")
                    return
                
                if buy_w + sell_w + hold_w == 0:
                    await ctx.send("❌ 至少需要一個權重大於 0。")
                    return
                
                await self.db.update_user_settings(
                    user_id,
                    monkey_buy_weight=buy_w,
                    monkey_sell_weight=sell_w,
                    monkey_hold_weight=hold_w
                )
                
                total = buy_w + sell_w + hold_w
                buy_pct = buy_w / total * 100
                sell_pct = sell_w / total * 100
                hold_pct = hold_w / total * 100
                
                await ctx.send(
                    f"✅ 已更新操作權重：\n"
                    f"買入: {buy_w} ({buy_pct:.1f}%)\n"
                    f"賣出: {sell_w} ({sell_pct:.1f}%)\n"
                    f"持有: {hold_w} ({hold_pct:.1f}%)"
                )
                
            except ValueError:
                await ctx.send("❌ 請輸入有效的整數。")
                return
        
        # Reset to defaults
        elif setting_type in ["reset", "重置", "預設"]:
            await self.db.db.execute("""
                UPDATE user_settings
                SET monkey_min_amount = 5000,
                    monkey_max_amount = 100000,
                    monkey_buy_weight = 35,
                    monkey_sell_weight = 30,
                    monkey_hold_weight = 35,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            await self.db.db.commit()
            
            await ctx.send("✅ 已重置為預設設定。")
        
        else:
            await ctx.send(
                "❌ 未知的設定類型。\n"
                "可用選項: `amount`, `weights`, `reset`"
            )
    
    async def _show_settings(self, ctx: commands.Context, settings):
        """Display current user settings."""
        total_weight = (settings['monkey_buy_weight'] + 
                       settings['monkey_sell_weight'] + 
                       settings['monkey_hold_weight'])
        
        buy_pct = settings['monkey_buy_weight'] / total_weight * 100
        sell_pct = settings['monkey_sell_weight'] / total_weight * 100
        hold_pct = settings['monkey_hold_weight'] / total_weight * 100
        
        embed = discord.Embed(
            title=f"⚙️ {ctx.author.display_name} 的猴子交易設定",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💰 交易金額範圍",
            value=(
                f"最小: ${settings['monkey_min_amount']:,}\n"
                f"最大: ${settings['monkey_max_amount']:,}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎲 操作權重",
            value=(
                f"買入: {settings['monkey_buy_weight']} ({buy_pct:.1f}%)\n"
                f"賣出: {settings['monkey_sell_weight']} ({sell_pct:.1f}%)\n"
                f"持有: {settings['monkey_hold_weight']} ({hold_pct:.1f}%)"
            ),
            inline=False
        )
        
        embed.set_footer(
            text="使用 !usersetting amount/weights 來修改設定"
        )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Required function to load the cog."""
    await bot.add_cog(SettingsCog(bot))