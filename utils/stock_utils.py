# utils/stock_utils.py
"""
Stock data utility functions.
These functions remain unchanged as they rely on external CSV files and APIs.
"""

import csv
import requests
from typing import Tuple, Optional
from pathlib import Path
import os

# Global stock data cache
stock_data = {}

# Constants - 使用絕對路徑確保從專案根目錄讀取
PROJECT_ROOT = Path(__file__).parent.parent  # 從 utils/ 往上到專案根目錄
STOCK_LIST_FILE = PROJECT_ROOT / "上市股票.csv"

def load_stock_data() -> None:
    """
    Load stock code and names from CSV file into memory.
    This function remains unchanged - still reads from CSV.
    """
    global stock_data
    try:
        with open(STOCK_LIST_FILE, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            stock_data = {
                row[0].strip(): row[1].strip()
                for row in reader if len(row) >= 2
            }
        print(f"✅ 成功載入 {len(stock_data)} 筆股票資料。")
    except FileNotFoundError:
        print(f"❌ 找不到股票清單檔案 `{STOCK_LIST_FILE}`。")
        stock_data = {}
    except Exception as e:
        print(f"❌ 載入股票資料時發生錯誤: {e}")
        stock_data = {}


def get_stock_info(identifier: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find stock information by code or name.
    This function remains unchanged.
    
    Args:
        identifier: Stock code or name
    
    Returns:
        Tuple of (stock_code, stock_name) or (None, None) if not found
    """
    # Check if it's a valid stock code
    if identifier.isdigit() and len(identifier) == 4 and identifier in stock_data:
        return identifier, stock_data[identifier]
    
    # Search by name
    for code, name in stock_data.items():
        if name == identifier:
            return code, name
    
    return None, None


def get_stock_price(stock_code: str) -> float:
    """
    Fetch real-time stock price from Taiwan Stock Exchange API.
    This function remains unchanged.
    
    Args:
        stock_code: 4-digit stock code
    
    Returns:
        Current stock price, or 0.0 if unavailable
    """
    url = f'https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=tse_{stock_code}.tw&json=1'
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status()
        data = res.json()
        
        msg = data.get('msgArray', [])
        if msg:
            # Try current price (z)
            price_str = msg[0].get('z')
            
            # Fallback to opening price (o)
            if price_str in (None, '-', ''):
                price_str = msg[0].get('o')
            
            # Fallback to yesterday's close (y)
            if price_str in (None, '-', ''):
                price_str = msg[0].get('y')
            
            if price_str and price_str not in (None, '-', '', '無資料'):
                return round(float(price_str), 2)
        
        return 0.0
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 取得 {stock_code} 股價時網路請求失敗: {e}")
        return 0.0
    except Exception as e:
        print(f"❌ 解析 {stock_code} 股價資料時失敗: {e}")
        return 0.0


def validate_stock_code(stock_code: str) -> bool:
    """
    Validate if a stock code exists in the loaded data.
    
    Args:
        stock_code: Stock code to validate
    
    Returns:
        True if valid, False otherwise
    """
    return stock_code in stock_data


def get_all_stock_codes() -> list:
    """
    Get a list of all available stock codes.
    
    Returns:
        List of stock codes
    """
    return list(stock_data.keys())


def get_random_stocks(count: int = 1) -> list:
    """
    Get random stock(s) from the available list.
    
    Args:
        count: Number of random stocks to return
    
    Returns:
        List of (code, name) tuples
    """
    import random
    if count > len(stock_data):
        count = len(stock_data)
    
    codes = random.sample(list(stock_data.keys()), count)

    return [(code, stock_data[code]) for code in codes]



