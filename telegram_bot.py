"""
telegram_bot.py — HIGA HOUSE Telegram Bot (Merged Final)
Combines old jarvis_telegram_bot.py features with new HIGA HOUSE commands.
Runs as poll_telegram() background task inside main.py lifespan.

FEATURES:
- Two-way chat — text anything, JARVIS responds with British wit
- Trading commands: buy 5 NVDA, sell all TSLA
- Technical indicators: analyze NVDA, scan portfolio
- YouTube: summarize this: [url]
- All HIGA HOUSE commands: /brief /portfolio /crypto /bots /debate /roundtable
- Memory: saves conversations to SQLite
- Briefings: 5AM/5PM auto-send via briefing_scheduler.py
"""
import asyncio, os, sys, httpx, psutil
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)
sys.path.insert(0, "/Users/higabot1/jarvis1-1")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OLLAMA_URL       = "http://localhost:11434/api/generate"
MODEL            = "qwen3:8b"

# ── SEND MESSAGE ──────────────────────────────────────────────────────────────

async def send_telegram(message: str, chat_id: str = None) -> bool:
    if not TELEGRAM_TOKEN:
        print(">> TELEGRAM: No token")
        return False
    cid = str(chat_id or TELEGRAM_CHAT_ID or "")
    if not cid:
        print(">> TELEGRAM: No chat ID")
        return False
    try:
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        async with httpx.AsyncClient(timeout=15) as h:
            for chunk in chunks:
                await h.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": cid, "text": chunk, "parse_mode": "Markdown"}
                )
                await asyncio.sleep(0.3)
        return True
    except Exception as e:
        print(f">> TELEGRAM SEND ERROR: {e}")
        return False

# ── DATA FETCHERS ─────────────────────────────────────────────────────────────

async def get_crypto_prices() -> dict:
    """Fetch live crypto prices from Binance."""
    try:
        url = 'https://api.binance.com/api/v3/ticker/price?symbols=["BTCUSDT","ETHUSDT","SOLUSDT","DOGEUSDT"]'
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(url)
            if r.status_code == 200:
                return {i["symbol"].replace("USDT",""): float(i["price"]) for i in r.json()}
    except Exception:
        pass
    return {}

async def get_portfolio() -> dict:
    """Fetch Alpaca paper portfolio."""
    try:
        import keys
        key    = keys.ALPACA_KEY
        secret = keys.ALPACA_SECRET
    except Exception:
        key    = os.getenv("ALPACA_KEY")
        secret = os.getenv("ALPACA_SECRET")
    if not key:
        return {}
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    try:
        async with httpx.AsyncClient(timeout=15, headers=headers) as h:
            acct = (await h.get("https://paper-api.alpaca.markets/v2/account")).json()
            pos  = (await h.get("https://paper-api.alpaca.markets/v2/positions")).json()
            equity   = float(acct.get("equity", 0))
            last_eq  = float(acct.get("last_equity", equity))
            return {
                "equity":       equity,
                "day_pl":       equity - last_eq,
                "buying_power": float(acct.get("buying_power", 0)),
                "positions": [
                    {
                        "symbol": p["symbol"],
                        "value":  float(p["market_value"]),
                        "pl":     float(p["unrealized_pl"])
                    }
                    for p in (pos if isinstance(pos, list) else [])
                ]
            }
    except Exception as e:
        print(f">> TELEGRAM PORTFOLIO ERROR: {e}")
        return {}

def get_metrics() -> dict:
    cpu  = psutil.cpu_percent(interval=0.5)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu":       round(cpu),
        "ram_used":  round(ram.used / 1e9, 1),
        "ram_total": round(ram.total / 1e9, 1),
        "disk_pct":  round(disk.percent)
    }

# ── OLLAMA ────────────────────────────────────────────────────────────────────

async def ask_jarvis(user_msg: str, extra: str = "") -> str:
    """Ask JARVIS via Ollama with live portfolio + crypto context."""
    crypto    = await get_crypto_prices()
    portfolio = await get_portfolio()

    market_str = ", ".join([f"{k}: ${v:,.2f}" for k, v in crypto.items()]) or "unavailable"
    pos_str    = ", ".join([
        f"{p['symbol']} ${p['value']:,.2f} ({p['pl']:+,.2f})"
        for p in portfolio.get("positions", [])
    ]) or "none"
    port_str = (
        f"Equity: ${portfolio.get('equity',0):,.2f} | "
        f"Day P/L: {portfolio.get('day_pl',0):+,.2f} | "
        f"Buying Power: ${portfolio.get('buying_power',0):,.2f} | "
        f"Positions: {pos_str}"
    ) if portfolio else "offline"

    m = get_metrics()
    prompt = f"""You are J.A.R.V.I.S., the AI chief of staff for HIGA HOUSE.
British wit. Direct. Precise. Never invent data. Mobile-friendly responses.

LIVE DATA:
CRYPTO: {market_str}
PORTFOLIO: {port_str}
SYSTEM: CPU {m['cpu']}% | RAM {m['ram_used']}GB/{m['ram_total']}GB
{extra}

User: {user_msg}
JARVIS:"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as h:
            r = await h.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
            result = r.json().get("response", "").strip()
            return result if result else "Neural link error, sir."
    except Exception as e:
        print(f">> TELEGRAM OLLAMA ERROR: {e}")
        return "Standing by — Ollama is processing, sir. Try again in a moment."

# ── COMMAND HANDLERS ──────────────────────────────────────────────────────────

async def handle_message(user_msg: str, chat_id: str) -> str:
    q = user_msg.lower().strip()

    # /start
    if q in ["/start", "start"]:
        return "*J.A.R.V.I.S. Online*\nType /help for commands, sir."

    # /help
    if q in ["/help", "help", "/commands"]:
        return """🤖 *HIGA HOUSE COMMANDS*

📊 *Portfolio*
/brief — morning/evening briefing
/portfolio — full portfolio snapshot
/crypto — live crypto prices
/system — Mac system stats
/trades — trade history
/memory — stored preferences

🤖 *Agents*
/bots — all 15 bot statuses
/roundtable [question] — ask all agents
/debate [topic] — 3-way debate

🔧 *Doctorbot*
/health — code health scan
/draft summary — session summary
/draft fix [bug] — bug fix draft
/draft feature [desc] — feature plan

📺 *Content*
summarize this: [YouTube URL]
search youtube for [topic]

💹 *Trading*
buy 5 NVDA
sell all TSLA
analyze NVDA
scan portfolio

💬 *Chat*
Any message → JARVIS responds

_HIGA HOUSE is always watching, sir._"""

    # /brief
    if q in ["/brief", "brief", "/briefing"]:
        await send_telegram("🔄 Generating briefing...", chat_id)
        try:
            from briefing_scheduler import generate_briefing
            hour = datetime.now().hour
            tod  = "morning" if 5 <= hour < 12 else "evening"
            return await generate_briefing(tod)
        except Exception as e:
            return f"Briefing error: {e}"

    # /portfolio
    if q in ["/portfolio", "portfolio", "/p"]:
        await send_telegram("🔄 Fetching portfolio...", chat_id)
        p = await get_portfolio()
        if not p:
            return "Portfolio offline, sir."
        pl_icon = "📈" if p.get("day_pl", 0) >= 0 else "📉"
        lines = [
            "💰 *PORTFOLIO*",
            f"Equity: `${p['equity']:,.2f}`",
            f"Day P/L: `{p['day_pl']:+,.2f}` {pl_icon}",
            f"Buying Power: `${p['buying_power']:,.2f}`",
            ""
        ]
        for pos in p.get("positions", []):
            e = "🟢" if pos["pl"] >= 0 else "🔴"
            lines.append(f"{e} {pos['symbol']}: `${pos['value']:,.2f}` ({pos['pl']:+,.2f})")
        return "\n".join(lines)

    # /crypto
    if q in ["/crypto", "crypto"]:
        prices = await get_crypto_prices()
        if not prices:
            return "Crypto prices unavailable, sir."
        try:
            from briefing_scheduler import get_real_crypto
            total, lines, wb, cb, kr = get_real_crypto()
            price_str = " | ".join([f"{k}: ${v:,.2f}" for k, v in prices.items()])
            return f"🪙 *CRYPTO PORTFOLIO* (${total:.2f})\n{lines}\n\n*Live:* {price_str}"
        except Exception:
            price_str = "\n".join([f"• {k}: `${v:,.2f}`" for k, v in prices.items()])
            return f"📊 *CRYPTO PRICES*\n{price_str}"

    # /system
    if q in ["/system", "system"]:
        m   = get_metrics()
        net = psutil.net_io_counters()
        return (f"⚙️ *SYSTEM*\n"
                f"CPU: `{m['cpu']}%`\n"
                f"RAM: `{m['ram_used']}GB/{m['ram_total']}GB`\n"
                f"Disk: `{m['disk_pct']}%`\n"
                f"Network: `↑{round(net.bytes_sent/1e6,1)}MB ↓{round(net.bytes_recv/1e6,1)}MB`")

    # /trades
    if q in ["/trades", "trades"]:
        try:
            from trading import get_trade_history
            return get_trade_history(10)
        except Exception as e:
            return f"Trade history error: {e}"

    # /memory
    if q in ["/memory", "memory"]:
        try:
            import memory as mem
            prefs = mem.get_all_preferences()
            if prefs:
                return "🧠 *Stored Preferences:*\n" + "\n".join([f"{k}: {v}" for k, v in list(prefs.items())[:20]])
            return "No preferences stored yet, sir."
        except Exception as e:
            return f"Memory error: {e}"

    # /bots
    if q in ["/bots", "bots", "status"]:
        try:
            async with httpx.AsyncClient(timeout=5) as h:
                r    = await h.get("http://localhost:8000/api/bots/status")
                data = r.json()
                lines = ["🤖 *HIGA HOUSE STATUS*"]
                for k, v in data.items():
                    icon   = v.get("icon", "?")
                    status = v.get("status", "unknown")
                    emoji  = "🟢" if status == "idle" else "🟡" if "working" in status else "🔴"
                    lines.append(f"{emoji} {icon} {k}: {status}")
                return "\n".join(lines)
        except Exception as e:
            return f"Status error: {e}"

    # /health
    if q in ["/health", "health check", "find bugs"]:
        try:
            from bots.doctorbot import scan_for_bugs
            return scan_for_bugs()
        except Exception as e:
            return f"Health check error: {e}"

    # /debate
    if q.startswith("/debate ") or q.startswith("debate "):
        topic = user_msg.split(" ", 1)[1].strip()
        await send_telegram(f"⚔️ Debate: {topic}\n_(2-3 minutes)_", chat_id)
        try:
            from bots.router import route_message
            from main import ask_ollama
            return await route_message("debateroom", topic, ask_ollama)
        except Exception as e:
            return f"Debate error: {e}"

    # /roundtable
    if q.startswith("/roundtable ") or q.startswith("roundtable "):
        question = user_msg.split(" ", 1)[1].strip()
        await send_telegram("🔄 Asking roundtable...\n_(3-4 minutes)_", chat_id)
        try:
            from bots.router import route_message
            from main import ask_ollama
            return await route_message("roundtable", question, ask_ollama)
        except Exception as e:
            return f"Roundtable error: {e}"

    # /draft
    if q.startswith("/draft ") or q.startswith("draft "):
        cmd = user_msg.split(" ", 1)[1].strip()
        await send_telegram(f"📋 Generating draft: {cmd}", chat_id)
        try:
            from bots.doctorbot import draft_session_summary, draft_bug_fix, draft_new_feature
            if cmd == "summary":
                return await draft_session_summary()
            elif cmd.startswith("fix "):
                return await draft_bug_fix(cmd[4:])
            elif cmd.startswith("feature "):
                return await draft_new_feature(cmd[8:])
            else:
                return "Try: /draft summary | /draft fix [bug] | /draft feature [desc]"
        except Exception as e:
            return f"Draft error: {e}"

    # YouTube
    if "youtube.com" in q or "youtu.be" in q or q.startswith("summarize this:"):
        await send_telegram("🎬 Fetching video...", chat_id)
        try:
            from youtube_tools import handle_youtube_request
            result, mode = await asyncio.to_thread(handle_youtube_request, user_msg)
            if result:
                if mode == "youtube_summarize":
                    return await ask_jarvis(user_msg, extra=f"YOUTUBE CONTENT:\n{result[:2000]}")
                return result
        except Exception as e:
            return f"YouTube error: {e}"

    # Technical indicators
    try:
        from indicators import is_indicator_request, is_portfolio_scan, extract_ticker, analyze_ticker, analyze_portfolio
        if is_indicator_request(user_msg):
            portfolio = await get_portfolio()
            if is_portfolio_scan(user_msg) and portfolio.get("positions"):
                symbols = [p["symbol"] for p in portfolio["positions"]]
                return await asyncio.to_thread(analyze_portfolio, symbols)
            ticker = extract_ticker(user_msg)
            if ticker:
                return await asyncio.to_thread(analyze_ticker, ticker)
    except Exception:
        pass

    # Trading commands
    try:
        from trading import is_trade_command, parse_trade_intent, execute_trade_intent
        if is_trade_command(user_msg):
            intent = parse_trade_intent(user_msg)
            if intent:
                portfolio = await get_portfolio()
                result = await asyncio.to_thread(
                    execute_trade_intent, intent,
                    os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"),
                    portfolio.get("positions", [])
                )
                if result:
                    return result
    except Exception:
        pass

    # Default — ask JARVIS
    reply = await ask_jarvis(user_msg)
    try:
        import memory as mem
        mem.save_conversation(user_msg, mem.extract_summary(reply))
    except Exception:
        pass
    return reply

# ── POLLING LOOP ──────────────────────────────────────────────────────────────

async def poll_telegram(interval: int = 2):
    """Poll Telegram for new messages. Runs as background task in main.py."""
    if not TELEGRAM_TOKEN:
        print(">> TELEGRAM BOT: No token — skipping")
        return

    print(">> TELEGRAM BOT: Started polling")
    last_update_id = 0

    while True:
        try:
            async with httpx.AsyncClient(timeout=30) as h:
                r = await h.get(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                    params={"offset": last_update_id + 1}
                )
                data = r.json()
                if not data.get("ok"):
                    await asyncio.sleep(interval)
                    continue

                for update in data.get("result", []):
                    last_update_id = update["update_id"]
                    msg     = update.get("message", {})
                    text    = msg.get("text", "").strip()
                    chat_id = str(msg.get("chat", {}).get("id", ""))

                    if not text or not chat_id:
                        continue

                    # Only respond to authorized chat
                    if TELEGRAM_CHAT_ID and chat_id != str(TELEGRAM_CHAT_ID):
                        continue

                    print(f">> TELEGRAM [{chat_id}]: {text[:60]}")

                    try:
                        reply = await handle_message(text, chat_id)
                        if reply:
                            await send_telegram(reply, chat_id)
                    except Exception as e:
                        print(f">> TELEGRAM HANDLER ERROR: {e}")
                        await send_telegram(f"Error: {e}", chat_id)

        except Exception as e:
            print(f">> TELEGRAM POLL ERROR: {e}")

        await asyncio.sleep(interval)
