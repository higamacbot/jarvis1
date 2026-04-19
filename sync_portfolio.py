import os, time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# PULLS FROM YOUR .ZSHRC
ALPACA_KEY      = os.getenv("ALPACA_KEY")
ALPACA_SECRET   = os.getenv("ALPACA_SECRET")

client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

# Check account balance first
account = client.get_account()
print(f"Account Balance: ${float(account.buying_power):.2f} buying power")

# YOUR MASTER LIST - REDUCED TO FIT BUYING POWER
holdings = {
    # Already have these stocks - skip
    # "META": 0.2658,  # HAVE
    # "NFLX": 1.5934,  # HAVE  
    # "PYPL": 0.5094,  # HAVE
    # "AMD": 0.5557,   # HAVE
    # "TSLA": 0.1581,  # HAVE
    # "NVDA": 0.2852,  # HAVE
    # "VOO": 0.3587,   # HAVE
    
    # Crypto - need $10 minimum, can't afford
    # "BTCUSD": 0.0062,  # NEED $589
    # "ETHUSD": 0.0315,  # NEED $95
    
    # ALTERNATIVE: Add smaller crypto positions when funding available
    # "BTCUSD": 0.0001,  # ~$9.50 (still over $6.37)
    # "ETHUSD": 0.001,   # ~$3.00 (under $10 min)
}

print("Mirroring Real Portfolio using Environment Variables...")

for symbol, qty in holdings.items():
    try:
        # Crypto orders need different time_in_force
        if symbol.endswith('USD'):
            time_force = TimeInForce.IOC  # Immediate or Cancel for crypto
        else:
            time_force = TimeInForce.DAY  # Regular stocks
            
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=time_force
        )
        client.submit_order(order_data=order_data)
        print(f"Ordered {qty} of {symbol}")
        time.sleep(0.5)
    except Exception as e:
        error_msg = str(e)
        if "insufficient buying power" in error_msg.lower():
            print(f"Insufficient funds for {symbol}")
        elif "invalid crypto time_in_force" in error_msg.lower():
            print(f"Invalid time force for crypto {symbol}")
        else:
            print(f"{symbol}: {e}")

print("Sync Complete.")
