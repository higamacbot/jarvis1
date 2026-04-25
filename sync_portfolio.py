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

# YOUR MASTER LIST
holdings = {
    "META": 0.2658,
    "NFLX": 1.5934,
    "PYPL": 0.5094,
    "AMD": 0.5557,
    "TSLA": 0.1581,
    "NVDA": 0.2852,
    "VOO": 0.3587,
    "BTCUSD": 0.0062,
    "ETHUSD": 0.0315,
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
