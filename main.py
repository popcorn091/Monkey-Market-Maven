# main.py - Refactored Discord Stock Trading Bot
"""
Monkey Market Maven - Database Edition
A virtual stock trading bot using Discord.py and SQLite
"""

import discord
from discord.ext import commands
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Import our modules
from database.schema import TradingDatabase
from utils.stock_utils import load_stock_data

# ========== Configuration ==========
load_dotenv()
TOKEN = os.getenv("TOKEN")

if not TOKEN:
    print("❌ 錯誤：找不到 Discord Bot Token。請檢查您的 .env 檔案。")
    exit()

# ========== Bot Initialization ==========
intents = discord.Intents.default()
intents.message_content = True  # Required for message content access
intents.members = False  # Not needed for this bot

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None  # We have custom help
)

# ========== Event Handlers ==========

@bot.event
async def on_ready():
    """Called when bot successfully connects to Discord."""
    print(f'🤖 機器人 {bot.user.name} ({bot.user.id}) 已成功登入！')
    print(f'📊 連接到 {len(bot.guilds)} 個伺服器')
    
    # Initialize database
    db = TradingDatabase()
    await db.connect()
    
    # Load stock data from CSV (this part stays the same)
    load_stock_data()
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Game(name="!bothelp 查看指令"),
        status=discord.Status.online
    )
    
    print("✅ 機器人已就緒！")


@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Global error handler for all commands."""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore invalid commands
    
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ 缺少必要參數：`{error.param.name}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ 參數格式錯誤，請檢查後再試。")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ 您沒有權限使用此指令。")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ 機器人缺少必要權限！")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏰ 此指令冷卻中，請在 {error.retry_after:.1f} 秒後再試。")
    else:
        # Log unexpected errors
        print(f"❌ 指令錯誤 [{ctx.command}]: {error}")
        await ctx.send("❌ 執行指令時發生錯誤。")


@bot.event
async def on_message(message: discord.Message):
    """
    Custom message handler to process monkey sell state.
    
    Data Flow:
    1. Check if user is in monkey sell state (query monkey_sell_state TABLE)
    2. If yes, process price input via MonkeyCog
    3. Otherwise, process commands normally
    """
    # Ignore bot messages
    if message.author.bot:
        return
    
    user_id = str(message.author.id)
    
    # Priority: Check if user is in monkey sell state
    db = TradingDatabase()
    monkey_state = await db.get_monkey_sell_state(user_id)
    
    if monkey_state:
        # User is waiting to input sell price
        monkey_cog = bot.get_cog("MonkeyCog")
        if monkey_cog:
            handled = await monkey_cog.process_monkey_sell_price(message)
            if handled:
                return  # Don't process as command
    
    # Check for pending trades (warn if trying to use other commands)
    pending_trade = await db.get_pending_trade(user_id)
    if pending_trade and not message.content.startswith(('!ry', '!rn', '!bothelp')):
        await message.channel.send(
            f"⚠️ {message.author.mention}，您有一筆隨機選股交易待確認，"
            f"請先使用 `!ry` 或 `!rn` 回覆。"
        )
        return
    
    # Process commands normally
    await bot.process_commands(message)


# ========== Cog Loading ==========

async def load_cogs():
    """Load all Cog modules."""
    cog_list = [
        "cogs.general",      # Help and general commands
        "cogs.trading",      # Buy, sell, random commands
        "cogs.portfolio",    # Summary, adjust_cost, show
        "cogs.profit",       # Profit tracking
        "cogs.monkey",       # Monkey trading
        "cogs.settings",     # User settings
    ]
    
    for cog in cog_list:
        try:
            await bot.load_extension(cog)
            print(f"✅ 已載入: {cog}")
        except Exception as e:
            print(f"❌ 載入失敗 {cog}: {e}")


# ========== Startup ==========

async def main():
    """Main entry point."""
    async with bot:
        # Load all cogs
        await load_cogs()
        
        # Start the bot
        await bot.start(TOKEN)


# ========== Entry Point ==========

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 機器人已關閉")
    except Exception as e:
        print(f"❌ 嚴重錯誤: {e}")
