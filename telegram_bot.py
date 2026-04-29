"""
telegram_bot.py — HIGA HOUSE Telegram Interface
Text anything to your bot and JARVIS responds like the roundtable.
Supports all HIGA HOUSE commands via Telegram.

INSTALL: pip3 install python-telegram-bot --break-system-packages
SETUP: Add TELEGRAM_TOKEN and TELEGRAM_CHAT_ID to .env
RUN: Added to main.py lifespan automatically
"""
import os, asyncio, sys, httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, "/Users/higabot1/jarvis1-1")

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OLLAMA_URL       = "http://localhost:11434/api/generate"
MODEL            = "qwen3:8b"

# ── SEND MESSAGE ──────────────────────────────────────────────────────────────

async def send_telegram(message: str, chat_id: str = None) -> bool:
    """Send a message to Telegram."""
    if not TELEGRAM_TOKEN:
        print(">> TELEGRAM: No token configured")
        return False
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid:
        print(">> TELEGRAM: No chat ID configured")
        return False
    try:
        # Split long messages (Telegram limit 4096 chars)
        chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
        async with httpx.AsyncClient(timeout=10) as h:
            for chunk in chunks:
                await h.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": cid, "text": chunk, "parse_mode": "Markdown"}
                )
        return True
    except Exception as e:
        print(f">> TELEGRAM SEND ERROR: {e}")
        return False


# ── ASK OLLAMA ────────────────────────────────────────────────────────────────

async def ask_jarvis(user_msg: str, system: str = None) -> str:
    """Ask Ollama and return response."""
    default_system = """You are J.A.R.V.I.S., the AI chief of staff for HIGA HOUSE.
You have access to a multi-agent system with 15 specialized bots.
You are responding via Telegram to your operator.
Be concise, direct, and helpful. Use real data when available.
Format responses cleanly for mobile viewing."""

    prompt = f"{system or default_system}\n\nUser: {user_msg}\nJARVIS:"
    try:
        async with httpx.AsyncClient(timeout=120.0) as h:
            r = await h.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            })
            return r.json().get("response", "Neural link error, sir.").strip()
    except Exception as e:
        return f"Error: {e}"


# ── COMMAND HANDLERS ──────────────────────────────────────────────────────────

async def handle_telegram_message(user_msg: str, chat_id: str) -> str:
    """
    Route incoming Telegram messages to the right handler.
    Works exactly like HIGA HOUSE but via Telegram.
    """
    msg = user_msg.strip()
    q = msg.lower()

    # /brief — full morning/evening briefing
    if q in ["/brief", "brief", "/briefing"]:
        await send_telegram("🔄 Generating briefing...", chat_id)
        try:
            from briefing_scheduler import generate_briefing
            hour = datetime.now().hour
            tod = "morning" if 5 <= hour < 12 else "evening"
            return await generate_briefing(tod)
        except Exception as e:
            return f"Briefing error: {e}"

    # /bots — show all bot statuses
    if q in ["/bots", "bots", "status"]:
        try:
            async with httpx.AsyncClient(timeout=5) as h:
                r = await h.get("http://localhost:8000/api/bots/status")
                data = r.json()
                lines = ["🤖 *HIGA HOUSE STATUS*"]
                for k, v in data.items():
                    icon = v.get("icon", "?")
                    status = v.get("status", "unknown")
                    emoji = "🟢" if status == "idle" else "🟡" if status == "working" else "🔴"
                    lines.append(f"{emoji} {icon} {k}: {status}")
                return "\n".join(lines)
        except Exception as e:
            return f"Status error: {e}"

    # /portfolio — quick portfolio summary
    if q in ["/portfolio", "portfolio", "/p"]:
        try:
            from briefing_scheduler import get_alpaca_portfolio, get_real_crypto
            port = await get_alpaca_portfolio()
            total, lines, wb, cb, kr = get_real_crypto()
            grand_total = port.get("equity", 0) + total + 454.36
            pl_icon = "📈" if port.get("day_pl", 0) >= 0 else "📉"
            msg = f"""💰 *PORTFOLIO SNAPSHOT*
Total: ~${grand_total:,.2f}
Stocks: ${port.get('equity', 0):,.2f} {pl_icon} {port.get('day_pl', 0):+,.2f}
Crypto: ${total:.2f}
Acorns: $454.36

*POSITIONS:*"""
            for p in port.get("positions", []):
                e = "🟢" if p["pl"] >= 0 else "🔴"
                msg += f"\n{e} {p['symbol']}: ${p['value']:,.2f} ({p['pl']:+,.2f})"
            msg += f"\n\n*CRYPTO:*\n{lines}"
            return msg
        except Exception as e:
            return f"Portfolio error: {e}"

    # /crypto — crypto only
    if q in ["/crypto", "crypto"]:
        try:
            from briefing_scheduler import get_real_crypto, get_crypto_prices
            total, lines, wb, cb, kr = get_real_crypto()
            prices = await get_crypto_prices()
            price_str = ", ".join([f"{k}: ${v:,.2f}" for k, v in prices.items()])
            return f"🪙 *CRYPTO* (Total: ${total:.2f})\n{lines}\n\nLive: {price_str}"
        except Exception as e:
            return f"Crypto error: {e}"

    # /debate — trigger debate room
    if q.startswith("/debate ") or q.startswith("debate "):
        topic = msg.split(" ", 1)[1].strip()
        await send_telegram(f"⚔️ Debate starting: {topic}\n_(takes 2-3 minutes)_", chat_id)
        try:
            from bots.router import route_message
            from main import ask_ollama
            result = await route_message("debateroom", topic, ask_ollama)
            return result
        except Exception as e:
            return f"Debate error: {e}"

    # /draft — trigger doctorbot draft
    if q.startswith("/draft ") or q.startswith("draft "):
        cmd = msg.split(" ", 1)[1].strip()
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
                return f"Unknown draft command. Try: draft summary, draft fix [bug], draft feature [desc]"
        except Exception as e:
            return f"Draft error: {e}"

    # /health — code health check
    if q in ["/health", "health check", "find bugs"]:
        try:
            from bots.doctorbot import scan_for_bugs
            return scan_for_bugs()
        except Exception as e:
            return f"Health check error: {e}"

    # /roundtable — ask all agents
    if q.startswith("/roundtable ") or q.startswith("roundtable "):
        question = msg.split(" ", 1)[1].strip()
        await send_telegram("🔄 Asking roundtable...\n_(takes 3-4 minutes)_", chat_id)
        try:
            from bots.router import route_message
            from main import ask_ollama
            result = await route_message("roundtable", question, ask_ollama)
            return result
        except Exception as e:
            return f"Roundtable error: {e}"

    # /youtube — summarize a video
    if "youtube.com" in q or "youtu.be" in q:
        await send_telegram("🎬 Fetching video...", chat_id)
        try:
            from youtube_tools import handle_youtube_request
            result, mode = handle_youtube_request(f"summarize this: {msg}")
            return result or "Could not fetch video"
        except Exception as e:
            return f"YouTube error: {e}"

    # /help — show all commands
    if q in ["/help", "help", "/commands"]:
        return """🤖 *HIGA HOUSE COMMANDS*

📊 *Portfolio*
/brief — full morning/evening briefing
/portfolio — quick portfolio snapshot
/crypto — crypto positions only

🤖 *Agents*
/bots — all bot statuses
/roundtable [question] — ask all agents
/debate [topic] — 3-way debate

🔧 *Doctorbot*
/health — code health check
/draft summary — session summary
/draft fix [bug] — bug fix draft
/draft feature [desc] — feature draft

📺 *Content*
[YouTube URL] — summarize video

💬 *Chat*
Any message — JARVIS responds directly

_HIGA HOUSE is always watching, sir._"""

    # DEFAULT — respond as JARVIS roundtable
    await send_telegram("🔄 Processing...", chat_id)
    return await ask_jarvis(msg)


# ── POLLING LOOP ──────────────────────────────────────────────────────────────

async def poll_telegram(interval: int = 2):
    """
    Poll Telegram for new messages and respond.
    Runs as a background task in main.py.
    """
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
                    params={"offset": last_update_id + 1, "timeout": 20}
                )
                data = r.json()

                if not data.get("ok"):
                    await asyncio.sleep(interval)
                    continue

                updates = data.get("result", [])
                for update in updates:
                    last_update_id = update["update_id"]
                    msg = update.get("message", {})
                    text = msg.get("text", "").strip()
                    chat_id = str(msg.get("chat", {}).get("id", ""))

                    if not text or not chat_id:
                        continue

                    print(f">> TELEGRAM: [{chat_id}] {text[:50]}")

                    try:
                        reply = await handle_telegram_message(text, chat_id)
                        if reply:
                            await send_telegram(reply, chat_id)
                    except Exception as e:
                        print(f">> TELEGRAM HANDLER ERROR: {e}")
                        await send_telegram(f"Error: {e}", chat_id)

        except Exception as e:
            print(f">> TELEGRAM POLL ERROR: {e}")

        await asyncio.sleep(interval)
