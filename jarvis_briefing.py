import asyncio
import os
import httpx
import psutil
import time
from datetime import datetime
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import pytz

load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ALPACA_KEY       = None
ALPACA_SECRET    = None

try:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import keys
    ALPACA_KEY    = keys.ALPACA_KEY
    ALPACA_SECRET = keys.ALPACA_SECRET
except Exception as e:
    print(f">> WARNING: keys.py not found: {e}")

CST = pytz.timezone("America/Chicago")

async def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(">> ERROR: No Telegram credentials.")
        return
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    async with httpx.AsyncClient(timeout=15) as client:
        for chunk in chunks:
            try:
                r = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "Markdown"}
                )
                if not r.json().get("ok"):
                    print(f">> TELEGRAM ERROR: {r.json()}")
            except Exception as e:
                print(f">> SEND ERROR: {e}")
            await asyncio.sleep(0.5)

async def get_crypto_prices():
    try:
        url = 'https://api.binance.com/api/v3/ticker/price?symbols=["BTCUSDT","ETHUSDT","SOLUSDT"]'
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 200:
                prices = {}
                for item in r.json():
                    symbol = item["symbol"].replace("USDT", "")
                    prices[symbol] = f"{float(item['price']):,.2f}"
                return prices
    except Exception as e:
        print(f">> CRYPTO ERROR: {e}")
    return {}

async def get_portfolio():
    if not ALPACA_KEY or not ALPACA_SECRET:
        return {}
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    base = "https://paper-api.alpaca.markets/v2"
    try:
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            acct_r = await client.get(f"{base}/account")
            pos_r  = await client.get(f"{base}/positions")
            portfolio = {}
            if acct_r.status_code == 200:
                acct    = acct_r.json()
                equity  = float(acct.get("equity", 0))
                last_eq = float(acct.get("last_equity", equity))
                portfolio["equity"]       = f"{equity:,.2f}"
                portfolio["day_pl"]       = f"{equity - last_eq:+,.2f}"
                portfolio["buying_power"] = f"{float(acct.get('buying_power', 0)):,.2f}"
            if pos_r.status_code == 200:
                positions = pos_r.json()
                portfolio["positions"] = [
                    {"symbol": p["symbol"],
                     "value":  f"{float(p['market_value']):,.2f}",
                     "pl":     f"{float(p['unrealized_pl']):+,.2f}"}
                    for p in positions
                ] if isinstance(positions, list) else []
            return portfolio
    except Exception as e:
        print(f">> ALPACA ERROR: {e}")
        return {}

async def get_news_headlines():
    headlines = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://feeds.bbci.co.uk/news/rss.xml")
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "xml")
                for item in soup.find_all("item")[:5]:
                    title = item.find("title")
                    if title:
                        headlines.append(title.get_text(strip=True))
    except Exception as e:
        print(f">> NEWS ERROR: {e}")
    return headlines

def get_system_status():
    cpu  = psutil.cpu_percent(interval=1)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return f"CPU: {cpu}% | RAM: {ram.used // (1024**3)}GB/{ram.total // (1024**3)}GB | Disk: {disk.percent}% used"

async def build_briefing(period: str):
    now       = datetime.now(CST)
    timestamp = now.strftime("%B %d, %Y — %I:%M %p CST")
    crypto, portfolio, headlines = await asyncio.gather(
        get_crypto_prices(), get_portfolio(), get_news_headlines()
    )
    system = get_system_status()
    lines  = []
    emoji  = "\U0001f305" if period == "MORNING" else "\U0001f306"
    lines.append(f"{emoji} *J.A.R.V.I.S. {period} BRIEFING*")
    lines.append(f"_{timestamp}_")
    lines.append("")
    lines.append("\U0001f4b0 *PORTFOLIO*")
    if portfolio:
        pl_emoji = "\U0001f4c8" if not portfolio.get("day_pl","0").startswith("-") else "\U0001f4c9"
        lines.append(f"Equity: `${portfolio.get('equity','?')}`")
        lines.append(f"Day P/L: `{portfolio.get('day_pl','?')}` {pl_emoji}")
        lines.append(f"Buying Power: `${portfolio.get('buying_power','?')}`")
        for p in portfolio.get("positions", []):
            sign = "\U0001f7e2" if not p["pl"].startswith("-") else "\U0001f534"
            lines.append(f"{sign} {p['symbol']}: `${p['value']}` ({p['pl']})")
    else:
        lines.append("_Portfolio unavailable_")
    lines.append("")
    lines.append("\U0001f4ca *CRYPTO*")
    if crypto:
        for symbol, price in crypto.items():
            lines.append(f"• {symbol}: `${price}`")
    lines.append("")
    lines.append("\U0001f4f0 *TOP HEADLINES*")
    for i, h in enumerate(headlines[:5], 1):
        lines.append(f"{i}. {h}")
    lines.append("")
    lines.append("\u2699\ufe0f *SYSTEM*")
    lines.append(f"`{system}`")
    lines.append("")
    if period == "MORNING":
        lines.append("_Markets open 9:30 AM ET. Standing by, sir._")
    else:
        lines.append("_Markets closed. Review complete. Standing by, sir._")
    return "\n".join(lines)

async def run_scheduler():
    print(">> BRIEFING SCHEDULER: Online.")
    await send_telegram("\U0001f916 *J.A.R.V.I.S. Briefing Scheduler Online*\nBriefings at 5:00 AM and 5:00 PM CST daily, sir.")
    while True:
        now        = datetime.now(CST)
        today      = now.date()
        morning    = CST.localize(datetime.combine(today, datetime.min.time().replace(hour=5,  minute=0)))
        evening    = CST.localize(datetime.combine(today, datetime.min.time().replace(hour=17, minute=0)))
        candidates = []
        if now < morning:
            candidates.append(("MORNING", morning))
        if now < evening:
            candidates.append(("EVENING", evening))
        if not candidates:
            from datetime import timedelta
            tomorrow     = today + timedelta(days=1)
            next_morning = CST.localize(datetime.combine(tomorrow, datetime.min.time().replace(hour=5, minute=0)))
            candidates.append(("MORNING", next_morning))
        period, next_time = candidates[0]
        wait_seconds = (next_time - now).total_seconds()
        print(f">> BRIEFING: Next {period} in {wait_seconds/3600:.1f} hours")
        await asyncio.sleep(wait_seconds)
        try:
            # Use main briefing_scheduler for full HIGA HOUSE briefing
            import sys
            sys.path.insert(0, "/Users/higabot1/jarvis1-1")
            from briefing_scheduler import generate_briefing
            tod = "morning" if period == "MORNING" else "evening"
            message = await generate_briefing(tod)
            if not message:
                message = await build_briefing(period)  # fallback
            await send_telegram(message)
            print(f">> BRIEFING: {period} sent.")
        except Exception as e:
            print(f">> BRIEFING ERROR: {e}")
            try:
                message = await build_briefing(period)
                await send_telegram(message)
            except Exception as e2:
                await send_telegram(f"Briefing failed, sir. Error: {e2}")
        await asyncio.sleep(60)

async def send_test_briefing():
    print(">> Sending test briefing...")
    message = await build_briefing("MORNING")
    await send_telegram(message)
    print(">> Done. Check Telegram.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(send_test_briefing())
    else:
        asyncio.run(run_scheduler())
