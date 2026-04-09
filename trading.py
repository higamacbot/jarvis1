"""
J.A.R.V.I.S. Trading Module
Natural language order routing via Alpaca Paper Trading.
"""

import os
import re
from datetime import datetime
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus

# Company name to ticker mapping
NAME_TO_TICKER = {
    "nvidia": "NVDA", "apple": "AAPL", "tesla": "TSLA",
    "amazon": "AMZN", "google": "GOOGL", "microsoft": "MSFT",
    "meta": "META", "netflix": "NFLX", "amd": "AMD",
    "paypal": "PYPL", "bitcoin": "BTC", "ethereum": "ETH",
    "solana": "SOL", "coinbase": "COIN", "palantir": "PLTR",
    "vanguard": "VOO", "robinhood": "HOOD", "rivian": "RIVN",
    "sofi": "SOFI", "nio": "NIO",
}

BUY_TRIGGERS     = ["buy", "purchase", "get me", "pick up", "long"]
SELL_TRIGGERS    = ["sell", "dump", "liquidate", "exit", "short"]
ORDER_TRIGGERS   = ["open orders", "pending orders", "my orders", "order status"]
CANCEL_TRIGGERS  = ["cancel all", "cancel orders", "cancel everything"]
CLOSE_ALL_TRIGGERS = ["close all positions", "liquidate everything",
                      "sell everything", "close all", "sell all positions"]

def get_client(api_key, api_secret):
    return TradingClient(api_key, api_secret, paper=True)

def is_market_open() -> bool:
    from datetime import datetime
    import zoneinfo
    now = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return market_open <= now <= market_close

def is_trade_command(message: str) -> bool:
    msg = message.lower()
    all_triggers = (BUY_TRIGGERS + SELL_TRIGGERS + ORDER_TRIGGERS +
                    CANCEL_TRIGGERS + CLOSE_ALL_TRIGGERS)
    return any(t in msg for t in all_triggers)

def parse_trade_intent(message: str) -> Optional[dict]:
    msg = message.lower().strip()

    if any(t in msg for t in CANCEL_TRIGGERS):
        return {"action": "CANCEL_ALL"}
    if any(t in msg for t in CLOSE_ALL_TRIGGERS):
        return {"action": "CLOSE_ALL"}
    if any(t in msg for t in ORDER_TRIGGERS):
        return {"action": "LIST_ORDERS"}

    # Resolve company names to tickers first
    resolved_msg = msg
    found_symbol = None
    for name, ticker in NAME_TO_TICKER.items():
        if name in msg:
            found_symbol = ticker
            resolved_msg = msg.replace(name, ticker)
            break

    # If no name match, look for uppercase ticker in original message
    if not found_symbol:
        ticker_match = re.search(r'\b([A-Z]{2,5})\b', message)
        if ticker_match:
            candidate = ticker_match.group(1)
            # Make sure it's not a trigger word
            skip_words = {"BUY", "SELL", "GET", "ALL", "MY", "ME"}
            if candidate not in skip_words:
                found_symbol = candidate

    if not found_symbol:
        return None

    # Dollar amount
    dollar_match = re.search(r'\$([0-9]+(?:\.[0-9]+)?)', msg)
    if dollar_match:
        dollar_amount = float(dollar_match.group(1))
        action = "BUY" if any(t in msg for t in BUY_TRIGGERS) else "SELL"
        return {"action": action, "symbol": found_symbol, "dollar_amount": dollar_amount}

    # Quantity
    qty = None
    if "all" in msg:
        qty = "all"
    elif "half" in msg:
        qty = "half"
    else:
        qty_match = re.search(r'\b(\d+(?:\.\d+)?)\b', resolved_msg)
        if qty_match:
            qty = float(qty_match.group(1))

    if qty is None:
        return None

    if any(t in msg for t in BUY_TRIGGERS):
        action = "BUY"
    elif any(t in msg for t in SELL_TRIGGERS):
        action = "SELL"
    else:
        return None

    return {"action": action, "symbol": found_symbol, "qty": qty}

def execute_trade_intent(intent, api_key, api_secret, current_positions) -> str:
    action = intent["action"]

    # Market hours check
    if action in ("BUY", "SELL") and not is_market_open():
        import zoneinfo
        now = datetime.now(zoneinfo.ZoneInfo("America/New_York"))
        return (
            f"Market is closed, sir. Current ET time is {now.strftime('%I:%M %p')}. "
            f"US markets trade Monday-Friday, 9:30 AM - 4:00 PM ET. "
            f"Your order to {action.lower()} {intent.get('symbol','')} has not been placed."
        )

    client = get_client(api_key, api_secret)

    if action == "LIST_ORDERS":
        try:
            orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))
            if not orders:
                return "No open orders at this time, sir."
            lines = [f"- {o.side.value.upper()} {o.qty} {o.symbol}" for o in orders]
            return "Open orders:\n" + "\n".join(lines)
        except Exception as e:
            return f"Could not retrieve orders, sir. Error: {e}"

    if action == "CANCEL_ALL":
        try:
            client.cancel_orders()
            return "All open orders cancelled, sir."
        except Exception as e:
            return f"Could not cancel orders, sir. Error: {e}"

    if action == "CLOSE_ALL":
        try:
            client.close_all_positions(cancel_orders=True)
            return "All positions closed, sir. Portfolio liquidated."
        except Exception as e:
            return f"Could not close positions, sir. Error: {e}"

    symbol = intent["symbol"]
    qty    = intent.get("qty")
    dollar = intent.get("dollar_amount")

    # Resolve all/half
    if qty in ("all", "half"):
        try:
            alpaca_pos = client.get_open_position(symbol)
            held_qty   = float(alpaca_pos.qty)
            qty = held_qty if qty == "all" else round(held_qty / 2, 2)
        except Exception as e:
            return f"Could not resolve position size for {symbol}, sir. Error: {e}"

    try:
        if dollar:
            order = client.submit_order(MarketOrderRequest(
                symbol=symbol,
                notional=dollar,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            ))
            result = f"{'📈' if action == 'BUY' else '📉'} {'Buying' if action == 'BUY' else 'Selling'} ${dollar:.2f} of {symbol}. Order ID: {str(order.id)[:8]}..."
        else:
            order = client.submit_order(MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
            ))
            result = f"{'📈' if action == 'BUY' else '📉'} {'Bought' if action == 'BUY' else 'Sold'} {qty} shares of {symbol}. Order ID: {str(order.id)[:8]}..."

        _log_trade(symbol, action, qty or dollar, dollar is not None)
        return result

    except Exception as e:
        error_msg = str(e)
        if "insufficient" in error_msg.lower():
            return f"Insufficient buying power to {action.lower()} {symbol}, sir."
        if "not found" in error_msg.lower():
            return f"Symbol {symbol} not found, sir. Check the ticker."
        return f"Trade failed for {symbol}, sir. Error: {error_msg}"

def _log_trade(symbol, action, amount, is_dollar=False):
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO trade_history (symbol, action, quantity, price, notes, timestamp) VALUES (?,?,?,?,?,?)",
                (symbol.upper(), action.upper(),
                 amount if not is_dollar else 0,
                 amount if is_dollar else None,
                 "dollar_order" if is_dollar else "qty_order",
                 datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
    except Exception as e:
        print(f">> TRADE LOG ERROR: {e}")

def get_trade_history(limit=10) -> str:
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memory.db")
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT symbol, action, quantity, price, notes, timestamp FROM trade_history ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        if not rows:
            return "No trade history recorded yet, sir."
        lines = []
        for symbol, action, qty, price, notes, ts in rows:
            if notes == "dollar_order":
                lines.append(f"- [{ts[:10]}] {action} ${price:.2f} of {symbol}")
            else:
                lines.append(f"- [{ts[:10]}] {action} {qty} {symbol}")
        return "Recent trades:\n" + "\n".join(lines)
    except Exception as e:
        return f"Could not retrieve trade history: {e}"
