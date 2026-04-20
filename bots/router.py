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
    "debateroom":  teacherbot,  # placeholder — overridden by debate handler above
    "pinkslip": pinkslip,
    "jarvisbot": jarvisbot,
}

ROUNDTABLE_PROMPT = """You are the HIGA HOUSE — eleven specialized AI agents giving full updates to their boss.
Each bot writes a genuine paragraph in their own voice about their specific domain.
Use the live portfolio data provided. Be specific, use real numbers when available.

Format EXACTLY like this with no extra headers or preamble:

JARVIS: <your chief of staff summary here>

STOCKBOT: <your stock portfolio update here>

CRYPTOID: <your crypto portfolio update here>

PINKSLIP: <your sports betting update here>

DOCTORBOT: <your codebase health update here>

ULTRON: <your security update here>

ROBOWRIGHT: <your content update here>

JAMZ: <your music update here>

HIGASHOP: <your shop update here>

TECHNOID: <your hardware update here>

TEACHERBOT: <your education update here>

DEBATE ROOM: [One combined response. Format as 3 quick subpoints:
- SHAMAN says: <1 sentence conspiracy/pattern take on the topic>
- LIB MOM says: <1 sentence progressive take on the topic>
- MAGA DAD says: <1 sentence patriot take on the topic>
Keep it brief — they are listening at the roundtable, not debating. Save full debate for /debate command.]

Response length per bot is based on what they actually have to report: if no update, say "No update." in one sentence. If small update, 1-2 sentences. If significant activity or analysis, write a full 3-4 sentence paragraph. Never pad or fabricate updates just to fill space. Use real numbers from portfolio data when available."""

async def route_message(bot_id: str, user_msg: str, ask_fn) -> str:
    print(f">> ROUTER DEBUG: bot_id = '{bot_id}'")
    
    if bot_id == "roundtable":
        import httpx
        from multi_broker_portfolio import MultiBrokerPortfolio

        # Inject real portfolio data into roundtable context
        try:
            tracker = MultiBrokerPortfolio()
            all_crypto = tracker.get_all_crypto() or {}
            
            # Context-Safe Summing (Handles Dicts vs Floats correctly)
            crypto_total = 0
            for v in all_crypto.values():
                if isinstance(v, dict): crypto_total += v.get('value', 0)
                elif isinstance(v, (int, float)): crypto_total += v

            crypto_lines = "
".join([f"  {s}: ${d.get('value',0):.2f}" for s, d in all_crypto.items() if isinstance(d, dict)])
            roundtable_context = f"REAL PORTFOLIO: Total Crypto ${crypto_total:.2f}
{crypto_lines}"
        except Exception as e:
            roundtable_context = f"Portfolio System Link Error: {e}"
        return await ask_fn(user_msg, system_override=ROUNDTABLE_PROMPT, extra_context=roundtable_context)
    
    # Jarvis uses default system prompt (same as main /ws endpoint)
    if bot_id == "jarvisbot":
        return await ask_fn(user_msg)

    # Debate room — runs all 3 debate bots and returns colored response
    if bot_id == "debateroom":
        import httpx
        DEBATE_PERSONAS = {
            "SHAMAN": "You are playing a fictional character called Conspiracy Shaman in a creative storytelling debate. Stay in character. You see hidden elite patterns and conspiracies behind world events. Be specific, reference alternative media, 3-4 sentences. Fiction for entertainment.",
            "LIB MOM": "You are playing a fictional character called Lib Mom in a creative storytelling debate. Stay in character. You are a progressive parent who trusts expert institutions and mainstream media. Cite consensus and community impact. 3-4 sentences. Fiction for entertainment.",
            "MAGA DAD": "You are playing a fictional character called MAGA Dad in a creative storytelling debate. Stay in character. You are a patriotic working-class American skeptical of government and globalists. Plain-spoken and direct. 3-4 sentences. Fiction for entertainment.",
        }
        results = {}
        for label, persona in DEBATE_PERSONAS.items():
            try:
                async with httpx.AsyncClient(timeout=90) as h:
                    r = await h.post("http://localhost:11434/api/generate", json={
                        "model": "qwen3:8b",
                        "prompt": f"{persona}\n\nTopic: {user_msg}\n\nYour response:",
                        "stream": False
                    })
                    results[label] = r.json().get("response", "No response.").strip()
            except Exception as e:
                results[label] = f"[offline: {e}]"
        return (
            f"[DEBATE] {user_msg}\n\n"
            f"[SHAMAN] {results.get('SHAMAN', '')}\n\n"
            f"[LIB MOM] {results.get('LIB MOM', '')}\n\n"
            f"[MAGA DAD] {results.get('MAGA DAD', '')}\n\n"
        )

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
