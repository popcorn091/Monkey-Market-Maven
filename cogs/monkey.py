# cogs/monkey.py
"""
Monkey trading Cog - Automated random trading with user-configurable settings
"""

import discord
from discord.ext import commands
import random

# Import from parent directory
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import TradingDatabase
from utils import stock_utils

# Fee constants
HANDLING_FEE = 0.001425
MIN_FEE = 20
ST_TAX = 0.003

class MonkeyCog(commands.Cog):
    """
    Automated trading simulation with weighted random actions.
    User settings stored in user_settings TABLE.
    Sell state stored in monkey_sell_state TABLE.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = TradingDatabase()
        self.cooldown_enabled = False  # Toggle for daily cooldown
    
    def calculate_buy_amount(self, shares: int, price: float) -> float:
        """Calculate total buy amount including fees."""
        base_amount = shares * price
        fee = round(base_amount * HANDLING_FEE, 2)
        return round(base_amount + (MIN_FEE if fee < MIN_FEE else fee), 2)
    
    def calculate_sell_amount(self, shares: int, price: float) -> float:
        """Calculate net sell amount after fees and taxes."""
        base_amount = shares * price
        fee = round(base_amount * HANDLING_FEE, 2)
        
        if fee < MIN_FEE:
            return round(base_amount - (base_amount * ST_TAX) - MIN_FEE, 2)
        
        return round(base_amount * (1 - HANDLING_FEE - ST_TAX), 2)
    
    @commands.command(name="monkey")
    async def monkey_trade(self, ctx: commands.Context, min_amount: int = None, 
                          max_amount: int = None):
        """
        Let the monkey trade for you!
        
        Data Flow:
        1. Load user_settings TABLE for weights and amount limits
        2. Check portfolio TABLE to determine available actions
        3. Randomly choose action based on weights
        4. Execute buy/hold/sell accordingly
        5. For sell: save to monkey_sell_state TABLE, await user input
        
        Usage:
        !monkey - Use default/saved settings
        !monkey 10000 50000 - Use custom amount range
        """
        user_id = str(ctx.author.id)
        str_user_id = str(user_id)
        
        # Check if already in sell state
        sell_state = await self.db.get_monkey_sell_state(str_user_id)
        if sell_state:
            await ctx.send("❌ 您已在等待輸入賣出價格的狀態，請先完成操作。")
            return
        
        # Cooldown check (optional)
        if self.cooldown_enabled:
            # Check last monkey transaction
            cursor = await self.db.db.execute("""
                SELECT timestamp FROM transactions
                WHERE user_id = ? AND command = '!monkey'
                ORDER BY timestamp DESC LIMIT 1
            """, (str_user_id,))
            last_trade = await cursor.fetchone()
            
            if last_trade:
                from datetime import datetime, date
                last_date = datetime.fromisoformat(last_trade['timestamp']).date()
                if last_date == date.today():
                    await ctx.send("🐵 猴子今天已經工作過了，請明天再來！")
                    return
        
        # Get user settings
        settings = await self.db.get_user_settings(str_user_id)
        
        # Use custom amounts if provided, otherwise use settings
        if min_amount is not None and max_amount is not None:
            if min_amount < 0 or max_amount < 0 or min_amount >= max_amount:
                await ctx.send("❌ 金額範圍無效。最小值必須小於最大值。")
                return
            if (max_amount - min_amount) < 1000:
                await ctx.send("❌ 金額範圍太小，至少需要 1000 元的差距。")
                return
            trade_min = min_amount
            trade_max = max_amount
        else:
            trade_min = settings['monkey_min_amount']
            trade_max = settings['monkey_max_amount']
        
        # Get portfolio to check if user has stocks
        holdings = await self.db.get_portfolio(str_user_id)
        has_inventory = len(holdings) > 0
        
        # Prepare action weights
        weights = {
            "buy": settings['monkey_buy_weight'],
            "sell": settings['monkey_sell_weight'] if has_inventory else 0,
            "hold": settings['monkey_hold_weight'] if has_inventory else 0
        }
        
        # If no inventory, force buy or warn
        if not has_inventory:
            weights["buy"] = 100
            weights["sell"] = 0
            weights["hold"] = 0
        
        # Choose action
        actions = list(weights.keys())
        action_weights = list(weights.values())
        chosen_action = random.choices(actions, weights=action_weights, k=1)[0]
        
        await ctx.send(
            f"🍌 猴子操盤手開始工作了 (金額範圍: ${trade_min:,} ~ ${trade_max:,})..."
        )
        
        # Execute chosen action
        if chosen_action == "buy":
            await self._execute_monkey_buy(ctx, str_user_id, trade_min, trade_max)
        elif chosen_action == "hold":
            await self._execute_monkey_hold(ctx)
        elif chosen_action == "sell":
            await self._execute_monkey_sell(ctx, str_user_id, holdings)
    
    async def _execute_monkey_buy(self, ctx, user_id: str, min_amount: int, max_amount: int):
        """Execute monkey buy action."""
        if not stock_utils.stock_data:
            await ctx.send("❌ 股票資料未載入。")
            return
        
        # Random stock selection
        stock_code, stock_name = random.choice(list(stock_utils.stock_data.items()))
        stock_price = stock_utils.get_stock_price(stock_code)
        
        if stock_price <= 0:
            await ctx.send(f"🐵 猴子想買 **{stock_name}**，但查不到它的股價，只好放棄。")
            return
        
        # Random amount
        amount = random.randrange(min_amount, max_amount + 1, 1000)
        shares = int(amount // stock_price)
        
        if shares == 0:
            await ctx.send(f"🐵 猴子想用約 {amount:,} 元買 **{stock_name}**，但錢不夠，只好放棄。")
            return
        
        # Calculate cost
        buy_amount = self.calculate_buy_amount(shares, stock_price)
        
        # Update portfolio
        await self.db.update_portfolio(
            user_id, stock_code, stock_name, shares, buy_amount
        )
        
        # Log transaction
        await self.db.log_transaction(
            user_id, "!monkey", "買入", stock_code, stock_name,
            shares, stock_price, buy_amount, "猴子自動買入"
        )
        
        await ctx.send(
            f"🐵 **買入！** 猴子幫您買了 **{shares}** 股的 **{stock_name}({stock_code})**，"
            f"股價為 **${stock_price}**，總計 **${buy_amount:,.2f}** 元！"
        )
    
    async def _execute_monkey_hold(self, ctx):
        """Execute monkey hold action."""
        await ctx.send("🙉 **持有！** 猴子決定抱緊處理，今天不進行任何操作。")
    
    async def _execute_monkey_sell(self, ctx, user_id: str, holdings):
        """
        Execute monkey sell action.
        Saves state to database and waits for user price input.
        """
        if not holdings:
            await ctx.send("🙈 猴子想賣股票，但您的庫存是空的！")
            return
        
        # Random stock selection from holdings
        holding = random.choice(holdings)
        stock_code = holding['stock_code']
        stock_name = holding['stock_name']
        shares_held = holding['shares']
        total_cost = holding['total_cost']
        
        # Random sell amount (1 to all shares)
        shares_to_sell = random.randint(1, shares_held)
        
        # Calculate average cost
        average_cost = total_cost / shares_held
        
        # Get current price for reference
        current_price = stock_utils.get_stock_price(stock_code)
        price_info = f"目前市場價格為 **${current_price}** 元" if current_price > 0 else ""
        
        # Save sell state to database
        await self.db.save_monkey_sell_state(
            user_id, stock_code, stock_name, shares_to_sell,
            average_cost, str(ctx.channel.id)
        )
        
        await ctx.send(
            f"🙈 {ctx.author.mention}，猴子決定賣出 **{shares_to_sell}** 股的 "
            f"**{stock_name}({stock_code})**！\n"
            f"{price_info}\n"
            f"請在 120 秒內直接於頻道中輸入您要的賣出價格 (純數字)："
        )
    
    async def process_monkey_sell_price(self, message: discord.Message):
        """
        Process sell price input when user is in monkey sell state.
        Called from main bot's on_message handler.
        """
        user_id = str(message.author.id)
        
        # Get sell state
        state = await self.db.get_monkey_sell_state(user_id)
        if not state:
            return False  # Not in sell state
        
        try:
            price_input = float(message.content)
            if price_input <= 0:
                await message.channel.send("❌ 價格必須是正數，請重新輸入：", delete_after=10)
                return True  # Handled but invalid
            
            await message.add_reaction('✅')
            
            # Execute the sell
            sell_price = price_input
            shares_to_sell = state['shares_to_sell']
            average_cost = state['average_cost']
            stock_code = state['stock_code']
            stock_name = state['stock_name']
            
            # Calculate proceeds
            sell_amount = self.calculate_sell_amount(shares_to_sell, sell_price)
            profit_loss = round(sell_amount - (average_cost * shares_to_sell), 2)
            
            # Update portfolio
            cost_basis = average_cost * shares_to_sell
            await self.db.update_portfolio(
                user_id, stock_code, stock_name, -shares_to_sell, -cost_basis
            )
            
            # Log transaction
            await self.db.log_transaction(
                user_id, "!monkey", "賣出", stock_code, stock_name,
                -shares_to_sell, sell_price, sell_amount, "猴子自動賣出"
            )
            
            # Record P&L
            await self.db.record_profit_loss(
                user_id, stock_code, stock_name, shares_to_sell,
                average_cost, sell_price, profit_loss, "猴子交易"
            )
            
            # Clear state
            await self.db.delete_monkey_sell_state(user_id)
            
            await message.channel.send(
                f"🙈 **賣出！** 猴子已遵照您的指示賣出 **{stock_name}({stock_code})**！\n"
                f"賣出 {shares_to_sell} 股，每股 ${sell_price}，淨收入 **${sell_amount:,.2f}** 元，"
                f"實現損益 **${profit_loss:+,.2f}** 元。"
            )
            
            return True  # Successfully handled
            
        except ValueError:
            await message.channel.send("❌ 格式錯誤，請輸入有效的數字價格：", delete_after=10)
            return True  # Handled but invalid
        except Exception as e:
            # Clean up state on error
            await self.db.delete_monkey_sell_state(user_id)
            await message.channel.send(f"❌ 處理賣出時發生錯誤: {e}")
            return True

async def setup(bot: commands.Bot):
    """Required function to load the cog."""

    await bot.add_cog(MonkeyCog(bot))

