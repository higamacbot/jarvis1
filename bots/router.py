"""
Clean router with proper imports and error handling
"""

from bots import stockbot
import sys
sys.path.insert(0, "/Users/higabot1/jarvis1-1")
try:
    from bot_memory import save_bot_memory, extract_durable_takeaway, get_bot_memory_summary
    BOT_MEMORY_AVAILABLE = True
except Exception:
    BOT_MEMORY_AVAILABLE = False
    def save_bot_memory(*a, **k): pass
    def extract_durable_takeaway(*a, **k): return ""
    def get_bot_memory_summary(*a, **k): return ""
from bots import cryptoid
from bots import doctorbot
from bots import ultron
from bots import robowright
from bots import jamz
from bots import higashop
from bots import technoid
from bots import teacherbot
from bots import pinkslip
from bots import jarvisbot

BOT_MAP = {
    "stockbot": stockbot,
    "cryptoid": cryptoid,
    "doctorbot": doctorbot,
    "ultron": ultron,
    "robowright": robowright,
    "jamz": jamz,
    "higashop": higashop,
    "technoid": technoid,
    "teacherbot": teacherbot,
    "debateroom":  teacherbot,  # placeholder — overridden by debate handler above
    "pinkslip": pinkslip,
    "jarvisbot": jarvisbot,
}

ROUND_ORDER = [
    "JARVIS",
    "STOCKBOT",
    "CRYPTOID",
    "PINKSLIP",
    "DOCTORBOT",
    "ULTRON",
    "ROBOWRIGHT",
    "JAMZ",
    "HIGASHOP",
    "TECHNOID",
    "TEACHERBOT",
    "DEBATE ROOM",
]


def build_generic_roundtable_update(stock_context: str, crypto_total: float, crypto_lines: str) -> str:
    """Build deterministic roundtable update from live data — no Ollama needed."""
    import re
    equity = "Unavailable"
    buying_power = "Unavailable"
    m = re.search(r"Equity[:\s]+\$?([0-9,]+(?:\.\d+)?)", stock_context or "")
    if m:
        equity = "$" + m.group(1)
    m2 = re.search(r"Buying Power[:\s]+\$?([0-9,]+(?:\.\d+)?)", stock_context or "")
    if m2:
        buying_power = "$" + m2.group(1)
    stock_lines = [l.strip() for l in (stock_context or "").splitlines()
                   if ": $" in l and ("P/L:" in l or "(+" in l or "(-" in l)]
    stock_summary = " | ".join(stock_lines[:3]) if stock_lines else "No update."
    crypto_assets = [l.strip() for l in (crypto_lines or "").splitlines() if l.strip()]
    crypto_summary = (f"Total ${crypto_total:.2f} — " + " | ".join(crypto_assets[:4])) if crypto_assets else "No update."
    return "\n".join([
        f"JARVIS: House online. Alpaca equity {equity}, buying power {buying_power}. All systems nominal.",
        f"STOCKBOT: {stock_summary}",
        f"CRYPTOID: {crypto_summary}",
        "PINKSLIP: No update.",
        "DOCTORBOT: Backend, API, and WebSocket online. No critical errors detected.",
        "ULTRON: No update.",
        "ROBOWRIGHT: No update.",
        "JAMZ: No update.",
        "HIGASHOP: No update.",
        "TECHNOID: System responsive and healthy.",
        "TEACHERBOT: No update.",
        "DEBATE ROOM:",
        "- SHAMAN says: No update.",
        "- LIB MOM says: No update.",
        "- MAGA DAD says: No update.",
    ])

def normalize_roundtable_output(text: str) -> str:
    import re

    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    sections = {}

    current = None
    for line in lines:
        matched = False
        for label in ROUND_ORDER:
            if line.upper().startswith(label + ":"):
                sections[label] = line.split(":", 1)[1].strip() or "No update."
                current = label
                matched = True
                break
        if matched:
            continue

        if line.startswith("- SHAMAN says:") or line.startswith("- LIB MOM says:") or line.startswith("- MAGA DAD says:"):
            current = "DEBATE ROOM"
            sections.setdefault("DEBATE ROOM", [])
            sections["DEBATE ROOM"].append(line)
            continue

        if current == "DEBATE ROOM" and line.startswith("- "):
            sections.setdefault("DEBATE ROOM", [])
            sections["DEBATE ROOM"].append(line)
            continue

    fixed = []
    for label in ROUND_ORDER:
        if label == "DEBATE ROOM":
            debate = sections.get("DEBATE ROOM")
            if isinstance(debate, list) and debate:
                fixed.append("DEBATE ROOM:")
                fixed.extend(debate)
            else:
                fixed.append("DEBATE ROOM:")
                fixed.append("- SHAMAN says: No update.")
                fixed.append("- LIB MOM says: No update.")
                fixed.append("- MAGA DAD says: No update.")
        else:
            fixed.append(f"{label}: {sections.get(label, 'No update.')}")
    return "\n".join(fixed)

ROUNDTABLE_PROMPT = """You are HIGA HOUSE roundtable mode.
You are NOT one assistant writing one summary.
You are simulating eleven distinct agents speaking in sequence.

Hard rules:
- Return ONLY plain text.
- No markdown bold, no bullet summary preamble, no 'Update Summary', no closing question, no emojis.
- Do NOT merge agents together.
- Do NOT speak as a generic narrator.
- Never output labels like Agent 1, Agent 2, Agent 3, or Agent 4.
- Every agent must appear, in the exact order below.
- If an agent has nothing meaningful to report, that agent says exactly: No update.
- Use only the live data and context provided. Do not invent trades, positions, motives, narratives, or reasons.
- Keep each agent to 1-3 sentences unless there is a genuinely important update.
- For generic update requests like "what's the update", "update", "status", "what's new", or "brief me":
  only discuss current portfolio, bots, system health, content pipeline, and real operational status.
- For those generic update requests, do NOT discuss conspiracies, hidden hands, geopolitics, Sanhedrin, Temple Mount, Great Reset, storm, awakening, or any prior debate topic unless the user explicitly asks for that topic.
- JARVIS sounds like a chief of staff.
- STOCKBOT sounds like a direct market strategist.
- CRYPTOID sounds like a crypto analyst.
- PINKSLIP sounds like a betting/risk analyst.
- DOCTORBOT sounds like a codebase and systems reviewer.
- ULTRON sounds like a security sentinel.
- ROBOWRIGHT sounds like a content strategist.
- JAMZ sounds like a producer/DJ.
- HIGASHOP sounds like an operator finding products/opportunities.
- TECHNOID sounds like a hardware and performance tech.
- TEACHERBOT sounds like an educator.
- DEBATE ROOM is brief and includes all 3 sub-voices.

Return EXACTLY this structure and nothing else:

JARVIS: ...
STOCKBOT: ...
CRYPTOID: ...
PINKSLIP: ...
DOCTORBOT: ...
ULTRON: ...
ROBOWRIGHT: ...
JAMZ: ...
HIGASHOP: ...
TECHNOID: ...
TEACHERBOT: ...
DEBATE ROOM:
- SHAMAN says: ...
- LIB MOM says: ...
- MAGA DAD says: ..."""

async def route_message(bot_id: str, user_msg: str, ask_fn) -> str:
    print(f">> ROUTER DEBUG: bot_id = '{bot_id}'")
    
    # Roundtable creative requests — hand off to Robowright
    if bot_id == "roundtable":
        q = user_msg.lower().strip()
        creative_triggers = ["make me a video", "make a video", "make me a youtube",
                             "make a youtube", "make me a short", "make a short",
                             "create a video", "make me a tiktok", "create a tiktok"]
        if any(t in q for t in creative_triggers):
            topic = user_msg.strip()
            from bots.robowright_media import pitch_video_concept, save_script
            from mac_tools import create_imovie_script_package
            result = await pitch_video_concept(topic)
            save_script(topic, result)
            launch_msg = create_imovie_script_package(topic, result)
            return f"ROBOWRIGHT\n{result}\n\n---\n{launch_msg}"
        beat_triggers = ["make me a beat", "make a beat", "make music", "make me music"]
        if any(t in q for t in beat_triggers):
            from bots.jamz_engine import design_beat
            from mac_tools import create_garageband_template
            result = await design_beat(user_msg)
            import re
            bpm_match = re.search(r'BPM[:\s]+(\d+)', result)
            bpm = int(bpm_match.group(1)) if bpm_match else 120
            launch_msg = create_garageband_template(user_msg, bpm)
            return f"JAMZ\n{result}\n\n---\n{launch_msg}"

    if bot_id == "roundtable":
        import httpx
        from multi_broker_portfolio import MultiBrokerPortfolio

        # Inject real portfolio data into roundtable context
        try:
            tracker = MultiBrokerPortfolio()
            all_crypto = tracker.get_all_crypto() or {}
            
            # Context-Safe Summing (Handles Dicts vs Floats correctly)
            crypto_total = 0
            for v in all_crypto.values():
                if isinstance(v, dict): crypto_total += v.get('value', 0)
                elif isinstance(v, (int, float)): crypto_total += v

            crypto_lines = "\n".join([f"  {s}: ${d.get('value',0):.2f}" for s, d in all_crypto.items() if isinstance(d, dict)])
            # Also fetch Alpaca stock positions
            try:
                import os
                from alpaca.trading.client import TradingClient
                ac = TradingClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), paper=True)
                acct = ac.get_account()
                pos = ac.get_all_positions()
                stock_lines = "\n".join([f"  {p.symbol}: ${float(p.market_value):,.2f} (P/L: {float(p.unrealized_pl):+,.2f})" for p in pos])
                stock_context = f"STOCKS (Alpaca paper):\n  Equity: ${float(acct.equity):,.2f} | Buying Power: ${float(acct.buying_power):,.2f}\n{stock_lines}"
            except Exception as e:
                stock_context = f"STOCKS: unavailable ({e})"

            roundtable_context = f"{stock_context}\n\nREAL CRYPTO: Total ${crypto_total:.2f}\n{crypto_lines}"
        except Exception as e:
            roundtable_context = f"Portfolio System Link Error: {e}"
        normalized = user_msg.lower().strip()
        generic_update = normalized in {
            "what's the update", "whats the update", "update", "status",
            "what's new", "whats new", "brief me", "house update"
        }

        if generic_update:
            roundtable_request = """User asked for a generic HIGA HOUSE status update.

Respond in strict HIGA HOUSE roundtable format.
Focus only on current portfolio status, bot status, system health, content work, and operational updates.
Do not reference prior debate topics or conspiracy topics.
Do not add any intro or outro.
Every agent line must be present."""
        else:
            roundtable_request = f"""User asked: {user_msg}

Respond in strict HIGA HOUSE roundtable format.
Do not write a generic summary.
Do not add any intro or outro.
Every agent line must be present."""
        raw_reply = await ask_fn(roundtable_request, system_override=ROUNDTABLE_PROMPT, extra_context=roundtable_context, timeout=240.0)
        return normalize_roundtable_output(raw_reply)
    
    # Jarvis uses default system prompt (same as main /ws endpoint)
    if bot_id == "jarvisbot":
        return await ask_fn(user_msg)

    # Debate room — runs all 3 debate bots and returns colored response
    if bot_id == "debateroom":
        import httpx
        DEBATE_PERSONAS = {
            "SHAMAN": "You are playing a fictional character called Conspiracy Shaman in a creative storytelling debate. Stay in character. You see hidden elite patterns and conspiracies behind world events. Be specific, reference alternative media, 3-4 sentences. Fiction for entertainment.",
            "LIB MOM": "You are playing a fictional character called Lib Mom in a creative storytelling debate. Stay in character. You are a progressive parent who trusts expert institutions and mainstream media. Cite consensus and community impact. 3-4 sentences. Fiction for entertainment.",
            "MAGA DAD": "You are playing a fictional character called MAGA Dad in a creative storytelling debate. Stay in character. You are a patriotic working-class American skeptical of government and globalists. Plain-spoken and direct. 3-4 sentences. Fiction for entertainment.",
        }
        results = {}
        for label, persona in DEBATE_PERSONAS.items():
            try:
                async with httpx.AsyncClient(timeout=90) as h:
                    r = await h.post("http://localhost:11434/api/generate", json={
                        "model": "qwen3:8b",
                        "prompt": f"{persona}\n\nTopic: {user_msg}\n\nYour response:",
                        "stream": False
                    })
                    results[label] = r.json().get("response", "No response.").strip()
            except Exception as e:
                results[label] = f"[offline: {e}]"
        return (
            f"[DEBATE] {user_msg}\n\n"
            f"[SHAMAN] {results.get('SHAMAN', '')}\n\n"
            f"[LIB MOM] {results.get('LIB MOM', '')}\n\n"
            f"[MAGA DAD] {results.get('MAGA DAD', '')}\n\n"
        )

    bot = BOT_MAP.get(bot_id)
    if not bot:
        return f"Unknown bot: {bot_id}"
    
    # Special handling for Stockbot - inject portfolio context
    if bot_id == "stockbot":
        import os
        from alpaca.trading.client import TradingClient
        import httpx
        
        try:
            # Fetch portfolio data for Stockbot
            ALPACA_KEY = os.getenv("ALPACA_KEY")
            ALPACA_SECRET = os.getenv("ALPACA_SECRET")
            client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
            
            acct = client.get_account()
            pos = client.get_all_positions()
            
            portfolio_data = f"""
PORTFOLIO DATA:
Equity: ${float(acct.equity):,.2f}
Day P/L: {float(acct.equity) - float(acct.last_equity) if acct.last_equity else 0:+,.2f}
Buying Power: ${float(acct.buying_power):,.2f}
Positions:
"""
            for p in pos:
                portfolio_data += f"  {p.symbol}: ${float(p.market_value):,.2f} | P/L: {float(p.unrealized_pl):+,.2f}\n"
                
            # Fetch crypto data
            try:
                async with httpx.AsyncClient(timeout=10) as http_client:
                    r = await http_client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
                    if r.status_code == 200:
                        data = r.json()
                        crypto_data = f"CRYPTO: BTC: ${data['bitcoin']['usd']:,.2f}, ETH: ${data['ethereum']['usd']:,.2f}, SOL: ${data['solana']['usd']:,.2f}"
                        portfolio_data += f"\n{crypto_data}"
            except:
                portfolio_data += "\nCRYPTO: Data unavailable"
                
            memory_context = get_bot_memory_summary("stockbot", user_msg)
            if memory_context:
                portfolio_data += f"\n\n{memory_context}"
            reply = await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=portfolio_data)
            takeaway = extract_durable_takeaway(user_msg, reply)
            if takeaway:
                save_bot_memory("stockbot", takeaway)
            return reply
                    
        except Exception as e:
            error_context = f"PORTFOLIO ERROR: {e}"
            return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=error_context)
         
    # Special handling for Cryptoid - inject complete crypto portfolio context
    if bot_id == "cryptoid":
        print(">> CRYPTOID ROUTER: Executing crypto portfolio injection...")
        import os
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from multi_broker_portfolio import MultiBrokerPortfolio
        import httpx
        
        try:
            # Fetch complete crypto portfolio data
            portfolio_tracker = MultiBrokerPortfolio()
            all_crypto = portfolio_tracker.get_all_crypto()
            
            # Build crypto portfolio context
            crypto_data = f"""
OWNED CRYPTO PORTFOLIO DATA:
Total Owned Crypto Value: ${sum(c['value'] for c in all_crypto.values()):,.2f}

IMPORTANT RULES:
- Use only the owned values shown below for position size.
- Never infer or mention coin quantities unless explicitly provided.
- Never multiply live market prices by guessed holdings.
- Keep live market prices separate from owned portfolio values.
- If a value is missing, say it is unavailable.

Owned Positions by Broker:
"""
            for symbol, data in all_crypto.items():
                pl_info = f"P/L: ${data.get('pl', 0):+,.2f}" if data.get('pl') is not None else "P/L: N/A"
                crypto_data += f"  {symbol}: ${data['value']:,.2f} | {pl_info} | Broker: {data.get('broker', 'unknown')}\n"
                
            # Add broker breakdown
            portfolio_data = portfolio_tracker.portfolio_data
            webull_crypto = sum(v['value'] for v in portfolio_data['webull']['crypto'].values()) if 'crypto' in portfolio_data['webull'] else 0
            coinbase_total = portfolio_data['coinbase']['total_value']
            kraken_equity = portfolio_data['paper_trading']['kraken']['equity']
            crypto_data += f"""
Broker Breakdown:
- Webull Crypto: ${webull_crypto:.2f}
- Coinbase Crypto: ${coinbase_total:.2f}
- Kraken Paper: ${kraken_equity:.2f}
"""
                
            # Fetch live crypto prices
            try:
                async with httpx.AsyncClient(timeout=10) as http_client:
                    r = await http_client.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd")
                    if r.status_code == 200:
                        data = r.json()
                        market_data = (
                            f"REFERENCE LIVE MARKET PRICES ONLY (not owned position values): "
                            f"BTC: ${data['bitcoin']['usd']:,.2f}, "
                            f"ETH: ${data['ethereum']['usd']:,.2f}, "
                            f"SOL: ${data['solana']['usd']:,.2f}"
                        )
                        crypto_data += f"\n{market_data}"
            except:
                crypto_data += "\nREFERENCE LIVE MARKET PRICES ONLY: Data unavailable"
                
            print(">> CRYPTOID ROUTER: Successfully built crypto context")
            memory_context = get_bot_memory_summary("cryptoid", user_msg)
            if memory_context:
                crypto_data += f"\n\n{memory_context}"
            reply = await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=crypto_data)
            takeaway = extract_durable_takeaway(user_msg, reply)
            if takeaway:
                save_bot_memory("cryptoid", takeaway)
            return reply
            
        except Exception as e:
            print(f">> CRYPTOID ROUTER ERROR: {e}")
            error_context = f"CRYPTO PORTFOLIO ERROR: {e}"
            return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, extra_context=error_context)
    
    # Doctorbot — code intelligence commands
    if bot_id == "doctorbot":
        q = user_msg.lower().strip()
        if q == "find bugs" or q == "scan":
            from bots.doctorbot import scan_for_bugs
            return scan_for_bugs()
        elif q == "scan imports":
            from bots.doctorbot import scan_imports
            return scan_imports()
        elif q.startswith("review "):
            filename = user_msg[7:].strip()
            from bots.doctorbot import review_file
            return await review_file(filename)
        elif q.startswith("brainstorm "):
            topic = user_msg[11:].strip()
            from bots.doctorbot import brainstorm
            return await brainstorm(topic)
        elif q == "repo health":
            from bots.doctorbot import repo_health
            return repo_health()
        elif q.startswith("draft improvement "):
            filename = user_msg[18:].strip()
            from bots.doctorbot import draft_improvement
            return await draft_improvement(filename)
        elif q.startswith("draft feature "):
            desc = user_msg[14:].strip()
            from bots.doctorbot import draft_new_feature
            return await draft_new_feature(desc)
        elif q.startswith("draft fix "):
            desc = user_msg[10:].strip()
            from bots.doctorbot import draft_bug_fix
            return await draft_bug_fix(desc)
        elif q == "draft summary":
            from bots.doctorbot import draft_session_summary
            return await draft_session_summary()
        elif q == "list drafts":
            from bots.doctorbot import list_drafts
            return list_drafts()
        elif q.startswith("cat draft "):
            import os
            fname = user_msg[10:].strip()
            path = f"/Users/higabot1/jarvis1-1/drafts/{fname}"
            if os.path.exists(path):
                with open(path) as f:
                    return f.read()
            return f"Draft not found: {fname}"
        elif q == "see and fix" or q == "fix screen":
            from doctorbot_vision import doctorbot_see_and_fix
            return await doctorbot_see_and_fix()
        elif q.startswith("see and fix ") and "push" in q:
            parts = q.replace("see and fix ", "").replace(" push", "").strip()
            from doctorbot_vision import doctorbot_see_and_fix
            return await doctorbot_see_and_fix(target_file=parts, auto_push=True)
        elif q.startswith("see and fix "):
            target = user_msg[12:].strip()
            from doctorbot_vision import doctorbot_see_and_fix
            return await doctorbot_see_and_fix(target_file=target)
        elif q in ["fix all", "scan and fix", "fix all push"]:
            auto_push = "push" in q
            from doctorbot_vision import doctorbot_scan_and_fix_all
            return await doctorbot_scan_and_fix_all(auto_push=auto_push)
        elif q.startswith("write ") or q.startswith("code "):
            prompt = user_msg.split(" ", 1)[1].strip()
            from doctorbot_vision import doctorbot_write_code
            return await doctorbot_write_code(prompt)
        elif q.startswith("apply ") and " to " in q:
            parts = q[6:].split(" to ")
            from doctorbot_vision import doctorbot_apply_draft
            return await doctorbot_apply_draft(parts[0].strip(), parts[1].strip())
        elif q == "push fix":
            from bots.doctorbot import git_commit_and_push
            return git_commit_and_push("fix: doctorbot auto-fix applied")
        elif q == "github diff":
            from doctorbot_vision import get_github_diff
            return get_github_diff()
        elif q == "screenshot":
            from doctorbot_vision import take_screenshot
            path = take_screenshot("doctorbot_manual")
            return f"Screenshot saved: {path}"

    # Robowright commands
    if bot_id == "robowright":
        q = user_msg.lower().strip()
        if q.startswith("pitch "):
            topic = user_msg[6:].strip()
            from bots.robowright_media import pitch_video_concept, save_script
            result = await pitch_video_concept(topic)
            save_script(topic, result)
            from mac_tools import create_imovie_script_package
            launch_msg = create_imovie_script_package(topic, result)
            return result + f"\n\n---\n{launch_msg}" 
        elif q.startswith("batch "):
            theme = user_msg[6:].strip()
            from bots.robowright_media import batch_content_plan
            return await batch_content_plan(theme)
        elif q.startswith("trending audio"):
            niche = user_msg[14:].strip() or "finance"
            from bots.robowright_media import find_trending_audio
            return await find_trending_audio(niche)
        elif q in ["open imovie", "imovie", "launch imovie"]:
            from mac_tools import open_imovie
            return open_imovie()
        elif q in ["open final cut", "final cut", "finalcut"]:
            from mac_tools import open_final_cut
            return open_final_cut()

    # Jamz commands
    if bot_id == "jamz":
        q = user_msg.lower().strip()
        if q.startswith("beat "):
            vibe = user_msg[5:].strip()
            from bots.jamz_engine import design_beat
            result = await design_beat(vibe)
            import re
            bpm_match = re.search(r'BPM[:\s]+(\d+)', result)
            bpm = int(bpm_match.group(1)) if bpm_match else 120
            from mac_tools import create_garageband_template
            launch_msg = create_garageband_template(vibe, bpm)
            return result + f"\n\n---\n{launch_msg}" 
        elif q.startswith("set "):
            event = user_msg[4:].strip()
            from bots.jamz_engine import plan_dj_set
            return await plan_dj_set(event)
        elif q.startswith("playlist "):
            mood = user_msg[9:].strip()
            from bots.jamz_engine import build_playlist
            return await build_playlist(mood)
        elif q.startswith("mashup "):
            parts = user_msg[7:].strip().split(" vs ")
            if len(parts) == 2:
                from bots.jamz_engine import mashup_concept
                return await mashup_concept(parts[0].strip(), parts[1].strip())
            return "Usage: mashup <track 1> vs <track 2>"
        elif q in ["open garageband", "garageband", "garage band"]:
            from mac_tools import open_garageband
            return open_garageband()
        elif q in ["open logic", "logic pro", "logic"]:
            from mac_tools import open_logic_pro
            return open_logic_pro()

    # PC Control commands — available to all bots
    q = user_msg.lower().strip()
    if q == "screenshot":
        from pc_control import jarvis_screenshot_status
        return jarvis_screenshot_status()
    if q.startswith("run "):
        from pc_control import run_command
        return run_command(user_msg[4:].strip())
    if q in ["open last project", "open project"]:
        from pc_control import robowright_open_last_project
        return robowright_open_last_project()
    if q in ["open last beat", "open beat"]:
        from pc_control import jamz_open_last_beat
        return jamz_open_last_beat()
    if q in ["health check", "run tests", "compile check"]:
        from pc_control import doctorbot_run_health_check
        return doctorbot_run_health_check()
    if q in ["git status", "repo status"]:
        from pc_control import doctorbot_git_status
        return doctorbot_git_status()

    return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT)
