"""
llm_router.py — HIGA HOUSE Multi-Provider LLM Router
Free-first routing: Ollama -> Gemini -> OpenAI -> Anthropic
Each provider only activates if its API key exists in .env
"""
import os, httpx
from dotenv import load_dotenv
load_dotenv()

OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_MODEL  = "qwen3:8b"
GEMINI_KEY    = os.getenv("GEMINI_API_KEY")
OPENAI_KEY    = os.getenv("OPENAI_API_KEY")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

# Which provider each bot prefers
BOT_PROVIDER = {
    "jarvisbot":   "ollama",
    "stockbot":    "ollama",
    "cryptoid":    "ollama",
    "doctorbot":   "ollama",
    "robowright":  "ollama",
    "jamz":        "ollama",
    "roundtable":  "ollama",
    "debateroom":  "ollama",
    "shaman":      "ollama",
    "libmom":      "ollama",
    "magadad":     "ollama",
    "pinkslip":    "ollama",
    "ultron":      "ollama",
    "higashop":    "ollama",
    "technoid":    "ollama",
    "teacherbot":  "ollama",
}

async def ask_ollama(prompt: str, system: str = "", timeout: float = 120.0) -> str:
    full = f"{system}\n\n{prompt}" if system else prompt
    try:
        async with httpx.AsyncClient(timeout=timeout) as h:
            r = await h.post(OLLAMA_URL, json={
                "model": OLLAMA_MODEL, "prompt": full, "stream": False
            })
            return r.json().get("response", "").strip()
    except Exception as e:
        return f"[Ollama error: {e}]"

async def ask_gemini(prompt: str, system: str = "", timeout: float = 30.0) -> str:
    if not GEMINI_KEY:
        print(">> LLM ROUTER: No Gemini key, falling back to Ollama")
        return await ask_ollama(prompt, system, timeout)
    full = f"{system}\n\n{prompt}" if system else prompt
    try:
        async with httpx.AsyncClient(timeout=timeout) as h:
            r = await h.post(
                f"{GEMINI_URL}?key={GEMINI_KEY}",
                json={"contents": [{"parts": [{"text": full}]}]}
            )
            data = r.json()
            if "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                print(f">> GEMINI ERROR: {data.get('error', data)}")
                return await ask_ollama(prompt, system, timeout)
    except Exception as e:
        print(f">> GEMINI ERROR: {e} — falling back to Ollama")
        return await ask_ollama(prompt, system, timeout)

async def ask_openai(prompt: str, system: str = "", model: str = "gpt-4o-mini") -> str:
    if not OPENAI_KEY:
        return await ask_ollama(prompt, system)
    try:
        async with httpx.AsyncClient(timeout=30.0) as h:
            r = await h.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}"},
                json={"model": model, "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ]}
            )
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f">> OPENAI ERROR: {e} — falling back to Ollama")
        return await ask_ollama(prompt, system)

async def ask_anthropic(prompt: str, system: str = "", model: str = "claude-haiku-4-5-20251001") -> str:
    if not ANTHROPIC_KEY:
        return await ask_ollama(prompt, system)
    try:
        async with httpx.AsyncClient(timeout=30.0) as h:
            r = await h.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01"
                },
                json={"model": model, "max_tokens": 1024,
                      "system": system,
                      "messages": [{"role": "user", "content": prompt}]}
            )
            return r.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f">> ANTHROPIC ERROR: {e} — falling back to Ollama")
        return await ask_ollama(prompt, system)

async def ask(
    prompt: str,
    system: str = "",
    bot_id: str = "jarvisbot",
    provider: str = None,
    timeout: float = 120.0
) -> str:
    """
    Main entry point. Routes to best available provider.
    Falls back to Ollama if preferred provider unavailable.
    """
    p = provider or BOT_PROVIDER.get(bot_id, "ollama")
    print(f">> LLM ROUTER: {bot_id} -> {p}")

    if p == "gemini" and GEMINI_KEY:
        return await ask_gemini(prompt, system, timeout)
    elif p == "openai" and OPENAI_KEY:
        return await ask_openai(prompt, system)
    elif p == "anthropic" and ANTHROPIC_KEY:
        return await ask_anthropic(prompt, system)
    else:
        return await ask_ollama(prompt, system, timeout)

def get_provider_status() -> dict:
    return {
        "ollama":    "✅ always available (local free)",
        "ollama":    "✅ ready (free 1500/day)" if GEMINI_KEY else "❌ add GEMINI_API_KEY to .env",
        "openai":    "✅ ready" if OPENAI_KEY else "❌ add OPENAI_API_KEY to .env",
        "anthropic": "✅ ready" if ANTHROPIC_KEY else "❌ add ANTHROPIC_API_KEY to .env",
    }
