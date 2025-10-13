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

    # 檢查是否正在歸檔，若是則暫停服務
    if is_archiving:
        await message.channel.send("系統正在進行每月資料整理，請稍後再試。", delete_after=10)
        return

    user_id = message.author.id
    # 優先處理猴子賣出狀態
    if user_id in monkey_sell_state:
        # (此處為猴子狀態處理邏輯，與前版本相同)
        try:
            price_input = float(message.content)
            if price_input <= 0:
                await message.channel.send("價格必須是正數，請重新輸入：", delete_after=10)
                return
            await message.add_reaction('✅')
            state_data = monkey_sell_state.pop(user_id)

            sell_price = price_input
            stock_code, stock_name, shares_to_sell, avg_cost = state_data[
                "stock_code"], state_data["stock_name"], state_data[
                    "shares_to_sell"], state_data["average_cost"]
            
                        
            if round(sell_price * shares_to_sell * handing_fee ,2) < 20:
                sell_amount = round(shares_to_sell * sell_price - (sell_price * ST_tax + 20), 2)
            else:
                sell_amount = round(shares_to_sell * sell_price - (sell_price * (handing_fee + ST_tax)), 2) #新增賣出含手續費&證交稅計算，手續費低於20元以20元計  za 250919.2048

            profit_loss = round(sell_amount - avg_cost * shares_to_sell , 2)
            
            log_to_user_csv(str(user_id), "!monkey", "庫存", stock_code,
                            stock_name, -shares_to_sell, sell_price,
                            -sell_amount)
            log_to_user_csv(str(user_id), "!monkey", "操作", stock_code,
                            stock_name, -shares_to_sell, sell_price,
                            sell_amount)
            log_to_user_csv(str(user_id),
                            "!monkey",
                            "損益",
                            stock_code,
                            stock_name,
                            shares_to_sell,
                            sell_price,
                            sell_amount,
                            profit_loss=profit_loss)
            await message.channel.send(
                f"🙈 **賣出！** 猴子已遵照您的指示賣出 **{stock_name}({stock_code})**！ 總計 **{sell_amount}** 元，實現損益共 **{profit_loss}** 元。")
        except ValueError:
            await message.channel.send("格式錯誤，請輸入有效的數字價格：", delete_after=10)
        except Exception as e:
            if user_id in monkey_sell_state: del monkey_sell_state[user_id]
            await message.channel.send(f"處理賣出時發生錯誤: {e}")
        return

    # 接著處理一般邏輯
    str_user_id = str(user_id)
    if str_user_id in pending_trades and not message.content.startswith(
        ('!ry', '!rn')):
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
    
    if round(shares_to_sell * average_cost_price * handing_fee ,2) < 20:
        sell_amount = round(shares_to_sell * current_price * (1 - ST_tax) - 20, 2)
    else:
        sell_amount = round(shares_to_sell * current_price * (1 - (handing_fee + ST_tax)), 2) #新增賣出含手續費&證交稅計算，手續費低於20元以20元計  za 250919.1820

    profit_loss = round(sell_amount - average_cost_price * shares_to_sell , 2)

    log_to_user_csv(user_id, "!sell", "庫存", stock_code, stock_name,
                    -shares_to_sell, current_price, -shares_to_sell * current_price)
    log_to_user_csv(user_id, "!sell", "操作", stock_code, stock_name,
                    -shares_to_sell, current_price, sell_amount)
    log_to_user_csv(user_id,
                    "!sell",
                    "損益",
                    stock_code,
                    stock_name,
                    shares_to_sell,
                    current_price,
                    sell_amount,
                    profit_loss=profit_loss)

    profit_loss_color = discord.Color.green(
    ) if profit_loss >= 0 else discord.Color.red()
    embed = discord.Embed(title="✅ 賣出成功！", color=profit_loss_color)
    embed.description = f"您已賣出 {shares_to_sell} 股 **{stock_name}({stock_code})**。"
    embed.add_field(name=f"賣出價格 {price_source_text}",
                    value=f"${current_price:,.2f}",
                    inline=True)
    embed.add_field(name="平均成本",
                    value=f"${average_cost_price:,.2f}",
                    inline=True)
    embed.add_field(name="損益", value=f"**${profit_loss:,.2f}**", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="summary")
async def summary_image(ctx):
    user_id = str(ctx.author.id)
    create_user_csv_if_not_exists(user_id)
    df = get_user_data(user_id)
    inventory = df[df['類別'] == '庫存']

    if inventory.empty:
        await ctx.send("您的庫存目前是空的。")
        return

    # 匯總資料
    summary_data = inventory.groupby(['股票代碼', '股票名稱']).agg(
        股數=('股數', 'sum'),
        總成本=('金額', 'sum')
    ).reset_index()
    summary_data = summary_data[summary_data['股數'] > 0]

    if summary_data.empty:
        await ctx.send("您的庫存目前是空的。")
        return

    # 生成表格資料
    rows = []
    total_cost = total_value = total_profit = 0
    for _, row in summary_data.iterrows():
        current_price = get_stock_price(row['股票代碼'])
        avg_cost = row['總成本'] / row['股數']
        if current_price > 0:
            current_value = row['股數'] * current_price
            if round(current_value * handing_fee ,2) < 20:
                profit_loss = round(current_value - (row['總成本'] + (current_value * ST_tax) + 20), 2)
            else:
                profit_loss = round(current_value - (row['總成本'] + (current_value * (handing_fee + ST_tax))), 2) #新增賣出含手續費&證交稅計算，手續費低於20元以20元計  za 250919.2048
            
            profit_pct = profit_loss / row['總成本'] * 100
            rows.append([
                f"{row['股票名稱']}({row['股票代碼']})",
                f"{int(row['股數']):,}",
                f"{avg_cost:,.2f}",
                f"{current_price:,.2f}",
                f"{current_value:,.2f}",
                f"{profit_loss:+,.2f}",
                f"{profit_pct:+.2f}%"
            ])
            total_cost += row['總成本']
            total_value += current_value
            total_profit += profit_loss
        else:
            rows.append([
                f"{row['股票名稱']}({row['股票代碼']})",
                f"{int(row['股數']):,}",
                f"{avg_cost:,.2f}",
                "N/A", "N/A", "N/A", "N/A"
            ])
            total_cost += row['總成本']

    # --- 產生圖片設定 ---
    row_height = 50
    header_height = 200
    footer_height = 80
    img_width = 1200
    img_height = header_height + len(rows)*row_height + footer_height

    img = Image.new("RGB", (img_width, img_height), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    if not os.path.exists(font_path):
        await ctx.send("❌ 找不到 NotoSansCJK 字型，請先安裝 fonts-noto-cjk")
        return

    font = ImageFont.truetype(font_path, 28)
    bold_font = ImageFont.truetype(font_path, 34)

    # 標題
    draw.text((20, 20), f"📊 {ctx.author.display_name} 的投資組合摘要",
              fill="white", font=bold_font)

    # 表頭與欄位設定
    headers = ["股票", "股數", "均價", "現價", "市值", "損益", "報酬率"]
    x_positions = [20, 200, 360, 500, 640, 820, 970]
    col_widths  = [230, 120, 120, 120, 140, 150, 120]

    # 畫表頭 (置中)
    for x, w, h in zip(x_positions, col_widths, headers):
        text_width = draw.textlength(h, font=font)
        draw.text((x + (w - text_width)/2, 100), h, fill="white", font=font)

    # 表格內容
    y = header_height
    for r in rows:
        for i, text in enumerate(r):
            if i == 0:  # 股票名稱置中
                text_width = draw.textlength(text, font=font)
                draw.text((x_positions[i] + (col_widths[i] - text_width)/2, y),
                          text, fill="white", font=font)
            else:  # 數字靠右
                # 損益與報酬率顯示紅綠
                if i in [5, 6] and text != "N/A":
                    value = float(text.replace(",", "").replace("%", ""))
                    color = "green" if value >= 0 else "red"
                else:
                    color = "white"
                text_width = draw.textlength(text, font=font)
                draw.text((x_positions[i] + col_widths[i] - text_width, y),
                          text, fill=color, font=font)
        y += row_height

    # 總計
    if total_cost > 0:
        profit_pct = total_profit / total_cost * 100
        total_shares = summary_data['股數'].sum()

        # 前半段文字 (白色)
        prefix_text = f"總計  股數:{total_shares:,}  市值:${total_value:,.2f}  "
        draw.text((20, y + 20), prefix_text, fill="white", font=bold_font)

        # 後半段文字 (損益與報酬率顏色)
        profit_text = f"損益:${total_profit:+,.2f}  報酬率:{profit_pct:+.2f}%"
        profit_color = "green" if total_profit >= 0 else "red"
        profit_width = draw.textlength(profit_text, font=bold_font)
        draw.text((img_width - 20 - profit_width, y + 20), profit_text, fill=profit_color, font=bold_font)

    # 存檔並傳送
    file_path = "portfolio_summary.png"
    img.save(file_path)
    await ctx.send(file=discord.File(file_path))

# 從 !summary 中獨立出調整成本指令 by car 20250912_2346
@bot.command(name="adjust_cost")
async def adjust_cost(ctx, stock_identifier: str, new_cost: float):
    user_id = str(ctx.author.id)
    create_user_csv_if_not_exists(user_id)

    if new_cost <= 0:
        await ctx.send("❌ 新的成本必須是正數。")
        return

    stock_code, stock_name = get_stock_info(stock_identifier)
    if not stock_code:
        await ctx.send(f"❌ 在您的庫存中找不到股票 `{stock_identifier}`。")
        return

    df = get_user_data(user_id)
    inventory = df[df['類別'] == '庫存']
    stock_inventory = inventory[inventory['股票代碼'] == stock_code]
    current_shares = stock_inventory['股數'].sum()

    if current_shares > 0:
        current_total_cost = stock_inventory['金額'].sum()
        new_total_cost = new_cost * current_shares
        cost_adjustment = new_total_cost - current_total_cost

        log_to_user_csv(user_id, "!adjust_cost", "庫存",
                        stock_code, stock_name, 0, 0,
                        cost_adjustment)
        await ctx.send(
            f"✅ 已將 **{stock_name}({stock_code})** 的平均成本調整為 **${new_cost:,.2f}**。"
        )
    else:
        await ctx.send(
            f"❌ 您目前未持有 **{stock_name}({stock_code})**，無法調整成本。")

@bot.command(name="profit")
async def _profit(ctx):
    user_id = str(ctx.author.id)
    create_user_csv_if_not_exists(user_id)
    df = get_user_data(user_id)
    if '損益' not in df.columns or df[df['類別'] == '損益'].empty:
        await ctx.send("目前沒有任何已實現的損益紀錄。")
        return
    profit_df = df[df['類別'] == '損益']
    total_profit = profit_df['損益'].sum()
    color = discord.Color.green() if total_profit >= 0 else discord.Color.red()
    title = "📈 總已實現損益" if total_profit >= 0 else "📉 總已實現損益"
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name=f"{ctx.author.display_name} 的總損益為：", value=f"**${total_profit:,.2f}**")
    await ctx.send(embed=embed)

@bot.command(name="profitclear")
async def _profitclear(ctx):
    user_id = str(ctx.author.id)
    create_user_csv_if_not_exists(user_id)
    df = get_user_data(user_id)
    if '損益' not in df.columns or df[df['類別'] == '損益'].empty:
        await ctx.send("您目前沒有任何損益紀錄可歸零。")
        return
    profit_df = df[df['類別'] == '損益']
    total_profit = profit_df['損益'].sum()
    if total_profit == 0:
        await ctx.send("您的總損益已經是 0，無需歸零。")
        return
    log_to_user_csv(user_id, "!profitclear", "損益", "SYSTEM", "損益歸零", 0, 0, 0, profit_loss=-total_profit)
    await ctx.send(f"✅ **損益已歸零！** 已新增一筆 ${-total_profit:,.2f} 的紀錄來平衡您的總損益。")



@bot.command(name="monkey")
async def _monkey(ctx, *args):
    user_id = ctx.author.id
    str_user_id = str(user_id)
    create_user_csv_if_not_exists(str_user_id)

    # ========== 冷卻開關 ==========
    ENABLE_COOLDOWN = False  # True = 啟用冷卻 (一天一次) / False = 禁用冷卻 (無限次)
    # =============================

    if ENABLE_COOLDOWN:
        # 原有的冷卻檢查邏輯
        df_user = get_user_data(str_user_id)
        cooldown_logs = df_user[(df_user['類別'] == '系統紀錄')
                                & (df_user['股票代碼'] == 'MONKEY_CD')]
        if not cooldown_logs.empty:
            last_used_str = cooldown_logs.iloc[-1]['操作時間']
            last_used_date = datetime.strptime(last_used_str,
                                               '%Y-%m-%d %H:%M:%S').date()
            if last_used_date == date.today():
                await ctx.send("猴子今天已經工作過了，請明天再來！")
                return
    # else: 如果禁用冷卻，就跳過檢查繼續執行

    # 剩下的猴子操盤邏輯保持不變...
    if user_id in monkey_sell_state:
        await ctx.send("您已在等待輸入賣出價格的狀態，請先完成操作。")
        return

    # (參數驗證與權重調整邏輯與前版相同)
    # ...
    #if user_id in monkey_sell_state:
    #    await ctx.send("您已在等待輸入賣出價格的狀態，請先完成操作。")
    #    return
    # ... (參數驗證與冷卻時間檢查，與前一版本相同) 這區間應該重複了? 先註解掉 za 250919.1847
    min_amount, max_amount = 5000, 100000
    if len(args) == 2:
        try:
            await bot.load_extension(cog)
            print(f"✅ 已載入: {cog}")
        except Exception as e:
            print(f"❌ 載入失敗 {cog}: {e}")


# ========== Startup ==========

    # --- 買入/持有邏輯 (不變) ---
    if chosen_action == "buy":
        stock_code, stock_name = random.choice(list(stock_data.items()))
        stock_price = get_stock_price(stock_code)
        if stock_price <= 0:
            await ctx.send(f"猴子想買 **{stock_name}**，但查不到它的股價，只好放棄。")
            return
        amount = random.randrange(min_amount, max_amount + 1, 1000)
        shares = int(amount // stock_price)
        if shares == 0:
            await ctx.send(f"猴子想用約 {amount:,} 元買 **{stock_name}**，但錢不夠，只好放棄。")
            return
        
        if round(shares * stock_price * handing_fee ,2) < 20:
            buy_amount = round(shares * stock_price * (1 + ST_tax) + 20, 2)
        else:
            buy_amount = round(shares * stock_price * (1 + handing_fee + ST_tax), 2) #新增買入含手續費計算，手續費低於20元以20元計  za 250919.1840
        
        log_to_user_csv(str(user_id), "!monkey", "庫存", stock_code, stock_name,
                        shares, stock_price, buy_amount)
        log_to_user_csv(str(user_id), "!monkey", "操作", stock_code, stock_name,
                        shares, stock_price, buy_amount)
        await ctx.send(
            f"🐵 **買入！** 猴子幫您買了 **{shares}** 股的 **{stock_name}({stock_code})**，股價為 **{stock_price}** ，總計 **{buy_amount}** 元！"
        )

    elif chosen_action == "hold":
        await ctx.send("🙉 **持有！** 猴子決定抱緊處理，今天不進行任何操作。")

    # --- 賣出邏輯 (進入狀態) ---
    elif chosen_action == "sell":
        stock_to_sell = summary_data[summary_data['股數'] > 0].sample(
            n=1).iloc[0]
        stock_code = stock_to_sell['股票代碼']
        shares_held = int(stock_to_sell['股數'])
        stock_name = get_stock_info(stock_code)[1]
        shares_to_sell = random.randint(1, shares_held)
        stock_price = get_stock_price(stock_code)
        # 計算平均成本
        stock_inventory = inventory[inventory['股票代碼'] == stock_code]
        total_cost = stock_inventory['金額'].sum()
        average_cost_price = total_cost / shares_held

        # 儲存狀態
        monkey_sell_state[user_id] = {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "shares_to_sell": shares_to_sell,
            "average_cost": average_cost_price,
            "channel_id": ctx.channel.id  # 記錄頻道ID以便超時提醒
        }
        # 啟動非阻塞的超時任務
        #asyncio.create_task(handle_monkey_timeout(ctx.channel, user_id))

        await ctx.send(
            f"{ctx.author.mention}，猴子決定賣出 **{shares_to_sell}** 股的 **{stock_name}({stock_code})**，目前市場價格為 **{stock_price}** 元，請在 120 秒內直接於頻道中輸入您要的賣出價格 (純數字)："   #新增顯示市場價格與提前拉取價格 by za 250928.2026
        )

    # --- 成功執行後，寫入冷卻紀錄 (重要) ---
    log_to_user_csv(str_user_id, "!monkey", "系統紀錄", "MONKEY_CD", "猴子冷卻紀錄", 0,
                    0, 0)


# --- 每月歸檔任務 ---
@tasks.loop(hours=1)  # 每小時檢查一次時間
async def monthly_archive():
    global is_archiving
    now = datetime.now()
    # 每月1號的 00:00 ~ 00:59 之間執行
    if now.day == 1 and now.hour == 0:
        is_archiving = True
        print(f"[{now}] 開始執行每月資料歸檔...")

        # 找出所有使用者 .csv 檔案 (排除上市股票.csv)
        csv_files = Path('.').glob('*.csv')
        user_csv_files = [f for f in csv_files if f.stem.isdigit()]


# ========== Entry Point ==========

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 機器人已關閉")
    except Exception as e:
        print(f"❌ 嚴重錯誤: {e}")