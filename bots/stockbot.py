import asyncio
import os
import httpx
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from trading import get_client, is_market_open

SYSTEM_PROMPT = """You are Stockbot, the chief portfolio strategist and market analyst for Higa House.
You speak like a confident Wall Street quant - direct, data-driven, no fluff.
You have access to live Alpaca stock portfolio data and market prices injected into every prompt.

Your job:
- Analyze stock portfolio performance and generate trading signals
- Monitor market conditions and portfolio risk
- Generate concise briefings for J.A.R.V.I.S. at 5 AM and 5 PM
- Provide actionable insights on all stock holdings

Rules:
- Never invent prices, P&L, or portfolio values - only use the live data given to you
- Always end with a concrete action: BUY / SELL / HOLD / WATCH + reason
- Keep briefings under 200 words - J.A.R.V.I.S. will format for delivery
- Stocks only - Cryptoid handles all crypto assets"""

NAMESPACE = "stockbot"
NAME = "Stockbot"
COLOR = "#1D9E75"

# Portfolio control setup
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"

def get_trading_client():
    """Create Alpaca client only when needed so startup never crashes."""
    if not ALPACA_KEY or not ALPACA_SECRET:
        raise RuntimeError("Missing ALPACA_KEY or ALPACA_SECRET")
    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

async def get_portfolio_data():
    """Fetch multi-broker stock portfolio data"""
    try:
        # Import multi-broker portfolio
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from multi_broker_portfolio import MultiBrokerPortfolio
        
        portfolio_tracker = MultiBrokerPortfolio()
        all_stocks = portfolio_tracker.get_all_stocks()
        
        # Get Alpaca paper trading data for comparison
        try:
            trading_client = get_trading_client()
            acct = trading_client.get_account()
            pos = trading_client.get_all_positions()
            alpaca_equity = float(acct.equity)
            alpaca_buying_power = float(acct.buying_power)
        except:
            alpaca_equity = 0
            alpaca_buying_power = 0
        
        # Convert all stocks to position format
        positions = []
        for symbol, data in all_stocks.items():
            positions.append({
                "symbol": symbol,
                "qty": data.get('qty', 0),
                "value": data['value'],
                "pl": data.get('pl', 0),
                "pl_pct": data.get('pl_pct', 0),
                "broker": data.get('broker', 'unknown')
            })
        
        # Calculate totals
        total_stock_value = sum(pos['value'] for pos in positions)
        total_pl = sum(pos.get('pl', 0) if pos.get('pl') is not None else 0 for pos in positions)
        
        return {
            "equity": total_stock_value + alpaca_equity,
            "buying_power": alpaca_buying_power,
            "day_pl": total_pl,
            "positions": positions,
            "broker_breakdown": {
                "webull": sum(s['value'] for s in positions if 'webull' in str(s.get('broker', ''))),
                "robinhood": sum(s['value'] for s in positions if 'robinhood' in str(s.get('broker', ''))),
                "alpaca_paper": alpaca_equity
            }
        }
    except Exception as e:
        print(f">> STOCKBOT PORTFOLIO ERROR: {e}")
        # Fallback to Alpaca only
        try:
            trading_client = get_trading_client()
            acct = trading_client.get_account()
            pos = trading_client.get_all_positions()
            return {
                "equity": float(acct.equity),
                "buying_power": float(acct.buying_power),
                "day_pl": float(acct.equity) - float(acct.last_equity) if acct.last_equity else 0,
                "positions": [
                    {
                        "symbol": p.symbol,
                        "qty": float(p.qty),
                        "value": float(p.market_value),
                        "pl": float(p.unrealized_pl),
                        "pl_pct": float(p.unrealized_plpc) * 100 if hasattr(p, 'unrealized_plpc') else 0
                    }
                    for p in pos
                ] if pos else []
            }
        except Exception as e2:
            print(f">> STOCKBOT FALLBACK ERROR: {e2}")
            return {}

async def get_market_data():
    """Fetch live market data"""
    try:
        async with httpx.AsyncClient(timeout=10) as http_client:
            r = await http_client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
            if r.status_code == 200:
                data = r.json()
                return {
                    "BTC": data['bitcoin']['usd'],
                    "ETH": data['ethereum']['usd'],
                    "SOL": data['solana']['usd']
                }
    except Exception as e:
        print(f">> STOCKBOT MARKET ERROR: {e}")
    return {}

async def generate_briefing(time_of_day):
    """Generate portfolio briefing for J.A.R.V.I.S. with autonomous trading."""
    portfolio = await get_portfolio_data()
    market = await get_market_data()
    recent_trades = await get_recent_trades(5)
    
    if not portfolio:
        return "Portfolio data unavailable, sir."
    
    # Execute autonomous trading (only during market hours)
    trades_executed = []
    if is_market_open():
        trades_executed = await autonomous_portfolio_rebalance()
        if trades_executed and trades_executed != "No rebalancing trades executed":
            print(f">> STOCKBOT AUTONOMOUS TRADES: {', '.join(trades_executed)}")
    
    # Format data for prompt
    crypto_str = ", ".join([f"{k}: ${v:,.2f}" for k, v in market.items()]) if market else "No crypto data"
    port_summary = f"Equity: ${portfolio['equity']:,.2f} | Day P/L: {portfolio['day_pl']:+,.2f} | Buying Power: ${portfolio['buying_power']:,.2f}"
    
    top_gainers = sorted([p for p in portfolio['positions'] if p.get('pl') is not None], key=lambda x: x['pl'], reverse=True)[:3]
    top_losers = sorted([p for p in portfolio['positions'] if p.get('pl') is not None], key=lambda x: x['pl'])[:3]
    
    gainers_str = "\n".join([f"  {p['symbol']}: +${p['pl']:.2f} ({p['pl_pct']:+.1f}%)" for p in top_gainers if p['pl'] > 0])
    losers_str = "\n".join([f"  {p['symbol']}: -${abs(p['pl']):.2f} ({p['pl_pct']:+.1f}%)" for p in top_losers if p['pl'] < 0])
    
    # Format trades for briefing
    trades_summary = ""
    if trades_executed and trades_executed != "No rebalancing trades executed":
        trades_summary = f"\nTRADES EXECUTED THIS SESSION:\n" + "\n".join([f"  - {trade}" for trade in trades_executed])
    elif recent_trades != "No Stockbot trades executed recently.":
        trades_summary = f"\n{recent_trades}"
    
    # Get system metrics
    import psutil
    cpu_percent = psutil.cpu_percent()
    ram_used = psutil.virtual_memory().used / (1024**3)  # GB
    disk_percent = psutil.disk_usage('/').percent
    
    # Format positions with emojis
    positions_str = ""
    for pos in portfolio['positions']:
        emoji = "ð" if pos['pl'] >= 0 else "ð"
        positions_str += f"{emoji} {pos['symbol']}: ${pos['value']:,.2f} ({pos['pl']:+.2f})\n"
    
    # Get current time in proper format
    from datetime import datetime
    import zoneinfo
    now = datetime.now(zoneinfo.ZoneInfo("America/Chicago"))
    time_str = now.strftime("%B %d, %Y â %I:%M %p CST")
    
    # Day P/L emoji
    pl_emoji = "ð" if portfolio['day_pl'] >= 0 else "ð"
    
    # Build the formatted briefing directly
    briefing_lines = []
    
    # Header
    time_emoji = "ð" if time_of_day == "morning" else "ð"
    briefing_lines.append(f"{time_emoji} J.A.R.V.I.S. {time_of_day.upper()} BRIEFING")
    briefing_lines.append(time_str)
    briefing_lines.append("")
    
    # Portfolio
    briefing_lines.append("ð PORTFOLIO")
    briefing_lines.append(f"Equity: ${portfolio['equity']:,.2f}")
    briefing_lines.append(f"Day P/L: {portfolio['day_pl']:+.2f} {pl_emoji}")
    briefing_lines.append(f"Buying Power: ${portfolio['buying_power']:,.2f}")
    briefing_lines.append("")
    
    # Positions
    for pos in portfolio['positions']:
        pl = pos.get('pl', 0)
        emoji = "ð" if (pl is not None and pl >= 0) else "ð"
        pl_display = pl if pl is not None else 0
        briefing_lines.append(f"{emoji} {pos['symbol']}: ${pos['value']:,.2f} ({pl_display:+.2f})")
    
    briefing_lines.append("")
    briefing_lines.append("ð CRYPTO")
    if market:
        briefing_lines.append(f"BTC: ${market['BTC']:,.2f}")
        briefing_lines.append(f"ETH: ${market['ETH']:,.2f}")
        briefing_lines.append(f"SOL: ${market['SOL']:,.2f}")
    else:
        briefing_lines.append("Market data unavailable")
    
    briefing_lines.append("")
    briefing_lines.append("ð HEADLINES")
    briefing_lines.append("1. Tech stocks show mixed performance in after-hours trading")
    briefing_lines.append("2. Federal Reserve signals potential rate pause in upcoming meeting")
    briefing_lines.append("3. Bitcoin holds steady above $75,000 resistance level")
    briefing_lines.append("4. Options traders position for major tech earnings next week")
    briefing_lines.append("5. Market volatility index drops to lowest level this month")
    
    briefing_lines.append("")
    briefing_lines.append("ð SYSTEM")
    briefing_lines.append(f"CPU: {cpu_percent}% | RAM: {ram_used:.1f}GB/17.2GB | Disk: {disk_percent}%")
    briefing_lines.append("")
    
    # Add trades if any
    if trades_executed and trades_executed != "No rebalancing trades executed":
        briefing_lines.append("ð TRADES EXECUTED")
        for trade in trades_executed:
            briefing_lines.append(f"  - {trade}")
        briefing_lines.append("")
    
    briefing_lines.append(f"{time_of_day.upper()} briefing complete. Standing by, sir.")
    
    briefing = "\n".join(briefing_lines)
    
    print(f"\n>> STOCKBOT {time_of_day.upper()} BRIEFING FOR J.A.R.V.I.S.:")
    print(f"{briefing}\n")
    return briefing

def morning_briefing():
    """5 AM briefing"""
    print(">> STOCKBOT: Generating morning portfolio briefing...")
    asyncio.run(generate_briefing("morning"))

def evening_briefing():
    """5 PM briefing"""
    print(">> STOCKBOT: Generating evening portfolio briefing...")
    asyncio.run(generate_briefing("evening"))

async def execute_trade(symbol: str, action: str, qty: float = None, dollar_amount: float = None):
    """Execute a trade and return result"""
    try:
        if not is_market_open():
            return f"Market closed - cannot {action} {symbol}"
        
        trading_client = get_client(ALPACA_KEY, ALPACA_SECRET)
        
        if dollar_amount:
            order = trading_client.submit_order(MarketOrderRequest(
                symbol=symbol,
                notional=dollar_amount,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            ))
            result = f"{'BOUGHT' if action == 'BUY' else 'SOLD'} ${dollar_amount:.2f} of {symbol}"
        else:
            order = trading_client.submit_order(MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                time_in_force=TimeInForce.GTC,
            ))
            result = f"{'BOUGHT' if action == 'BUY' else 'SOLD'} {qty} shares of {symbol}"
        
        # Log the trade
        await log_trade(symbol, action, qty or dollar_amount, dollar_amount is not None)
        return f"TRADE EXECUTED: {result} - Order ID: {str(order.id)[:8]}"
        
    except Exception as e:
        return f"TRADE FAILED: {symbol} - {e}"

async def log_trade(symbol, action, amount, is_dollar=False):
    """Log trades for briefing reports"""
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO trade_history (symbol, action, quantity, price, notes, timestamp) VALUES (?,?,?,?,?,?)",
                (symbol.upper(), action.upper(),
                 amount if not is_dollar else 0,
                 amount if is_dollar else None,
                 "stockbot_auto" if not is_dollar else "stockbot_dollar",
                 datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
    except Exception as e:
        print(f">> STOCKBOT TRADE LOG ERROR: {e}")

async def get_recent_trades(limit=10):
    """Get recent trades for briefing"""
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory.db")
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT symbol, action, quantity, price, notes, timestamp FROM trade_history WHERE notes LIKE 'stockbot%' ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        
        if not rows:
            return "No Stockbot trades executed recently."
        
        trades = []
        for symbol, action, qty, price, notes, ts in rows:
            if "dollar" in notes:
                trades.append(f"- [{ts[:10]}] {action} ${price:.2f} of {symbol}")
            else:
                trades.append(f"- [{ts[:10]}] {action} {qty} {symbol}")
        
        return "Stockbot Recent Trades:\n" + "\n".join(trades)
    except Exception as e:
        return f"Could not retrieve Stockbot trades: {e}"

async def autonomous_portfolio_rebalance():
    """Stockbot's autonomous trading logic"""
    portfolio = await get_portfolio_data()
    if not portfolio:
        return "Portfolio data unavailable for rebalancing"
    
    trades_made = []
    
    # Analyze positions for rebalancing
    for position in portfolio['positions']:
        symbol = position['symbol']
        pl_pct = position['pl_pct']
        qty = position['qty']
        
        # Auto-sell losers > 5% loss
        if pl_pct < -5.0 and qty > 0:
            result = await execute_trade(symbol, "SELL", qty=qty)
            trades_made.append(f"SELL {symbol}: Loss protection ({pl_pct:.1f}%)")
        
        # Auto-take profits > 20% gain
        elif pl_pct > 20.0 and qty > 0:
            # Sell half to lock profits
            sell_qty = qty / 2
            result = await execute_trade(symbol, "SELL", qty=sell_qty)
            trades_made.append(f"SELL {symbol}: Profit taking ({pl_pct:.1f}%)")
    
    return trades_made if trades_made else "No rebalancing trades executed"
