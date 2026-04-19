"""
Clean router with proper imports and error handling
"""

from bots import stockbot
from bots import cryptoid
from bots import doctorbot
from bots import ultron
from bots import robowright
from bots import jamz
from bots import higashop
from bots import technoid
from bots import teacherbot
from bots import pinkslip
from bots import jarvisbot

BOT_MAP = {
    "stockbot": stockbot,
    "cryptoid": cryptoid,
    "doctorbot": doctorbot,
    "ultron": ultron,
    "robowright": robowright,
    "jamz": jamz,
    "higashop": higashop,
    "technoid": technoid,
    "teacherbot": teacherbot,
    "pinkslip": pinkslip,
    "jarvisbot": jarvisbot,
}

ROUNDTABLE_PROMPT = """You are coordinating a roundtable discussion between multiple specialized AI agents.
Each bot provides their unique perspective.

Format responses as:
JARVIS: [response]
STOCKBOT: [response]
CRYPTOID: [response]
PINKSLIP: [response]
DOCTORBOT: [response]
ULTRON: [response]
ROBOWRIGHT: [response]
JAMZ: [response]
HIGASHOP: [response]
TECHNOID: [response]
TEACHERBOT: [response]

Each bot gets max 2 sentences. Be direct. No preamble."""

async def route_message(bot_id: str, user_msg: str, ask_fn) -> str:
    print(f">> ROUTER DEBUG: bot_id = '{bot_id}'")
    
    if bot_id == "roundtable":
        import httpx
        from multi_broker_portfolio import MultiBrokerPortfolio

        # Inject real portfolio data into roundtable context
        try:
            tracker = MultiBrokerPortfolio()
            all_crypto = tracker.get_all_crypto()
            pd = tracker.portfolio_data

            webull_crypto = sum(v['value'] for v in pd['webull']['crypto'].values())
            coinbase_total = pd['coinbase']['total_value']
            kraken_equity = pd['paper_trading']['kraken']['equity']
            crypto_total = sum(c['value'] for c in all_crypto.values())

            crypto_lines = "\n".join(
                f"  {sym}: ${d['value']:.2f} (P/L: ${d.get('pl',0):+.2f}) [{d.get('broker','')}]"
                for sym, d in all_crypto.items()
            )

            roundtable_context = f"""
LIVE PORTFOLIO DATA FOR ALL AGENTS:

STOCKS (Alpaca paper):
  Equity: $1,801.29 | Buying Power: $6.37
  Positions: AMD, META, NFLX, NVDA, PYPL, TSLA, VOO

CRYPTO PORTFOLIO (Total: ${crypto_total:.2f}):
{crypto_lines}

BROKER TOTALS:
  Webull: $834.81 | Robinhood: $273.85 | Coinbase: ${coinbase_total:.2f}
  Acorns: $454.36 | Alpaca paper: $1,801.29 | Kraken paper: ${kraken_equity:.2f}
  TOTAL REAL PORTFOLIO: ~$3,696
"""
        except Exception as e:
            roundtable_context = f"Portfolio data unavailable: {e}"

        return await ask_fn(user_msg, system_override=ROUNDTABLE_PROMPT, extra_context=roundtable_context)
    
    # Jarvis uses default system prompt (same as main /ws endpoint)
    if bot_id == "jarvisbot":
        return await ask_fn(user_msg)
    
    bot = BOT_MAP.get(bot_id)
    if not bot:
        return f"Unknown bot: {bot_id}"
    
    # Special handling for Stockbot - inject portfolio context
    if bot_id == "stockbot":
        import os
        from alpaca.trading.client import TradingClient
        import httpx
        
        try:
            # Fetch portfolio data for Stockbot
            ALPACA_KEY = os.getenv("ALPACA_KEY")
            ALPACA_SECRET = os.getenv("ALPACA_SECRET")
            client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
            
            acct = client.get_account()
            pos = client.get_all_positions()
            
            portfolio_data = f"""
PORTFOLIO DATA:
Equity: ${float(acct.equity):,.2f}
Day P/L: {float(acct.equity) - float(acct.last_equity) if acct.last_equity else 0:+,.2f}
Buying Power: ${float(acct.buying_power):,.2f}
Positions:
"""
            for p in pos:
                portfolio_data += f"  {p.symbol}: ${float(p.market_value):,.2f} | P/L: {float(p.unrealized_pl):+,.2f}\n"
                
            # Fetch crypto data
            try:
                async with httpx.AsyncClient(timeout=10) as http_client:
                    r = await http_client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
                    if r.status_code == 200:
                        data = r.json()
                        crypto_data = f"CRYPTO: BTC: ${data['bitcoin']['usd']:,.2f}, ETH: ${data['ethereum']['usd']:,.2f}, SOL: ${data['solana']['usd']:,.2f}"
                        portfolio_data += f"\n{crypto_data}"
            except:
                portfolio_data += "\nCRYPTO: Data unavailable"
                
            return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=portfolio_data)
                    
        except Exception as e:
            error_context = f"PORTFOLIO ERROR: {e}"
            return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=error_context)
         
    # Special handling for Cryptoid - inject complete crypto portfolio context
    if bot_id == "cryptoid":
        print(">> CRYPTOID ROUTER: Executing crypto portfolio injection...")
        import os
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from multi_broker_portfolio import MultiBrokerPortfolio
        import httpx
        
        try:
            # Fetch complete crypto portfolio data
            portfolio_tracker = MultiBrokerPortfolio()
            all_crypto = portfolio_tracker.get_all_crypto()
            
            # Build crypto portfolio context
            crypto_data = f"""
COMPLETE CRYPTO PORTFOLIO DATA:
Total Crypto Value: ${sum(c['value'] for c in all_crypto.values()):,.2f}

Crypto Positions by Broker:
"""
            for symbol, data in all_crypto.items():
                pl_info = f"P/L: ${data.get('pl', 0):+,.2f}" if data.get('pl') is not None else "P/L: N/A"
                crypto_data += f"  {symbol}: ${data['value']:,.2f} | {pl_info} | Broker: {data.get('broker', 'unknown')}\n"
                
            # Add broker breakdown
            portfolio_data = portfolio_tracker.portfolio_data
            webull_crypto = sum(v['value'] for v in portfolio_data['webull']['crypto'].values()) if 'crypto' in portfolio_data['webull'] else 0
            coinbase_total = portfolio_data['coinbase']['total_value']
            kraken_equity = portfolio_data['paper_trading']['kraken']['equity']
            crypto_data += f"""
Broker Breakdown:
- Webull Crypto: ${webull_crypto:.2f}
- Coinbase Crypto: ${coinbase_total:.2f}
- Kraken Paper: ${kraken_equity:.2f}
"""
                
            # Fetch live crypto prices
            try:
                async with httpx.AsyncClient(timeout=10) as http_client:
                    r = await http_client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
                    if r.status_code == 200:
                        data = r.json()
                        market_data = f"LIVE PRICES: BTC: ${data['bitcoin']['usd']:,.2f}, ETH: ${data['ethereum']['usd']:,.2f}, SOL: ${data['solana']['usd']:,.2f}"
                        crypto_data += f"\n{market_data}"
            except:
                crypto_data += "\nLIVE PRICES: Data unavailable"
                
            print(">> CRYPTOID ROUTER: Successfully built crypto context")
            return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=crypto_data)
            
        except Exception as e:
            print(f">> CRYPTOID ROUTER ERROR: {e}")
            error_context = f"CRYPTO PORTFOLIO ERROR: {e}"
            return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=error_context)
    
    return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT)
