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
    Repo: higamacbot/jarvis1 — jarvis1-1 IS live on GitHub (main branch)
    All commits pushed. Auto-starts on login via LaunchAgent.

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

### Apr 19, 2026 @ 11:15 PM — Fixed roundtable Neural Link Error — was timing out at 90s generating 11 agent responses. Increased to 240s.

### Apr 19, 2026 @ 11:20 PM — Fixed Neural Link Error on roundtable — httpx timeout was hardcoded 120s, now uses dynamic timeout param (240s for roundtable)

### Apr 19, 2026 @ 11:24 PM — MILESTONE: Roundtable fully restored. All 11 agents responding. Timeout fixed (hardcoded 120s -> dynamic 240s). Debate room working with colored responses. Room colors yellow->green->blue cycle live.

### Apr 20, 2026 @ 07:33 PM — Doctorbot code intelligence added: find bugs, scan imports, review [file], brainstorm [topic]. OpenClaw placeholder ready for API key. Brainstorm saves to brainstorm/ folder.

### Apr 20, 2026 @ 07:41 PM — MILESTONE: Doctorbot code intelligence fully operational. find bugs (48 files clean), review main.py (3 suggestions), brainstorm pinkslip (7 ideas saved to brainstorm/). OpenClaw placeholder ready.

### Apr 20, 2026 @ 07:43 PM — Memory upgraded: ChromaDB semantic search added alongside SQLite. semantic_search() available for future use in ask_ollama.

### Apr 20, 2026 @ 07:45 PM — PDF bot deployed: auto-generates debate PDFs, /pdf command in HIGA HOUSE, create_youtube_pdf and create_market_pdf available

### Apr 21, 2026 @ 05:30 PM — Pipeline deployed: YouTube scrapes every 6hrs, routes stocks to stockbot, crypto to cryptoid, geopolitics to shaman. /pipeline command for manual trigger. PDF bot auto-generates on debates.

### Apr 22, 2026 @ 06:56 AM — SECURITY: Removed hardcoded Alpaca keys from jarvis_autopilot.py and Telegram token from jarvis_proactive.py. Both now use os.getenv() only. Keys rotated on alpaca.markets and BotFather.

### Apr 22, 2026 @ 09:03 PM — Briefing upgraded: live AP/BBC headlines via fetch.py, real crypto P/L from multi_broker_portfolio, full agent-voice format. Duplicate headlines to fix next session.

### Apr 23, 2026 @ 07:07 PM — Deployed: autonomous_runner.py with batch job queue. /queue, /review, /batches commands live. /brief now sends full agent briefing. Crypto blank fixed in scheduled briefings.

### Apr 23, 2026 @ 07:15 PM — ROADMAP logged: Phase 1 stability, Phase 2 intelligence, Phase 3 content pipeline, Phase 4 HIGASHOP business, Phase 5 expansion. See JARVIS_CONTEXT.md for full plan.

### Apr 25, 2026 @ 10:52 AM — SESSION COMPLETE: Phase 1+2 deployed. bot_memory.py ChromaDB per-bot namespaces, autopilot_scan job type, robowright pitch/batch/trending, jamz beat/set/playlist/mashup, notifications API polling, briefing fixed with real crypto+headlines, autonomous runner /queue /review /batches live, pipeline removed from auto-start, 36 old tasks cleaned, keys.py print removed.

### Apr 26, 2026 @ 09:34 PM — Robowright: pitch command auto-opens iMovie with script+shot list package in ~/Movies/HIGA HOUSE Productions. Jamz: beat command auto-opens GarageBand with BPM setup note in ~/Music/GarageBand Projects. Voice commands: open imovie, open garageband, final cut, logic pro.

### Apr 26, 2026 @ 09:58 PM — SESSION COMPLETE Apr 26: Robowright/Jamz YouTube bypass fixed. Robowright pitch now generates full video scripts + opens iMovie. Jamz beat generates full beat design with Suno/Udio prompts + opens GarageBand. Both save files to clips/ and beats/. BPM auto-extracted for GarageBand setup.

### Apr 26, 2026 @ 10:00 PM — MILESTONE: Robowright fully operational. pitch command generates complete TikTok/Shorts scripts with hook/script/edit notes/audio/caption, saves to clips/, opens iMovie with production package in ~/Movies/HIGA HOUSE Productions/. Jamz generates beat designs with Suno/Udio prompts, saves to beats/, opens GarageBand at correct BPM.

### Apr 27, 2026 @ 06:36 AM — llm_router.py deployed: Gemini 2.0 Flash free tier (1500/day) wired in. Robowright, Jamz, Doctorbot, Pinkslip, Ultron, Higashop, Teacherbot now use Gemini. Ollama fallback always active. Add OPENAI_API_KEY or ANTHROPIC_API_KEY to .env to enable those providers.

### Apr 27, 2026 @ 06:38 PM — pc_control.py deployed: bots can take screenshots, run safe terminal commands, open files in Finder/apps, open last Robowright project in iMovie, open last Jamz beat in GarageBand. Commands: screenshot, run [cmd], open last project, open last beat, health check, git status

### Apr 27, 2026 @ 06:39 PM — doctorbot_vision.py deployed: Doctorbot can screenshot screen, read errors with Gemini Vision, generate fixes, compile test, and push to GitHub. Commands: see and fix, see and fix [file], fix all, write [prompt], apply [draft] to [file], push fix, github diff, screenshot

### Apr 27, 2026 @ 06:42 PM — SESSION COMPLETE Apr 27: doctorbot_vision.py full pipeline deployed. Commands: see and fix, see and fix [file] push, fix all push, write [prompt], apply [draft] to [file], push fix, github diff, screenshot. pc_control.py deployed. llm_router.py with Gemini 2.5 Flash. 23 bak files cleaned. All systems operational.

### Apr 28, 2026 @ 06:58 AM — Fixed: briefing crypto section now force-injected with real data if Ollama leaves it blank. Total portfolio (~3696) shown. Day P/L icon added.

### Apr 28, 2026 @ 06:59 AM — SESSION COMPLETE Apr 28: llm_router Gemini/Ollama logic fixed (inverted condition). Briefing crypto force-inject added. Roundtable creative requests route to Robowright/Jamz. All bots on Ollama. System fully operational.

### Apr 28, 2026 @ 04:48 PM — Doctorbot draft writer deployed: draft improvement [file], draft feature [desc], draft fix [bug], draft summary, list drafts, cat draft [name]. All drafts saved to drafts/ folder for Claude review.

### Apr 28, 2026 @ 10:09 PM — Telegram bot deployed: poll_telegram() polls every 2s, handles /brief /bots /portfolio /crypto /debate /roundtable /draft /health /help and any freeform message as JARVIS chat. Briefings now include code health status and daily draft idea.

### Apr 30, 2026 @ 06:57 AM — Telegram fully operational: chat ID 7343414006 saved to .env. poll_telegram() running in main.py lifespan. Two-way chat active - text @higamacbot anything and JARVIS responds. Commands: /brief /portfolio /crypto /bots /debate /roundtable /draft /health /help

### Apr 30, 2026 @ 07:00 AM — Telegram bot merged: combined old jarvis_telegram_bot.py (trading, indicators, YouTube, British wit, briefings) with new HIGA HOUSE commands (/debate /roundtable /draft /bots /health). Single poll_telegram() runs in main.py lifespan.

### May 02, 2026 @ 05:42 PM — Telegram bot merged: combined old jarvis_telegram_bot.py (trading, indicators, YouTube, British wit, briefings) with new HIGA HOUSE commands (/debate /roundtable /draft /bots /health). Single poll_telegram() runs in main.py lifespan.

### May 03, 2026 @ 02:22 PM — Fixed: jarvis_briefing.py scheduled briefings now call generate_briefing() from briefing_scheduler.py - shows real crypto portfolio instead of blank. Telegram Ollama offline message improved.

### May 03, 2026 @ 11:46 PM — SESSION May 3: jarvis_briefing.py fixed to use generate_briefing(). Telegram Ollama error improved. LaunchAgent updated with proper env loading. JARVIS_CONTEXT.md header updated - repo IS on GitHub. 15 bots online.

### May 03, 2026 @ 11:56 PM — SESSION May 3: Fixed Stockbot startup crash by lazy-loading Alpaca TradingClient instead of creating it at import time. Replaced sys.path.append with sys.path.insert. LaunchAgent startup now succeeds and /api/bots/status reports 15 bots online.
