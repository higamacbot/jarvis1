import asyncio
import os
import time
import httpx
from datetime import datetime
import schedule
from alpaca.trading.client import TradingClient
import yfinance as yf

ALPACA_KEY    = os.getenv("ALPACA_KEY",    "PKJAUIEC7IAEZ6Y4KLHVGGK2SK")
ALPACA_SECRET = os.getenv("ALPACA_SECRET", "7xirUrAWACJp7dL8EdHzNWMjEXWggge3EQMoTaZY9ZZy")
OLLAMA_URL    = "http://localhost:11434/api/generate"
MODEL         = "qwen3:8b"

client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

async def get_market_data():
    """Fetch live crypto and stock prices"""
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
        print(f">> MARKET DATA ERROR: {e}")
    return {}

async def get_portfolio():
    """Fetch Alpaca portfolio data"""
    try:
        acct = client.get_account()
        pos = client.get_all_positions()
        return {
            "equity": float(acct.equity),
            "buying_power": float(acct.buying_power),
            "day_pl": float(acct.equity) - float(acct.last_equity) if acct.last_equity else 0,
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty),
                    "value": float(p.market_value),
                    "pl": float(p.unrealized_pl)
                }
                for p in pos
            ] if pos else []
        }
    except Exception as e:
        print(f">> PORTFOLIO ERROR: {e}")
    return {}

async def generate_briefing(time_of_day):
    """Generate AI briefing with market data"""
    crypto = await get_market_data()
    portfolio = await get_portfolio()
    
    crypto_str = ", ".join([f"{k}: ${v:,.2f}" for k, v in crypto.items()]) if crypto else "No data"
    port_str = f"Equity: ${portfolio['equity']:,.2f} | Day P/L: {portfolio['day_pl']:+,.2f}" if portfolio else "No data"
    pos_str = "\n".join([f"  {p['symbol']}: {p['qty']} shares | ${p['value']:,.2f} | P/L: {p['pl']:+,.2f}" for p in portfolio.get('positions', [])]) if portfolio.get('positions') else "No positions"
    
    prompt = f"""You are J.A.R.V.I.S., the master intelligence of the Higa House system.
Generate a {time_of_day.upper()} BRIEFING for the user. Be concise, direct, professional.

CURRENT DATA:
CRYPTO: {crypto_str}
PORTFOLIO: {port_str}
POSITIONS:
{pos_str}

Format the briefing like this:
🌅 J.A.R.V.I.S. {time_of_day.upper()} BRIEFING
{datetime.now().strftime('%B %d, %Y — %I:%M %p %Z')}

💰 PORTFOLIO
[equity, day P/L, status]

📊 MARKET
[crypto prices, market sentiment]

⚙️ SYSTEM
[uptime, recommendations]

Keep it tight. No fluff. Sir."""

    try:
        async with httpx.AsyncClient(timeout=60) as http_client:
            resp = await http_client.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            })
            briefing = resp.json().get("response", "Neural link error, sir.")
            print(f"\n{briefing}\n")
            return briefing
    except Exception as e:
        print(f">> BRIEFING ERROR: {e}")
        return ""

def morning_briefing():
    """Schedule morning briefing"""
    print("\n🌅 Generating morning briefing...")
    asyncio.run(generate_briefing("morning"))

def evening_briefing():
    """Schedule evening briefing"""
    print("\n🌆 Generating evening briefing...")
    asyncio.run(generate_briefing("evening"))

if __name__ == "__main__":
    schedule.every().day.at("05:00").do(morning_briefing)
    schedule.every().day.at("17:00").do(evening_briefing)
    
    print("🤖 Briefing scheduler online. Waiting for 5 AM and 5 PM...")
    while True:
        schedule.run_pending()
        time.sleep(60)
