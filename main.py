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

# Import the memory functions
import memory

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

MODEL      = "qwen3:8b"
OLLAMA_URL = "http://localhost:11434/api/generate"

SYSTEM_PROMPT = """You are J.A.R.V.I.S., a sophisticated AI.
Use the provided LIVE DATA and LONG-TERM MEMORY to answer.
Address the user as 'sir'. Be concise and witty."""

# ─────────────────────────────────────────────────────────────────────────────
# KEYS & STATE
# ─────────────────────────────────────────────────────────────────────────────

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
ALPACA_KEY = None
ALPACA_SECRET = None

try:
    import keys
    ALPACA_KEY = keys.ALPACA_KEY
    ALPACA_SECRET = keys.ALPACA_SECRET
    print(">> SECURITY HANDSHAKE: KEYS VERIFIED.")
except:
    print(">> WARNING: keys.py not found.")

latest_market_data = {}
latest_portfolio = {"equity": "0.00", "buying_power": "0.00", "day_pl": "0.00", "positions": []}
start_time = time.time()
command_count = 0

# ─────────────────────────────────────────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────────────────────────────────────────

def speak(text):
    try:
        clean = text.replace("*", "").replace("#", "")[:500]
        subprocess.Popen(["say", "-v", "Daniel", "-r", "160", clean])
    except: pass

async def fetch_binance():
    global latest_market_data
    url = 'https://api.binance.com/api/v3/ticker/price?symbols=["BTCUSDT","ETHUSDT","SOLUSDT"]'
    while True:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url)
                if r.status_code == 200:
                    for item in r.json():
                        symbol = item["symbol"].replace("USDT", "")
                        latest_market_data[symbol] = {"price": f"{float(item['price']):,.2f}"}
            await asyncio.sleep(2)
        except: await asyncio.sleep(10)

# PATCH 1: RESTORE ALPACA POSITIONS
async def fetch_alpaca():
    global latest_portfolio
    if not ALPACA_KEY: return
    headers = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET}
    base = "https://paper-api.alpaca.markets/v2"
    while True:
        try:
            async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                acct_r = await client.get(f"{base}/account")
                pos_r  = await client.get(f"{base}/positions")
                
                if acct_r.status_code == 200:
                    acct = acct_r.json()
                    equity = float(acct.get('equity', 0))
                    last_equity = float(acct.get('last_equity', equity))
                    latest_portfolio["equity"] = f"{equity:,.2f}"
                    latest_portfolio["buying_power"] = f"{float(acct.get('buying_power', 0)):,.2f}"
                    latest_portfolio["day_pl"] = f"{equity - last_equity:+,.2f}"
                
                if pos_r.status_code == 200:
                    pos = pos_r.json()
                    latest_portfolio["positions"] = [
                        {"symbol": p["symbol"], 
                         "value": f"{float(p['market_value']):,.2f}", 
                         "pl": f"{float(p['unrealized_pl']):+,.2f}"}
                        for p in pos
                    ] if isinstance(pos, list) else []
                    
            print(f">> ALPACA: Equity ${latest_portfolio['equity']} | {len(latest_portfolio['positions'])} positions")
        except Exception as e:
            print(f">> ALPACA ERROR: {e}")
        await asyncio.sleep(30)

# ─────────────────────────────────────────────────────────────────────────────
# INTELLIGENCE
# ─────────────────────────────────────────────────────────────────────────────

async def ask_ollama(user_msg):
    memory.save_conversation("user", user_msg)
    memory.detect_and_save_preference(user_msg)
    
    mem_context = memory.get_memory_context()
    market_str = ", ".join([f"{k}: ${v['price']}" for k, v in latest_market_data.items()])
    
    # PATCH 2: INJECT POSITIONS INTO PROMPT
    pos_str = ", ".join([f"{p['symbol']} ${p['value']} ({p['pl']})" for p in latest_portfolio.get('positions', [])]) or 'none'
    
    full_prompt = f"""{SYSTEM_PROMPT}

{mem_context}

--- LIVE MARKET DATA ---
CRYPTO: {market_str}
EQUITY: ${latest_portfolio.get('equity', '0.00')} (Day P/L: {latest_portfolio.get('day_pl', '0.00')})
BUYING POWER: ${latest_portfolio.get('buying_power', '0.00')}
POSITIONS: {pos_str}

User: {user_msg}
JARVIS:"""

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(OLLAMA_URL, json={"model": MODEL, "prompt": full_prompt, "stream": False})
            answer = response.json().get("response", "Neural error.").strip()
            memory.save_conversation("jarvis", answer)
            return answer
    except Exception as e:
        return f"Link Error: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# APP CORE
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    memory.init_db()
    t1 = asyncio.create_task(fetch_binance())
    t2 = asyncio.create_task(fetch_alpaca())
    yield
    t1.cancel(); t2.cancel()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global command_count
    await websocket.accept()
    
    async def broadcaster():
        try:
            while True:
                await websocket.send_json({
                    "type": "telemetry",
                    "stocks": [{"symbol": k, "price": v["price"]} for k, v in latest_market_data.items()],
                    "stats": {"uptime": "LIVE", "load": psutil.cpu_percent(), "commands": command_count},
                    "portfolio": latest_portfolio
                })
                await asyncio.sleep(1)
        except: pass

    asyncio.create_task(broadcaster())

    try:
        while True:
            data = await websocket.receive_json()
            command_count += 1
            reply = await ask_ollama(data.get("message", ""))
            await asyncio.to_thread(speak, reply)
            await websocket.send_json({"type": "answer", "text": reply})
    except: pass

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
