# cogs/portfolio.py
"""
Portfolio management Cog - Handles summary, adjust_cost, show commands
"""

import discord
from discord.ext import commands
from datetime import datetime
import os

# Import from parent directory
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database.schema import TradingDatabase
from utils import stock_utils

# For image generation (if PIL is available)
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Fee constants for P&L calculation
HANDLING_FEE = 0.001425
MIN_FEE = 20
ST_TAX = 0.003

class PortfolioCog(commands.Cog):
    """
    Handles portfolio display and management operations.
    All data retrieved from database tables.
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = TradingDatabase()
    
    @commands.command(name="summary")
    async def portfolio_summary(self, ctx: commands.Context):
        """
        Display portfolio summary with current market values and P&L.
        
        Data Flow:
        1. Query portfolio TABLE for all holdings
        2. Fetch current prices via API
        3. Calculate unrealized P&L for each position
        4. Generate visual summary (image or embed)
        """
        user_id = str(ctx.author.id)
        
        # Get all holdings from database
        holdings = await self.db.get_portfolio(user_id)
        
        if not holdings:
            await ctx.send("📭 您的庫存目前是空的。")
            return
        
        # Build summary data
        summary_rows = []
        total_cost = 0
        total_value = 0
        total_profit = 0
        
        for holding in holdings:
            stock_code = holding['stock_code']
            stock_name = holding['stock_name']
            shares = holding['shares']
            cost = holding['total_cost']
            
            current_price = stock_utils.get_stock_price(stock_code)
            avg_cost = cost / shares if shares > 0 else 0
            
            if current_price > 0:
                current_value = shares * current_price
                
                # Calculate P&L if sold now (with fees and taxes)
                fee = round(current_value * HANDLING_FEE, 2)
                if fee < MIN_FEE:
                    net_proceeds = round(current_value - (current_value * ST_TAX) - MIN_FEE, 2)
                else:
                    net_proceeds = round(current_value * (1 - HANDLING_FEE - ST_TAX), 2)
                
                profit_loss = round(net_proceeds - cost, 2)
                profit_pct = (profit_loss / cost * 100) if cost > 0 else 0
                
                summary_rows.append({
                    'stock': f"{stock_name}({stock_code})",
                    'shares': shares,
                    'avg_cost': avg_cost,
                    'current_price': current_price,
                    'current_value': current_value,
                    'profit_loss': profit_loss,
                    'profit_pct': profit_pct
                })
                
                total_cost += cost
                total_value += current_value
                total_profit += profit_loss
            else:
                summary_rows.append({
                    'stock': f"{stock_name}({stock_code})",
                    'shares': shares,
                    'avg_cost': avg_cost,
                    'current_price': 'N/A',
                    'current_value': 'N/A',
                    'profit_loss': 'N/A',
                    'profit_pct': 'N/A'
                })
                total_cost += cost
        
        # Try to generate image, fall back to embed
        if PIL_AVAILABLE and len(summary_rows) > 0:
            try:
                await self._send_summary_image(ctx, summary_rows, total_cost, 
                                              total_value, total_profit)
                return
            except Exception as e:
                print(f"圖片生成失敗，改用文字摘要: {e}")
        
        # Fallback: Text-based embed
        await self._send_summary_embed(ctx, summary_rows, total_cost, 
                                      total_value, total_profit)
    
    async def _send_summary_embed(self, ctx, rows, total_cost, total_value, total_profit):
        """Send portfolio summary as Discord embed."""
        embed = discord.Embed(
            title=f"📊 {ctx.author.display_name} 的投資組合摘要",
            color=discord.Color.green() if total_profit >= 0 else discord.Color.red()
        )
        
        for row in rows[:10]:  # Limit to 10 to avoid embed size limits
            value_str = f"${row['current_value']:,.0f}" if row['current_value'] != 'N/A' else 'N/A'
            pl_str = f"${row['profit_loss']:+,.0f} ({row['profit_pct']:+.2f}%)" \
                     if row['profit_loss'] != 'N/A' else 'N/A'
            
            embed.add_field(
                name=row['stock'],
                value=(
                    f"持股: {row['shares']:,} 股\n"
                    f"均價: ${row['avg_cost']:,.2f}\n"
                    f"市值: {value_str}\n"
                    f"損益: {pl_str}"
                ),
                inline=True
            )
        
        if len(rows) > 10:
            embed.add_field(name="...", value=f"還有 {len(rows)-10} 檔股票", inline=False)
        
        # Total summary
        total_shares = sum(r['shares'] for r in rows)
        profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0
        
        embed.add_field(
            name="📈 總計",
            value=(
                f"總股數: {total_shares:,}\n"
                f"總成本: ${total_cost:,.0f}\n"
                f"總市值: ${total_value:,.0f}\n"
                f"未實現損益: ${total_profit:+,.0f} ({profit_pct:+.2f}%)"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def _send_summary_image(self, ctx, rows, total_cost, total_value, total_profit):
        """Generate and send portfolio summary as image (same as original code)."""
        # Image generation code (similar to original but reading from database)
        row_height = 50
        header_height = 200
        footer_height = 80
        img_width = 1200
        img_height = header_height + len(rows)*row_height + footer_height

        img = Image.new("RGB", (img_width, img_height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
        if not os.path.exists(font_path):
            raise FileNotFoundError("NotoSansCJK font not found")

        font = ImageFont.truetype(font_path, 28)
        bold_font = ImageFont.truetype(font_path, 34)

        # Title
        draw.text((20, 20), f"📊 {ctx.author.display_name} 的投資組合摘要",
                  fill="white", font=bold_font)

        # Headers
        headers = ["股票", "股數", "均價", "現價", "市值", "損益", "報酬率"]
        x_positions = [20, 200, 360, 500, 640, 820, 970]
        col_widths  = [230, 120, 120, 120, 140, 150, 120]

        for x, w, h in zip(x_positions, col_widths, headers):
            text_width = draw.textlength(h, font=font)
            draw.text((x + (w - text_width)/2, 100), h, fill="white", font=font)

        # Data rows
        y = header_height
        for row in rows:
            texts = [
                row['stock'],
                f"{int(row['shares']):,}",
                f"{row['avg_cost']:,.2f}",
                f"{row['current_price']:,.2f}" if row['current_price'] != 'N/A' else 'N/A',
                f"{row['current_value']:,.2f}" if row['current_value'] != 'N/A' else 'N/A',
                f"{row['profit_loss']:+,.2f}" if row['profit_loss'] != 'N/A' else 'N/A',
                f"{row['profit_pct']:+.2f}%" if row['profit_pct'] != 'N/A' else 'N/A'
            ]
            
            for i, text in enumerate(texts):
                if i == 0:  # Stock name centered
                    text_width = draw.textlength(text, font=font)
                    draw.text((x_positions[i] + (col_widths[i] - text_width)/2, y),
                              text, fill="white", font=font)
                else:  # Numbers right-aligned
                    if i in [5, 6] and text != "N/A":
                        try:
                            value = float(text.replace(",", "").replace("%", "").replace("+", ""))
                            color = "green" if value >= 0 else "red"
                        except:
                            color = "white"
                    else:
                        color = "white"
                    text_width = draw.textlength(text, font=font)
                    draw.text((x_positions[i] + col_widths[i] - text_width, y),
                              text, fill=color, font=font)
            y += row_height

        # Totals
        if total_cost > 0:
            profit_pct = total_profit / total_cost * 100
            total_shares = sum(r['shares'] for r in rows)

            prefix = f"總計  股數:{total_shares:,}  市值:${total_value:,.2f}  "
            draw.text((20, y + 20), prefix, fill="white", font=bold_font)

            profit_text = f"損益:${total_profit:+,.2f}  報酬率:{profit_pct:+.2f}%"
            profit_color = "green" if total_profit >= 0 else "red"
            profit_width = draw.textlength(profit_text, font=bold_font)
            draw.text((img_width - 20 - profit_width, y + 20), profit_text, 
                     fill=profit_color, font=bold_font)

        # Save and send
        file_path = f"portfolio_{ctx.author.id}.png"
        img.save(file_path)
        await ctx.send(file=discord.File(file_path))
        
        # Clean up
        try:
            os.remove(file_path)
        except:
            pass
    
    @commands.command(name="adjust_cost")
    async def adjust_cost(self, ctx: commands.Context, stock_identifier: str, 
                         new_cost: float):
        """
        Manually adjust the average cost of a holding.
        
        Data Flow:
        1. Query portfolio TABLE
        2. Calculate new total cost
        3. Update portfolio TABLE
        4. Log to transactions TABLE
        """
        user_id = str(ctx.author.id)
        
        if new_cost <= 0:
            await ctx.send("❌ 新的成本必須是正數。")
            return
        
        stock_code, stock_name = stock_utils.get_stock_info(stock_identifier)
        if not stock_code:
            await ctx.send(f"❌ 找不到股票 `{stock_identifier}`。")
            return
        
        # Check if user owns this stock
        holding = await self.db.get_stock_holding(user_id, stock_code)
        if not holding or holding['shares'] <= 0:
            await ctx.send(f"❌ 您目前未持有 **{stock_name}({stock_code})**。")
            return
        
        # Calculate cost adjustment
        old_avg_cost = holding['total_cost'] / holding['shares']
        success = await self.db.adjust_cost(user_id, stock_code, new_cost)
        
        if success:
            # Log the adjustment
            await self.db.log_transaction(
                user_id, "!adjust_cost", "調整成本",
                stock_code, stock_name, 0, 0, 0,
                f"從 ${old_avg_cost:.2f} 調整為 ${new_cost:.2f}"
            )
            
            await ctx.send(
                f"✅ 已將 **{stock_name}({stock_code})** 的平均成本調整為 **${new_cost:,.2f}**。"
            )
        else:
            await ctx.send("❌ 調整失敗，請稍後再試。")
    
    @commands.command(name="show")
    async def show_recent(self, ctx: commands.Context, limit: int = 5):
        """
        Display the N most recent transactions.
        
        Data Flow:
        1. Query transactions TABLE
        2. Format and display results
        """
        user_id = str(ctx.author.id)
        
        if limit < 1 or limit > 20:
            await ctx.send("❌ 顯示數量必須在 1-20 之間。")
            return
        
        # Get recent transactions from database
        transactions = await self.db.get_recent_transactions(user_id, limit)
        
        if not transactions:
            await ctx.send("📭 您還沒有任何操作紀錄。")
            return
        
        embed = discord.Embed(
            title=f"📜 最近 {len(transactions)} 筆操作紀錄",
            color=discord.Color.blue()
        )
        
        for i, tx in enumerate(transactions, 1):
            timestamp = datetime.fromisoformat(tx['timestamp']).strftime('%Y-%m-%d %H:%M')
            
            value_text = (
                f"**時間:** {timestamp}\n"
                f"**指令:** {tx['command']}\n"
                f"**類型:** {tx['transaction_type']}\n"
                f"**股票:** {tx['stock_name']}({tx['stock_code']})\n"
                f"**股數:** {tx['shares']:+,} 股\n"
                f"**價格:** ${tx['price']:,.2f}\n"
                f"**金額:** ${tx['amount']:,.2f}"
            )
            
            embed.add_field(
                name=f"#{i}",
                value=value_text,
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Required function to load the cog."""

    await bot.add_cog(PortfolioCog(bot))

