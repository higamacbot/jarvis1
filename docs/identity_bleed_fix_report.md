# Identity Bleed Fix Report
Generated: 2026-05-18

## Root Cause

Two issues in `main.py` `ask_ollama()` caused all 5 agents to bleed identity:

**1. Hardcoded `JARVIS:` completion token (line 317)**
qwen3:8b is a text-completion model, not a chat model. The prompt ends with `JARVIS:`, which the model interprets as "continue as JARVIS." Any `system_override` persona is overridden by this token — the model pattern-matches the last word before its turn, not the system instruction.

**2. Crypto/trade context injected into all agents (lines 310-313)**
`CRYPTO: {market_str}` and `RECENT TRADES: {trade_hist}` were injected into every prompt regardless of bot identity. robowright, jamz, technoid all generated crypto-themed responses because it dominated the context.

**3. No persona lock in system prompt (none existed)**
Even when `system_override=bot.SYSTEM_PROMPT` was passed, there was no explicit instruction telling the model NOT to be JARVIS. With the JARVIS: completion token, the model ignored the system_override.

**4. `bots/router.py` fallthrough (line 1217) passed no `bot_name`**
All 4 non-keyword-gated agents (pinkslip, doctorbot, robowright, jamz) fall through to:
```python
return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT)
```
Without `bot_name`, `ask_ollama` used full JARVIS context for all of them.

---

## Files Changed

### `main.py`

**Signature** — added `bot_name: str = ""` parameter:
```python
# BEFORE
async def ask_ollama(user_msg, extra_context="", timeout=240.0, system_override=None) -> str:

# AFTER
async def ask_ollama(user_msg, extra_context="", timeout=240.0, system_override=None, bot_name="") -> str:
    _market_bots = {"jarvisbot", "stockbot", "cryptoid"}
    _use_market_ctx = not bot_name or bot_name in _market_bots
    ...
    trade_hist = get_trade_history(limit=5) if _use_market_ctx else ""
```

**Prompt template** — persona lock + dynamic completion token + conditional crypto context:
```python
_persona_lock = (
    f"\n[YOU ARE {bot_name.upper()}. RESPOND ONLY AS {bot_name.upper()}. DO NOT USE THE NAME JARVIS.]\n"
    if bot_name and bot_name not in _market_bots else ""
)
_completion_token = f"{bot_name.upper()}:" if bot_name and bot_name not in _market_bots else "JARVIS:"
_live_data = (
    f"CRYPTO: {market_str}\nSYSTEM: {system_stats}"
    if _use_market_ctx else f"SYSTEM: {system_stats}"
)
_trade_section = f"--- RECENT TRADES ---\n{trade_hist}\n---" if _use_market_ctx else ""
```

### `bots/router.py`

**Technoid handler** (line 670): added `bot_name="technoid"`:
```python
# BEFORE
return await ask_fn(tech_prompt, system_override=technoid.SYSTEM_PROMPT)
# AFTER
return await ask_fn(tech_prompt, system_override=technoid.SYSTEM_PROMPT, bot_name="technoid")
```

**Fallthrough line** (line 1217): added `bot_name=bot_id`:
```python
# BEFORE
return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT)
# AFTER
return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT, bot_name=bot_id)
```

---

## Verification

### Logic unit test (code-level, no server required)

| bot_name    | use_market | persona_lock | completion_token | has_trades | has_crypto |
|-------------|------------|--------------|------------------|------------|------------|
| (default)   | True       | False        | JARVIS:          | True       | True       |
| jarvisbot   | True       | False        | JARVIS:          | True       | True       |
| stockbot    | True       | False        | JARVIS:          | True       | True       |
| cryptoid    | True       | False        | JARVIS:          | True       | True       |
| pinkslip    | False      | **True**     | **PINKSLIP:**    | False      | False      |
| doctorbot   | False      | **True**     | **DOCTORBOT:**   | False      | False      |
| robowright  | False      | **True**     | **ROBOWRIGHT:**  | False      | False      |
| jamz        | False      | **True**     | **JAMZ:**        | False      | False      |
| technoid    | False      | **True**     | **TECHNOID:**    | False      | False      |

All 4 JARVIS-path bots: unchanged. All 5 identity-bleed bots: persona-locked, crypto-stripped, correct token.

### Live WS test (pre-restart baseline — old code)

Server was running `python main.py` without `--reload`. File changes are on disk but not yet active.
Results below are the **pre-fix baseline** confirming the bleed existed:

| agent      | jarvis_bleed | crypto_bleed | elapsed |
|------------|-------------|--------------|---------|
| pinkslip   | no          | no           | 133.2s  |
| doctorbot  | **YES**     | no           | 35.2s   |
| robowright | no          | **YES**      | 90.4s   |
| jamz       | no          | **YES**      | 70.0s   |
| technoid   | no          | **YES**      | 99.8s   |

**A server restart is required to activate the fix for live verification.**
After restart, re-run: `python3 docs/_bench_identity_verify.py`

---

## Remaining Risks

**1. qwen3:8b is still a completion model**
The persona lock (`[YOU ARE PINKSLIP...]`) is an instruction token injected into the prompt. It helps, but completion models follow the completion token more than instructions. If the fix reduces but doesn't eliminate bleed, the only full solution is switching to a chat-mode API (e.g., `/api/chat` instead of `/api/generate` in Ollama) with proper role separation.

**2. ROUNDTABLE WS timeout is unchanged**
Not addressed in this fix. Root cause: uvicorn/OS-level WS timeout fires during ~60-120s Ollama inference for multi-agent coordination calls.

**3. Shaman/libmom/magadad have no bot module**
They're not in BOT_MAP and fall through to the "Unknown bot" path. Identity is undefined for these — not a regression from this fix, and not in scope.

**4. Doctorbot's JARVIS_CONTEXT.md reference**
`bots/doctorbot.py` SYSTEM_PROMPT references JARVIS_CONTEXT.md extensively. The persona lock overrides JARVIS identity at the prompt level, but if doctorbot's system prompt itself imports JARVIS framing, the persona lock may need strengthening for doctorbot specifically.

**5. Memory/rule-recall fast-path is unaffected**
Lines 259-290 in `main.py` handle rule-recall queries with a hardcoded `JARVIS:` completion token, bypassing `bot_name`. This path is only reachable for the main JARVIS flow (no `system_override`), so no regression — but worth noting.
