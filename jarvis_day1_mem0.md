# JARVIS — Day 1: mem0 Integration Plan
# Status: IN PROGRESS (existing layer present; mem0 not yet wired)
# Last updated: 2026-05-10

---

## 1. What Already Exists (confirmed by code inspection)

### memory.py — SQLite + ChromaDB layer
- **SQLite tables**: `conversation` (role, content, timestamp), `preferences` (key, value)
- **ChromaDB collection**: `jarvis_memory` at `./chroma_db/` — cosine-similarity search
- **Functions in use**:
  - `get_memory_context(limit=10)` — returns last N conversation rows (by recency only)
  - `save_conversation(role, content)` — writes to SQLite + ChromaDB
  - `save_preference(key, value)` — writes keyword-triggered user notes
  - `semantic_search(query)` — queries ChromaDB by embedding **but is never called in any request path**
  - `extract_summary(text)` — truncates to 500 chars before storing

### main.py — how memory is currently used
- Line 249: `memory_block = await asyncio.to_thread(memory.get_memory_context)` — injected into every Ollama prompt
- Lines 425-426, 462-463, 589, 637, 663, 744: `memory.save_conversation()` after every reply
- Line 132-148: keyword-triggered `save_preference()` ("remember this", "my name is")
- `semantic_search()` is imported but **never called**

### jarvis_telegram_bot.py — Telegram memory
- Line 261: `mem.save_conversation(user_msg, reply)` after replies — saves to SQLite/ChromaDB
- Does **not** call `get_memory_context()` before replies — Telegram has no memory injection

### bot_memory.py — separate per-bot ChromaDB namespaces
- Independent of memory.py
- Used by clipfarmer pipeline to store clip analysis per bot
- Not part of the mem0 integration path

---

## 2. Current Limitations

| Limitation | Impact |
|---|---|
| `get_memory_context()` returns last 10 rows by timestamp only | Irrelevant old turns get injected; relevant turns from 3 days ago get dropped |
| `semantic_search()` is never called in any request path | ChromaDB embedding layer exists but does nothing at runtime |
| No structured fact extraction | Raw conversation transcripts stored — not "user prefers X" or "user owns BTC" as discrete facts |
| No user_id scoping | Single-user now, but not extensible |
| Telegram bot has no memory injection | Telegram replies have zero context from past conversations |
| Preferences only saved on explicit keyword match | "remember my name is X" works; automatic preference extraction does not |

---

## 3. What mem0 Integration Is Supposed to Add

mem0 (https://mem0.ai) is a managed memory layer with:
- **Auto fact extraction** — turns raw conversation into structured memory cells
  (e.g., "user's name is Higa", "user holds BTC on Webull", "user prefers short briefings")
- **Semantic retrieval before every reply** — `memory.search(query, user_id=...)` replaces the recency dump
- **user_id scoping** — multi-user capable from day one
- **Automatic deduplication and decay** — doesn't re-store facts already known
- **REST API or Python SDK** — can layer on top of existing SQLite as fallback

### What changes in the codebase

| File | Line(s) | Current | After mem0 |
|---|---|---|---|
| `memory.py` | top | — | `from mem0 import MemoryClient; _mem0 = MemoryClient(api_key=...)` |
| `memory.py` | new functions | — | `mem0_add(messages, user_id)`, `mem0_search(query, user_id)` wrappers |
| `main.py` | 249 | `get_memory_context(limit=10)` | `mem0_search(user_msg, user_id="higa")` |
| `main.py` | 425-426 | `save_conversation(role, content)` | `mem0_add([{role, content}], user_id="higa")` |
| `main.py` | 462-463 | same | same |
| `jarvis_telegram_bot.py` | before reply | nothing | `mem0_search(user_msg, user_id="higa_telegram")` |
| `jarvis_telegram_bot.py` | 261 | `save_conversation()` | `mem0_add()` + keep `save_conversation()` as local backup |

### What stays the same
- SQLite `conversation` table — keep as local audit log regardless of mem0
- ChromaDB `jarvis_memory` collection — keep for `semantic_search()` fallback if mem0 is unavailable
- `save_preference()` — keep for explicit keyword triggers
- All bot_memory.py per-bot collections — unrelated, untouched

---

## 4. Recommended Implementation Order

1. **Install**: `pip install mem0ai` in `.venv311` and add `MEM0_API_KEY` to `.env`
2. **Wrap in memory.py**: Add `mem0_add()` and `mem0_search()` with try/except fallback to existing layer
3. **Wire into main.py reply path** (line 249): Replace `get_memory_context()` with `mem0_search()` — single-line swap
4. **Wire into main.py save path** (lines 425-426, 462-463): Add `mem0_add()` alongside existing `save_conversation()`
5. **Wire into Telegram bot**: Add `mem0_search()` injection before Ollama call in Telegram handler
6. **Test**: Send 5 messages about preferences, then a follow-up — confirm mem0 recalls them without full transcript injection
7. **Update JARVIS_CONTEXT.md** with milestone log entry

---

## 5. Day 1 Tracker Status

| Component | Status | Notes |
|---|---|---|
| SQLite conversation memory | ✅ LIVE | Injected into every reply via get_memory_context() |
| ChromaDB semantic storage | ✅ LIVE (partial) | Stores embeddings; semantic_search() never called at runtime |
| Per-bot ChromaDB namespaces | ✅ LIVE | bot_memory.py, used by clipfarmer |
| mem0 SDK installed | ❌ NOT STARTED | No mem0 import anywhere in repo |
| mem0 search before replies | ❌ NOT STARTED | main.py still uses recency dump |
| mem0 add after replies | ❌ NOT STARTED | save_conversation() only |
| Telegram memory injection | ❌ NOT STARTED | jarvis_telegram_bot.py has no pre-reply context |
| semantic_search() wired in | ❌ NOT STARTED | Function exists, never called |

**Overall Day 1 Status: IN PROGRESS — existing memory layer is live but mem0 is not integrated.**
