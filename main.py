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
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL MODULES
# ─────────────────────────────────────────────────────────────────────────────

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import memory
from youtube_tools import handle_youtube_request
from trading import is_trade_command, parse_trade_intent, execute_trade_intent, get_trade_history
from bots.router import route_message
from indicators import is_indicator_request, is_portfolio_scan, extract_ticker, analyze_ticker, analyze_portfolio

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

MODEL      = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_REGISTRY = {
    "local_fast":   "qwen3:8b",
    "local_deep":   "llama3:latest",
}

SYSTEM_PROMPT = """You are J.A.R.V.I.S., a highly intelligent AI modeled after the AI from Iron Man.
You speak with calm confidence, dry wit, and British sophistication.
You address the user as 'sir' occasionally, but not in every response.
You are direct and precise — never ramble.

CRITICAL RULES:
1. You will be given LIVE MARKET DATA in each prompt. Always use these exact numbers.
2. If you are NOT given data about something, say so clearly. Never invent facts.
3. If asked about real-time events you do not have access to, admit it directly.
4. You have access to MEMORY from past conversations. Use it for continuity.
5. Trade history will be provided. Reference it when discussing portfolio strategy."""

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
    # FALLBACK TO ENVIRONMENT VARIABLES
    ALPACA_KEY    = os.getenv("ALPACA_KEY")
    ALPACA_SECRET = os.getenv("ALPACA_SECRET")
    if ALPACA_KEY and ALPACA_SECRET:
        print(">> SECURITY HANDSHAKE: ENVIRONMENT VARIABLES VERIFIED.")
    else:
        print(">> WARNING: NO ALPACA CREDENTIALS FOUND")

# ─────────────────────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────────────────────

latest_market_data = {}
latest_portfolio   = {"equity": "0.00", "buying_power": "0.00", "day_pl": "0.00", "positions": []}
start_time         = time.time()
command_count      = 0
daily_messages     = 0
daily_tokens_est   = 0

# ─────────────────────────────────────────────────────────────────────────────
# VOICE
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
# TOKEN USAGE TRACKER
# ─────────────────────────────────────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    return len(text) // 4

def track_usage(prompt: str, response: str):
    global daily_messages, daily_tokens_est
    daily_messages   += 1
    tokens            = estimate_tokens(prompt) + estimate_tokens(response)
    daily_tokens_est += tokens
    try:
        today = time.strftime("%Y-%m-%d")
        memory.save_preference(
            f"usage_{today}",
            f"messages={daily_messages}, tokens_est={daily_tokens_est}, model={MODEL}"
        )
    except Exception:
        pass

def get_usage_report() -> str:
    today = time.strftime("%Y-%m-%d")
    prefs = memory.get_all_preferences()
    usage = prefs.get(f"usage_{today}", None)
    if not usage:
        return f"No usage recorded today ({today}) yet, sir."
    return f"Usage report for {today}:\n{usage}"

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM METRICS
# ─────────────────────────────────────────────────────────────────────────────

def get_system_metrics() -> dict:
    cpu_per_core = psutil.cpu_percent(percpu=True)
    ram          = psutil.virtual_memory()
    disk         = psutil.disk_usage('/')
    net          = psutil.net_io_counters()

    return {
        "cpu_total":    round(psutil.cpu_percent()),
        "cpu_cores":    [round(c) for c in cpu_per_core],
        "ram_percent":  round(ram.percent),
        "ram_used_gb":  round(ram.used / 1e9, 1),
        "ram_total_gb": round(ram.total / 1e9, 1),
        "disk_percent": round(disk.percent),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "net_sent_mb":  round(net.bytes_sent / 1e6, 1),
        "net_recv_mb":  round(net.bytes_recv / 1e6, 1),
        "uptime":       time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time)),
    }

# ─────────────────────────────────────────────────────────────────────────────
# DATA FEEDS
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_crypto():
    global latest_market_data
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd"
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    data = r.json()
                    latest_market_data["BTC"] = {"price": f"{data['bitcoin']['usd']:,.2f}", "source": "COINGECKO"}
                    latest_market_data["ETH"] = {"price": f"{data['ethereum']['usd']:,.2f}", "source": "COINGECKO"}
                    latest_market_data["SOL"] = {"price": f"{data['solana']['usd']:,.2f}", "source": "COINGECKO"}
            await asyncio.sleep(30)
        except Exception as e:
            print(f">> CRYPTO ERROR: {e}")
            await asyncio.sleep(60)
        except Exception:
            await asyncio.sleep(10)

async def fetch_alpaca():
    global latest_portfolio
    if not ALPACA_KEY or not ALPACA_SECRET: return

    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    base = "https://paper-api.alpaca.markets/v2"

    while True:
        try:
            async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                acct_r = await client.get(f"{base}/account")
                pos_r  = await client.get(f"{base}/positions")

                if acct_r.status_code == 200:
                    acct = acct_r.json()
                    equity = float(acct.get("equity", 0))
                    latest_portfolio["equity"] = f"{equity:,.2f}"
                    latest_portfolio["buying_power"] = f"{float(acct.get('buying_power', 0)):,.2f}"
                    latest_portfolio["day_pl"] = f"{equity - float(acct.get('last_equity', equity)):+,.2f}"

                if pos_r.status_code == 200:
                    pos = pos_r.json()
                    latest_portfolio["positions"] = [
                        {"symbol": p["symbol"], "value": f"{float(p['market_value']):,.2f}", "pl": f"{float(p['unrealized_pl']):+,.2f}"}
                        for p in pos
                    ] if isinstance(pos, list) else []
            print(f">> ALPACA: Equity ${latest_portfolio['equity']}")
        except Exception as e:
            print(f">> ALPACA ERROR: {e}")
        await asyncio.sleep(30)

# ─────────────────────────────────────────────────────────────────────────────
# OLLAMA LOGIC
# ─────────────────────────────────────────────────────────────────────────────

async def ask_ollama(user_msg: str, extra_context: str = "", timeout: float = 90.0, system_override: str = None) -> str:
    market_str = ", ".join([f"{k}: ${v['price']}" for k, v in latest_market_data.items()]) or "No market data."
    metrics = get_system_metrics()
    system_stats = f"CPU: {metrics['cpu_total']}% | RAM: {metrics['ram_used_gb']}GB | Uptime: {metrics['uptime']}"
    trade_hist = get_trade_history(limit=5)
    memory_block = await asyncio.to_thread(memory.get_memory_context)
    
    sys_prompt = system_override if system_override else SYSTEM_PROMPT
    
    full_prompt = f"""{sys_prompt}
--- LIVE DATA ---
CRYPTO: {market_str}
SYSTEM: {system_stats}
---
{memory_block}
--- RECENT TRADES ---
{trade_hist}
---
{extra_context}
User: {user_msg}
JARVIS:"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(OLLAMA_URL, json={"model": MODEL, "prompt": full_prompt, "stream": False})
            answer = response.json().get("response", "Neural logic error, sir.").strip()
            await asyncio.to_thread(track_usage, full_prompt, answer)
            return answer
    except asyncio.TimeoutError:
        return "Query timeout — Ollama processing too long. Try a simpler question, sir."
    except Exception as e:
        return f"Neural Link Error: {str(e)[:100]}"

# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI & WEBSOCKET
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(memory.init_db)
    tasks = [asyncio.create_task(fetch_crypto()), asyncio.create_task(fetch_alpaca())]
    yield
    for t in tasks: t.cancel()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global command_count
    await websocket.accept()

    async def broadcaster():
        try:
            while True:
                metrics = get_system_metrics()
                await websocket.send_json({
                    "type": "telemetry",
                    "stocks": [{"symbol": k, "price": v["price"], "change": "LIVE"} for k, v in latest_market_data.items()],
                    "stats": metrics,
                    "portfolio": latest_portfolio
                })
                await asyncio.sleep(1)
        except: pass

    asyncio.create_task(broadcaster())

    try:
        while True:
            data = await websocket.receive_json()
            command_count += 1
            user_msg = data.get("message", "").strip()
            if not user_msg: continue

            # FAST PATHS
            if user_msg.lower().startswith("/brief"):
                reply = f"System online. CPU: {psutil.cpu_percent()}% | Portfolio: ${latest_portfolio.get('equity')}"
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            # TRADE PATH
            if is_trade_command(user_msg) and ALPACA_KEY:
                intent = parse_trade_intent(user_msg)
                if intent:
                    reply = await asyncio.to_thread(execute_trade_intent, intent, ALPACA_KEY, ALPACA_SECRET, latest_portfolio.get("positions", []))
                    await asyncio.to_thread(speak, reply)
                    await websocket.send_json({"type": "answer", "text": reply})
                    continue

            # INDICATOR PATH
            if is_indicator_request(user_msg):
                if is_portfolio_scan(user_msg):
                    symbols = [p["symbol"] for p in latest_portfolio.get("positions", [])]
                    reply = await asyncio.to_thread(analyze_portfolio, symbols) if symbols else "No positions found, sir."
                else:
                    ticker = extract_ticker(user_msg)
                    if ticker:
                        await websocket.send_json({"type": "answer", "text": f"Analyzing {ticker}..."})
                        reply = await asyncio.to_thread(analyze_ticker, ticker)
                    else:
                        reply = await ask_ollama(user_msg)
                await asyncio.to_thread(speak, reply)
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            # YOUTUBE PATH
            # ── NEWS PATH ────────────────────────────────────────────────
            from news_sources import NEWS_TRIGGERS, get_site_sources
            from fetch import fetch_source_context
            if any(t in user_msg.lower() for t in NEWS_TRIGGERS):
                await websocket.send_json({"type": "answer", "text": "Scanning news sources..."})
                sources = get_site_sources()[:3]  # AP, BBC, Al Jazeera
                news_context = ""
                for src in sources:
                    try:
                        url, text = await asyncio.to_thread(fetch_source_context, src["url"])
                        news_context += f"\n--- {src['name']} ---\n{text[:800]}\n"
                    except Exception as e:
                        news_context += f"\n--- {src['name']} --- (unavailable)\n"
                reply = await ask_ollama(user_msg, extra_context=news_context)
                memory.save_conversation("user", user_msg)
                memory.save_conversation("jarvis", memory.extract_summary(reply))
                await asyncio.to_thread(speak, reply)
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            yt_result, yt_mode = await asyncio.to_thread(handle_youtube_request, user_msg)
            if yt_result and yt_mode == "youtube_summarize":
                await websocket.send_json({"type": "answer", "text": "Fetching and analyzing video..."})
                reply = await ask_ollama(user_msg, extra_context=yt_result)
                await asyncio.to_thread(speak, reply)
                await websocket.send_json({"type": "answer", "text": reply})
                continue
            elif yt_result:
                await asyncio.to_thread(speak, yt_result[:500])
                await websocket.send_json({"type": "answer", "text": yt_result})
                continue

            # DEFAULT PATH
            await asyncio.to_thread(detect_and_save_preference, user_msg)
            reply = await ask_ollama(user_msg)
            await asyncio.to_thread(memory.save_conversation, "user", user_msg)
            await asyncio.to_thread(memory.save_conversation, "jarvis", memory.extract_summary(reply))
            await asyncio.to_thread(speak, reply)
            await websocket.send_json({"type": "answer", "text": reply})

    except WebSocketDisconnect: pass


@app.get("/house")
async def serve_house():
    return FileResponse("frontend/house.html")

@app.websocket("/ws/house")
async def house_websocket(websocket: WebSocket):
    await websocket.accept()
    print(">> HIGA HOUSE: Client connected.")

    async def broadcaster():
        try:
            while True:
                uptime = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
                stock_list = [
                    {"symbol": k, "price": v["price"], "change": "LIVE"}
                    for k, v in latest_market_data.items()
                ]
                await websocket.send_json({
                    "type": "telemetry",
                    "stocks": stock_list or [{"symbol": "SYNCING", "price": "...", "change": ""}],
                    "stats": {
                        "uptime": uptime,
                        "load": round(psutil.cpu_percent()),
                        "ram": round(psutil.virtual_memory().percent),
                    },
                    "portfolio": latest_portfolio,
                })
                await asyncio.sleep(3)
        except Exception:
            pass

    asyncio.create_task(broadcaster())

    try:
        while True:
            data = await websocket.receive_json()
            bot_id   = data.get("bot", "jarvisbot")
            user_msg = data.get("message", "").strip()
            if not user_msg:
                continue
            await websocket.send_json({"type": "thinking", "bot": bot_id})

            # News PATH (jarvisbot only) 
            from news_sources import NEWS_TRIGGERS, get_site_sources
            from fetch import fetch_source_context
            if bot_id == "jarvisbot" and any(t in user_msg.lower() for t in NEWS_TRIGGERS):
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": "Scanning news sources, sir..."})
                sources = get_site_sources()[:3]
                news_context = ""
                for src in sources:
                    try:
                        url, text = await asyncio.to_thread(fetch_source_context, src["url"])
                        news_context += f"\n--- {src['name']} ---\n{text[:800]}\n"
                    except Exception:
                        news_context += f"\n--- {src['name']} --- (unavailable)\n"
                reply = await ask_ollama(user_msg, extra_context=news_context)
                memory.save_conversation(f"[{bot_id}] {user_msg}", memory.extract_summary(reply))
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            reply = await route_message(bot_id, user_msg, ask_ollama)
            memory.save_conversation(f"[{bot_id}] {user_msg}", memory.extract_summary(reply))
            await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
    except WebSocketDisconnect:
        print(">> HIGA HOUSE: Client disconnected.")

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
