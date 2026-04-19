import asyncio
import os
import time
import httpx
import psutil
from datetime import datetime
import schedule
from alpaca.trading.client import TradingClient

ALPACA_KEY    = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
OLLAMA_URL    = "http://localhost:11434/api/generate"
MODEL         = "qwen3:8b"

client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

async def get_crypto_prices():
    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
            if r.status_code == 200:
                d = r.json()
                return {"BTC": d['bitcoin']['usd'], "ETH": d['ethereum']['usd'], "SOL": d['solana']['usd']}
    except Exception as e:
        print(f">> CRYPTO PRICE ERROR: {e}")
    return {}

async def get_alpaca_portfolio():
    try:
        acct = client.get_account()
        pos  = client.get_all_positions()
        return {
            "equity":       float(acct.equity),
            "buying_power": float(acct.buying_power),
            "day_pl":       float(acct.equity) - float(acct.last_equity) if acct.last_equity else 0,
            "positions":    [{"symbol": p.symbol, "value": float(p.market_value), "pl": float(p.unrealized_pl)} for p in pos] if pos else []
        }
    except Exception as e:
        print(f">> PORTFOLIO ERROR: {e}")
    return {}

def get_real_crypto():
    try:
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from multi_broker_portfolio import MultiBrokerPortfolio
        tracker = MultiBrokerPortfolio()
        all_crypto = tracker.get_all_crypto()
        pd = tracker.portfolio_data
        webull_crypto = sum(v['value'] for v in pd['webull']['crypto'].values())
        coinbase_total = pd['coinbase']['total_value']
        kraken_equity = pd['paper_trading']['kraken']['equity']
        total = sum(c['value'] for c in all_crypto.values())
        lines = "\n".join(
            f"  {sym}: ${d['value']:.2f} (P/L: ${d.get('pl', 0):+.2f}) [{d.get('broker','')}]"
            for sym, d in all_crypto.items()
        )
        return total, lines, webull_crypto, coinbase_total, kraken_equity
    except Exception as e:
        print(f">> REAL CRYPTO ERROR: {e}")
        return 0, "Unavailable", 0, 0, 0

def get_system_stats():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    return cpu, ram.used / (1024**3), ram.total / (1024**3), disk.percent

async def generate_briefing(time_of_day):
    now = datetime.now().strftime('%B %d, %Y — %I:%M %p CST')
    is_morning = time_of_day == "morning"
    market_note = "Markets open 9:30 AM ET. Standing by, sir." if is_morning else "Markets closed. Review complete. Standing by, sir."
    icon = "🌅" if is_morning else "🌆"

    # Fetch all data
    prices      = await get_crypto_prices()
    portfolio   = await get_alpaca_portfolio()
    cpu, ram_used, ram_total, disk = get_system_stats()
    crypto_total, crypto_lines, wb_crypto, cb_total, kr_equity = get_real_crypto()

    # Build position strings
    pos_lines = ""
    for p in portfolio.get("positions", []):
        emoji = "🟢" if p['pl'] >= 0 else "🔴"
        pos_lines += f"{emoji} {p['symbol']}: ${p['value']:,.2f} (P/L: ${p['pl']:+,.2f})\n"

    price_str = ", ".join([f"{k}: ${v:,.2f}" for k, v in prices.items()]) if prices else "Unavailable"

    prompt = f"""You are J.A.R.V.I.S. generating a {time_of_day.upper()} BRIEFING for Higa House.
Use ONLY the real data provided below. No invented numbers.

--- LIVE DATA ---
STOCKS (Alpaca paper):
  Equity: ${portfolio.get('equity', 0):,.2f} | Day P/L: {portfolio.get('day_pl', 0):+,.2f} | Buying Power: ${portfolio.get('buying_power', 0):,.2f}
{pos_lines}
CRYPTO PORTFOLIO (Total: ${crypto_total:.2f}):
{crypto_lines}
  Webull crypto: ${wb_crypto:.2f} | Coinbase: ${cb_total:.2f} | Kraken paper: ${kr_equity:.2f}

LIVE PRICES: {price_str}
SYSTEM: CPU {cpu:.0f}% | RAM {ram_used:.1f}GB/{ram_total:.1f}GB | Disk {disk:.0f}%
---

Format the briefing EXACTLY like this — each section is its own agent voice:

{icon} J.A.R.V.I.S. {time_of_day.upper()} BRIEFING
{now}

⚙️ SYSTEM: [1 sentence system status]

📈 STOCKBOT: [1-3 sentences. Which stocks are up/down, any sell signals, buying power status.]

🪙 CRYPTOID: [1-3 sentences. Real crypto P/L numbers. Which to hold, which to reduce. Total portfolio value.]

📰 HEADLINES: [Leave blank — will be filled separately]

🔒 ULTRON: [1 sentence security status]

📺 ROBOWRIGHT: [1 sentence — any content opportunities or "No update."]

🎵 JAMZ: [1 sentence — any music activity or "No update."]

🛍️ HIGASHOP: [1 sentence — shop status or "No update."]

🖥️ TECHNOID: [1 sentence — hardware status]

{market_note}"""

    try:
        async with httpx.AsyncClient(timeout=90) as h:
            resp = await h.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
            briefing = resp.json().get("response", "Neural link error, sir.")
            print(f"\n{briefing}\n")
            return briefing
    except Exception as e:
        print(f">> BRIEFING ERROR: {e}")
        return ""

def morning_briefing():
    print("\n🌅 Generating morning briefing...")
    asyncio.run(generate_briefing("morning"))

def evening_briefing():
    print("\n🌆 Generating evening briefing...")
    asyncio.run(generate_briefing("evening"))

if __name__ == "__main__":
    schedule.every().day.at("05:00").do(morning_briefing)
    schedule.every().day.at("17:00").do(evening_briefing)
    print("🤖 Briefing scheduler online. Waiting for 5 AM and 5 PM...")
    while True:
        schedule.run_pending()
        time.sleep(60)
