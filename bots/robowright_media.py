import os
import httpx
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"
CLIPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

async def _ask(prompt: str, timeout: float = 90.0) -> str:
    import httpx as _httpx
    try:
        async with _httpx.AsyncClient(timeout=timeout) as h:
            r = await h.post(OLLAMA_URL, json={"model": MODEL, "prompt": prompt, "stream": False})
            data = r.json()
            return data.get("response", "").strip()
    except Exception as e:
        # Fallback: try sync request
        try:
            import urllib.request, json as _json
            req = urllib.request.Request(
                OLLAMA_URL,
                data=_json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                return _json.loads(resp.read()).get("response", "").strip()
        except Exception as e2:
            return f"Robowright error: {e} | fallback: {e2}"

def save_script(title: str, content: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_title = title.replace(" ", "_")[:40]
    filepath = os.path.join(CLIPS_DIR, f"{timestamp}_{safe_title}.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(content)
    return filepath

async def pitch_video_concept(topic: str, platform: str = "tiktok") -> str:
    prompt = f"""You are Robowright, a viral video strategist.
Make a concise, production-ready concept for: {topic}
Platform: {platform}

Return:
CONCEPT:
HOOK:
SCRIPT:
EDIT NOTES:
AUDIO:
CAPTION:
BEST POST TIME:
"""
    result = await _ask(prompt)
    path = save_script(topic, result)
    return result + f"\n\nSaved: {path}"

async def find_trending_audio(niche: str = "finance") -> str:
    prompt = f"""You are Robowright.
Suggest 5 trending audio styles for {niche} content.
Include:
- sound style
- why it works
- royalty-free direction
- example use
"""
    return await _ask(prompt)

async def batch_content_plan(theme: str, n_videos: int = 5) -> str:
    prompt = f"""You are Robowright.
Plan a {n_videos}-video content batch for: {theme}

Return:
SERIES NAME:
FORMAT:
For each video:
- Title
- Hook
- Length
- Key visual
- Posting note
"""
    result = await _ask(prompt, timeout=90.0)
    path = save_script(f"batch_plan_{theme[:30]}", result)
    return result + f"\n\nSaved: {path}"
