# database/schema.py
"""
Database schema for Discord Stock Trading Bot
Replaces the CSV-based storage with proper relational database
"""

import aiosqlite
from typing import Optional
import asyncio
from pathlib import Path

class TradingDatabase:
    """
    Centralized database manager for stock trading bot.
    Handles all database operations asynchronously.
    """
    
    _instance: Optional['TradingDatabase'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.db_path = Path("trading_bot.db")
            self.db: Optional[aiosqlite.Connection] = None
            self.initialized = False
    
    async def connect(self):
        """Initialize database connection and create all tables."""
        if self.db is not None:
            return
        
        async with self._lock:
            if self.db is not None:
                return
            
            self.db = await aiosqlite.connect(self.db_path)
            self.db.row_factory = aiosqlite.Row
            
            # Enable WAL mode for better concurrency
            await self.db.execute("PRAGMA journal_mode=WAL")
            await self.db.execute("PRAGMA foreign_keys=ON")
            await self.db.commit()
            
            await self._create_tables()
            self.initialized = True
            print("✅ Database connected and initialized")
    
    async def _create_tables(self):
        """Create all necessary tables for the trading bot."""
        
        # 1. Portfolio Table - Current holdings for each user
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                shares INTEGER NOT NULL DEFAULT 0,
                total_cost REAL NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, stock_code)
            )
        """)
        
        # Index for faster queries
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_portfolio_user 
            ON portfolio(user_id)
        """)
        
        # 2. Transactions Table - Complete log of all operations
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                command TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                shares INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                notes TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_transactions_user_time 
            ON transactions(user_id, timestamp DESC)
        """)
        
        # 3. Profit/Loss Table - Realized gains/losses
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS profit_loss (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                shares INTEGER NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL NOT NULL,
                profit_loss REAL NOT NULL,
                notes TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_profit_user 
            ON profit_loss(user_id)
        """)
        
        # 4. User Settings Table - Monkey trading preferences
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                monkey_min_amount INTEGER DEFAULT 5000,
                monkey_max_amount INTEGER DEFAULT 100000,
                monkey_buy_weight INTEGER DEFAULT 35,
                monkey_sell_weight INTEGER DEFAULT 30,
                monkey_hold_weight INTEGER DEFAULT 35,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 5. Pending Trades Table - Temporary storage for !random command
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS pending_trades (
                user_id TEXT PRIMARY KEY,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                shares INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 6. Monkey Sell State Table - Tracks monkey sell operations
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS monkey_sell_state (
                user_id TEXT PRIMARY KEY,
                stock_code TEXT NOT NULL,
                stock_name TEXT NOT NULL,
                shares_to_sell INTEGER NOT NULL,
                average_cost REAL NOT NULL,
                channel_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self.db.commit()
        print("✅ All database tables created successfully")
    
    # ========== Portfolio Operations ==========
    
    async def get_portfolio(self, user_id: str):
        """Get user's entire portfolio."""
        cursor = await self.db.execute("""
            SELECT stock_code, stock_name, shares, total_cost
            FROM portfolio
            WHERE user_id = ? AND shares > 0
            ORDER BY stock_code
        """, (user_id,))
        return await cursor.fetchall()
    
    async def get_stock_holding(self, user_id: str, stock_code: str):
        """Get specific stock holding."""
        cursor = await self.db.execute("""
            SELECT stock_code, stock_name, shares, total_cost
            FROM portfolio
            WHERE user_id = ? AND stock_code = ?
        """, (user_id, stock_code))
        return await cursor.fetchone()
    
    async def update_portfolio(self, user_id: str, stock_code: str, 
                              stock_name: str, shares_delta: int, 
                              cost_delta: float):
        """
        Update portfolio (buy/sell operations).
        shares_delta: positive for buy, negative for sell
        cost_delta: positive for buy, negative for sell
        """
        # Get current holding
        holding = await self.get_stock_holding(user_id, stock_code)
        
        if holding:
            new_shares = holding['shares'] + shares_delta
            new_cost = holding['total_cost'] + cost_delta
            
            await self.db.execute("""
                UPDATE portfolio
                SET shares = ?, total_cost = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND stock_code = ?
            """, (new_shares, new_cost, user_id, stock_code))
        else:
            # Insert new holding
            await self.db.execute("""
                INSERT INTO portfolio (user_id, stock_code, stock_name, shares, total_cost)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, stock_code, stock_name, shares_delta, cost_delta))
        
        await self.db.commit()
    
    async def adjust_cost(self, user_id: str, stock_code: str, new_avg_cost: float):
        """Manually adjust average cost of a holding."""
        holding = await self.get_stock_holding(user_id, stock_code)
        if not holding:
            return False
        
        new_total_cost = new_avg_cost * holding['shares']
        await self.db.execute("""
            UPDATE portfolio
            SET total_cost = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND stock_code = ?
        """, (new_total_cost, user_id, stock_code))
        await self.db.commit()
        return True
    
    # ========== Transaction Logging ==========
    
    async def log_transaction(self, user_id: str, command: str, 
                             transaction_type: str, stock_code: str,
                             stock_name: str, shares: int, price: float,
                             amount: float, notes: str = None):
        """Log a transaction to the database."""
        await self.db.execute("""
            INSERT INTO transactions 
            (user_id, command, transaction_type, stock_code, stock_name, 
             shares, price, amount, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, command, transaction_type, stock_code, stock_name,
              shares, price, amount, notes))
        await self.db.commit()
    
    async def get_recent_transactions(self, user_id: str, limit: int = 5):
        """Get the N most recent transactions for a user."""
        cursor = await self.db.execute("""
            SELECT timestamp, command, transaction_type, stock_code, 
                   stock_name, shares, price, amount
            FROM transactions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        return await cursor.fetchall()
    
    # ========== Profit/Loss Operations ==========
    
    async def record_profit_loss(self, user_id: str, stock_code: str,
                                stock_name: str, shares: int, buy_price: float,
                                sell_price: float, profit_loss: float,
                                notes: str = None):
        """Record a realized profit/loss."""
        await self.db.execute("""
            INSERT INTO profit_loss
            (user_id, stock_code, stock_name, shares, buy_price, 
             sell_price, profit_loss, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, stock_code, stock_name, shares, buy_price,
              sell_price, profit_loss, notes))
        await self.db.commit()
    
    async def get_total_profit_loss(self, user_id: str):
        """Calculate total realized profit/loss."""
        cursor = await self.db.execute("""
            SELECT COALESCE(SUM(profit_loss), 0) as total
            FROM profit_loss
            WHERE user_id = ?
        """, (user_id,))
        result = await cursor.fetchone()
        return result['total'] if result else 0
    
    async def clear_profit_loss(self, user_id: str):
        """Clear all profit/loss records for a user."""
        total = await self.get_total_profit_loss(user_id)
        if total != 0:
            # Record clearing transaction
            await self.record_profit_loss(
                user_id, "SYSTEM", "損益歸零", 0, 0, 0, -total, "清空損益紀錄"
            )
        return total
    
    # ========== User Settings ==========
    
    async def get_user_settings(self, user_id: str):
        """Get user's monkey trading settings."""
        cursor = await self.db.execute("""
            SELECT * FROM user_settings WHERE user_id = ?
        """, (user_id,))
        result = await cursor.fetchone()
        
        if not result:
            # Create default settings
            await self.db.execute("""
                INSERT INTO user_settings (user_id) VALUES (?)
            """, (user_id,))
            await self.db.commit()
            return await self.get_user_settings(user_id)
        
        return result
    
    async def update_user_settings(self, user_id: str, **kwargs):
        """Update user's monkey trading settings."""
        allowed_fields = ['monkey_min_amount', 'monkey_max_amount',
                         'monkey_buy_weight', 'monkey_sell_weight', 
                         'monkey_hold_weight']
        
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(user_id)
        query = f"""
            UPDATE user_settings 
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """
        
        await self.db.execute(query, values)
        await self.db.commit()
        return True
    
    # ========== Pending Trades ==========
    
    async def save_pending_trade(self, user_id: str, stock_code: str,
                                stock_name: str, shares: int, price: float,
                                amount: float):
        """Save a pending trade from !random command."""
        await self.db.execute("""
            INSERT OR REPLACE INTO pending_trades
            (user_id, stock_code, stock_name, shares, price, amount)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, stock_code, stock_name, shares, price, amount))
        await self.db.commit()
    
    async def get_pending_trade(self, user_id: str):
        """Get pending trade for user."""
        cursor = await self.db.execute("""
            SELECT * FROM pending_trades WHERE user_id = ?
        """, (user_id,))
        return await cursor.fetchone()
    
    async def delete_pending_trade(self, user_id: str):
        """Remove pending trade."""
        await self.db.execute("""
            DELETE FROM pending_trades WHERE user_id = ?
        """, (user_id,))
        await self.db.commit()
    
    # ========== Monkey Sell State ==========
    
    async def save_monkey_sell_state(self, user_id: str, stock_code: str,
                                    stock_name: str, shares_to_sell: int,
                                    average_cost: float, channel_id: str):
        """Save monkey sell state."""
        await self.db.execute("""
            INSERT OR REPLACE INTO monkey_sell_state
            (user_id, stock_code, stock_name, shares_to_sell, average_cost, channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, stock_code, stock_name, shares_to_sell, average_cost, channel_id))
        await self.db.commit()
    
    async def get_monkey_sell_state(self, user_id: str):
        """Get monkey sell state."""
        cursor = await self.db.execute("""
            SELECT * FROM monkey_sell_state WHERE user_id = ?
        """, (user_id,))
        return await cursor.fetchone()
    
    async def delete_monkey_sell_state(self, user_id: str):
        """Remove monkey sell state."""
        await self.db.execute("""
            DELETE FROM monkey_sell_state WHERE user_id = ?
        """, (user_id,))
        await self.db.commit()
    
    async def close(self):
        """Close database connection."""
        if self.db:
            await self.db.close()
            self.db = None
            print("🔌 Database connection closed")