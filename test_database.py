# test_database.py
"""
Database testing script to verify all operations work correctly.
Run this before deploying the bot.
"""

import asyncio
from database.schema import TradingDatabase

async def test_database():
    """Comprehensive database testing."""
    print("🧪 Starting database tests...\n")
    
    db = TradingDatabase()
    await db.connect()
    
    test_user_id = "TEST_USER_123"
    
    # ========== Test 1: Portfolio Operations ==========
    print("📊 Test 1: Portfolio Operations")
    
    # Buy stock
    await db.update_portfolio(test_user_id, "2330", "台積電", 10, 6000)
    print("✅ Buy: Added 10 shares of 2330")
    
    # Check holding
    holding = await db.get_stock_holding(test_user_id, "2330")
    assert holding['shares'] == 10, "Share count mismatch!"
    assert holding['total_cost'] == 6000, "Cost mismatch!"
    print(f"✅ Verify: Holding {holding['shares']} shares, cost ${holding['total_cost']}")
    
    # Buy more (average up)
    await db.update_portfolio(test_user_id, "2330", "台積電", 5, 3100)
    holding = await db.get_stock_holding(test_user_id, "2330")
    assert holding['shares'] == 15, "Share count mismatch after second buy!"
    assert holding['total_cost'] == 9100, "Cost mismatch after second buy!"
    print(f"✅ Buy more: Now holding {holding['shares']} shares, cost ${holding['total_cost']}")
    
    # Sell some
    await db.update_portfolio(test_user_id, "2330", "台積電", -5, -3000)
    holding = await db.get_stock_holding(test_user_id, "2330")
    assert holding['shares'] == 10, "Share count mismatch after sell!"
    print(f"✅ Sell: Now holding {holding['shares']} shares\n")
    
    # ========== Test 2: Transaction Logging ==========
    print("📝 Test 2: Transaction Logging")
    
    await db.log_transaction(
        test_user_id, "!buy", "買入", "0050", "元大台灣50",
        10, 150.5, 1505, "Test transaction"
    )
    print("✅ Logged buy transaction")
    
    await db.log_transaction(
        test_user_id, "!sell", "賣出", "0050", "元大台灣50",
        -5, 152.0, 760, "Test sell"
    )
    print("✅ Logged sell transaction")
    
    # Retrieve recent transactions
    recent = await db.get_recent_transactions(test_user_id, 2)
    assert len(recent) == 2, "Transaction count mismatch!"
    print(f"✅ Retrieved {len(recent)} recent transactions\n")
    
    # ========== Test 3: Profit/Loss Tracking ==========
    print("💰 Test 3: Profit/Loss Tracking")
    
    # Record profit
    await db.record_profit_loss(
        test_user_id, "2330", "台積電", 5, 600, 650, 250, "Test profit"
    )
    print("✅ Recorded profit: $250")
    
    # Record loss
    await db.record_profit_loss(
        test_user_id, "2454", "聯發科", 3, 1000, 950, -150, "Test loss"
    )
    print("✅ Recorded loss: -$150")
    
    # Get total P&L
    total_pnl = await db.get_total_profit_loss(test_user_id)
    assert total_pnl == 100, f"P&L calculation error! Expected 100, got {total_pnl}"
    print(f"✅ Total P&L: ${total_pnl}\n")
    
    # ========== Test 4: User Settings ==========
    print("⚙️ Test 4: User Settings")
    
    # Get default settings
    settings = await db.get_user_settings(test_user_id)
    assert settings['monkey_min_amount'] == 5000, "Default min amount wrong!"
    print(f"✅ Default settings loaded: min=${settings['monkey_min_amount']}")
    
    # Update settings
    await db.update_user_settings(
        test_user_id,
        monkey_min_amount=10000,
        monkey_max_amount=50000,
        monkey_buy_weight=40
    )
    
    settings = await db.get_user_settings(test_user_id)
    assert settings['monkey_min_amount'] == 10000, "Settings update failed!"
    assert settings['monkey_buy_weight'] == 40, "Weight update failed!"
    print(f"✅ Settings updated: min=${settings['monkey_min_amount']}, buy_weight={settings['monkey_buy_weight']}\n")
    
    # ========== Test 5: Pending Trades ==========
    print("🎲 Test 5: Pending Trades")
    
    # Save pending trade
    await db.save_pending_trade(
        test_user_id, "2881", "富邦金", 10, 85.5, 855
    )
    print("✅ Saved pending trade")
    
    # Retrieve
    pending = await db.get_pending_trade(test_user_id)
    assert pending is not None, "Failed to retrieve pending trade!"
    assert pending['stock_code'] == "2881", "Stock code mismatch!"
    print(f"✅ Retrieved pending trade: {pending['stock_name']}")
    
    # Delete
    await db.delete_pending_trade(test_user_id)
    pending = await db.get_pending_trade(test_user_id)
    assert pending is None, "Failed to delete pending trade!"
    print("✅ Deleted pending trade\n")
    
    # ========== Test 6: Monkey Sell State ==========
    print("🐵 Test 6: Monkey Sell State")
    
    # Save state
    await db.save_monkey_sell_state(
        test_user_id, "2330", "台積電", 5, 600, "123456789"
    )
    print("✅ Saved monkey sell state")
    
    # Retrieve
    state = await db.get_monkey_sell_state(test_user_id)
    assert state is not None, "Failed to retrieve monkey sell state!"
    assert state['shares_to_sell'] == 5, "Shares mismatch!"
    print(f"✅ Retrieved state: selling {state['shares_to_sell']} shares")
    
    # Delete
    await db.delete_monkey_sell_state(test_user_id)
    state = await db.get_monkey_sell_state(test_user_id)
    assert state is None, "Failed to delete monkey sell state!"
    print("✅ Deleted monkey sell state\n")
    
    # ========== Test 7: Cost Adjustment ==========
    print("🔧 Test 7: Cost Adjustment")
    
    # Adjust cost
    success = await db.adjust_cost(test_user_id, "2330", 620)
    assert success, "Cost adjustment failed!"
    
    holding = await db.get_stock_holding(test_user_id, "2330")
    expected_cost = 620 * holding['shares']
    assert holding['total_cost'] == expected_cost, "Cost adjustment calculation error!"
    print(f"✅ Adjusted cost to $620/share, total: ${holding['total_cost']}\n")
    
    # ========== Test 8: Clear Profit/Loss ==========
    print("🧹 Test 8: Clear Profit/Loss")
    
    initial_pnl = await db.get_total_profit_loss(test_user_id)
    print(f"Initial P&L: ${initial_pnl}")
    
    cleared = await db.clear_profit_loss(test_user_id)
    assert cleared == initial_pnl, "Cleared amount mismatch!"
    
    final_pnl = await db.get_total_profit_loss(test_user_id)
    assert final_pnl == 0, "P&L not cleared!"
    print(f"✅ Cleared ${cleared}, new total: ${final_pnl}\n")
    
    # ========== Test 9: Portfolio Query ==========
    print("📋 Test 9: Portfolio Query")
    
    # Add multiple holdings
    await db.update_portfolio(test_user_id, "0050", "元大台灣50", 20, 3000)
    await db.update_portfolio(test_user_id, "2454", "聯發科", 5, 5000)
    
    portfolio = await db.get_portfolio(test_user_id)
    print(f"✅ Portfolio contains {len(portfolio)} stocks:")
    for holding in portfolio:
        avg_cost = holding['total_cost'] / holding['shares']
        print(f"   - {holding['stock_name']}({holding['stock_code']}): "
              f"{holding['shares']} shares @ ${avg_cost:.2f}")
    
    # ========== Cleanup ==========
    print("\n🧹 Cleaning up test data...")
    
    # Delete test user data
    await db.db.execute("DELETE FROM portfolio WHERE user_id = ?", (test_user_id,))
    await db.db.execute("DELETE FROM transactions WHERE user_id = ?", (test_user_id,))
    await db.db.execute("DELETE FROM profit_loss WHERE user_id = ?", (test_user_id,))
    await db.db.execute("DELETE FROM user_settings WHERE user_id = ?", (test_user_id,))
    await db.db.commit()
    print("✅ Test data cleaned up")
    
    await db.close()
    
    print("\n" + "="*50)
    print("🎉 All tests passed successfully!")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(test_database())