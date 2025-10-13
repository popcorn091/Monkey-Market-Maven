# migrate_csv_to_db.py
"""
Migration script to convert existing CSV data to SQLite database.
Run this ONCE to migrate your existing user data.
"""

import asyncio
import pandas as pd
from pathlib import Path
from datetime import datetime
from database.schema import TradingDatabase

async def migrate_user_csv(user_id: str, csv_path: Path):
    """
    Migrate a single user's CSV file to database.
    
    Args:
        user_id: User's Discord ID (filename without .csv)
        csv_path: Path to the CSV file
    """
    print(f"\n{'='*60}")
    print(f"📂 Processing: {csv_path.name}")
    print(f"{'='*60}")
    
    db = TradingDatabase()
    await db.connect()
    
    try:
        # Read CSV with proper encoding
        df = pd.read_csv(csv_path, encoding='utf-8-sig', dtype={'股票代碼': str})
        
        if df.empty:
            print(f"⚠️  Empty CSV file, skipping...")
            return
        
        print(f"📊 Found {len(df)} total records")
        
        # ========== Migrate Portfolio (庫存) ==========
        print("\n1️⃣  Migrating portfolio data...")
        
        inventory_df = df[df['類別'] == '庫存'].copy()
        
        if not inventory_df.empty:
            # Group by stock code to calculate totals
            portfolio_summary = inventory_df.groupby(['股票代碼', '股票名稱']).agg({
                '股數': 'sum',
                '金額': 'sum'
            }).reset_index()
            
            migrated_count = 0
            for _, row in portfolio_summary.iterrows():
                stock_code = row['股票代碼']
                stock_name = row['股票名稱']
                total_shares = int(row['股數'])
                total_cost = float(row['金額'])
                
                # Only migrate if positive shares
                if total_shares > 0:
                    await db.update_portfolio(
                        user_id, stock_code, stock_name,
                        total_shares, total_cost
                    )
                    
                    avg_cost = total_cost / total_shares
                    print(f"   ✅ {stock_name}({stock_code}): "
                          f"{total_shares} 股 @ ${avg_cost:.2f}")
                    migrated_count += 1
            
            print(f"   📦 Migrated {migrated_count} portfolio holdings")
        else:
            print("   📭 No portfolio data found")
        
        # ========== Migrate Transactions (操作) ==========
        print("\n2️⃣  Migrating transaction log...")
        
        operations_df = df[df['類別'] == '操作'].copy()
        
        if not operations_df.empty:
            for _, row in operations_df.iterrows():
                try:
                    # Determine transaction type
                    shares = int(row['股數'])
                    tx_type = "買入" if shares > 0 else "賣出"
                    
                    await db.log_transaction(
                        user_id,
                        row['指令'],
                        tx_type,
                        row['股票代碼'],
                        row['股票名稱'],
                        shares,
                        float(row['股價']),
                        float(row['金額']),
                        f"Migrated from CSV"
                    )
                except Exception as e:
                    print(f"   ⚠️  Failed to migrate transaction: {e}")
            
            print(f"   📝 Migrated {len(operations_df)} transaction records")
        else:
            print("   📭 No transaction data found")
        
        # ========== Migrate Profit/Loss (損益) ==========
        print("\n3️⃣  Migrating profit/loss records...")
        
        pnl_df = df[df['類別'] == '損益'].copy()
        
        if not pnl_df.empty:
            migrated_pnl = 0
            total_pnl = 0
            
            for _, row in pnl_df.iterrows():
                try:
                    # Check if 損益 column exists and has value
                    if pd.notna(row.get('損益', None)):
                        profit_loss = float(row['損益'])
                        shares = int(row['股數']) if pd.notna(row['股數']) else 1
                        price = float(row['股價']) if pd.notna(row['股價']) else 0
                        
                        # Estimate buy price (rough calculation)
                        # sell_price = price, profit_loss = (sell_price - buy_price) * shares
                        # buy_price ≈ sell_price - (profit_loss / shares)
                        buy_price = price - (profit_loss / shares) if shares > 0 else 0
                        
                        await db.record_profit_loss(
                            user_id,
                            row['股票代碼'],
                            row['股票名稱'],
                            shares,
                            buy_price,
                            price,
                            profit_loss,
                            "Migrated from CSV"
                        )
                        
                        total_pnl += profit_loss
                        migrated_pnl += 1
                except Exception as e:
                    print(f"   ⚠️  Failed to migrate P&L record: {e}")
            
            print(f"   💰 Migrated {migrated_pnl} P&L records")
            print(f"   📊 Total realized P&L: ${total_pnl:,.2f}")
        else:
            print("   📭 No P&L data found")
        
        # ========== Create Default User Settings ==========
        print("\n4️⃣  Creating default user settings...")
        
        settings = await db.get_user_settings(user_id)
        print(f"   ⚙️  User settings initialized")
        
        print(f"\n✅ Successfully migrated {csv_path.name}")
        
    except Exception as e:
        print(f"\n❌ Error migrating {csv_path.name}: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await db.close()


async def migrate_all_users():
    """Find and migrate all user CSV files."""
    print("🚀 Starting CSV to Database Migration")
    print("="*60)
    
    # Find all CSV files that are user data (numeric filenames)
    current_dir = Path('.')
    user_csv_files = [f for f in current_dir.glob('*.csv') 
                      if f.stem.isdigit()]
    
    if not user_csv_files:
        print("❌ No user CSV files found (looking for files like 123456789.csv)")
        return
    
    print(f"📁 Found {len(user_csv_files)} user CSV files to migrate:")
    for f in user_csv_files:
        print(f"   - {f.name}")
    
    # Confirm before proceeding
    print("\n⚠️  WARNING: This will migrate all data to the database.")
    print("   Make sure you have backed up your CSV files!")
    response = input("\nProceed with migration? (yes/no): ")
    
    if response.lower() != 'yes':
        print("❌ Migration cancelled.")
        return
    
    # Migrate each user
    migrated_count = 0
    failed_count = 0
    
    for csv_file in user_csv_files:
        user_id = csv_file.stem
        try:
            await migrate_user_csv(user_id, csv_file)
            migrated_count += 1
        except Exception as e:
            print(f"\n❌ Failed to migrate {csv_file.name}: {e}")
            failed_count += 1
    
    # Summary
    print("\n" + "="*60)
    print("🎉 Migration Complete!")
    print("="*60)
    print(f"✅ Successfully migrated: {migrated_count}")
    print(f"❌ Failed: {failed_count}")
    print("\n💡 Next steps:")
    print("   1. Verify data in database using test_database.py")
    print("   2. Test bot functionality")
    print("   3. Once confirmed, you can archive/delete CSV files")
    print("   4. CSV files can be moved to an 'archive' folder for backup")


async def verify_migration():
    """Verify migration by showing database statistics."""
    print("\n" + "="*60)
    print("📊 Database Statistics")
    print("="*60)
    
    db = TradingDatabase()
    await db.connect()
    
    # Count records in each table
    tables = ['portfolio', 'transactions', 'profit_loss', 'user_settings']
    
    for table in tables:
        cursor = await db.db.execute(f"SELECT COUNT(*) as count FROM {table}")
        result = await cursor.fetchone()
        print(f"   {table}: {result['count']} records")
    
    # Show unique users
    cursor = await db.db.execute("""
        SELECT COUNT(DISTINCT user_id) as count FROM portfolio
    """)
    result = await cursor.fetchone()
    print(f"\n   Unique users with portfolio: {result['count']}")
    
    await db.close()


if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║       CSV to Database Migration Tool                       ║
║       Monkey Market Maven - Database Edition               ║
╚════════════════════════════════════════════════════════════╝
""")
    
    # Run migration
    asyncio.run(migrate_all_users())
    
    # Show statistics
    asyncio.run(verify_migration())
    
    print("\n✨ Migration process finished!")