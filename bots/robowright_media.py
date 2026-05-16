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


# ── Carousel / Storyboard pipeline ──────────────────────────────────────────

def _carousel_fallback(topic: str, n_slides: int, platform: str, source: str = "") -> dict:
    """Deterministic carousel structure when Ollama returns sparse or malformed JSON."""
    import re as _re
    aspect = "1:1" if platform == "instagram" else "9:16"
    text = source if source.strip() else topic
    sentences = [s.strip() for s in _re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 15]
    n_content = max(1, n_slides - 2)
    slides = []
    for i in range(n_content):
        body = sentences[i] if i < len(sentences) else f"Key point {i + 1} about {topic}"
        headline = (body[:42].rsplit(" ", 1)[0] if len(body) > 42 else body)
        slides.append({
            "number": i + 1,
            "headline": headline,
            "body": body,
            "image_prompt": f"{aspect} clean minimal graphic: {headline}",
            "duration_note": "clear and readable",
        })
    return {
        "title": topic[:60],
        "hook": {
            "headline": f"Here's what you need to know about {topic}",
            "subtext": sentences[0] if sentences else f"A guide to {topic}",
            "image_prompt": f"{aspect} bold eye-catching hook slide about: {topic}",
        },
        "slides": slides,
        "caption": f"Everything about {topic[:40]} 👇 #contentcreator #aitools",
        "cta": "Follow for more",
    }


async def make_carousel(
    topic: str,
    n_slides: int = 7,
    platform: str = "instagram",
    transcript: str = "",
    context_hint: str = "",
) -> str:
    """
    One Ollama call → carousel.json + carousel.md + image_prompts.txt.
    Returns a short summary with saved path and preview.
    """
    import json as _json
    import re as _re

    source_label = "transcript" if transcript.strip() else "topic"
    source_content = transcript.strip() if transcript.strip() else topic
    aspect = "1:1" if platform == "instagram" else "9:16"
    handoff_ids = []

    try:
        from loop_memory import get_pending_handoffs
        pending_handoffs = get_pending_handoffs("robowright")
    except Exception as e:
        print(f">> ROBOWRIGHT CAROUSEL: handoff read failed: {e}")
        pending_handoffs = []

    if pending_handoffs:
        handoff_ids = [int(h.get("id", 0)) for h in pending_handoffs if h.get("id")]
        handoff_lines = []
        for handoff in pending_handoffs[:2]:
            topic_note = str(handoff.get("topic", "")).strip()
            context_note = str(handoff.get("context", "")).strip()
            if topic_note or context_note:
                handoff_lines.append(
                    f"- {topic_note or 'untitled'}: {context_note}"
                )
        if handoff_lines:
            handoff_text = "\n".join(handoff_lines)
            source_content = f"{source_content}\n\nClipfarmer handoff context:\n{handoff_text}".strip()
            if source_label == "topic":
                source_label = "topic + handoff"

    slug = _re.sub(r"[^a-z0-9]+", "_", topic.lower())[:30].strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = os.path.join(CLIPS_DIR, f"carousel_{timestamp}_{slug}")
    os.makedirs(out_dir, exist_ok=True)

    source_block = (
        f"Source material ({source_label}):\n" + source_content[:2000]
        if source_content.strip() and source_content.strip() != topic
        else ""
    )
    pattern_block = f"Prior successful pattern:\n{context_hint}\n\n" if context_hint.strip() else ""
    prompt = f"""You are Robowright, a short-form carousel content strategist.
Create a {n_slides}-slide carousel for {platform.upper()} about: {topic}
{pattern_block}{source_block}

Return ONLY a valid JSON object, no markdown, no extra text:
{{
  "title": "short punchy carousel title",
  "hook": {{
    "headline": "Hook line — scroll-stopping, under 8 words",
    "subtext": "1 sentence supporting the hook",
    "image_prompt": "Detailed {aspect} image prompt for the hook slide visual"
  }},
  "slides": [
    {{
      "number": 1,
      "headline": "Slide headline, under 6 words",
      "body": "1-2 sentence slide body",
      "image_prompt": "Detailed {aspect} image prompt for this slide",
      "duration_note": "e.g. pause here, fast swipe, let it breathe"
    }}
  ],
  "caption": "IG/TikTok caption with hashtags, under 150 chars",
  "cta": "Final slide CTA text, under 10 words"
}}

Include exactly {max(1, n_slides - 2)} content slides in the slides array.
Hook and CTA are separate fields, not inside slides.
Make image_prompts specific and visual. Keep all text punchy and platform-native."""

    raw = ""
    try:
        r = httpx.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False, "think": False},
            timeout=120.0,
        )
        if r.status_code == 200:
            raw = r.json().get("response", "").strip()
            print(f">> ROBOWRIGHT CAROUSEL: Ollama OK, raw len={len(raw)}")
    except Exception as e:
        print(f">> ROBOWRIGHT CAROUSEL: Ollama error: {e}")

    data = None
    if raw:
        # qwen3 sometimes inserts a stray " " token before field names (e.g. { " "number": 3)
        cleaned = _re.sub(r'"\s*"(\w)', r'"\1', raw)
        m = _re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                data = _json.loads(m.group(0))
            except _json.JSONDecodeError as je:
                print(f">> ROBOWRIGHT CAROUSEL: JSON parse failed: {je}")

    if not data or not data.get("hook") or not data.get("slides"):
        print(">> ROBOWRIGHT CAROUSEL: sparse output — applying deterministic fallback")
        data = _carousel_fallback(topic, n_slides, platform, source_content)

    # Patch any slides missing image_prompts
    for slide in data.get("slides", []):
        if not slide.get("image_prompt"):
            slide["image_prompt"] = f"{aspect} clean bold graphic: {slide.get('headline', topic)}"

    carousel = {
        "title": data.get("title", topic),
        "platform": platform,
        "n_slides": n_slides,
        "hook": data.get("hook", {}),
        "slides": data.get("slides", []),
        "caption": data.get("caption", ""),
        "cta": data.get("cta", ""),
    }

    # ── carousel.json ──────────────────────────────────────────────────────
    json_path = os.path.join(out_dir, "carousel.json")
    with open(json_path, "w", encoding="utf-8") as f:
        _json.dump(carousel, f, indent=2, ensure_ascii=False)

    # ── carousel.md ────────────────────────────────────────────────────────
    md = [
        f"# Carousel — {carousel['title']}",
        "",
        f"**Platform:** {platform}  ",
        f"**Slides:** {n_slides}  ",
        f"**Source:** {source_label}  ",
        "",
        "---",
        "",
        "## HOOK",
        f"**Headline:** {carousel['hook'].get('headline', '')}",
        f"**Subtext:** {carousel['hook'].get('subtext', '')}",
        f"**Image Prompt:** `{carousel['hook'].get('image_prompt', '')}`",
        "",
    ]
    for slide in carousel["slides"]:
        md += [
            f"## Slide {slide.get('number', '')} — {slide.get('headline', '')}",
            slide.get("body", ""),
            "",
            f"**Image Prompt:** `{slide.get('image_prompt', '')}`",
            f"**Note:** {slide.get('duration_note', '')}",
            "",
        ]
    md += [
        "## CTA",
        carousel["cta"],
        "",
        "## Caption",
        carousel["caption"],
        "",
        "---",
        f"_Generated by HIGA HOUSE Robowright — {out_dir}_",
    ]
    md_path = os.path.join(out_dir, "carousel.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    # ── image_prompts.txt ──────────────────────────────────────────────────
    prompts_lines = [f"[HOOK] {carousel['hook'].get('image_prompt', '')}"]
    for slide in carousel["slides"]:
        prompts_lines.append(f"[SLIDE {slide.get('number', '')}] {slide.get('image_prompt', '')}")
    prompts_lines.append(f"[CTA] {aspect} bold text card: {carousel['cta']}")
    prompts_path = os.path.join(out_dir, "image_prompts.txt")
    with open(prompts_path, "w", encoding="utf-8") as f:
        f.write("\n".join(prompts_lines) + "\n")

    if handoff_ids:
        try:
            from loop_memory import consume_handoff
            for handoff_id in handoff_ids:
                consume_handoff(handoff_id)
        except Exception as e:
            print(f">> ROBOWRIGHT CAROUSEL: handoff consume failed: {e}")

    # ── Return summary ─────────────────────────────────────────────────────
    hook_line = carousel["hook"].get("headline", "")
    slide_preview = "\n".join(
        f"  Slide {s.get('number', '')}: {s.get('headline', '')}"
        for s in carousel["slides"][:3]
    )
    return (
        f"Carousel ready — {n_slides} slides for {platform.upper()}\n"
        f"Title: {carousel['title']}\n"
        f"\nHook: {hook_line}\n"
        f"{slide_preview}\n"
        f"  ...\n"
        f"CTA: {carousel['cta']}\n"
        f"\nCaption: {carousel['caption']}\n"
        f"\nSaved: {out_dir}\n"
        f"  carousel.json  |  carousel.md  |  image_prompts.txt"
    )
