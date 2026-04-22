import os
import pandas as pd
import yfinance as yf
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# Setup
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

TICKERS = ["META", "AAPL", "NFLX", "AMD", "NVDA", "TSLA"]

def get_signal(ticker):
    # Fetch data
    df = yf.Ticker(ticker).history(period="5d", interval="15m")
    if len(df) < 22: return None
    
    # Calculate SMAs
    df['SMA_Fast'] = df['Close'].rolling(window=9).mean()
    df['SMA_Slow'] = df['Close'].rolling(window=21).mean()
    
    # Isolate the last two rows to check for a crossover
    prev = df.iloc[-2]
    last = df.iloc[-1]
    
    # Logic: Fast crosses ABOVE Slow
    if prev['SMA_Fast'] <= prev['SMA_Slow'] and last['SMA_Fast'] > last['SMA_Slow']:
        return "BUY"
    # Logic: Fast crosses BELOW Slow
    elif prev['SMA_Fast'] >= prev['SMA_Slow'] and last['SMA_Fast'] < last['SMA_Slow']:
        return "SELL"
    
    return "HOLD"

def get_position_qty(ticker):
    """Get the quantity of a specific ticker currently held"""
    try:
        positions = client.get_all_positions()
        for pos in positions:
            if pos.symbol == ticker:
                return float(pos.qty)
        return 0.0
    except Exception as e:
        print(f"❌ Error fetching positions: {e}")
        return 0.0

def get_buying_power():
    """Get available buying power"""
    try:
        account = client.get_account()
        return float(account.buying_power)
    except Exception as e:
        print(f"❌ Error fetching account: {e}")
        return 0.0

def execute_trade(ticker, side):
    try:
        # Check buying power if BUY
        if side == "BUY":
            bp = get_buying_power()
            # Get current price
            price = yf.Ticker(ticker).info.get("currentPrice", 0)
            if price == 0:
                print(f"⚠️  Could not fetch price for {ticker}")
                return
            if bp < price:
                print(f"⚠️  Insufficient buying power for {ticker}: ${bp:.2f} < ${price:.2f}")
                return
            qty = 1
        
        # Check position qty if SELL
        elif side == "SELL":
            qty = get_position_qty(ticker)
            if qty <= 0:
                print(f"⚠️  No position to sell for {ticker}")
                return
            # Sell exact fractional qty held
            qty = round(qty, 4)
        
        order_details = MarketOrderRequest(
            symbol=ticker,
            qty=qty,
            side=OrderSide.BUY if side == "BUY" else OrderSide.SELL,
            time_in_force=TimeInForce.GTC
        )
        client.submit_order(order_data=order_details)
        print(f"🚀 Executed {side} {qty} share(s) of {ticker}")
    except Exception as e:
        print(f"❌ Trade failed for {ticker}: {e}")

if __name__ == "__main__":
    print("🤖 Jarvis Autopilot Engaged. Monitoring Trends...")
    for ticker in TICKERS:
        signal = get_signal(ticker)
        print(f"Checked {ticker}: {signal}")
        if signal in ["BUY", "SELL"]:
            execute_trade(ticker, signal)
