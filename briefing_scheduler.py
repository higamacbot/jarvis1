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

def get_alpaca_client():
    if not ALPACA_KEY or not ALPACA_SECRET:
        return None
    return TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)

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
        acct = get_alpaca_client().get_account()
        pos  = get_alpaca_client().get_all_positions()
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


# ── Text helpers ──────────────────────────────────────────────────────────────

def _normalize_headline(text: str) -> str:
    import re
    text = text.lower()
    text = re.sub(r'^[0-9]+\.\s*', '', text)
    text = re.sub(r'^[a-z]+:\s*', '', text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _classify_driver(text: str) -> str:
    t = text.lower()
    RULES = [
        (["iran", "tehran", "persian gulf", "ceasefire iran"],         "Iran ceasefire risk"),
        (["israel", "gaza", "hamas", "hezbollah", "idf", "west bank"], "Middle East conflict"),
        (["ukraine", "russia", "nato", "zelensky", "putin", "kyiv"],   "Russia-Ukraine conflict"),
        (["china", "taiwan", "south china sea", "xi jinping", "beijing"], "China geopolitical pressure"),
        (["outbreak", "hantavirus", "mpox", "ebola", "pandemic",
           "virus-stricken", "cruise ship virus", "disease outbreak"], "outbreak travel risk"),
        (["ransomware", "cyberattack", "data breach", "data leak", "hack"], "cybersecurity breach wave"),
        (["fed", "federal reserve", "interest rate", "rate hike", "rate cut", "fomc", "powell"], "Fed rate watch"),
        (["tariff", "trade war", "trade deal", "import tax"],          "trade war escalation"),
        (["inflation", "cpi", "ppi", "recession", "gdp slowdown"],     "macro economic signal"),
        (["earnings", "eps", "quarterly results", "revenue beat"],     "earnings season"),
        (["trump", "congress", "senate", "white house"],               "US political risk"),
        (["oil", "opec", "crude", "energy crisis"],                    "energy market shift"),
        (["bitcoin", "ethereum", "crypto", "defi", "sec crypto"],      "crypto regulatory risk"),
        (["bank run", "fdic", "credit suisse", "svb", "bank failure"], "banking sector stress"),
        (["openai", "nvidia", "ai chip", "artificial intelligence", "llm"], "AI/tech sector move"),
    ]
    for keywords, label in RULES:
        if any(kw in t for kw in keywords):
            return label
    return ""

# Market implications per driver — used by JARVIS // FEED for deterministic "why it matters"
_DRIVER_IMPLICATIONS = {
    "Iran ceasefire risk":          "energy/defense stocks may reprice; watch crude and Lockheed",
    "Middle East conflict":         "oil supply risk; defense sector in focus; safe-haven flows",
    "Russia-Ukraine conflict":      "commodity and energy exposure; NATO defense spend rising",
    "China geopolitical pressure":  "supply chain disruption risk; TSMC and chip sector react",
    "outbreak travel risk":         "cruise and airline sector at risk; watch biotech response",
    "cybersecurity breach wave":    "security sector uplift; regulatory scrutiny likely follows",
    "Fed rate watch":               "rate-sensitive names move; growth vs value rotation in play",
    "trade war escalation":         "import-heavy sectors hit; manufacturing costs rise",
    "macro economic signal":        "GDP-sensitive positions at risk; consumer discretionary watch",
    "earnings season":              "individual stock volatility high; check your positions' dates",
    "US political risk":            "policy uncertainty; regulatory and fiscal exposure",
    "energy market shift":          "energy positions and transport costs directly affected",
    "crypto regulatory risk":       "crypto positions may reprice sharply on any ruling",
    "banking sector stress":        "financial exposure; watch credit spreads and deposit flows",
    "AI/tech sector move":          "NVDA and chip names lead; AI infrastructure spend in focus",
}

def _headline_fingerprint(text: str):
    import re
    stop_words = {
        "the", "a", "an", "and", "or", "but", "for", "to", "of", "in", "on",
        "at", "by", "with", "from", "is", "are", "was", "were", "be", "as",
        "has", "have", "had", "that", "this", "it", "its", "their", "his",
        "her", "they", "them", "you", "your", "our", "after", "before",
    }
    normalized = _normalize_headline(text)
    words = [w for w in re.findall(r"[a-z0-9]+", normalized) if w not in stop_words]
    return tuple(words[:5])

def _dedupe_headline_lines(lines, limit=3):
    seen_bigrams: set = set()
    seen_drivers: set = set()
    out = []
    for line in lines:
        driver = _classify_driver(line)
        if driver and driver in seen_drivers:
            continue
        fp = _headline_fingerprint(line)
        if not fp:
            continue
        bigrams = set(zip(fp, fp[1:]))
        if bigrams and (bigrams & seen_bigrams):
            continue
        if driver:
            seen_drivers.add(driver)
        seen_bigrams.update(bigrams)
        out.append(line)
        if len(out) >= limit:
            break
    return out


# ── Data fetchers ─────────────────────────────────────────────────────────────

async def fetch_headlines(n=5) -> str:
    try:
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from fetch import fetch_source_context
        from news_sources import get_site_sources
        sources = get_site_sources()[:2]
        headlines = []
        for src in sources:
            try:
                url, text = await asyncio.to_thread(fetch_source_context, src["url"])
                lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 30][:3]
                for line in lines:
                    clean = line.strip()
                    if len(clean) > 85:
                        truncated = clean[:85]
                        if " " in truncated:
                            truncated = truncated.rsplit(" ", 1)[0]
                        clean = truncated + "..."
                    headlines.append(f"{src['name']}: {clean}")
            except Exception:
                pass
        unique = _dedupe_headline_lines(headlines, min(n, 3))
        return "\n".join([f"{i+1}. {h}" for i, h in enumerate(unique)])
    except Exception as e:
        return f"Headlines unavailable: {e}"

async def _get_pinkslip_brief() -> str:
    try:
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from pinkslip_odds import get_all_default
        return await get_all_default(limit_per_sport=1)
    except Exception as e:
        print(f">> PINKSLIP BRIEF ERROR: {e}")
        return ""

def _fetch_repo_state() -> dict:
    try:
        import subprocess
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd="/Users/higabot1/jarvis1-1",
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        last_commit = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd="/Users/higabot1/jarvis1-1",
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return {
            "dirty_count": len(status.splitlines()) if status else 0,
            "last_commit": last_commit or "none",
        }
    except Exception:
        return {"dirty_count": 0, "last_commit": "unknown"}

def _fetch_pending_jobs() -> int:
    try:
        import sqlite3
        conn = sqlite3.connect("/Users/higabot1/jarvis1-1/jarvis_memory.db")
        n = conn.execute("SELECT count(*) FROM jobs WHERE status='pending'").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0

def _latest_content(folder: str, ext: str = ".md") -> tuple:
    """Return (count, slug, date_str) for the most recent file in a content folder."""
    try:
        files = sorted(
            [f for f in os.listdir(folder) if f.endswith(ext)],
            reverse=True
        )
        count = len(files)
        if not files:
            return count, "", ""
        stem = files[0][:-len(ext)]
        parts = stem.split("_")
        date_str = ""
        slug = stem
        if len(parts) >= 3:
            raw_date = parts[0]
            try:
                if len(raw_date) == 8 and raw_date.isdigit():
                    date_str = f"{raw_date[4:6]}/{raw_date[6:]}"
                elif "-" in raw_date and len(raw_date) >= 7:
                    date_str = raw_date[5:]
            except Exception:
                pass
            slug = " ".join(parts[2:])[:40]
        return count, slug, date_str
    except Exception:
        return 0, "", ""


# ── Context extractor ─────────────────────────────────────────────────────────

def _clean_headline(text: str) -> str:
    """Strip source suffixes like '| AP News', '| BBC News', '| Reuters' from headline text."""
    import re as _re
    text = text.strip()
    text = _re.sub(r'\s*\|\s*\S.*$', '', text).strip()   # strip "| AP News" etc.
    text = _re.sub(r'\s*—\s*\S.*$', '', text).strip()    # strip "— BBC" etc.
    return text

def _extract_briefing_context(portfolio: dict, headlines_str: str):
    lines = [l.strip() for l in (headlines_str or "").splitlines() if l.strip()]
    top_headline = ""
    if lines:
        top_headline = lines[0]
        top_headline = top_headline.split(". ", 1)[1] if ". " in top_headline else top_headline
        top_headline = top_headline.split(": ", 1)[1] if ": " in top_headline else top_headline
        top_headline = _clean_headline(top_headline)

    positions = list(portfolio.get("positions", [])) if portfolio else []
    best_pos = ""
    worst_pos = ""
    if positions:
        best  = max(positions, key=lambda p: p.get("pl", 0))
        worst = min(positions, key=lambda p: p.get("pl", 0))
        best_pos  = f"{best.get('symbol','?')} {best.get('pl',0):+,.2f}"
        worst_pos = f"{worst.get('symbol','?')} {worst.get('pl',0):+,.2f}"
    return top_headline, best_pos, worst_pos


# ── Section divider ───────────────────────────────────────────────────────────
_DIV = "━━━━━━━━━━━━━━━━"


# ── Section builders ──────────────────────────────────────────────────────────

def _section_header_higa(time_of_day: str, now: str) -> str:
    label = "MORNING BRIEF" if time_of_day == "morning" else "EVENING DEBRIEF"
    icon  = "🌅" if time_of_day == "morning" else "🌆"
    return f"{icon} *HIGA COMMAND // {label}*\n_{now}_"


def _section_feed(headlines_str: str) -> str:
    """JARVIS // FEED: headline + why-it-matters implication, fully deterministic."""
    if not headlines_str or "unavailable" in headlines_str.lower():
        return "📡 *JARVIS // FEED*\n_No headline data available._"
    lines = ["📡 *JARVIS // FEED*"]
    for line in headlines_str.splitlines():
        line = line.strip()
        if not line:
            continue
        body = line
        if ". " in body:
            body = body.split(". ", 1)[1]
        if ": " in body:
            body = body.split(": ", 1)[1]
        body = _clean_headline(body)
        driver = _classify_driver(body)
        implication = _DRIVER_IMPLICATIONS.get(driver, "")
        lines.append(f"• {body}")
        if driver and implication:
            lines.append(f"  ↳ _{driver}_ — {implication}")
        elif driver:
            lines.append(f"  ↳ _{driver}_")
    return "\n".join(lines)


def _section_stockbot(portfolio: dict) -> str:
    lines = ["📈 *STOCKBOT*"]
    if not portfolio:
        lines.append("_Portfolio data unavailable (Alpaca offline)_")
        return "\n".join(lines)
    equity = portfolio.get("equity", 0)
    day_pl = portfolio.get("day_pl", 0)
    bp     = portfolio.get("buying_power", 0)
    pl_icon = "📈" if day_pl >= 0 else "📉"
    lines.append(f"Equity `${equity:,.2f}` | Day P/L `{day_pl:+,.2f}` {pl_icon} | Cash `${bp:,.2f}`")
    lines.append("Acorns `$454.36` _(static)_")
    positions = portfolio.get("positions", [])
    for p in positions:
        emoji = "🟢" if p["pl"] >= 0 else "🔴"
        lines.append(f"{emoji} {p['symbol']}: `${p['value']:,.2f}` ({p['pl']:+,.2f})")
    if positions:
        green   = sum(1 for p in positions if p["pl"] >= 0)
        posture = "risk-on" if day_pl >= 0 else "defensive"
        lines.append(f"Posture: {posture} — {green}/{len(positions)} positions green.")
    return "\n".join(lines)


def _section_cryptoid(crypto_total: float, crypto_lines: str, wb_crypto: float,
                      cb_total: float, kr_equity: float, prices: dict) -> str:
    lines = [f"🪙 *CRYPTOID* — `${crypto_total:,.2f} total`"]
    for line in (crypto_lines or "").splitlines():
        line = line.strip()
        if line:
            lines.append(f"  {line}")
    lines.append(f"Webull `${wb_crypto:.2f}` | Coinbase `${cb_total:.2f}` | Kraken `${kr_equity:.2f}`")
    if prices:
        price_parts = [f"{k} `${v:,.2f}`" for k, v in prices.items()]
        lines.append("Spot: " + " | ".join(price_parts))
    return "\n".join(lines)


def _section_doctorbot(health_line: str, repo: dict) -> str:
    dirty  = repo.get("dirty_count", 0)
    commit = repo.get("last_commit", "unknown")
    dirty_str = f"{dirty} uncommitted file{'s' if dirty != 1 else ''}" if dirty else "repo clean"
    return "\n".join([
        "🩺 *DOCTORBOT*",
        f"Code: {health_line}",
        f"Repo: {dirty_str} | Last commit: `{commit[:60]}`",
    ])


def _section_ultron(repo: dict, pending_jobs: int) -> str:
    dirty = repo.get("dirty_count", 0)
    lines = ["🛡️ *ULTRON*"]
    if dirty:
        lines.append(f"⚠️ {dirty} uncommitted change{'s' if dirty != 1 else ''} — push recommended.")
    else:
        lines.append("✅ Repo clean — no drift detected.")
    if pending_jobs:
        lines.append(f"⏳ {pending_jobs} job{'s' if pending_jobs != 1 else ''} pending in queue.")
    else:
        lines.append("Queue clear — no pending jobs.")
    lines.append("No active threat flags.")
    return "\n".join(lines)


def _section_technoid(cpu: float, ram_used: float, ram_total: float, disk: float) -> str:
    try:
        boot    = datetime.fromtimestamp(psutil.boot_time())
        uptime_h = int((datetime.now() - boot).total_seconds() // 3600)
        net     = psutil.net_io_counters()
        extras  = f" | Up `{uptime_h}h` | Net ↑`{net.bytes_sent/1e6:.0f}MB` ↓`{net.bytes_recv/1e6:.0f}MB`"
    except Exception:
        extras = ""
    return "\n".join([
        "🖥️ *TECHNOID*",
        f"CPU `{cpu:.0f}%` | RAM `{ram_used:.1f}/{ram_total:.1f}GB` | Disk `{disk:.0f}%`{extras}",
    ])


def _section_robowright(statuses: dict) -> str:
    _CLIPS_DIR  = "/Users/higabot1/jarvis1-1/clips"
    _DRAFTS_DIR = "/Users/higabot1/jarvis1-1/drafts"
    clip_count, clip_slug, clip_date   = _latest_content(_CLIPS_DIR)
    draft_count, _, _                  = _latest_content(_DRAFTS_DIR)
    lines = ["🎬 *ROBOWRIGHT*"]
    lines.append(f"{clip_count} clips | {draft_count} draft{'s' if draft_count != 1 else ''} staged")
    if clip_slug:
        lines.append(f"Latest: `{clip_slug}`" + (f" ({clip_date})" if clip_date else ""))
    task = statuses.get("robowright", {}).get("current_task", "")
    if task and task not in {"Waiting for next task.", "Monitoring system health."}:
        lines.append(f"Active: {str(task)[:80]}")
    return "\n".join(lines)


def _section_jamz(statuses: dict) -> str:
    _BEATS_DIR = "/Users/higabot1/jarvis1-1/beats"
    beat_count, beat_slug, beat_date = _latest_content(_BEATS_DIR)
    lines = ["🎵 *JAMZ*"]
    lines.append(f"{beat_count} beat{'s' if beat_count != 1 else ''} in library")
    if beat_slug:
        lines.append(f"Latest: `{beat_slug}`" + (f" ({beat_date})" if beat_date else ""))
    task = statuses.get("jamz", {}).get("current_task", "")
    if task and task not in {"Waiting for next task.", "Monitoring system health."}:
        lines.append(f"Active: {str(task)[:80]}")
    return "\n".join(lines)


def _section_higashop() -> str:
    try:
        import json
        with open("/Users/higabot1/jarvis1-1/higashop_inventory.json") as f:
            inv = json.load(f)
        bankroll = inv.get("bankroll", 0)
        products = inv.get("products", [])
        active   = [p for p in products if p.get("status") == "active"]
        goals    = inv.get("goals", [])
        goal_str = " → ".join(goals[:3]) if goals else "No goals set"
        return "\n".join([
            "🛍️ *HIGASHOP*",
            f"Bankroll `${bankroll:,.0f}` | {len(active)} active product{'s' if len(active) != 1 else ''}",
            f"Goals: {goal_str}",
        ])
    except Exception:
        return "🛍️ *HIGASHOP*\n_Inventory data unavailable_"


def _section_teacherbot() -> str:
    try:
        import json
        with open("/Users/higabot1/jarvis1-1/teacherbot_tracker.json") as f:
            data = json.load(f)
        students = data.get("students", [])
        if not students:
            return "📚 *TEACHERBOT*\n_No active student profile_"
        s        = students[0]
        subjects = s.get("subjects", {})
        lines    = ["📚 *TEACHERBOT*"]
        for subj, info in list(subjects.items())[:2]:
            level       = info.get("level", "?")
            completed   = info.get("completed", [])
            next_lesson = info.get("next_lesson", "—")
            done_str    = ", ".join(completed[-2:]) if completed else "none"
            lines.append(f"{subj.capitalize()} — {level} | Done: {done_str} | Next: _{next_lesson}_")
        return "\n".join(lines)
    except Exception:
        return "📚 *TEACHERBOT*\n_Tracker data unavailable_"


def _section_pinkslip(pinkslip_str: str) -> str:
    if not pinkslip_str or not pinkslip_str.strip():
        return ""
    import re as _re
    items = []
    current_sport = ""
    for line in pinkslip_str.splitlines():
        line = line.strip()
        m = _re.match(r'^\*([a-z_]+)\*$', line)
        if m:
            parts = m.group(1).split("_")
            current_sport = parts[-1].upper()
        elif line.startswith("• ") and current_sport:
            matchup = line[2:].split(" — ")[0]
            items.append(f"*{current_sport}*: {matchup}")
            current_sport = ""
            if len(items) >= 2:
                break
    if not items:
        return ""
    return "🎯 *PINKSLIP*\n" + "\n".join(items)


def _section_debate_room(statuses: dict) -> str:
    debate_bots = ["shaman", "libmom", "magadad"]
    lines = ["🧿 *DEBATE ROOM*"]
    active = []
    for bot_id in debate_bots:
        data = statuses.get(bot_id, {})
        task = str(data.get("current_task", "") or "").strip()
        if task and task not in {"Waiting for next task.", "Monitoring system health."}:
            active.append(f"{data.get('icon','•')} {data.get('name', bot_id)}: {task[:60]}")
    if active:
        lines.extend(active)
    else:
        lines.append("Shaman | Lib Mom | Maga Dad — standing by. No active debate.")
    return "\n".join(lines)


def _section_one_thing(portfolio: dict, top_headline: str,
                       worst_pos: str, best_pos: str) -> str:
    lines = ["🔺 *ONE THING BEFORE TOMORROW*"]
    day_pl = portfolio.get("day_pl", 0) if portfolio else 0
    driver = _classify_driver(top_headline) if top_headline else ""

    if day_pl < -50 and worst_pos:
        action = f"Review *{worst_pos}* — cut or add before open. Don't hold a bleeding position overnight."
    elif day_pl < 0 and worst_pos:
        action = f"Watch *{worst_pos}* — down today. Set a stop or plan your exit before market open."
    elif day_pl >= 0 and best_pos:
        action = f"Let *{best_pos}* run — strongest name today. Trail your stop and don't take it off early."
    elif driver:
        action = f"Track *{driver}* overnight — this is the macro thread most likely to move your book."
    else:
        action = "Review open positions before market open. No obvious laggard today — hold the line."
    lines.append(action)
    return "\n".join(lines)


def _section_close_higa(time_of_day: str) -> str:
    if time_of_day == "morning":
        return "_HIGA COMMAND ONLINE. Markets open 9:30 AM ET. All systems go. Standing by, sir._"
    return "_HIGA COMMAND STANDING BY. Review complete. Next brief: 05:00 CST. Good night, sir._"


# ── TOP OF MIND — single Ollama call ─────────────────────────────────────────

async def _build_top_of_mind(portfolio: dict, crypto_total: float, prices: dict,
                              headlines_str: str, time_of_day: str) -> str:
    equity    = portfolio.get("equity", 0)
    day_pl    = portfolio.get("day_pl", 0)
    price_str = ", ".join(f"{k}: ${v:,.2f}" for k, v in prices.items()) if prices else "unavailable"
    top_headline, best_pos, worst_pos = _extract_briefing_context(portfolio, headlines_str)

    prompt = (
        f"You are J.A.R.V.I.S. running HIGA COMMAND. Write a 2-sentence {time_of_day} command briefing.\n"
        f"News: {top_headline or 'No major headline available'}\n"
        f"Portfolio: ${equity:,.2f} equity | day P/L {day_pl:+,.2f} | "
        f"best {best_pos or 'n/a'} | worst {worst_pos or 'n/a'}\n"
        f"Crypto: ${crypto_total:,.2f} total | {price_str}\n"
        f"Sentence 1: macro theme and market implication — direct, specific. "
        f"Sentence 2: portfolio posture with one clear watch or action. "
        f"Plain prose only. No bullets. No markdown."
    )
    try:
        import re as _re
        async with httpx.AsyncClient(timeout=90) as h:
            resp = await h.post(
                OLLAMA_URL,
                json={"model": MODEL, "prompt": prompt, "stream": False,
                      "think": False,
                      "options": {"num_predict": 220, "temperature": 0.7}},
            )
            if resp.status_code == 200:
                raw = resp.json().get("response", "").strip()
                # Strip qwen3 think blocks — handle both closed and unclosed tags
                raw = _re.sub(r'<think>.*?</think>', '', raw, flags=_re.DOTALL).strip()
                raw = _re.sub(r'<think>.*',          '', raw, flags=_re.DOTALL).strip()
                if not raw:
                    print(">> TOP OF MIND: empty after think-strip — using fallback")
                else:
                    text = raw.replace("\n", " ")
                    sentences = [s.strip() for s in _re.split(r'(?<=[.!?])\s+(?=[A-Z])', text) if s.strip()]
                    print(f">> TOP OF MIND: Ollama OK — {len(sentences)} sentence(s) extracted")
                    if len(sentences) >= 2:
                        return sentences[0] + " " + sentences[1]
                    if sentences and len(sentences[0]) > 20:
                        if worst_pos and day_pl < 0:
                            s2 = f"Watch {worst_pos} for continued pressure; consider trimming before open."
                        elif best_pos:
                            s2 = f"Your strongest name is {best_pos} — let it run, keep stops tight."
                        else:
                            s2 = f"Portfolio sits at ${equity:,.2f} — hold and review after the open."
                        return sentences[0] + " " + s2
                    print(f">> TOP OF MIND: sentence parse failed on: {text[:120]!r}")
            else:
                print(f">> TOP OF MIND ERROR: Ollama returned {resp.status_code}")
    except Exception as e:
        print(f">> TOP OF MIND ERROR: {type(e).__name__}: {e}")

    print(">> TOP OF MIND: deterministic fallback")

    driver = _classify_driver(top_headline) if top_headline else ""
    news_frame = (
        f"The dominant macro driver is {driver}"
        if driver else (top_headline or "Headline flow is mixed")
    )
    s2 = (f"Your best name is {best_pos} — stay the course." if best_pos and day_pl >= 0
          else f"Watch {worst_pos} closely before adding exposure." if worst_pos
          else f"Hold at ${equity:,.2f} equity and monitor the tape.")
    return f"{news_frame}. {s2}"


# ── Main briefing entry point ─────────────────────────────────────────────────

async def generate_briefing(time_of_day: str) -> str:
    now = datetime.now().strftime('%B %d, %Y — %I:%M %p CST')

    # Parallel data fetch
    prices, portfolio, headlines = await asyncio.gather(
        get_crypto_prices(),
        get_alpaca_portfolio(),
        fetch_headlines(3),
    )
    pinkslip_str = await _get_pinkslip_brief()

    cpu, ram_used, ram_total, disk = get_system_stats()
    crypto_total, crypto_lines, wb_crypto, cb_total, kr_equity = get_real_crypto()

    # Code health
    try:
        from bots.doctorbot import scan_for_bugs
        health = scan_for_bugs()
        health_line = "Code ✅ all clean" if ("All" in health and "clean" in health) else f"⚠️ Issues: {health[:80]}"
    except Exception:
        health_line = "Code health unknown"

    # Bot statuses
    try:
        import sys as _sys
        _sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from bot_orchestrator import orchestrator
        statuses = orchestrator.get_all_statuses()
    except Exception:
        statuses = {}

    # Repo + jobs
    repo         = _fetch_repo_state()
    pending_jobs = _fetch_pending_jobs()

    # Context for TOP OF MIND and ONE THING
    top_headline, best_pos, worst_pos = _extract_briefing_context(portfolio, headlines)

    # Single LLM call
    top_of_mind = await _build_top_of_mind(portfolio, crypto_total, prices, headlines, time_of_day)

    # Build sections
    s_header     = _section_header_higa(time_of_day, now)
    s_tom        = f"🧠 *TOP OF MIND*\n{top_of_mind}"
    s_feed       = _section_feed(headlines)
    s_stockbot   = _section_stockbot(portfolio)
    s_cryptoid   = _section_cryptoid(crypto_total, crypto_lines, wb_crypto, cb_total, kr_equity, prices)
    s_doctorbot  = _section_doctorbot(health_line, repo)
    s_ultron     = _section_ultron(repo, pending_jobs)
    s_technoid   = _section_technoid(cpu, ram_used, ram_total, disk)
    s_robowright = _section_robowright(statuses)
    s_jamz       = _section_jamz(statuses)
    s_higashop   = _section_higashop()
    s_teacherbot = _section_teacherbot()
    s_pinkslip   = _section_pinkslip(pinkslip_str)
    s_debate     = _section_debate_room(statuses)
    s_one_thing  = _section_one_thing(portfolio, top_headline, worst_pos, best_pos)
    s_close      = _section_close_higa(time_of_day)

    # Assemble
    _SEP = f"\n{_DIV}\n"
    blocks = [
        s_header, s_tom, s_feed,
        s_stockbot, s_cryptoid,
        s_doctorbot, s_ultron, s_technoid,
        s_robowright, s_jamz,
        s_higashop, s_teacherbot,
    ]
    if s_pinkslip:
        blocks.append(s_pinkslip)
    blocks.extend([s_debate, s_one_thing])

    briefing = _SEP.join(blocks) + f"\n{_DIV}\n{s_close}"
    print(f"\n{briefing}\n")

    # Write status file for /api/health observability endpoint
    import json as _json
    _status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "briefing_status.json")
    try:
        with open(_status_path, "w") as _sf:
            _json.dump({
                "status":      "ok",
                "last_period": time_of_day,
                "sent_at":     datetime.now().isoformat(),
                "error":       None,
            }, _sf)
    except Exception as _e:
        print(f">> BRIEFING STATUS WRITE ERROR: {_e}")

    return briefing


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
