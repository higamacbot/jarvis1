# JARVIS Upgrade Tracker
# Last updated: 2026-05-10

---

## How to read this file
- ✅ COMPLETE — confirmed live in runtime code
- 🔄 IN PROGRESS — partially implemented; not fully wired end-to-end
- ❌ NOT STARTED — no code exists yet

---

## Phase 1 — Stability & Foundation ✅ COMPLETE
- FastAPI server on port 8000, 15 bots online
- multi_broker_portfolio.py — real portfolio ($3,696 total) across Webull/Robinhood/Coinbase/Acorns/Alpaca/Kraken
- SQLite + ChromaDB memory layer (memory.py)
- Telegram bot: /brief /bots /portfolio /crypto /debate /roundtable /help
- Bot orchestrator with persistent status, task queue
- Doctorbot code intelligence (scan_for_bugs, review, brainstorm)
- LaunchAgent auto-start on login (Python 3.11 venv)

## Phase 2 — Intelligence & Data ✅ COMPLETE
- llm_router.py: Gemini Flash / Ollama routing per bot
- Per-bot ChromaDB namespaces (bot_memory.py)
- pinkslip_odds.py: live sports odds via the-odds-api.com
- obsidian_brain.py: all bots can write to Obsidian vault
- jarvis_state.py: shared state bus, portfolio/crypto/system cached every 60s
- Technoid: real psutil metrics; Ultron: real repo health; Higashop: inventory JSON

## Phase 3 — Content Pipeline 🔄 IN PROGRESS
- clipfarmer.py: YouTube clip detection, Whisper transcript, ChromaDB ingestion, report.md ✅
- TikTok URL support (all formats: @user/video/, t/, vm.tiktok.com/) ✅
- robowright_assets.py: asset tracking ✅
- jamz_midi.py: MIDI beat triggers ✅
- openai-whisper install for TikTok Tier 3 transcript: ❌ NOT DONE (falls through to "none" method)
- Verify analysis.json write path in _analyze_clips(): ❌ NEEDS RETEST with real video

## Phase 4 — Memory Upgrade (mem0) 🔄 IN PROGRESS
See: jarvis_day1_mem0.md for full breakdown.

### What exists now (confirmed live):
- SQLite conversation memory — injected into every Ollama reply via get_memory_context(limit=10)
- ChromaDB semantic storage — embeddings saved; semantic_search() NOT called at runtime
- Keyword-triggered preference saving ("remember X", "my name is X")
- Telegram bot saves conversations to SQLite/ChromaDB after replies
- Telegram bot does NOT inject any memory context before replies

### What is NOT done yet:
- mem0 SDK not installed (no mem0 import anywhere in repo)
- mem0 semantic search not wired into main.py reply path
- mem0 add not wired into main.py save path
- Telegram has no pre-reply memory injection
- semantic_search() in memory.py exists but is never called in any request path

**Day 1 Status: IN PROGRESS — existing memory layer is live but mem0 is not integrated.**

### Next step for mem0 Day 1:
1. `pip install mem0ai` in .venv311
2. Add `MEM0_API_KEY` to .env
3. Add `mem0_add()` / `mem0_search()` wrappers in memory.py with SQLite fallback
4. Wire `mem0_search()` into main.py line 249 (replace get_memory_context recency dump)
5. Wire `mem0_add()` alongside save_conversation() at main.py lines 425-426, 462-463
6. Wire search + add into jarvis_telegram_bot.py handler

## Phase 5 — War-Room Briefing 🔄 IN PROGRESS
- briefing_scheduler.py: deterministic section builders, single Ollama call (TOP OF MIND) ✅
- Bigram overlap headline dedup + driver-label pre-bucketing ✅
- _classify_driver() geopolitical/macro labeling ✅
- PINKSLIP section with sport labels, odds stripped ✅
- BOT PULSE: driver label in JARVIS line, matchup in PINKSLIP line ✅
- 2-sentence TOP OF MIND enforcement with deterministic s2 fallback ✅
- Pinkslip live odds wired into /brief morning and evening ✅
- Scheduled sends (5 AM / 5 PM CST) ✅

## Phase 6 — HIGASHOP & Business Tools ❌ NOT STARTED
- Higashop inventory JSON is live, but e-commerce automation not built
- No payment/order pipeline yet

## Phase 7 — Expansion ❌ NOT STARTED
- Multi-user support (user_id scoping in memory layer)
- Web dashboard upgrade
- External API integrations beyond current set

---

## Pending / Known Issues (as of 2026-05-10)
- openai-whisper not installed in .venv311 — TikTok transcript Tier 3 silently skips to "none"
- analysis.json write path in clipfarmer._analyze_clips() not re-verified after diagnostic logging added
- briefing_scheduler.py and bots/router.py have uncommitted changes (router TikTok pattern, main.py _HAS_CLIP_URL)
- mem0 Day 1 is the next implementation priority
