
import asyncio, os, sys, httpx, psutil, time, sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CST        = pytz.timezone("America/Chicago")
MODEL      = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"
ALPACA_KEY = None
ALPACA_SECRET = None

try:
    import keys
    ALPACA_KEY    = keys.ALPACA_KEY
    ALPACA_SECRET = keys.ALPACA_SECRET
except: pass

def is_authorized(update):
    return str(update.effective_chat.id) == str(TELEGRAM_CHAT_ID)

async def get_crypto():
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbols=[\"BTCUSDT\",\"ETHUSDT\",\"SOLUSDT\"]"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url)
            if r.status_code == 200:
                return {i["symbol"].replace("USDT",""): f"{float(i['price']):,.2f}" for i in r.json()}
    except: pass
    return {}

async def get_portfolio():
    if not ALPACA_KEY: return {}
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    try:
        async with httpx.AsyncClient(timeout=15, headers=headers) as c:
            acct = (await c.get("https://paper-api.alpaca.markets/v2/account")).json()
            pos  = (await c.get("https://paper-api.alpaca.markets/v2/positions")).json()
            equity  = float(acct.get("equity",0))
            last_eq = float(acct.get("last_equity",equity))
            return {
                "equity": f"{equity:,.2f}",
                "day_pl": f"{equity-last_eq:+,.2f}",
                "buying_power": f"{float(acct.get('buying_power',0)):,.2f}",
                "positions": [{"symbol":p["symbol"],"value":f"{float(p['market_value']):,.2f}","pl":f"{float(p['unrealized_pl']):+,.2f}"} for p in pos] if isinstance(pos,list) else []
            }
    except Exception as e:
        print(f"Alpaca error: {e}")
        return {}

async def get_news():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get("https://feeds.bbci.co.uk/news/rss.xml")
            soup = BeautifulSoup(r.text, "xml")
            return [i.find("title").text for i in soup.find_all("item")[:5]]
    except: return []

def get_metrics():
    cpu  = psutil.cpu_percent(interval=0.5)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {"cpu":round(cpu),"ram_used":round(ram.used/1e9,1),"ram_total":round(ram.total/1e9,1),"disk_pct":round(disk.percent)}

async def ask_ollama(user_msg, extra=""):
    crypto    = await get_crypto()
    portfolio = await get_portfolio()
    market_str = ", ".join([f"{k}: ${v}" for k,v in crypto.items()]) or "unavailable"
    pos_str = ", ".join([f"{p['symbol']} ${p['value']} ({p['pl']})" for p in portfolio.get("positions",[])]) or "none"
    portfolio_str = f"Equity: ${portfolio.get('equity','?')} | Day P/L: {portfolio.get('day_pl','?')} | Buying Power: ${portfolio.get('buying_power','?')} | Positions: {pos_str}" if portfolio else "offline"
    prompt = f"""You are J.A.R.V.I.S., a highly intelligent AI. British wit. Direct. Never invent data.
LIVE DATA:
CRYPTO: {market_str}
PORTFOLIO: {portfolio_str}
{extra}
User: {user_msg}
JARVIS:"""
    try:
        async with httpx.AsyncClient(timeout=90) as c:
            r = await c.post(OLLAMA_URL, json={"model":MODEL,"prompt":prompt,"stream":False})
            return r.json().get("response","Neural error, sir.").strip()
    except Exception as e:
        return f"Ollama offline: {e}"

async def handle_trade(msg):
    try:
        from trading import is_trade_command, parse_trade_intent, execute_trade_intent
        if not is_trade_command(msg): return None
        intent = parse_trade_intent(msg)
        if not intent: return None
        portfolio = await get_portfolio()
        return await asyncio.to_thread(execute_trade_intent, intent, ALPACA_KEY, ALPACA_SECRET, portfolio.get("positions",[]))
    except Exception as e:
        return f"Trade error: {e}"

async def handle_youtube(msg):
    try:
        from youtube_tools import handle_youtube_request
        result, mode = await asyncio.to_thread(handle_youtube_request, msg)
        if not result: return None
        if mode == "youtube_summarize":
            return await ask_ollama(msg, extra=f"YOUTUBE CONTENT:\n{result}")
        return result
    except Exception as e:
        return f"YouTube error: {e}"

async def send_msg(bot, chat_id, text):
    chunks = [text[i:i+4000] for i in range(0,len(text),4000)]
    for chunk in chunks:
        try:
            await bot.send_message(chat_id=chat_id, text=chunk, parse_mode="Markdown")
        except:
            try: await bot.send_message(chat_id=chat_id, text=chunk)
            except Exception as e: print(f"Send error: {e}")
        await asyncio.sleep(0.3)

async def build_briefing(period):
    now = datetime.now(CST)
    crypto, portfolio, news = await asyncio.gather(get_crypto(), get_portfolio(), get_news())
    m = get_metrics()
    emoji = "\U0001f305" if period=="MORNING" else "\U0001f306"
    lines = [f"{emoji} *J.A.R.V.I.S. {period} BRIEFING*", f"_{now.strftime('%B %d, %Y — %I:%M %p CST')}_", ""]
    lines += ["\U0001f4b0 *PORTFOLIO*"]
    if portfolio:
        pl_e = "\U0001f4c8" if not portfolio.get("day_pl","0").startswith("-") else "\U0001f4c9"
        lines += [f"Equity: `${portfolio.get('equity','?')}`", f"Day P/L: `{portfolio.get('day_pl','?')}` {pl_e}", f"Buying Power: `${portfolio.get('buying_power','?')}`",""]
        for p in portfolio.get("positions",[]):
            sign = "\U0001f7e2" if not p["pl"].startswith("-") else "\U0001f534"
            lines.append(f"{sign} {p['symbol']}: `${p['value']}` ({p['pl']})")
    lines += ["","\U0001f4ca *CRYPTO*"] + [f"• {k}: `${v}`" for k,v in crypto.items()]
    lines += ["","\U0001f4f0 *HEADLINES*"] + [f"{i+1}. {h}" for i,h in enumerate(news[:5])]
    lines += ["","\u2699\ufe0f *SYSTEM*", f"`CPU: {m['cpu']}% | RAM: {m['ram_used']}GB/{m['ram_total']}GB | Disk: {m['disk_pct']}%`",""]
    lines.append("_Markets open 9:30 AM ET. Standing by, sir._" if period=="MORNING" else "_Markets closed. Review complete. Standing by, sir._")
    return "\n".join(lines)

async def briefing_scheduler(bot):
    print(">> Briefing scheduler online.")
    while True:
        now = datetime.now(CST)
        today = now.date()
        morning = CST.localize(datetime.combine(today, datetime.min.time().replace(hour=5, minute=0)))
        evening = CST.localize(datetime.combine(today, datetime.min.time().replace(hour=17, minute=0)))
        candidates = [(p,t) for p,t in [("MORNING",morning),("EVENING",evening)] if t > now]
        if not candidates:
            candidates = [("MORNING", CST.localize(datetime.combine(today+timedelta(days=1), datetime.min.time().replace(hour=5,minute=0))))]
        period, next_time = candidates[0]
        wait = (next_time - now).total_seconds()
        print(f">> Next {period} briefing in {wait/3600:.1f}h")
        await asyncio.sleep(wait)
        try:
            msg = await build_briefing(period)
            await send_msg(bot, TELEGRAM_CHAT_ID, msg)
            print(f">> {period} briefing sent.")
        except Exception as e:
            print(f">> Briefing error: {e}")
        await asyncio.sleep(60)

async def cmd_start(update, context):
    if not is_authorized(update): return
    await update.message.reply_text("*J.A.R.V.I.S. Online*\nType /help for commands, sir.", parse_mode="Markdown")

async def cmd_help(update, context):
    if not is_authorized(update): return
    await update.message.reply_text("*COMMANDS*\n/brief — Status\n/portfolio — Full portfolio\n/system — PC metrics\n/trades — Trade history\n/memory — Preferences\n\n*TRADING*\nbuy 5 NVDA\nsell all TSLA\ncancel all orders\n\n*YOUTUBE*\nsummarize this: [url]\nsearch youtube for [topic]\n\nAnything else → AI response", parse_mode="Markdown")

async def cmd_brief(update, context):
    if not is_authorized(update): return
    m = get_metrics()
    portfolio = await get_portfolio()
    crypto = await get_crypto()
    prices = ", ".join([f"{k} ${v}" for k,v in crypto.items()]) or "syncing"
    await update.message.reply_text(f"*M4 CORE STATUS*\nCPU: `{m['cpu']}%` | RAM: `{m['ram_used']}GB/{m['ram_total']}GB`\nPortfolio: `${portfolio.get('equity','offline')}`\nMarkets: `{prices}`", parse_mode="Markdown")

async def cmd_portfolio(update, context):
    if not is_authorized(update): return
    await update.message.reply_text("Fetching portfolio...")
    p = await get_portfolio()
    if not p:
        await update.message.reply_text("Portfolio offline, sir.")
        return
    pl_e = "\U0001f4c8" if not p.get("day_pl","0").startswith("-") else "\U0001f4c9"
    lines = [f"\U0001f4b0 *PORTFOLIO*", f"Equity: `${p.get('equity','?')}`", f"Day P/L: `{p.get('day_pl','?')}` {pl_e}", f"Buying Power: `${p.get('buying_power','?')}`", ""]
    for pos in p.get("positions",[]):
        sign = "\U0001f7e2" if not pos["pl"].startswith("-") else "\U0001f534"
        lines.append(f"{sign} {pos['symbol']}: `${pos['value']}` ({pos['pl']})")
    await send_msg(context.bot, update.effective_chat.id, "\n".join(lines))

async def cmd_system(update, context):
    if not is_authorized(update): return
    m = get_metrics()
    net = psutil.net_io_counters()
    await update.message.reply_text(f"*SYSTEM REPORT*\nCPU: `{m['cpu']}%`\nRAM: `{m['ram_used']}GB/{m['ram_total']}GB`\nDisk: `{m['disk_pct']}%` used\nNetwork: `\u2191{round(net.bytes_sent/1e6,1)}MB \u2193{round(net.bytes_recv/1e6,1)}MB`", parse_mode="Markdown")

async def cmd_trades(update, context):
    if not is_authorized(update): return
    try:
        from trading import get_trade_history
        await update.message.reply_text(get_trade_history(10))
    except Exception as e:
        await update.message.reply_text(f"Trade history error: {e}")

async def cmd_memory(update, context):
    if not is_authorized(update): return
    try:
        import memory as mem
        prefs = mem.get_all_preferences()
        reply = "\U0001f9e0 *Stored Preferences:*\n" + "\n".join([f"{k}: {v}" for k,v in list(prefs.items())[:20]]) if prefs else "No preferences stored yet, sir."
        await update.message.reply_text(reply, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Memory error: {e}")

async def handle_message(update, context):
    if not is_authorized(update): return
    user_msg = update.message.text.strip()
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    trade = await handle_trade(user_msg)
    if trade:
        await update.message.reply_text(trade)
        return
    yt = await handle_youtube(user_msg)
    if yt:
        if "youtube.com" in user_msg.lower() or "summarize" in user_msg.lower():
            await update.message.reply_text("\u23f3 Fetching and analyzing video...")
        await send_msg(context.bot, update.effective_chat.id, yt)
        return
    reply = await ask_ollama(user_msg)
    try:
        import memory as mem
        mem.save_conversation(user_msg, mem.extract_summary(reply))
    except: pass
    await send_msg(context.bot, update.effective_chat.id, reply)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("brief",     cmd_brief))
    app.add_handler(CommandHandler("portfolio", cmd_portfolio))
    app.add_handler(CommandHandler("system",    cmd_system))
    app.add_handler(CommandHandler("trades",    cmd_trades))
    app.add_handler(CommandHandler("memory",    cmd_memory))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        asyncio.create_task(briefing_scheduler(app.bot))
        print(">> J.A.R.V.I.S. TELEGRAM: Fully Operational.")
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
