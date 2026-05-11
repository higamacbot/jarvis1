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
    """Lazy-load Alpaca client so import never crashes startup."""
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


def _normalize_headline(text: str) -> str:
    import re
    text = text.lower()
    text = re.sub(r'^[0-9]+\.\s*', '', text)
    text = re.sub(r'^[a-z]+:\s*', '', text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
    out = []
    for line in lines:
        fp = _headline_fingerprint(line)
        if not fp:
            continue
        bigrams = set(zip(fp, fp[1:]))
        if bigrams and (bigrams & seen_bigrams):
            continue  # topic overlaps an already-accepted headline
        seen_bigrams.update(bigrams)
        out.append(line)
        if len(out) >= limit:
            break
    return out

def _build_clean_crypto_block(crypto_total, crypto_lines, wb_crypto, cb_total, kr_equity):
    coin_lines = [line.rstrip() for line in (crypto_lines or "").splitlines() if line.strip()]
    block = [f"CRYPTO (Total: ${crypto_total:.2f})"]
    block.extend(coin_lines)
    block.append(f"Broker: Webull ${wb_crypto:.2f} | Coinbase ${cb_total:.2f} | Kraken ${kr_equity:.2f}")
    return "\n".join(block)

async def fetch_headlines(n=5) -> str:
    """Scrape real headlines from AP and BBC."""
    try:
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from fetch import fetch_source_context
        from news_sources import get_site_sources
        sources = get_site_sources()[:2]  # AP + BBC
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

# ── Section divider ───────────────────────────────────────────────────────────
_DIV = "━━━━━━━━━━━━━━━━"


# ── Deterministic section builders ────────────────────────────────────────────

def _section_header(icon: str, time_of_day: str, now: str) -> str:
    return f"{icon} *J.A.R.V.I.S. {time_of_day.upper()} BRIEFING*\n_{now}_"


def _section_portfolio(portfolio: dict) -> str:
    lines = ["💰 *PORTFOLIO*"]
    if not portfolio:
        lines.append("_Portfolio data unavailable_")
        return "\n".join(lines)
    equity       = portfolio.get("equity", 0)
    day_pl       = portfolio.get("day_pl", 0)
    buying_power = portfolio.get("buying_power", 0)
    pl_icon      = "📈" if day_pl >= 0 else "📉"
    lines.append(
        f"Stocks: `${equity:,.2f}` | Day P/L: `{day_pl:+,.2f}` {pl_icon} | Cash: `${buying_power:,.2f}`"
    )
    lines.append("Acorns: `$454.36` _(static)_")
    for p in portfolio.get("positions", []):
        emoji = "🟢" if p["pl"] >= 0 else "🔴"
        lines.append(f"{emoji} {p['symbol']}: `${p['value']:,.2f}` ({p['pl']:+,.2f})")
    return "\n".join(lines)


def _section_crypto(crypto_total: float, crypto_lines: str, wb_crypto: float,
                    cb_total: float, kr_equity: float, prices: dict) -> str:
    lines = [f"🪙 *CRYPTO* — `${crypto_total:,.2f} total`"]
    for line in (crypto_lines or "").splitlines():
        line = line.strip()
        if line:
            lines.append(f"  {line}")
    lines.append(
        f"Webull `${wb_crypto:.2f}` | Coinbase `${cb_total:.2f}` | Kraken `${kr_equity:.2f}`"
    )
    if prices:
        price_parts = [f"{k} `${v:,.2f}`" for k, v in prices.items()]
        lines.append("Spot: " + " | ".join(price_parts))
    return "\n".join(lines)


def _section_headlines(headlines_str: str) -> str:
    lines = ["📰 *HEADLINES*"]
    if not headlines_str or "unavailable" in headlines_str.lower():
        lines.append("_Headlines unavailable_")
    else:
        lines.append(headlines_str)
    return "\n".join(lines)


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
            # Humanize: americanfootball_nfl → NFL, basketball_nba → NBA
            parts = m.group(1).split("_")
            current_sport = parts[-1].upper()
        elif line.startswith("• ") and current_sport:
            matchup = line[2:].split(" — ")[0]   # drop odds, keep teams
            items.append(f"*{current_sport}*: {matchup}")
            current_sport = ""  # one game per sport, then move on
            if len(items) >= 2:
                break
    if not items:
        return ""
    return "🎯 *PINKSLIP*\n" + "\n".join(items)


def _extract_briefing_context(portfolio: dict, headlines_str: str):
    lines = [l.strip() for l in (headlines_str or "").splitlines() if l.strip()]
    top_headline = ""
    if lines:
        top_headline = lines[0]
        top_headline = top_headline.split(". ", 1)[1] if ". " in top_headline else top_headline
        top_headline = top_headline.split(": ", 1)[1] if ": " in top_headline else top_headline

    positions = list(portfolio.get("positions", [])) if portfolio else []
    best_pos = ""
    worst_pos = ""
    if positions:
        best = max(positions, key=lambda p: p.get("pl", 0))
        worst = min(positions, key=lambda p: p.get("pl", 0))
        best_pos = f"{best.get('symbol', '?')} {best.get('pl', 0):+,.2f}"
        worst_pos = f"{worst.get('symbol', '?')} {worst.get('pl', 0):+,.2f}"
    return top_headline, best_pos, worst_pos


def _section_bot_pulse(statuses: dict, portfolio: dict, crypto_total: float,
                       prices: dict, top_headline: str, pinkslip_str: str) -> str:
    def _task_for(bot_id: str) -> str:
        data = statuses.get(bot_id, {})
        task = str(data.get("current_task", "") or "").strip()
        if task in {"Waiting for next task.", "Monitoring system health."}:
            task = ""
        return task

    def _first_pick(text: str) -> str:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("• "):
                return line[2:]
        return ""

    lines = ["🤖 *BOT PULSE*"]
    equity = portfolio.get("equity", 0) if portfolio else 0
    day_pl = portfolio.get("day_pl", 0) if portfolio else 0
    stock_line = f"Equity `${equity:,.2f}` | Day `{day_pl:+,.2f}`"
    crypto_parts = [f"{k} `${v:,.0f}`" for k, v in prices.items()] if prices else [f"Total `${crypto_total:,.2f}`"]
    pink_pick = _first_pick(pinkslip_str)

    # Compress top_headline to a short topic anchor (first 5 words)
    if top_headline:
        words = top_headline.split()
        topic = " ".join(words[:5]) + ("..." if len(words) > 5 else "")
    else:
        topic = "No dominant signal"

    # PINKSLIP: show matchup only, strip odds
    if pink_pick:
        matchup = pink_pick.split(" — ")[0] if " — " in pink_pick else pink_pick
        pink_line = f"Board: {matchup}"
    else:
        pink_line = "No standout line on the board."

    contributions = [
        ("jarvisbot", f"Tracking: {topic}"),
        ("stockbot", f"Portfolio posture: {stock_line}"),
        ("cryptoid", f"Crypto posture: {' | '.join(crypto_parts)}"),
        ("pinkslip", pink_line),
        ("robowright", "Content angle: top headline → fast explainer clip."),
        ("jamz", "Mood bed: tense, minimal, low-distract for briefing mode."),
    ]

    for bot_id, fallback in contributions:
        data = statuses.get(bot_id, {})
        icon = data.get("icon", "•")
        name = data.get("name", bot_id.upper())
        pulse = _task_for(bot_id) or fallback
        if len(pulse) > 95:
            pulse = pulse[:95].rsplit(" ", 1)[0] + "..."
        lines.append(f"{icon} *{name}*: {pulse}")
    return "\n".join(lines)


def _section_system(cpu: float, ram_used: float, ram_total: float,
                    disk: float, health_line: str) -> str:
    return (
        f"⚙️ *SYSTEM*\n"
        f"CPU `{cpu:.0f}%` | RAM `{ram_used:.1f}/{ram_total:.1f}GB` | Disk `{disk:.0f}%`\n"
        f"🔧 {health_line}"
    )


def _section_close(time_of_day: str) -> str:
    if time_of_day == "morning":
        return "_Markets open 9:30 AM ET. All systems go. Standing by, sir._"
    return "_Markets closed. Review complete. Positions locked. Standing by, sir._"


async def _build_top_of_mind(portfolio: dict, crypto_total: float, prices: dict,
                              headlines_str: str, time_of_day: str) -> str:
    """One short Ollama call: 2-sentence market thesis. Deterministic fallback on failure."""
    equity    = portfolio.get("equity", 0)
    day_pl    = portfolio.get("day_pl", 0)
    price_str = ", ".join(f"{k}: ${v:,.2f}" for k, v in prices.items()) if prices else "unavailable"
    top_headline, best_pos, worst_pos = _extract_briefing_context(portfolio, headlines_str)

    prompt = (
        f"You are J.A.R.V.I.S. Write exactly 2 sentences for a {time_of_day} command briefing.\n"
        f"Dominant news: {top_headline or 'No major headline available'}\n"
        f"Portfolio: ${equity:,.2f} equity | day P/L {day_pl:+,.2f} | best {best_pos or 'n/a'} | worst {worst_pos or 'n/a'}\n"
        f"Crypto: ${crypto_total:,.2f} total | {price_str}\n"
        f"Sentence 1: lead with the news theme and market implication. Sentence 2: tie it to portfolio posture and one clear watch. "
        f"No bullet points. No asterisks. No markdown. Plain prose only."
    )
    try:
        import re as _re
        async with httpx.AsyncClient(timeout=45) as h:
            resp = await h.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip().replace("\n", " ")
                # Split on sentence boundary followed by a capital letter
                sentences = [s.strip() for s in _re.split(r'(?<=[.!?])\s+(?=[A-Z])', text) if s.strip()]
                if len(sentences) >= 2:
                    return sentences[0] + " " + sentences[1]
                if len(sentences) == 1 and len(sentences[0]) > 20:
                    # Ollama gave only one sentence — build a deterministic second
                    if best_pos and day_pl < 0:
                        s2 = f"Watch {worst_pos} for continued pressure and consider trimming before it costs more."
                    elif best_pos:
                        s2 = f"Your strongest name is {best_pos} — let it run, but keep stops tight."
                    else:
                        s2 = f"Portfolio is at ${equity:,.2f} equity — hold position and review after the open."
                    return sentences[0] + " " + s2
    except Exception as e:
        print(f">> TOP OF MIND ERROR: {e}")

    direction = "positive" if day_pl >= 0 else "negative"
    news = top_headline or "Headline flow is mixed"
    s2 = (f"Your best name is {best_pos} — stay the course." if best_pos and day_pl >= 0
          else f"Watch {worst_pos} closely before adding exposure." if worst_pos
          else f"Hold at ${equity:,.2f} equity and monitor the tape.")
    return f"{news}. {s2}"


# ── Main briefing entry point ─────────────────────────────────────────────────

async def generate_briefing(time_of_day: str) -> str:
    now        = datetime.now().strftime('%B %d, %Y — %I:%M %p CST')
    icon       = "🌅" if time_of_day == "morning" else "🌆"

    # Fetch all data — parallel where possible
    prices, portfolio, headlines = await asyncio.gather(
        get_crypto_prices(),
        get_alpaca_portfolio(),
        fetch_headlines(3),
    )
    pinkslip_str = await _get_pinkslip_brief()

    cpu, ram_used, ram_total, disk = get_system_stats()
    crypto_total, crypto_lines, wb_crypto, cb_total, kr_equity = get_real_crypto()

    # Code health (sync, fast)
    try:
        from bots.doctorbot import scan_for_bugs
        health      = scan_for_bugs()
        health_line = "Code ✅ all clean" if ("All" in health and "clean" in health) else f"⚠️ Issues: {health[:80]}"
    except Exception:
        health_line = "Code health unknown"

    try:
        import sys as _sys
        _sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from bot_orchestrator import orchestrator
        statuses = orchestrator.get_all_statuses()
    except Exception:
        statuses = {}

    top_headline, _, _ = _extract_briefing_context(portfolio, headlines)

    # Single LLM call — TOP OF MIND only
    top_of_mind = await _build_top_of_mind(portfolio, crypto_total, prices, headlines, time_of_day)

    # Build all sections
    s_header    = _section_header(icon, time_of_day, now)
    s_tom       = f"🧠 *TOP OF MIND*\n{top_of_mind}"
    s_portfolio = _section_portfolio(portfolio)
    s_crypto    = _section_crypto(crypto_total, crypto_lines, wb_crypto, cb_total, kr_equity, prices)
    s_headlines = _section_headlines(headlines)
    s_pinkslip  = _section_pinkslip(pinkslip_str)
    s_bots      = _section_bot_pulse(statuses, portfolio, crypto_total, prices, top_headline, pinkslip_str)
    s_system    = _section_system(cpu, ram_used, ram_total, disk, health_line)
    s_close     = _section_close(time_of_day)

    # Assemble with dividers
    _SEP = f"\n{_DIV}\n"
    blocks = [s_header, s_tom, s_portfolio, s_crypto, s_headlines]
    if s_pinkslip:
        blocks.append(s_pinkslip)
    blocks.extend([s_bots, s_system])

    briefing = _SEP.join(blocks) + f"\n{_DIV}\n{s_close}"

    print(f"\n{briefing}\n")
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
