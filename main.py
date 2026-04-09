import asyncio
import time
import httpx
import sys
import os
import psutil
import subprocess
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ─────────────────────────────────────────────────────────────────────────────
# MEMORY & YOUTUBE
# ─────────────────────────────────────────────────────────────────────────────

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import memory
from youtube_tools import handle_youtube_request

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

MODEL      = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = """You are J.A.R.V.I.S., a highly intelligent AI modeled after the AI from Iron Man.
You speak with calm confidence, dry wit, and British sophistication.
You address the user as 'sir' occasionally, but not in every response.
You are direct and precise — never ramble.

CRITICAL RULES:
1. You will be given LIVE MARKET DATA in each prompt. Always use these exact numbers when discussing markets.
2. If you are NOT given data about something, say so clearly. Never invent facts, prices, statistics, or news.
3. If asked about real-time events (sports, crime, news) you do not have access to, admit it directly.
4. Never fabricate portfolio values, CPU stats, or system metrics — these will be provided to you.
5. You have access to MEMORY from past conversations. Use it to give continuity to the user's experience.
6. If the user states a preference, acknowledge it — it will be stored for future sessions."""

# ─────────────────────────────────────────────────────────────────────────────
# KEYS
# ─────────────────────────────────────────────────────────────────────────────

ALPACA_KEY    = None
ALPACA_SECRET = None
HANDSHAKE     = "UNVERIFIED"

try:
    import keys
    ALPACA_KEY    = keys.ALPACA_KEY
    ALPACA_SECRET = keys.ALPACA_SECRET
    HANDSHAKE     = "VERIFIED"
    print(">> SECURITY HANDSHAKE: KEYS VERIFIED.")
except Exception as e:
    print(f">> WARNING: keys.py not found or invalid: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────────────────────

latest_market_data = {}
latest_portfolio   = {"equity": "0.00", "buying_power": "0.00", "day_pl": "0.00", "positions": []}
start_time         = time.time()
command_count      = 0

# ─────────────────────────────────────────────────────────────────────────────
# VOICE (macOS only)
# ─────────────────────────────────────────────────────────────────────────────

def speak(text: str):
    try:
        clean = text.replace("*", "").replace("#", "").replace("`", "")[:500]
        subprocess.Popen(["say", "-v", "Daniel", "-r", "160", clean])
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# PREFERENCE DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

PREFERENCE_TRIGGERS = [
    "i prefer", "i like", "i don't like", "i dislike", "i want",
    "i avoid", "my strategy", "i trade", "i hold", "i invest",
    "remember that", "note that", "keep in mind",
]

def detect_and_save_preference(user_msg: str):
    if any(t in user_msg.lower() for t in PREFERENCE_TRIGGERS):
        memory.save_preference(f"user_note_{int(time.time())}", user_msg.strip())

# ─────────────────────────────────────────────────────────────────────────────
# MARKET DATA — Binance
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_binance():
    global latest_market_data
    url = 'https://api.binance.com/api/v3/ticker/price?symbols=["BTCUSDT","ETHUSDT","SOLUSDT"]'
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    for item in r.json():
                        symbol = item["symbol"].replace("USDT", "")
                        latest_market_data[symbol] = {
                            "price":  f"{float(item['price']):,.2f}",
                            "source": "BINANCE",
                        }
            await asyncio.sleep(2)
        except Exception:
            await asyncio.sleep(10)

# ─────────────────────────────────────────────────────────────────────────────
# PORTFOLIO DATA — Alpaca
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_alpaca():
    global latest_portfolio
    if not ALPACA_KEY or not ALPACA_SECRET:
        print(">> ALPACA: No credentials — portfolio feed offline.")
        return

    headers = {
        "APCA-API-KEY-ID":     ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
    }
    base = "https://paper-api.alpaca.markets/v2"

    while True:
        try:
            async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                acct_r = await client.get(f"{base}/account")
                pos_r  = await client.get(f"{base}/positions")

                if acct_r.status_code == 200:
                    acct    = acct_r.json()
                    equity  = float(acct.get("equity", 0))
                    last_eq = float(acct.get("last_equity", equity))
                    latest_portfolio["equity"]       = f"{equity:,.2f}"
                    latest_portfolio["buying_power"] = f"{float(acct.get('buying_power', 0)):,.2f}"
                    latest_portfolio["day_pl"]       = f"{equity - last_eq:+,.2f}"

                if pos_r.status_code == 200:
                    pos = pos_r.json()
                    latest_portfolio["positions"] = [
                        {
                            "symbol": p["symbol"],
                            "value":  f"{float(p['market_value']):,.2f}",
                            "pl":      f"{float(p['unrealized_pl']):+,.2f}",
                        }
                        for p in pos
                    ] if isinstance(pos, list) else []

            print(f">> ALPACA: Equity ${latest_portfolio['equity']} | {len(latest_portfolio['positions'])} positions")

        except Exception as e:
            print(f">> ALPACA ERROR: {e}")

        await asyncio.sleep(30)

# ─────────────────────────────────────────────────────────────────────────────
# OLLAMA — Intelligence Layer
# ─────────────────────────────────────────────────────────────────────────────

async def ask_ollama(user_msg: str, extra_context: str = "") -> str:
    market_lines = [f"{k}: ${v['price']}" for k, v in latest_market_data.items()]
    market_str   = ", ".join(market_lines) if market_lines else "No market data yet."

    portfolio_str = "Alpaca portfolio offline."
    if latest_portfolio.get("equity", "0.00") != "0.00":
        pos_str = ", ".join(
            [f"{p['symbol']} ${p['value']} ({p['pl']})" for p in latest_portfolio.get("positions", [])]
        ) or "none"
        portfolio_str = (
            f"Equity: ${latest_portfolio.get('equity','?')} | "
            f"Day P/L: {latest_portfolio.get('day_pl','?')} | "
            f"Buying Power: ${latest_portfolio.get('buying_power','?')} | "
            f"Positions: {pos_str}"
        )

    system_stats = (
        f"CPU: {psutil.cpu_percent()}% | "
        f"RAM: {psutil.virtual_memory().percent}% | "
        f"Uptime: {time.strftime('%H:%M:%S', time.gmtime(time.time() - start_time))}"
    )

    memory_block = await asyncio.to_thread(memory.get_memory_context)

    # extra_context used for YouTube summaries
    extra = f"\n--- YOUTUBE CONTENT ---\n{extra_context}\n---\n" if extra_context else ""

    full_prompt = f"""{SYSTEM_PROMPT}

--- LIVE DATA ---
CRYPTO    : {market_str}
PORTFOLIO : {portfolio_str}
SYSTEM    : {system_stats}
---
{memory_block}
{extra}
User: {user_msg}
JARVIS:"""

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(OLLAMA_URL, json={
                "model":  MODEL,
                "prompt": full_prompt,
                "stream": False,
            })
            return response.json().get("response", "Neural logic error, sir.").strip()
    except Exception as e:
        return f"Neural Link Error: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(memory.init_db)
    tasks = [
        asyncio.create_task(fetch_binance()),
        asyncio.create_task(fetch_alpaca()),
    ]
    yield
    for t in tasks:
        t.cancel()

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET
# ─────────────────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global command_count
    await websocket.accept()

    async def broadcaster():
        try:
            while True:
                uptime      = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
                stock_list = [
                    {"symbol": k, "price": v["price"], "change": "LIVE"}
                    for k, v in latest_market_data.items()
                ]
                await websocket.send_json({
                    "type": "telemetry",
                    "stocks": stock_list or [{"symbol": "SYNCING", "price": "...", "change": ""}],
                    "stats": {
                        "uptime":   uptime,
                        "load":     round(psutil.cpu_percent()),
                        "ram":      round(psutil.virtual_memory().percent),
                        "commands": command_count,
                    },
                    "portfolio": latest_portfolio,
                })
                await asyncio.sleep(1)
        except Exception:
            pass

    asyncio.create_task(broadcaster())

    try:
        while True:
            data     = await websocket.receive_json()
            command_count += 1
            user_msg = data.get("message", "").strip()

            if not user_msg:
                continue

            # ── FAST PATH: system shortcuts ───────────────────────────────────
            if user_msg.lower().startswith("/brief"):
                equity = latest_portfolio.get("equity", "offline")
                prices = ", ".join([f"{k} ${v['price']}" for k, v in latest_market_data.items()])
                reply  = (
                    f"M4 CORE STATUS — "
                    f"CPU: {round(psutil.cpu_percent())}% | "
                    f"RAM: {round(psutil.virtual_memory().percent)}% | "
                    f"Handshake: {HANDSHAKE} | "
                    f"Portfolio: ${equity} | "
                    f"Markets: {prices or 'syncing...'}"
                )
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            elif user_msg.lower().startswith("/model"):
                reply = f"Active model: {MODEL}. Ollama endpoint: {OLLAMA_URL}."
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            elif user_msg.lower().startswith("/memory"):
                prefs = await asyncio.to_thread(memory.get_all_preferences)
                reply = ("Stored preferences:\n" + "\n".join(f"{k}: {v}" for k, v in prefs.items())) \
                        if prefs else "No preferences stored yet, sir."
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            # ── YOUTUBE PATH ──────────────────────────────────────────────────
            yt_result, yt_mode = await asyncio.to_thread(handle_youtube_request, user_msg)

            if yt_result and yt_mode == "youtube_summarize":
                # Feed YouTube content to Ollama for intelligent summary
                await websocket.send_json({"type": "answer", "text": "⏳ Fetching and analyzing video..."})
                reply = await ask_ollama(user_msg, extra_context=yt_result)
                memory.save_conversation("user", user_msg)
                memory.save_conversation("jarvis", memory.extract_summary(reply))
                await asyncio.to_thread(speak, reply)
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            elif yt_result:
                # Direct YouTube result (search, transcript, comments, info)
                await asyncio.to_thread(speak, yt_result[:500])
                await websocket.send_json({"type": "answer", "text": yt_result})
                continue

            # ── INTELLIGENCE PATH: full LLM ───────────────────────────────────
            await asyncio.to_thread(detect_and_save_preference, user_msg)
            reply   = await ask_ollama(user_msg)
            summary = await asyncio.to_thread(memory.extract_summary, reply)
            await asyncio.to_thread(memory.save_conversation, user_msg, summary)
            await asyncio.to_thread(speak, reply)
            await websocket.send_json({"type": "answer", "text": reply})

    except WebSocketDisconnect:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# STATIC FRONTEND
# ─────────────────────────────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
