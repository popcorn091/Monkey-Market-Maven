# cogs/trading.py
"""
Trading operations Cog - Handles buy, sell, random, ry, rn commands
"""

import discord
from discord.ext import commands
import random
from typing import Optional

# Import from parent directory
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import TradingDatabase
from utils import stock_utils

# Fee constants
HANDLING_FEE = 0.001425  # 0.1425%
MIN_FEE = 20
ST_TAX = 0.003  # 0.3%

class TradingCog(commands.Cog):
    """
    Handles all trading operations: buy, sell, random selection.
    All data now flows through the database instead of CSV files.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = TradingDatabase()
    
    def calculate_buy_amount(self, shares: int, price: float) -> float:
        """Calculate total buy amount including fees."""
        base_amount = shares * price
        fee = round(base_amount * HANDLING_FEE, 2)
        
        if fee < MIN_FEE:
            return round(base_amount + MIN_FEE, 2)
        return round(base_amount + fee, 2)
    
    def calculate_sell_amount(self, shares: int, price: float) -> float:
        """Calculate net sell amount after fees and taxes."""
        base_amount = shares * price
        fee = round(base_amount * HANDLING_FEE, 2)
        
        if fee < MIN_FEE:
            return round(base_amount - (base_amount * ST_TAX) - MIN_FEE, 2)
        
        total_deduction = base_amount * (HANDLING_FEE + ST_TAX)
        return round(base_amount - total_deduction, 2)
    
    @commands.command(name="random")
    async def random_stock(self, ctx: commands.Context):
        """
        Randomly select a stock and generate a trade proposal.
        
        Data Flow:
        1. Random stock selection from stock_data (still from CSV)
        2. Get current price via API
        3. Save to pending_trades TABLE (not CSV)
        """
        user_id = str(ctx.author.id)
        
        if not stock_utils.stock_data:
            await ctx.send("❌ 股票資料未載入，無法執行隨機選股。")
            return
        
        # Check if user already has a pending trade
        existing = await self.db.get_pending_trade(user_id)
        if existing:
            await ctx.send(f"⚠️ 您已有待確認的交易，請先使用 `!ry` 或 `!rn` 回覆。")
            return
        
        # Random selection
        stock_code, stock_name = random.choice(list(stock_utils.stock_data.items()))
        stock_price = stock_utils.get_stock_price(stock_code)
        
        if stock_price <= 0:
            await ctx.send(f"❌ 無法取得 {stock_name}({stock_code}) 的有效股價。")
            return
        
        # Generate random amount and calculate shares
        amount = random.randrange(5000, 100001, 1000)
        shares = int(amount // stock_price)
        
        if shares == 0:
            await ctx.send(
                f"以 {amount:,} 元的預算，無法購買至少一股 {stock_name}({stock_code})。"
            )
            return
        
        total_amount = self.calculate_buy_amount(shares, stock_price)
        
        # Save to database (not CSV!)
        await self.db.save_pending_trade(
            user_id, stock_code, stock_name, shares, stock_price, total_amount
        )
        
        embed = discord.Embed(title="🎲 隨機選股產生器", color=discord.Color.blue())
        embed.add_field(name="股票", value=f"{stock_name}({stock_code})", inline=False)
        embed.add_field(name="股數", value=f"{shares} 股", inline=True)
        embed.add_field(name="股價", value=f"${stock_price:,.2f}", inline=True)
        embed.add_field(name="總金額", value=f"${total_amount:,.2f}", inline=False)
        embed.set_footer(text="是否買入? 請使用 !ry (是) 或 !rn (否) 指令回覆。")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="ry")
    async def confirm_random(self, ctx: commands.Context):
        """
        Confirm and execute the pending random trade.
        
        Data Flow:
        1. Retrieve from pending_trades TABLE
        2. Update portfolio TABLE
        3. Log to transactions TABLE
        4. Delete from pending_trades TABLE
        """
        user_id = str(ctx.author.id)
        
        trade = await self.db.get_pending_trade(user_id)
        if not trade:
            await ctx.send("❌ 您沒有待確認的購買交易。")
            return
        
        # Execute the trade
        await self.db.update_portfolio(
            user_id,
            trade['stock_code'],
            trade['stock_name'],
            trade['shares'],
            trade['amount']
        )
        
        # Log the transaction
        await self.db.log_transaction(
            user_id,
            "!random -> !ry",
            "買入",
            trade['stock_code'],
            trade['stock_name'],
            trade['shares'],
            trade['price'],
            trade['amount']
        )
        
        # Remove pending trade
        await self.db.delete_pending_trade(user_id)
        
        await ctx.send(
            f"✅ **購買成功！** 已將 **{trade['stock_name']}({trade['stock_code']})** "
            f"加入您的庫存。共 {trade['shares']} 股，總計 ${trade['amount']:,.2f} 元。"
        )
    
    @commands.command(name="rn")
    async def cancel_random(self, ctx: commands.Context):
        """Cancel the pending random trade."""
        user_id = str(ctx.author.id)
        
        trade = await self.db.get_pending_trade(user_id)
        if not trade:
            await ctx.send("❌ 您沒有待確認的購買交易。")
            return
        
        await self.db.delete_pending_trade(user_id)
        await ctx.send("👌 交易已取消。")
    
    @commands.command(name="buy")
    async def buy_stock(self, ctx: commands.Context, stock_identifier: str,
                       shares_to_buy: int, custom_price: float = None):
        """
        Buy stock command with optional custom price.
        
        Data Flow:
        1. Validate stock and get current price
        2. Calculate total cost with fees
        3. Update portfolio TABLE
        4. Log to transactions TABLE
        
        Parameters:
        - stock_identifier: Stock code or name
        - shares_to_buy: Number of shares
        - custom_price: Optional custom price (default: use real-time price)
        """
        user_id = str(ctx.author.id)
        
        stock_code, stock_name = stock_utils.get_stock_info(stock_identifier)
        if not stock_code:
            await ctx.send(f"❌ 找不到股票 `{stock_identifier}`。")
            return
        
        if shares_to_buy <= 0:
            await ctx.send("❌ 購買股數必須為正整數。")
            return
        
        # Determine price
        if custom_price is not None:
            if custom_price <= 0:
                await ctx.send("❌ 自訂價格必須為正數。")
                return
            current_price = custom_price
            price_source = "(自訂價格)"
        else:
            current_price = get_stock_price(stock_code)
            if current_price <= 0:
                await ctx.send(f"❌ 無法取得 **{stock_name}({stock_code})** 的即時股價。")
                return
            price_source = "(即時市價)"
        
        # Calculate total amount
        buy_amount = self.calculate_buy_amount(shares_to_buy, current_price)
        
        # Update portfolio in database
        await self.db.update_portfolio(
            user_id, stock_code, stock_name, shares_to_buy, buy_amount
        )
        
        # Log transaction
        await self.db.log_transaction(
            user_id, "!buy", "買入", stock_code, stock_name,
            shares_to_buy, current_price, buy_amount, price_source
        )
        
        await ctx.send(
            f"✅ **購買成功！** 您已購買了 {shares_to_buy} 股 "
            f"**{stock_name}({stock_code})**，買入股價為 **{current_price}** 元 {price_source}，"
            f"總計 **{buy_amount:,.2f}** 元。"
        )
    
    @buy_stock.error
    async def buy_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ 指令參數不足！請使用 `!buy <股票代碼/名稱> <股數> [價格]` 格式。")
    
    @commands.command(name="sell")
    async def sell_stock(self, ctx: commands.Context, stock_identifier: str,
                        shares_to_sell: int, custom_price: float = None):
        """
        Sell stock command with profit/loss calculation.
        
        Data Flow:
        1. Query portfolio TABLE to check holdings
        2. Calculate average cost from portfolio
        3. Calculate P&L and net proceeds
        4. Update portfolio TABLE (reduce shares)
        5. Log to transactions TABLE
        6. Record in profit_loss TABLE
        """
        user_id = str(ctx.author.id)
        
        stock_code, stock_name = stock_utils.get_stock_info(stock_identifier)
        if not stock_code:
            await ctx.send(f"❌ 找不到股票 `{stock_identifier}`。")
            return
        
        if shares_to_sell <= 0:
            await ctx.send("❌ 賣出股數必須為正整數。")
            return
        
        # Check holdings
        holding = await self.db.get_stock_holding(user_id, stock_code)
        if not holding or holding['shares'] < shares_to_sell:
            current = holding['shares'] if holding else 0
            await ctx.send(
                f"❌ 操作失敗：您的庫存中只有 {int(current)} 股 "
                f"**{stock_name}({stock_code})**，不足以賣出 {shares_to_sell} 股。"
            )
            return
        
        # Determine price
        if custom_price is not None:
            if custom_price <= 0:
                await ctx.send("❌ 自訂價格必須為正數。")
                return
            current_price = custom_price
            price_source = "(自訂價格)"
        else:
            current_price = get_stock_price(stock_code)
            if current_price <= 0:
                await ctx.send(f"❌ 無法取得 **{stock_name}({stock_code})** 的有效股價。")
                return
            price_source = "(即時市價)"
        
        # Calculate average cost
        average_cost_price = holding['total_cost'] / holding['shares']
        
        # Calculate sell proceeds
        sell_amount = self.calculate_sell_amount(shares_to_sell, current_price)
        
        # Calculate profit/loss
        cost_basis = average_cost_price * shares_to_sell
        profit_loss = round(sell_amount - cost_basis, 2)
        
        # Update portfolio (reduce shares and cost)
        await self.db.update_portfolio(
            user_id, stock_code, stock_name,
            -shares_to_sell,
            -cost_basis
        )
        
        # Log transaction
        await self.db.log_transaction(
            user_id, "!sell", "賣出", stock_code, stock_name,
            -shares_to_sell, current_price, sell_amount, price_source
        )
        
        # Record P&L
        await self.db.record_profit_loss(
            user_id, stock_code, stock_name, shares_to_sell,
            average_cost_price, current_price, profit_loss
        )
        
        # Send response
        profit_loss_color = discord.Color.green() if profit_loss >= 0 else discord.Color.red()
        embed = discord.Embed(title="✅ 賣出成功！", color=profit_loss_color)
        embed.description = f"您已賣出 {shares_to_sell} 股 **{stock_name}({stock_code})**。"
        embed.add_field(name=f"賣出價格 {price_source}",
                       value=f"${current_price:,.2f}", inline=True)
        embed.add_field(name="平均成本",
                       value=f"${average_cost_price:,.2f}", inline=True)
        embed.add_field(name="淨收入",
                       value=f"${sell_amount:,.2f}", inline=True)
        embed.add_field(name="損益", value=f"**${profit_loss:,.2f}**", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Required function to load the cog."""

    await bot.add_cog(TradingCog(bot))

