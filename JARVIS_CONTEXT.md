# JARVIS1-1 Project Context
# Last Updated: April 19, 2026
# Read this BEFORE touching any file.

## Directory
/Users/higabot1/jarvis1-1

## Architecture
- main.py — FastAPI server, port 8000, Ollama qwen3:8b backend
- bots/router.py — routes messages to each agent by bot_id
- bots/ — 11 agents: jarvisbot, stockbot, cryptoid, pinkslip, doctorbot,
           ultron, robowright, jamz, higashop, technoid, teacherbot
- frontend/ — HIGA HOUSE UI
- multi_broker_portfolio.py — real portfolio data (NOT Alpaca paper)
- fetch.py — web scraper (BeautifulSoup) — DO NOT create news_scraper.py or market_scraper.py
- youtube_tools.py — YouTube search, transcripts, summaries, comments
- news_sources.py — news site config list (AP, BBC, CNN, Fox, KSLA, KALB, etc.)
- market_sources.py — market site config list (Bloomberg, CNBC, CoinDesk, etc.)
- memory.py — SQLite conversation memory
- indicators.py — technical analysis
- trading.py — Alpaca trade execution

## Real Portfolio (~$3,696 total)
- Webull:       $834.81  (META, NFLX, AMD, NVDA, TSLA, PYPL + BTC, ETH, SHIBxM)
- Robinhood:    $273.85  (VOO, TSLA)
- Coinbase:     $232.36  (SOL, BNB, XRP)
- Acorns:       $454.36
- Alpaca paper: $1,801.29 (paper trading ONLY — NOT real money)
- Kraken paper: $99.97   (DOGE paper)

## Crypto Positions (~$466 total) — source: multi_broker_portfolio.py
- BTC:    $140.07  P/L: +$56.46  (Webull)
- ETH:    $74.31   P/L: -$25.69  (Webull)
- SHIBxM: $10.43   P/L: -$39.57  (Webull)
- SOL:    $189.61  P/L: -$44.38  (Coinbase)
- BNB:    $37.65   P/L: -$12.47  (Coinbase)
- XRP:    $5.08    P/L: -$1.55   (Coinbase)
- DOGE:   $9.49    P/L: -$0.03   (Kraken paper)

## Stock Positions — source: Alpaca paper trading
- AMD, META, NFLX, NVDA, PYPL, TSLA, VOO

## Bot Rules (NEVER violate these)
- Stockbot = stocks ONLY (Alpaca paper trading data)
- Cryptoid = all crypto (multi_broker_portfolio.py is source of truth)
- Alpaca paper equity ($1,801.29) is NOT the real portfolio total ($3,696)
- DO NOT create news_scraper.py or market_scraper.py — fetch.py handles scraping
- DO NOT use sys.path.append('..') — use sys.path.insert(0, "/Users/higabot1/jarvis1-1")

## Critical Code Patterns
### Correct broker breakdown in router.py (Cryptoid section):
    webull_crypto = sum(v['value'] for v in portfolio_data['webull']['crypto'].values())
    coinbase_total = portfolio_data['coinbase']['total_value']
    kraken_equity = portfolio_data['paper_trading']['kraken']['equity']

### portfolio_data structure:
    portfolio_data['webull']['crypto']          = dict of assets (NOT a number)
    portfolio_data['coinbase']['total_value']   = float
    portfolio_data['paper_trading']['kraken']['equity'] = float

## Launch Commands
    cd /Users/higabot1/jarvis1-1
    python3 main.py &                          # HIGA HOUSE on port 8000
    python3 higabot-dashboard/server.py &      # Dashboard on port 3000
    pkill -f "main.py"                         # Kill JARVIS
    pkill -f "server.py"                       # Kill dashboard

## GitHub
    Repo: https://github.com/higamacbot/jarvis1
    Note: GitHub has jarvis1 (old single-agent). jarvis1-1 is the live multi-agent version.
    jarvis1-1 has NOT been pushed to GitHub yet — back it up!

## ─── TIMELINE / MISTAKE LOG ─────────────────────────────────────────────────

### Apr 18, 2026 — Multi-broker portfolio integration
- Added multi_broker_portfolio.py tracking Webull, Robinhood, Coinbase, Acorns
- Stockbot updated to show combined stock portfolio
- Cryptoid assigned all crypto across all brokers

### Apr 18, 2026 — MISTAKE: Wrong directory
- Tests kept failing because terminal was in jarvis1/ not jarvis1-1/
- Fix: always cd /Users/higabot1/jarvis1-1 first

### Apr 18, 2026 — MISTAKE: news_scraper.py and market_scraper.py created
- AI generated these files but they were unnecessary — fetch.py already handles scraping
- These files had wrong import names (get_market_sources vs get_stock_sources)
- Fix: removed imports from main.py, fetch.py is the correct tool

### Apr 18, 2026 — MISTAKE: sys.path.append('..') in router.py
- Caused multi_broker_portfolio import to silently fail
- Cryptoid kept showing "No crypto positions" and Alpaca stock data instead
- Fix: replaced with sys.path.insert(0, "/Users/higabot1/jarvis1-1")

### Apr 18, 2026 — MISTAKE: f-string formatting dict as float
- router.py Cryptoid section: portfolio_data['webull']['crypto'] is a dict not a number
- Caused "unsupported format string passed to dict.__format__" error
- Fix: use sum(v['value'] for v in portfolio_data['webull']['crypto'].values())

### Apr 19, 2026 — FIXED: Cryptoid now shows real crypto portfolio
- Cryptoid correctly shows $466.64 across Webull, Coinbase, Kraken
- BTC hold signal, reduce SOL/BNB/XRP recommendation working

## ─── HOW TO USE THIS FILE WITH OTHER AIs ────────────────────────────────────
# Windsurf: Open this file in editor, say "Read JARVIS_CONTEXT.md before touching anything"
# Ollama:   Paste this file content at the start of your session prompt
# Always tell the AI: "Do not create new files unless absolutely necessary.
#                      Check what already exists in fetch.py, youtube_tools.py first."

### Apr 19, 2026 — Doctorbot assigned as git/context owner
- Doctorbot now owns JARVIS_CONTEXT.md updates and all git commits
- Has functions: git_status(), git_commit_and_push(), log_to_context(), read_context()
- All future fixes should be logged via Doctorbot before committing
- .gitignore created: blocks keys.py, *.db, router_broken.py, market_scraper.py, news_scraper.py

### Apr 19, 2026 @ 06:55 AM — Doctorbot v2 deployed — auto-logging every commit and context access

### Apr 19, 2026 @ 07:01 AM — fix: resolve ROUNDTABLE Neural Link Error and keys.py attribute names

### Apr 19, 2026 @ 07:02 AM — FIXED: keys.py renamed ALPACA_API_KEY->ALPACA_KEY and ALPACA_SECRET_KEY->ALPACA_SECRET. ROUNDTABLE Neural Link Error resolved.

### Apr 19, 2026 — MISTAKE: keys.py wrong attribute names
- keys.py had ALPACA_API_KEY and ALPACA_SECRET_KEY
- main.py was looking for ALPACA_KEY and ALPACA_SECRET
- Caused "module 'keys' has no attribute 'ALPACA_KEY'" warning every boot
- Fix: sed rename in keys.py — now verified and handshake passes
- NOTE: keys.py is gitignored — this fix only lives locally

### Apr 19, 2026 @ 07:06 AM — ROUNDTABLE fully operational — all 11 agents responding correctly

### Apr 19, 2026 @ 07:06 AM — Roundtable now has real portfolio data injected — crypto $466, stocks, all brokers

### Apr 19, 2026 @ 07:09 AM — MILESTONE: Roundtable fully operational with real portfolio data. Cryptoid showing BTC +$56.46, ETH -$25.69 in group sessions.

### Apr 19, 2026 @ 07:14 AM — Roundtable prompt upgraded — each agent now gives full paragraph updates in their own voice

### Apr 19, 2026 @ 07:14 AM — Roundtable prompt updated — response length now scales to actual update size, no padding

### Apr 19, 2026 — Roundtable prompt behavior documented
- Each bot responds based on what they actually have to report
- No update = 1 sentence "No update."
- Small update = 1-2 sentences
- Big update = 3-4 sentence paragraph
- Roundtable has real portfolio data injected (crypto $466, stocks, all brokers)
- Cryptoid shows real P/L numbers in roundtable (BTC +$56.46, ETH -$25.69 etc)
- Do NOT change roundtable prompt without reading this note first

### Apr 19, 2026 @ 07:20 AM — MILESTONE: Roundtable fully dialed in. All 11 agents responding with appropriate length updates. Cryptoid showing real P/L numbers. Teacherbot correctly isolated from financial data.

### Apr 19, 2026 @ 07:25 AM — Briefing scheduler rewritten — real crypto P/L, agent-style voices, psutil system stats

### Apr 19, 2026 @ 07:46 AM — News fetching wired into main.py — triggers on news/headlines keywords, scrapes AP+BBC+AlJazeera via fetch.py

### Apr 19, 2026 @ 07:59 AM — News handler moved to /ws/house endpoint - was incorrectly in /ws only

### Apr 19, 2026 @ 08:03 AM — MILESTONE: News fully working on both /ws and /ws/house endpoints. AP, BBC, Al Jazeera scraping live via fetch.py. JARVIS summarizes via Ollama.

### Apr 19, 2026 @ 08:12 AM — YouTube handler moved to /ws/house endpoint - was incorrectly in /ws only

### Apr 19, 2026 @ 08:21 AM — YouTube functionality fully working in HIGA HOUSE - API key configured, video analysis, transcripts, comments all operational

### Apr 19, 2026 @ 09:13 AM — YouTube transcript PDFs now save into per-channel folders from summarize/transcript paths

### Apr 19, 2026 @ 09:16 AM — YouTube transcripts now save to Obsidian vault per-channel folders with PDF and markdown note output

### Apr 19, 2026 @ 11:39 AM — Bot orchestrator deployed: persistent status, task queue, debate engine, /bots /assign /debate commands, REST API endpoints

### Apr 19, 2026 @ 11:45 AM — MILESTONE: Debate room live — Shaman (conspiracy room), Lib Mom, MAGA Dad added to HIGA HOUSE grid rows 5-6. Room colors polling /api/bots/status every 3s. /debate command triggers all three bots via Ollama.

### Apr 19, 2026 @ 11:47 AM — Debate bots added to orchestrator registry - shaman/libmom/magadad now show in /api/bots/status and get room colors

### Apr 19, 2026 @ 11:58 AM — Fixed: roundtable prompt no longer echoes bracket instructions. Debate arena click now engages shaman+libmom+magadad simultaneously.

### Apr 19, 2026 @ 12:03 PM — Debate room: clicking arena opens debateroom bot which runs all 3 personas. Roundtable shows shaman/libmom/magadad as subpoints under DEBATE ROOM.

### Apr 19, 2026 @ 12:06 PM — Debate arena: bots animate into arena on click, rooms flash yellow while waiting, debate personas use fiction framing to avoid Ollama refusals

### Apr 19, 2026 @ 12:08 PM — Room color: flashes yellow while waiting for response, restores after answer. Debate persona prompt fixed to avoid Ollama refusal.

### Apr 19, 2026 @ 12:12 PM — Debate room: colored responses per persona (shaman=pink, lib=blue, maga=red, topic=orange). Arena glows orange on click. Debate bot rooms flash yellow while waiting.

### Apr 19, 2026 @ 06:49 PM — Debate arena: 3 bots drawn at chairs around debate table inside arena canvas. Own rooms show IN ARENA when debate active.

### Apr 19, 2026 @ 06:50 PM — Room status colors: yellow while thinking, green flash on response ready, blue after 2s idle

### Apr 19, 2026 @ 08:47 PM — CRITICAL FIX: Resolved Roundtable Neural Link Error by hardening portfolio data summation. DEPLOYED: Debate Room chairs and physical animation. DEPLOYED: Status color cycle Yellow->Green->Blue. REPO CLEANUP: Removed blocked news_scraper.py and market_scraper.py.

### Apr 19, 2026 @ 11:09 PM — FIXED: router.py crypto_lines syntax error. JARVIS fully operational. Debate room colored responses working. Room colors yellow->green->blue cycle live.
