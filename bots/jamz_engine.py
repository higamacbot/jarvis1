import os
import httpx
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"
BEATS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "beats")
os.makedirs(BEATS_DIR, exist_ok=True)

async def _ask(prompt: str, timeout: float = 60.0) -> str:
    try:
        async with httpx.AsyncClient(timeout=timeout) as h:
            r = await h.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
            return r.json().get("response", "").strip()
    except Exception as e:
        return f"Jamz error: {e}"

def _save_note(title: str, content: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe = title.replace(" ", "_")[:40]
    filepath = os.path.join(BEATS_DIR, f"{timestamp}_{safe}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n{content}")
    return filepath

async def design_beat(vibe: str) -> str:
    prompt = f"""You are Jamz.
Design a beat for: {vibe}

Return:
BEAT CONCEPT:
BPM:
KEY:
MOOD:
DRUMS:
BASS:
LEAD:
SUNO PROMPT:
UDIO PROMPT:
"""
    result = await _ask(prompt)
    path = _save_note(vibe, result)
    return result + f"\n\nSaved: {path}"

async def plan_dj_set(event: str, duration_mins: int = 120) -> str:
    prompt = f"""You are Jamz.
Plan a {duration_mins}-minute DJ set for: {event}

Return:
SET CONCEPT:
ENERGY ARC:
TRACK FLOW:
TRANSITION NOTES:
BACKUP TRACKS:
"""
    result = await _ask(prompt, timeout=90.0)
    path = _save_note(f"djset_{event}", result)
    return result + f"\n\nSaved: {path}"

async def build_playlist(mood: str, n_tracks: int = 10) -> str:
    prompt = f"""You are Jamz.
Build a {n_tracks}-track playlist for: {mood}

For each track include:
- Track
- BPM
- Key
- Why it fits
- Copyright risk
"""
    return await _ask(prompt)

async def mashup_concept(track1: str, track2: str) -> str:
    prompt = f"""You are Jamz.
Plan a mashup between:
Track A: {track1}
Track B: {track2}

Include:
- BPM compatibility
- Key compatibility
- Structure
- Transition point
- Tool suggestions
- Copyright risk
"""
    return await _ask(prompt)
