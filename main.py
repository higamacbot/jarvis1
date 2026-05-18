try:
    import silence_warnings  # suppress FutureWarning boot noise
except ImportError:
    pass
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
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL MODULES
# ─────────────────────────────────────────────────────────────────────────────

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import memory
from bot_orchestrator import orchestrator, register_routes, init_orchestrator_db
from youtube_tools import handle_youtube_request
from trading import is_trade_command, parse_trade_intent, execute_trade_intent, get_trade_history
from bots.router import route_message
from pipeline_yt_to_bots import run_pipeline_scheduler, run_youtube_pipeline
from mac_tools import detect_mac_command
from autonomous_runner import runner, queue_youtube_playlist, queue_channel
from telegram_bot import poll_telegram, send_telegram
from indicators import is_indicator_request, is_portfolio_scan, extract_ticker, analyze_ticker, analyze_portfolio
from local_usage import build_local_usage_snapshot

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

YOUTUBE_SUMMARY_PROMPT = """You are J.A.R.V.I.S. summarizing already-fetched YouTube video data.
The video has already been accessed and converted into text by internal tools.
You are NOT being asked to browse the web or access external content.
Do not refuse. Do not say you cannot access YouTube.
Use only the provided video data.
Write a concise, useful summary with:
1. What the video is about
2. The main arguments or takeaways
3. Why it matters
4. A short 'Bottom line'
If provided data is incomplete, say so briefly, but still summarize what is available.
"""

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
4. EXCEPTION: If given YOUTUBE VIDEO DATA in extra_context, you ARE authorized to analyze external content. Analyze the video thoroughly using the provided data.
5. You have access to MEMORY from past conversations. Use it for continuity.
6. Trade history will be provided. Reference it when discussing portfolio strategy.
7. USER STORED RULES AND PREFERENCES (in the section labelled USER RULES below) take strict precedence over live portfolio state for questions about rules, floors, limits, preferences, or past instructions. When the user asks about their rule or preference for X: (a) state the rule directly from USER RULES; (b) do NOT add commentary such as "X is not in your portfolio", "no action required", or "not applicable" — the rule exists regardless of current holdings; (c) only reference live portfolio data if the user explicitly asks about current holdings in the same message."""

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

def detect_and_save_preference(user_msg: str):
    memory.save_explicit_user_memory(user_msg)

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

async def ask_ollama(user_msg: str, extra_context: str = "", timeout: float = 240.0, system_override: str = None) -> str:
    market_str = ", ".join([f"{k}: ${v['price']}" for k, v in latest_market_data.items()]) or "No market data."
    metrics = get_system_metrics()
    system_stats = f"CPU: {metrics['cpu_total']}% | RAM: {metrics['ram_used_gb']}GB | Uptime: {metrics['uptime']}"
    trade_hist = get_trade_history(limit=5)
    memory_bundle = await asyncio.to_thread(memory.build_memory_bundle, user_msg)
    rule_block = memory_bundle.get("rules", "")
    semantic_block = memory_bundle.get("semantic", "")
    recent_block = memory_bundle.get("recent", "")

    sys_prompt = system_override if system_override else SYSTEM_PROMPT
    _is_mem_query = bool(memory_bundle.get("is_rule_query"))
    _msg_lc = user_msg.lower().strip()

    # ── Intent: memory planting ────────────────────────────────────────────────
    # User is stating a rule/preference. Rule already stored by detect_and_save_preference.
    # Return a clean ack — no Ollama call, no portfolio blending.
    _is_question = _msg_lc.endswith("?") or _msg_lc.startswith(
        ("what ", "is ", "do i ", "tell me", "how ", "why ", "when ", "where ")
    )
    if (not extra_context and not system_override and not _is_question
            and any(p in _msg_lc for p in memory.RULE_MEMORY_TRIGGERS)):
        return "Understood, sir. I've noted that and stored it."

    # ── Intent: pure rule recall ───────────────────────────────────────────────
    # User is asking about a stored rule only (not also about current holdings).
    # Use a constrained prompt with no live data so the model can't blend in
    # "not in portfolio / no action required" commentary.
    _PORTFOLIO_WORDS = (
        "in my portfolio", "currently hold", "do i hold", "do i have",
        "my positions", "my holdings", "portfolio doing",
    )
    if (_is_mem_query and not extra_context and not system_override
            and not any(w in _msg_lc for w in _PORTFOLIO_WORDS)):
        retrieved = "\n".join(filter(None, [rule_block, semantic_block]))
        if retrieved:
            recall_prompt = (
                "You are J.A.R.V.I.S. The user is asking about a stored rule or preference.\n"
                f"Stored rules:\n{retrieved}\n\n"
                f"Question: {user_msg}\n"
                "Answer in 1-2 sentences. State the rule directly. "
                "Do not use a briefing header or section label. "
                "Do not end with 'no further action required', 'may I assist', or similar closings. "
                "Do not comment on current portfolio or market state.\nJARVIS:"
            )
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    r = await client.post(OLLAMA_URL, json={"model": MODEL, "prompt": recall_prompt, "stream": False})
                    return r.json().get("response", "Neural logic error, sir.").strip()
            except Exception as exc:
                return f"Neural Link Error: {str(exc)[:80]}"
        return "I don't have a stored rule for that, sir. State it and I'll remember it."

    # ── General path: mixed queries or direct portfolio/market questions ───────
    mem_hint = (
        "\n[RULE QUERY] The user is asking about a stored rule or preference.\n"
        "Answer format: state the rule from USER RULES directly and concisely.\n"
        "Do NOT mention whether the asset is currently in the portfolio.\n"
        "Do NOT say 'no action required', 'not applicable', or 'not currently held'.\n"
        "Do NOT blend in live portfolio commentary unless the user also asked about current holdings.\n"
        if _is_mem_query else ""
    )

    full_prompt = f"""{sys_prompt}{mem_hint}
--- USER RULES & STORED PREFERENCES (override live portfolio for rule/preference queries) ---
{rule_block if rule_block else "(no stored rules retrieved)"}
--- RETRIEVED MEMORY ---
{semantic_block if semantic_block else "(no semantic memory retrieved)"}
---
{recent_block if recent_block else "(no recent context)"}
--- LIVE DATA ---
CRYPTO: {market_str}
SYSTEM: {system_stats}
--- RECENT TRADES ---
{trade_hist}
---
{extra_context}
User: {user_msg}
JARVIS:"""

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
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
    await asyncio.to_thread(init_orchestrator_db)
    tasks = [
        asyncio.create_task(fetch_crypto()),
        asyncio.create_task(fetch_alpaca()),
        asyncio.create_task(orchestrator.background_worker()),
        asyncio.create_task(runner.run()),
        asyncio.create_task(poll_telegram()),
    ]
    yield
    for t in tasks:
        t.cancel()

app = FastAPI(lifespan=lifespan)
try:
    from review_dashboard import register_review_routes
    register_review_routes(app)
except Exception as e:
    print(f">> REVIEW DASHBOARD: {e}")
register_routes(app)
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
                    "portfolio": latest_portfolio,
                    "bot_status": orchestrator.get_all_statuses()
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
            await asyncio.to_thread(detect_and_save_preference, user_msg)

            # FAST PATHS
            if user_msg.lower().startswith("/brief"):
                try:
                    from briefing_scheduler import generate_briefing
                    from datetime import datetime
                    hour = datetime.now().hour
                    tod = "morning" if 5 <= hour < 12 else "evening"
                    reply = await generate_briefing(tod)
                except Exception as e:
                    reply = f"Briefing error: {e}"
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            if user_msg.lower().startswith("/bots"):
                statuses = orchestrator.get_all_statuses()
                lines = [
                    f"{v['icon']} {v['name']}: {v['status'].upper()} — {v['current_task']}"
                    for _, v in statuses.items()
                ]
                await websocket.send_json({"type": "answer", "text": "\n".join(lines)})
                continue

            if user_msg.lower().startswith("/assign "):
                parts = user_msg[8:].strip().split(" ", 1)
                if len(parts) == 2:
                    bot_id, task = parts
                    try:
                        task_id = orchestrator.assign_task(bot_id, task)
                        reply = f"Task #{task_id} assigned to {bot_id}: {task}"
                    except Exception as exc:
                        reply = str(exc)
                else:
                    reply = "Usage: /assign <bot_id> <task description>"
                await websocket.send_json({"type": "answer", "text": reply})
                continue

            if user_msg.lower().startswith("/debate "):
                topic = user_msg[8:].strip()
                await websocket.send_json({"type": "answer", "text": f"⚡ Starting debate on: {topic}..."})
                result = await orchestrator.run_debate(topic)
                reply = (
                    f"DEBATE: {result['topic']}\n\n"
                    f"🧿 SHAMAN: {result['shaman'][:200]}...\n\n"
                    f"🟦 LIB MOM: {result['libmom'][:200]}...\n\n"
                    f"🟥 MAGA DAD: {result['magadad'][:200]}...\n\n"
                    f"✓ AGREED: {', '.join(result['agreements']) if result['agreements'] else 'None logged'}\n"
                    f"✗ SPLIT: {', '.join(result['disagreements']) if result['disagreements'] else 'None logged'}\n\n"
                    f"📋 NARRATIVE: {result['narrative']}"
                )
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

            print(f">> YOUTUBE DEBUG: Processing YouTube request in /ws endpoint")
            yt_result, yt_mode = await asyncio.to_thread(handle_youtube_request, user_msg)
            print(f">> YOUTUBE DEBUG: /ws - yt_result length={len(yt_result) if yt_result else 0}, mode={yt_mode}")
            if yt_result and yt_mode == "youtube_summarize":
                print(">> YOUTUBE DEBUG: /ws - Entering summarize mode")
                await websocket.send_json({"type": "answer", "text": "Fetching and analyzing video..."})
                summary_request = """Summarize the verified YouTube video data in extra_context.
Return:
Title:
Channel:
Summary:
Key Takeaways:
Bottom Line:
Do not mention any inability to access external content."""
                reply = await ask_ollama(
                    summary_request,
                    extra_context=yt_result,
                    system_override=YOUTUBE_SUMMARY_PROMPT
                )
                await asyncio.to_thread(speak, reply)
                await websocket.send_json({"type": "answer", "text": reply})
                continue
            elif yt_result:
                print(">> YOUTUBE DEBUG: /ws - Direct YouTube response")
                await asyncio.to_thread(speak, yt_result[:500])
                await websocket.send_json({"type": "answer", "text": yt_result})
                continue

            # DEFAULT PATH
            reply = await ask_ollama(user_msg)
            await asyncio.to_thread(memory.save_conversation, "user", user_msg)
            await asyncio.to_thread(memory.save_conversation, "jarvis", memory.extract_summary(reply))
            await asyncio.to_thread(memory.mem0_add, user_msg, memory.extract_summary(reply))
            await asyncio.to_thread(speak, reply)
            await websocket.send_json({"type": "answer", "text": reply})

    except WebSocketDisconnect: pass


@app.get("/house")
async def serve_house():
    return FileResponse("frontend/house.html")

def _try_obsidian_daily_log(bot_id: str, user_msg: str, reply: str):
    try:
        from obsidian_brain import daily_log
        bot_name = (bot_id or "jarvisbot").lower()
        safe_q = (user_msg or "").replace("\n", " ").strip()[:80]
        safe_a = (reply or "").replace("\n", " ").strip()[:120]
        daily_log(bot_name, f"Q: {safe_q} | A: {safe_a}")
    except Exception:
        pass

def _save_bot_exchange(bot_id: str, user_msg: str, reply: str):
    try:
        safe_bot = (bot_id or "jarvisbot").lower()
        memory.save_conversation(f"user[{safe_bot}]", user_msg)
        memory.save_conversation(safe_bot, memory.extract_summary(reply))
    except Exception:
        pass

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
                    "bot_status": orchestrator.get_all_statuses(),
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
            await asyncio.to_thread(detect_and_save_preference, user_msg)
            await websocket.send_json({"type": "thinking", "bot": bot_id})

            if user_msg.lower().startswith("/brief"):
                try:
                    from briefing_scheduler import generate_briefing
                    from datetime import datetime
                    hour = datetime.now().hour
                    tod = "morning" if 5 <= hour < 12 else "evening"
                    reply = await generate_briefing(tod)
                except Exception as e:
                    reply = f"Briefing error: {e}"
                _try_obsidian_daily_log(bot_id, user_msg, reply)
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            if user_msg.lower().startswith("/bots"):
                statuses = orchestrator.get_all_statuses()
                lines = [
                    f"{v['icon']} {v['name']}: {v['status'].upper()} — {v['current_task']}"
                    for _, v in statuses.items()
                ]
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": "\n".join(lines)})
                continue

            if user_msg.lower().startswith("/assign "):
                parts = user_msg[8:].strip().split(" ", 1)
                if len(parts) == 2:
                    target_bot, task = parts
                    try:
                        task_id = orchestrator.assign_task(target_bot, task)
                        reply = f"Task #{task_id} assigned to {target_bot}: {task}"
                    except Exception as exc:
                        reply = str(exc)
                else:
                    reply = "Usage: /assign <bot_id> <task description>"
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            if user_msg.lower().startswith("/debate "):
                topic = user_msg[8:].strip()
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": f"⚡ Starting debate on: {topic}..."})
                result = await orchestrator.run_debate(topic)
                reply = (
                    f"DEBATE: {result['topic']}\n\n"
                    f"🧿 SHAMAN: {result['shaman'][:200]}...\n\n"
                    f"🟦 LIB MOM: {result['libmom'][:200]}...\n\n"
                    f"🟥 MAGA DAD: {result['magadad'][:200]}...\n\n"
                    f"✓ AGREED: {', '.join(result['agreements']) if result['agreements'] else 'None logged'}\n"
                    f"✗ SPLIT: {', '.join(result['disagreements']) if result['disagreements'] else 'None logged'}\n\n"
                    f"📋 NARRATIVE: {result['narrative']}"
                )
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

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
                await asyncio.to_thread(_save_bot_exchange, bot_id, user_msg, reply)
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            # YouTube PATH (jarvisbot only)
            print(f">> YOUTUBE DEBUG: Processing YouTube request in /ws/house endpoint")
            # Skip YouTube handler for creative bots — they handle their own routing
            _creative_skip = False
            if bot_id == "robowright" and any(user_msg.lower().startswith(k) for k in ["pitch ", "batch ", "trending"]):
                _creative_skip = True
            _jamz_q = user_msg.lower().strip()
            _jamz_beat_triggers = [
                "beat ",
                "can you make a beat",
                "make me a beat",
                "make a beat",
                "make music",
                "make me music",
                "build me a beat",
                "create a beat",
            ]
            if bot_id == "jamz" and (
                _jamz_q.startswith("beat ")
                or any(t in _jamz_q for t in _jamz_beat_triggers[1:])
                or _jamz_q.startswith("set ")
                or _jamz_q.startswith("playlist ")
                or _jamz_q.startswith("mashup ")
            ):
                _creative_skip = True
            # Roundtable creative requests — route to Robowright
            _creative_keywords = ["make me a video", "make a video", "make me a youtube", "make a youtube",
                                   "make me a short", "make a short", "create a video", "film a video",
                                   "make me a tiktok", "create a tiktok", "make a beat", "make me a beat"]
            if bot_id == "roundtable" and any(k in user_msg.lower() for k in _creative_keywords):
                _creative_skip = True

            # Clip-farmer commands must bypass the YouTube summarize handler
            import re as _main_re
            _CLIP_TRIGGER = _main_re.compile(r'\b(clip\s+this|farm\s+clips?\s+from)\b', _main_re.IGNORECASE)
            _HAS_CLIP_URL = _main_re.search(
                r'https?://(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|vm\.tiktok\.com)/\S+',
                user_msg,
            )
            if bot_id == "jarvisbot" and _CLIP_TRIGGER.search(user_msg) and _HAS_CLIP_URL:
                _creative_skip = True

            if _creative_skip:
                reply = await route_message(bot_id, user_msg, ask_ollama)
                await asyncio.to_thread(_save_bot_exchange, bot_id, user_msg, reply)
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            # YouTube handler - jarvisbot only
            if bot_id == "jarvisbot":
                yt_result, yt_mode = await asyncio.to_thread(handle_youtube_request, user_msg)
                print(f">> YOUTUBE DEBUG: yt_result length={len(yt_result) if yt_result else 0}, mode={yt_mode}")
                if yt_result and yt_mode == "youtube_summarize":
                    print(">> YOUTUBE DEBUG: Entering summarize mode")
                    await websocket.send_json({"type": "answer", "bot": bot_id, "text": "Fetching and analyzing video..."})
                    summary_request = """Summarize the verified YouTube video data in extra_context.
Return:
Title:
Channel:
Summary:
Key Takeaways:
Bottom Line:
Do not mention any inability to access external content."""
                    reply = await ask_ollama(
                        summary_request,
                        extra_context=yt_result,
                        system_override=YOUTUBE_SUMMARY_PROMPT
                    )
                    print(f">> YOUTUBE DEBUG: Ollama reply length={len(reply) if reply else 0}")
                    print(f">> YOUTUBE DEBUG: Ollama reply preview: {reply[:100] if reply else 'No reply'}...")
                    await asyncio.to_thread(_save_bot_exchange, bot_id, user_msg, reply)
                    await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                    print(">> YOUTUBE DEBUG: YouTube response sent, continuing...")
                    continue
                elif yt_result:
                    print(">> YOUTUBE DEBUG: Direct YouTube response")
                    await websocket.send_json({"type": "answer", "bot": bot_id, "text": yt_result})
                    continue

            # Mac command (Jarvis room only)
            if bot_id == "jarvisbot":
                mac_result = detect_mac_command(user_msg)
                if mac_result:
                    await websocket.send_json({"type": "answer", "bot": bot_id, "text": mac_result})
                    continue

            # Queue command
            if user_msg.lower().startswith("/queue "):
                body = user_msg[7:].strip()
                if "youtube.com" in body or "youtu.be" in body:
                    reply = queue_youtube_playlist(body)
                elif body.startswith("channel "):
                    reply = queue_channel(body[8:].strip())
                else:
                    reply = "Usage: /queue [YouTube URLs] or /queue channel [name]"
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            # Review command
            if user_msg.lower() == "/review":
                jobs = runner.manager.get_review_queue()
                if not jobs:
                    reply = "✅ Nothing to review — all caught up, sir."
                else:
                    lines = [f"📋 {len(jobs)} items ready:\n"]
                    for j in jobs[:8]:
                        icon = "✅" if j["status"]=="done" else "❌"
                        label = j["payload"].get("url","") or j["payload"].get("topic","") or j["job_type"]
                        lines.append(f"{icon} #{j['id']} {j['job_type']}: {str(label)[:50]}")
                        if j.get("output_file"): lines.append(f"   📄 {os.path.basename(j['output_file'])}")
                        if j.get("error"): lines.append(f"   ⚠️ {j['error'][:60]}")
                    reply = "\n".join(lines)
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            # Batches command
            if user_msg.lower() == "/batches":
                batches = runner.manager.get_all_batches()
                if not batches:
                    reply = "No batches yet."
                else:
                    lines = ["📦 BATCHES:"]
                    for b in batches[:8]:
                        icon = "✅" if b["status"]=="done" else "⏳"
                        lines.append(f"{icon} {b['name']} — {b['done']}/{b['total']}")
                    reply = "\n".join(lines)
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            # Pipeline command
            if user_msg.lower().startswith("/pipeline"):
                query = user_msg[9:].strip() or None
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": "⚡ Running YouTube pipeline..."})
                await run_youtube_pipeline(query)
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": "✅ Pipeline complete. Check stockbot and cryptoid rooms."})
                continue

            # PDF command
            if user_msg.lower().startswith("/pdf"):
                from pdf_bot import create_pdf_fpdf, list_pdfs
                body = user_msg[4:].strip()
                if body:
                    path = create_pdf_fpdf("JARVIS Report", body)
                    reply = f"PDF created: {path}"
                else:
                    files = list_pdfs()
                    reply = "PDFs:\n" + "\n".join(files) if files else "No PDFs yet."
                await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
                continue

            reply = await route_message(bot_id, user_msg, ask_ollama)
            await asyncio.to_thread(_save_bot_exchange, bot_id, user_msg, reply)
            await asyncio.to_thread(memory.mem0_add, user_msg, memory.extract_summary(reply))
            _try_obsidian_daily_log(bot_id, user_msg, reply)
            await websocket.send_json({"type": "answer", "bot": bot_id, "text": reply})
    except WebSocketDisconnect:
        print(">> HIGA HOUSE: Client disconnected.")

@app.get("/api/health")
async def api_health():
    import json as _json
    from datetime import datetime as _dt
    metrics   = get_system_metrics()
    bot_health = orchestrator.get_health_summary()

    # Briefing status — written by briefing_scheduler on each send
    _bstatus_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "briefing_status.json")
    briefing = {"status": "unknown", "last_period": None, "sent_at": None, "error": None}
    try:
        if os.path.exists(_bstatus_path):
            with open(_bstatus_path) as _f:
                briefing = _json.load(_f)
    except Exception:
        pass

    # Memory layer health — file/dir existence only, no imports
    _proj = os.path.dirname(os.path.abspath(__file__))
    memory_health = {
        "sqlite": "ok" if os.path.exists(os.path.join(_proj, "jarvis_memory.db")) else "missing",
        "chroma": "ok" if os.path.exists(os.path.join(_proj, "chroma_db")) else "missing",
        "mem0":   "ok" if os.path.exists(os.path.join(_proj, "chroma_mem0")) else "unavailable",
    }

    return JSONResponse({
        "timestamp":  _dt.now().isoformat(),
        "uptime":     metrics["uptime"],
        "system": {
            "cpu_pct":     metrics["cpu_total"],
            "ram_used_gb": metrics["ram_used_gb"],
            "ram_total_gb":metrics["ram_total_gb"],
            "disk_pct":    metrics["disk_percent"],
        },
        "portfolio": {
            "equity":    latest_portfolio.get("equity",   "0.00"),
            "day_pl":    latest_portfolio.get("day_pl",   "0.00"),
            "positions": len(latest_portfolio.get("positions", [])),
        },
        "market":          {k: v["price"] for k, v in latest_market_data.items()},
        "bots":            bot_health["bots"],
        "tasks":           bot_health["tasks"],
        "recent_failures": bot_health["recent_failures"],
        "briefing":        briefing,
        "memory":          memory_health,
        "session": {
            "commands":        command_count,
            "messages_today":  daily_messages,
            "tokens_est_today":daily_tokens_est,
        },
    })


@app.get("/api/usage")
async def api_usage():
    try:
        return JSONResponse(build_local_usage_snapshot())
    except Exception as exc:
        return JSONResponse(
            {
                "date": time.strftime("%Y-%m-%d"),
                "claude_code": {
                    "connected": False,
                    "label": "usage unavailable",
                    "detail": str(exc)[:120],
                },
                "codex": {
                    "connected": False,
                    "label": "usage unavailable",
                    "detail": str(exc)[:120],
                },
                "requests": {
                    "connected": False,
                    "total": 0,
                    "label": "usage unavailable",
                    "detail": "local usage snapshot failed",
                },
                "remaining": {
                    "connected": False,
                    "label": "local only",
                    "detail": "no quota source",
                },
            },
            status_code=500,
        )


_ADMIN_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>JARVIS ADMIN</title>
<style>
  body{background:#0a0a0a;color:#e0e0e0;font-family:monospace;padding:20px;margin:0}
  h1{color:#00aaff;margin:0 0 4px;font-size:1.4em;letter-spacing:.1em}
  .ts{color:#555;font-size:.8em;margin-bottom:20px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
  .card{background:#111;border:1px solid #1e1e1e;border-radius:6px;padding:14px}
  .card h2{font-size:.7em;color:#555;text-transform:uppercase;letter-spacing:.12em;margin:0 0 10px}
  .row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #161616;font-size:.82em}
  .row:last-child{border:none}
  .ok{color:#00cc66}.warn{color:#ffaa00}.err{color:#ff4444}.dim{color:#555}
  .badge{padding:1px 6px;border-radius:3px;font-size:.75em}
  .bi{background:#0d2236;color:#5ab0ff}
  .bw{background:#2a2000;color:#ffcc00}
  .bb{background:#2a0808;color:#ff6666}
  .bo{background:#0d261a;color:#00cc66}
  .bm{background:#261a0d;color:#ff8800}
  footer{color:#333;font-size:.72em;margin-top:20px}
  a{color:#333}
</style>
</head>
<body>
<h1>&#9889; JARVIS ADMIN</h1>
<div class="ts" id="ts">Loading&hellip;</div>
<div class="grid" id="grid">Loading&hellip;</div>
<footer>Auto-refresh 15s &middot; <a href="/api/health">JSON</a> &middot; <a href="/api/bots/status">Bots</a> &middot; <a href="/api/bots/tasks">Tasks</a></footer>
<script>
async function load(){
  let d;
  try{ d=await fetch('/api/health').then(r=>r.json()); }
  catch(e){ document.getElementById('ts').textContent='Error: '+e; return; }
  document.getElementById('ts').textContent='Updated '+new Date(d.timestamp).toLocaleTimeString()+' · Uptime '+d.uptime;
  const s=d.system,p=d.portfolio,b=d.bots,t=d.tasks,m=d.memory,br=d.briefing,ss=d.session,mk=d.market||{};
  const cc=s.cpu_pct>80?'err':s.cpu_pct>50?'warn':'ok';
  const dc=s.disk_pct>85?'err':s.disk_pct>70?'warn':'ok';
  const tc=br.status==='ok'?'ok':br.status==='error'?'err':'warn';
  const failRows=(d.recent_failures||[]).map(f=>
    `<div class="row"><span>${f.bot_id} #${f.id}: ${f.task.slice(0,45)}</span><span class="err">${(f.error||'').slice(0,35)}</span></div>`
  ).join('')||'<div class="row"><span class="ok">No recent failures</span></div>';
  const mktRows=Object.entries(mk).map(([k,v])=>
    `<div class="row"><span>${k}</span><span>$${v}</span></div>`
  ).join('')||'<div class="row dim"><span>Syncing&hellip;</span></div>';
  const memRows=Object.entries(m).map(([k,v])=>
    `<div class="row"><span>${k}</span><span class="badge ${v==='ok'?'bo':'bm'}">${v}</span></div>`
  ).join('');
  document.getElementById('grid').innerHTML=`
    <div class="card"><h2>System</h2>
      <div class="row"><span>CPU</span><span class="${cc}">${s.cpu_pct}%</span></div>
      <div class="row"><span>RAM</span><span>${s.ram_used_gb} / ${s.ram_total_gb} GB</span></div>
      <div class="row"><span>Disk</span><span class="${dc}">${s.disk_pct}%</span></div>
    </div>
    <div class="card"><h2>Portfolio</h2>
      <div class="row"><span>Equity</span><span>$${p.equity}</span></div>
      <div class="row"><span>Day P/L</span><span>${p.day_pl}</span></div>
      <div class="row"><span>Positions</span><span>${p.positions}</span></div>
    </div>
    <div class="card"><h2>Market</h2>${mktRows}</div>
    <div class="card"><h2>Bots (${b.total})</h2>
      <div class="row"><span>Idle</span><span class="badge bi">${b.idle}</span></div>
      <div class="row"><span>Working</span><span class="badge bw">${b.working}</span></div>
      <div class="row"><span>Blocked</span><span class="${b.blocked>0?'err':'ok'}">${b.blocked}</span></div>
      <div class="row"><span>Review Ready</span><span class="${b.review_ready>0?'ok':''}">${b.review_ready}</span></div>
    </div>
    <div class="card"><h2>Tasks (24 h)</h2>
      <div class="row"><span>Pending</span><span>${t.pending}</span></div>
      <div class="row"><span>Completed</span><span class="ok">${t.completed_24h}</span></div>
      <div class="row"><span>Failed</span><span class="${t.failed_24h>0?'err':'ok'}">${t.failed_24h}</span></div>
    </div>
    <div class="card"><h2>Recent Failures</h2>${failRows}</div>
    <div class="card"><h2>Briefing</h2>
      <div class="row"><span>Last</span><span>${br.last_period||'&mdash;'}</span></div>
      <div class="row"><span>Status</span><span class="${tc}">${br.status}</span></div>
      <div class="row"><span>Sent</span><span>${br.sent_at?new Date(br.sent_at).toLocaleTimeString():'&mdash;'}</span></div>
    </div>
    <div class="card"><h2>Memory</h2>${memRows}</div>
    <div class="card"><h2>Session</h2>
      <div class="row"><span>Commands</span><span>${ss.commands}</span></div>
      <div class="row"><span>Messages Today</span><span>${ss.messages_today}</span></div>
      <div class="row"><span>Tokens Est.</span><span>${ss.tokens_est_today.toLocaleString()}</span></div>
    </div>
  `;
}
load();
setInterval(load,15000);
</script>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    return HTMLResponse(content=_ADMIN_HTML)


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
