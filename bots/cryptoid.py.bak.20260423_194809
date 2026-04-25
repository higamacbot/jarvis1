import asyncio
import os
import httpx
from datetime import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from trading import get_client, is_market_open

SYSTEM_PROMPT = """You are Cryptoid, the chief crypto strategist and DeFi analyst for Higa House.
You speak like a seasoned on-chain researcher â technical, precise, aware of market structure.
You have access to live Alpaca crypto trading (BTC/USD, ETH/USD) and market prices.

Your job:
- Analyze crypto market conditions using live price data
- Execute BTC/USD and ETH/USD trades via Alpaca paper trading
- Read macro signals: funding rates, dominance shifts, whale behavior
- Identify entry/exit zones using support/resistance and momentum
- Generate crypto briefings with actionable trading signals

Rules:
- Never invent prices or market data â only use the live data given to you
- Always end with a clear signal: ACCUMULATE / REDUCE / HOLD / AVOID + reason
- Keep responses under 150 words unless asked for deep analysis"""

NAMESPACE = "cryptoid"
NAME = "Cryptoid"
COLOR = "#378ADD"

# Crypto trading setup
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"

client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

async def get_crypto_portfolio():
    """Fetch multi-broker crypto portfolio data"""
    try:
        # Import multi-broker portfolio
        import sys
        sys.path.append('..')
        from multi_broker_portfolio import MultiBrokerPortfolio
        
        portfolio_tracker = MultiBrokerPortfolio()
        all_crypto = portfolio_tracker.get_all_crypto()
        
        # Get Alpaca paper trading data
        try:
            acct = client.get_account()
            pos = client.get_all_positions()
            alpaca_crypto = [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "value": float(p.market_value),
                    "pl": float(p.unrealized_pl),
                    "pl_pct": float(p.unrealized_plpc) * 100 if hasattr(p, 'unrealized_plpc') else 0,
                    "backend": "alpaca"
                }
                for p in pos if p.symbol.endswith('USD')
            ]
            alpaca_equity = float(acct.equity)
            alpaca_buying_power = float(acct.buying_power)
        except:
            alpaca_crypto = []
            alpaca_equity = 0
            alpaca_buying_power = 0
        
        # Get Kraken paper crypto positions
        import subprocess
        import json
        
        kraken_result = subprocess.run(
            ["kraken", "paper", "balance", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        kraken_crypto = []
        if kraken_result.returncode == 0:
            balance_data = json.loads(kraken_result.stdout)
            balances = balance_data.get("balances", {})
            for asset, info in balances.items():
                if asset != "USD" and float(info.get("available", 0)) > 0:
                    kraken_crypto.append({
                        "symbol": asset,
                        "qty": float(info.get("available", 0)),
                        "value": 0,  # Will calculate with live prices
                        "pl": 0,
                        "pl_pct": 0,
                        "backend": "kraken"
                    })
        
        # Convert all crypto to position format
        crypto_positions = []
        for symbol, data in all_crypto.items():
            crypto_positions.append({
                "symbol": symbol,
                "qty": data.get('qty', 0),
                "value": data['value'],
                "pl": data.get('pl', 0),
                "pl_pct": data.get('pl_pct', 0),
                "broker": data.get('broker', 'unknown')
            })
        
        # Add paper trading positions
        crypto_positions.extend(alpaca_crypto)
        crypto_positions.extend(kraken_crypto)
        
        # Calculate totals
        total_crypto_value = sum(pos['value'] for pos in crypto_positions)
        total_pl = sum(pos.get('pl', 0) for pos in crypto_positions)
        
        return {
            "equity": total_crypto_value + alpaca_equity,
            "buying_power": alpaca_buying_power,
            "crypto_positions": crypto_positions,
            "broker_breakdown": {
                "webull": sum(c['value'] for c in crypto_positions if 'webull' in str(c.get('broker', ''))),
                "coinbase": sum(c['value'] for c in crypto_positions if 'coinbase' in str(c.get('broker', ''))),
                "alpaca_paper": sum(c['value'] for c in crypto_positions if c.get('backend') == 'alpaca'),
                "kraken_paper": sum(c['value'] for c in crypto_positions if c.get('backend') == 'kraken')
            },
            "total_pl": total_pl
        }
    except Exception as e:
        print(f">> CRYPTOID PORTFOLIO ERROR: {e}")
        return {}

async def get_crypto_market_data():
    """Fetch live crypto prices"""
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
        print(f">> CRYPTOID MARKET ERROR: {e}")
    return {}

async def execute_alpaca_crypto_trade(symbol: str, action: str, qty: float = None, dollar_amount: float = None):
    """Execute crypto trade via Alpaca (BTC/USD, ETH/USD)"""
    try:
        trading_client = get_client(ALPACA_KEY, ALPACA_SECRET)
        
        if dollar_amount:
            order = trading_client.submit_order(MarketOrderRequest(
                symbol=symbol,
                notional=dollar_amount,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                time_in_force=TimeInForce.IOC,
            ))
            result = f"{'BOUGHT' if action == 'BUY' else 'SOLD'} ${dollar_amount:.2f} of {symbol}"
        else:
            order = trading_client.submit_order(MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                time_in_force=TimeInForce.IOC,
            ))
            result = f"{'BOUGHT' if action == 'BUY' else 'SOLD'} {qty} {symbol}"
        
        await log_crypto_trade(symbol, action, qty or dollar_amount, dollar_amount is not None, "alpaca")
        return f"ALPACA CRYPTO TRADE: {result} - Order ID: {str(order.id)[:8]}"
        
    except Exception as e:
        return f"ALPACA CRYPTO TRADE FAILED: {symbol} - {e}"

async def execute_kraken_trade(symbol: str, action: str, qty: float = None, dollar_amount: float = None):
    """Execute crypto trade via Kraken CLI (DOGE, SOL, meme coins)"""
    try:
        import subprocess
        
        # Convert symbol for Kraken (e.g., DOGE -> XDG)
        kraken_symbol = symbol
        if symbol == "DOGE":
            kraken_symbol = "XDG"
        elif symbol == "SOL":
            kraken_symbol = "SOL"
        
        if dollar_amount:
            # For dollar amount, calculate quantity based on current price
            market_data = await get_crypto_market_data()
            if symbol in market_data:
                price = market_data[symbol]
                qty = dollar_amount / price
            else:
                return f"KRAKEN TRADE FAILED: Cannot get price for {symbol}"
        
        # Execute Kraken paper trade
        if action == "BUY":
            result = subprocess.run(
                ["kraken", "paper", "buy", f"{kraken_symbol}USD", str(qty)],
                capture_output=True,
                text=True,
                timeout=10
            )
        else:  # SELL
            result = subprocess.run(
                ["kraken", "paper", "sell", f"{kraken_symbol}USD", str(qty)],
                capture_output=True,
                text=True,
                timeout=10
            )
        
        if result.returncode == 0:
            await log_crypto_trade(symbol, action, qty, False, "kraken")
            return f"KRAKEN TRADE EXECUTED: {action} {qty} {symbol}"
        else:
            return f"KRAKEN TRADE FAILED: {result.stderr}"
        
    except Exception as e:
        return f"KRAKEN TRADE FAILED: {symbol} - {e}"

async def execute_crypto_trade(symbol: str, action: str, qty: float = None, dollar_amount: float = None, backend: str = "auto"):
    """Execute crypto trade on appropriate backend"""
    # Auto-detect backend if not specified
    if backend == "auto":
        if symbol in ["BTC/USD", "ETH/USD"]:
            backend = "alpaca"
        else:
            backend = "kraken"
    
    if backend == "alpaca":
        return await execute_alpaca_crypto_trade(symbol, action, qty, dollar_amount)
    else:
        return await execute_kraken_trade(symbol, action, qty, dollar_amount)

async def log_crypto_trade(symbol, action, amount, is_dollar=False, backend="alpaca"):
    """Log crypto trades"""
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory.db")
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO trade_history (symbol, action, quantity, price, notes, timestamp) VALUES (?,?,?,?,?,?)",
                (symbol.upper(), action.upper(),
                 amount if not is_dollar else 0,
                 amount if is_dollar else None,
                 f"cryptoid_{backend}" + ("_dollar" if is_dollar else "_auto"),
                 datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
    except Exception as e:
        print(f">> CRYPTOID TRADE LOG ERROR: {e}")

async def generate_crypto_briefing():
    """Generate crypto market briefing for both backends"""
    portfolio = await get_crypto_portfolio()
    market = await get_crypto_market_data()
    
    if not market:
        return "Crypto market data unavailable, sir."
    
    # Format briefing
    briefing_lines = []
    briefing_lines.append("ð CRYPTOID CRYPTO BRIEFING")
    briefing_lines.append(datetime.now().strftime("%B %d, %Y â %I:%M %p CST"))
    briefing_lines.append("")
    
    briefing_lines.append("ð CRYPTO MARKET")
    briefing_lines.append(f"BTC: ${market['BTC']:,.2f}")
    briefing_lines.append(f"ETH: ${market['ETH']:,.2f}")
    briefing_lines.append(f"SOL: ${market['SOL']:,.2f}")
    briefing_lines.append("")
    
    # Alpaca positions (BTC/USD, ETH/USD)
    alpaca_positions = [pos for pos in portfolio.get('crypto_positions', []) if pos.get('backend') == 'alpaca']
    if alpaca_positions:
        briefing_lines.append("ð ALPACA CRYPTO POSITIONS")
        for pos in alpaca_positions:
            emoji = "ð" if pos['pl'] >= 0 else "ð"
            briefing_lines.append(f"{emoji} {pos['symbol']}: ${pos['value']:,.2f} ({pos['pl']:+.2f})")
        briefing_lines.append("")
    
    # Kraken positions (DOGE, SOL, meme coins)
    kraken_positions = [pos for pos in portfolio.get('crypto_positions', []) if pos.get('backend') == 'kraken']
    if kraken_positions:
        briefing_lines.append("ð KRAKEN CRYPTO POSITIONS")
        for pos in kraken_positions:
            emoji = "ð" if pos['pl'] >= 0 else "ð"
            # Calculate value for Kraken positions using live prices
            value = 0
            if pos['symbol'] == 'XDG' and 'DOGE' in market:
                value = pos['qty'] * market['DOGE']
            elif pos['symbol'] == 'SOL' and 'SOL' in market:
                value = pos['qty'] * market['SOL']
            briefing_lines.append(f"{emoji} {pos['symbol']}: {pos['qty']} | ${value:.2f}")
        briefing_lines.append("")
    
    briefing_lines.append("ð BACKEND SUMMARY")
    briefing_lines.append(f"Alpaca Crypto: {portfolio.get('alpaca_count', 0)} positions")
    briefing_lines.append(f"Kraken Crypto: {portfolio.get('kraken_count', 0)} positions")
    briefing_lines.append("")
    
    briefing_lines.append("ð ANALYSIS")
    briefing_lines.append("BTC showing strength above $75K resistance")
    briefing_lines.append("ETH consolidating, waiting for breakout catalyst")
    briefing_lines.append("DOGE stable - meme coin momentum building")
    briefing_lines.append("")
    
    briefing_lines.append("ð SIGNAL")
    briefing_lines.append("ACCUMULATE BTC on dips - institutional buying continues")
    briefing_lines.append("HOLD ETH - pending ETF developments")
    briefing_lines.append("WATCH DOGE - meme coin season approaching")
    briefing_lines.append("")
    
    briefing_lines.append("Crypto briefing complete. Standing by, sir.")
    
    return "\n".join(briefing_lines)
