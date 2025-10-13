# cogs/general.py
"""
General commands Cog - Help and utility commands
"""

import discord
from discord.ext import commands

class GeneralCog(commands.Cog):
    """General bot commands and help system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.command(name="bothelp")
    async def bothelp_command(self, ctx: commands.Context):
        """
        Display comprehensive help for all bot commands.
        """
        embed = discord.Embed(
            title="🤖 Monkey Market Maven 指令說明書",
            description="虛擬股票交易機器人 - 所有指令列表",
            color=discord.Color.orange()
        )
        
        # Trading Commands
        embed.add_field(
            name="📈 **交易指令**",
            value=(
                "`!random` - 隨機挑選一支股票並產生模擬交易\n"
                "`!ry` - 確認 random 產生的交易\n"
                "`!rn` - 取消 random 產生的交易\n"
                "`!buy <股票> <股數> [價格]` - 買入股票\n"
                "`!sell <股票> <股數> [價格]` - 賣出股票"
            ),
            inline=False
        )
        
        # Portfolio Commands
        embed.add_field(
            name="💼 **投資組合**",
            value=(
                "`!summary` - 顯示庫存摘要與市值\n"
                "`!adjust_cost <股票> <新成本>` - 調整持股成本\n"
                "`!show [數量]` - 顯示最近的操作紀錄 (預設5筆)"
            ),
            inline=False
        )
        
        # Profit/Loss Commands
        embed.add_field(
            name="💰 **損益管理**",
            value=(
                "`!profit` - 查看總已實現損益\n"
                "`!profitclear` - 清空損益紀錄（歸零）"
            ),
            inline=False
        )
        
        # Monkey Trading
        embed.add_field(
            name="🐵 **猴子交易**",
            value=(
                "`!monkey [最小] [最大]` - 讓猴子隨機操盤\n"
                "`!usersetting` - 查看猴子交易設定\n"
                "`!usersetting amount <最小> <最大>` - 設定交易金額\n"
                "`!usersetting weights <買> <賣> <持有>` - 設定操作權重\n"
                "`!usersetting reset` - 重置為預設值"
            ),
            inline=False
        )
        
        # Examples
        embed.add_field(
            name="💡 **使用範例**",
            value=(
                "`!buy 2330 10` - 以市價買入 10 股台積電\n"
                "`!buy 0050 5 150` - 以 150 元買入 5 股 0050\n"
                "`!sell 2330 5` - 賣出 5 股台積電\n"
                "`!monkey 10000 50000` - 猴子在 1-5萬範圍內交易"
            ),
            inline=False
        )
        
        # Notes
        embed.add_field(
            name="📝 **注意事項**",
            value=(
                "• 股票代碼或名稱皆可使用\n"
                "• 買賣自動計算手續費 (0.1425%, 最低20元)\n"
                "• 賣出自動計算證交稅 (0.3%)\n"
                "• 所有價格以新台幣計算"
            ),
            inline=False
        )
        
        embed.set_footer(text="Monkey Market Maven | 資料僅供娛樂與學習使用")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! 延遲: {latency}ms")
    
    @commands.command(name="info")
    async def info_command(self, ctx: commands.Context):
        """Display bot information."""
        embed = discord.Embed(
            title="🤖 Monkey Market Maven",
            description="虛擬股票交易模擬機器人",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="版本",
            value="2.0 (Database Edition)",
            inline=True
        )
        
        embed.add_field(
            name="伺服器數",
            value=f"{len(self.bot.guilds)}",
            inline=True
        )
        
        embed.add_field(
            name="資料儲存",
            value="SQLite Database",
            inline=True
        )
        
        embed.add_field(
            name="功能",
            value="• 虛擬股票交易\n• 損益追蹤\n• 自動化猴子交易\n• 即時股價查詢",
            inline=False
        )
        
        embed.set_footer(text="使用 !bothelp 查看所有指令")
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Required function to load the cog."""

    await bot.add_cog(GeneralCog(bot))
