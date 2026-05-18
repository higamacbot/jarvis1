"""
clipfarmer.py — YouTube / TikTok → short-form clip pipeline.

Pipeline: yt-dlp download → timestamped transcript → Ollama moment selection → ffmpeg cut.
Transcript sources tried in order: YouTube transcript API → yt-dlp subtitles → local Whisper.
Falls back to equal-segment split when no transcript is available.
"""
import os
import re
import json
import subprocess
from typing import Optional, List, Dict, Tuple

FFMPEG  = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3:8b"
CLIPS_BASE   = os.path.expanduser("~/Movies/HIGA HOUSE Clips")


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_youtube(url: str) -> bool:
    return bool(re.search(r'(?:youtube\.com|youtu\.be)', url, re.IGNORECASE))


def _extract_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else re.sub(r"[^A-Za-z0-9_-]", "_", url)[-20:]


def _is_tiktok_shortlink(url: str) -> bool:
    return bool(re.search(r'https?://(?:www\.)?tiktok\.com/t/|https?://vm\.tiktok\.com/', url, re.IGNORECASE))


def _resolve_redirect_url(url: str) -> str:
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.6 Mobile/15E148 Safari/604.1"
        ),
        "Referer": "https://www.tiktok.com/",
    }
    with httpx.Client(follow_redirects=True, headers=headers, timeout=15.0) as client:
        response = client.get(url)
        response.raise_for_status()
        return str(response.url)


def _normalize_clip_url(url: str, resolver=None) -> Tuple[str, str]:
    """Expand supported shortlinks before handing off to yt-dlp."""
    if not _is_tiktok_shortlink(url):
        return url, ""
    resolver = resolver or _resolve_redirect_url
    try:
        resolved = resolver(url)
    except Exception as exc:
        return url, f"redirect resolution failed: {exc}"
    if not resolved or _is_tiktok_shortlink(resolved):
        return url, "redirect resolution failed: unresolved shortlink"
    return resolved, ""


def _classify_download_error(exc_str: str) -> Tuple[str, str]:
    """Returns (error_kind, user_hint) from a yt-dlp exception string."""
    s = exc_str.lower()
    # Check bot detection before auth — "sign in to confirm you're not a bot" is bot detection
    if any(p in s for p in ("not a bot", "captcha", "robot", "confirm you")):
        return "bot_detection", "TikTok bot detection triggered — try the full video URL (tiktok.com/@user/video/...)"
    # Check geo before generic unavailable — "not available in your country" is geo
    if any(p in s for p in ("your country", "not available in", "geo", "region")):
        return "geo", "video appears geo-restricted"
    # Check network before generic unavailable — "503 Service Unavailable" is a network error
    if any(p in s for p in ("network", "connection", "timeout", "ssl", "http error")):
        return "network", "network error during download — check your connection"
    if any(p in s for p in ("private", "not available", "unavailable", "removed", "deleted")):
        return "unavailable", "video is private, deleted, or unavailable"
    # "log in" (space) and "login" (no space) both appear in yt-dlp messages
    if any(p in s for p in ("log in", "login", "sign in", "authentication", "age-restricted")):
        return "auth_required", "TikTok requires login — try a public post URL"
    if any(p in s for p in ("copyright", "blocked", "takedown")):
        return "blocked", "video blocked due to copyright"
    if "unsupported url" in s:
        return "unsupported", "URL format not supported by yt-dlp"
    return "unknown", "check server console for details"


def _download_video(url: str, out_dir: str) -> Tuple[Optional[str], str, int, str]:
    """yt-dlp download. Returns (local_path, title, duration_secs, error_detail)."""
    try:
        import yt_dlp
        ydl_opts = {
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": os.path.join(out_dir, "source.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
        if not _is_youtube(url):
            # TikTok combined streams don't support format merging.
            # cookiesfrombrowser fingerprints Chrome headers even when 0 cookies
            # are extracted — sufficient to pass TikTok bot detection.
            ydl_opts["format"] = "best[ext=mp4]/best"
            ydl_opts["cookiesfrombrowser"] = ("chrome",)
            ydl_opts["retries"] = 3
            ydl_opts["fragment_retries"] = 3
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title    = info.get("title", "untitled")
            duration = int(info.get("duration", 0))
        for ext in ("mp4", "mkv", "webm"):
            path = os.path.join(out_dir, f"source.{ext}")
            if os.path.isfile(path):
                return path, title, duration, ""
        return None, title, duration, "file not found after download"
    except Exception as e:
        print(f">> CLIPFARMER: download failed: {e}")
        return None, "", 0, str(e)


def _get_transcript(url: str, source_path: str) -> Tuple[List[Dict], str]:
    """
    Fetch transcript segments using the best available method.
    Returns (segments, method) where method is one of:
      "youtube_api" | "yt_dlp_subs" | "whisper" | "none"
    """
    # ── Tier 1: YouTube Transcript API (YouTube only) ─────────────────────────
    if _is_youtube(url):
        video_id = _extract_video_id(url)
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            ytt = YouTubeTranscriptApi()
            fetched = ytt.fetch(video_id)
            segs = [{"text": s.text, "start": s.start, "duration": s.duration}
                    for s in fetched]
            if segs:
                print(f">> CLIPFARMER: transcript via youtube_api ({len(segs)} segments)")
                return segs, "youtube_api"
        except Exception as e:
            print(f">> CLIPFARMER: youtube_api failed: {e}")

    # ── Tier 2: yt-dlp subtitles (any platform) ───────────────────────────────
    try:
        import yt_dlp
        sub_dir = os.path.dirname(source_path)
        ydl_opts = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en", "en-US", "en-GB"],
            "subtitlesformat": "vtt",
            "skip_download": True,
            "outtmpl": os.path.join(sub_dir, "subs.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # Find any .vtt file dropped in sub_dir
        vtt_files = [f for f in os.listdir(sub_dir) if f.endswith(".vtt")]
        if vtt_files:
            vtt_path = os.path.join(sub_dir, vtt_files[0])
            segs = _parse_vtt(vtt_path)
            if segs:
                print(f">> CLIPFARMER: transcript via yt_dlp_subs ({len(segs)} segments, {vtt_files[0]})")
                return segs, "yt_dlp_subs"
    except Exception as e:
        print(f">> CLIPFARMER: yt_dlp_subs failed: {e}")

    # ── Tier 3: local Whisper ─────────────────────────────────────────────────
    try:
        import whisper
        print(f">> CLIPFARMER: loading Whisper base model…")
        model = whisper.load_model("base")
        print(f">> CLIPFARMER: transcribing with Whisper…")
        result = model.transcribe(source_path, fp16=False)
        segs = [
            {"text": s["text"].strip(), "start": s["start"],
             "duration": s["end"] - s["start"]}
            for s in result.get("segments", [])
            if s.get("text", "").strip()
        ]
        if segs:
            print(f">> CLIPFARMER: transcript via whisper ({len(segs)} segments)")
            return segs, "whisper"
        print(">> CLIPFARMER: Whisper returned no segments")
    except ImportError:
        print(">> CLIPFARMER: openai-whisper not installed — skipping Whisper fallback")
    except Exception as e:
        print(f">> CLIPFARMER: Whisper failed: {e}")

    print(">> CLIPFARMER: no transcript available — will use equal-split")
    return [], "none"


def _parse_vtt(path: str) -> List[Dict]:
    """Parse a WebVTT file into segment dicts. Returns [] on any parse failure."""
    try:
        segs = []
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Each cue block: timestamp line + text line(s)
        cue_re = re.compile(
            r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})[^\n]*\n([\s\S]*?)(?=\n\n|\Z)',
            re.MULTILINE,
        )
        for m in cue_re.finditer(content):
            start_str, end_str, text_block = m.group(1), m.group(2), m.group(3)
            text = re.sub(r'<[^>]+>', '', text_block).strip()  # strip VTT inline tags
            if not text or text.startswith("WEBVTT") or text.startswith("NOTE"):
                continue

            def _ts(s: str) -> float:
                h, mi, sec = s.split(":")
                return int(h) * 3600 + int(mi) * 60 + float(sec)

            start = _ts(start_str)
            end   = _ts(end_str)
            segs.append({"text": text, "start": start, "duration": max(0.1, end - start)})
        return segs
    except Exception as e:
        print(f">> CLIPFARMER: VTT parse failed: {e}")
        return []


def _build_summary(segments: List[Dict], max_chars: int = 3000) -> str:
    """Collapse timestamped segments into ~15s chunks for LLM context."""
    lines, chunk_start, chunk_words = [], None, []
    for seg in segments:
        t = seg.get("start", 0)
        chunk_start = chunk_start if chunk_start is not None else t
        chunk_words.append(seg.get("text", "").strip())
        if t - chunk_start >= 15:
            m, s = divmod(int(chunk_start), 60)
            lines.append(f"[{m:02d}:{s:02d}] {' '.join(chunk_words)}")
            chunk_start, chunk_words = t, []
    if chunk_words and chunk_start is not None:
        m, s = divmod(int(chunk_start), 60)
        lines.append(f"[{m:02d}:{s:02d}] {' '.join(chunk_words)}")
    return "\n".join(lines)[:max_chars]


def _pick_moments(summary: str, n: int, duration: int) -> List[Dict]:
    """Ask Ollama to select N strong moments. Returns [] on any failure."""
    prompt = (
        f"You are a short-form video editor. Pick {n} strong moments from this transcript "
        f"for TikTok/Reels clips (20–50 seconds each). Choose moments with strong hooks, "
        f"a complete thought, or emotional punch.\n\n"
        f"Transcript:\n{summary}\n\n"
        f"Return ONLY a JSON array, no other text:\n"
        f'[{{"start_sec": 45, "end_sec": 85, "reason": "..."}}]\n'
        f"Use integer seconds. Pick exactly {n} moments."
    )
    try:
        import httpx
        r = httpx.post(OLLAMA_URL,
                       json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                       timeout=90.0)
        if r.status_code != 200:
            print(f">> CLIPFARMER: Ollama {r.status_code}")
            return []
        raw = r.json().get("response", "")
        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        if not m:
            print(f">> CLIPFARMER: no JSON in Ollama response")
            return []
        moments = json.loads(m.group(0))
        valid = []
        for mo in moments:
            start = max(0, int(mo.get("start_sec", 0)))
            end   = min(duration, int(mo.get("end_sec", start + 35)))
            if end - start < 10:
                end = min(start + 35, duration)
            if start < end:
                valid.append({"start_sec": start, "end_sec": end,
                              "reason": str(mo.get("reason", ""))[:120]})
        return valid[:n]
    except Exception as e:
        print(f">> CLIPFARMER: Ollama failed: {e}")
        return []


def _equal_split(duration: int, n: int) -> List[Dict]:
    """Equal-segment fallback when transcript/Ollama is unavailable."""
    step = duration // (n + 1)
    moments = []
    for i in range(n):
        start = max(0, step * (i + 1) - 20)
        end   = min(duration, start + 40)
        moments.append({"start_sec": start, "end_sec": end,
                        "reason": f"equal split segment {i + 1}"})
    return moments


def _dimensions(path: str) -> Tuple[int, int]:
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=10,
        )
        w, h = r.stdout.strip().split(",")
        return int(w), int(h)
    except Exception:
        return 1920, 1080


def _cut_clip(source: str, start: int, end: int, out: str, landscape: bool) -> bool:
    vf = ["-vf", "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"] if landscape else []
    cmd = [FFMPEG, "-y", "-ss", str(start), "-to", str(end), "-i", source,
           *vf, "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", out]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.isfile(out):
            return True
        print(f">> CLIPFARMER: ffmpeg error: {r.stderr.decode()[:200]}")
        return False
    except Exception as e:
        print(f">> CLIPFARMER: ffmpeg exception: {e}")
        return False


# ── analysis artifacts ────────────────────────────────────────────────────────

def _save_transcript(segments: List[Dict], title: str, out_dir: str) -> bool:
    """Write transcript.json and transcript.md. Returns True on success."""
    try:
        with open(os.path.join(out_dir, "transcript.json"), "w", encoding="utf-8") as f:
            json.dump(segments, f, indent=2, ensure_ascii=False)

        lines = [f"# Transcript — {title}", ""]
        for seg in segments:
            t = seg.get("start", 0)
            mm, ss = divmod(int(t), 60)
            lines.append(f"[{mm:02d}:{ss:02d}] {seg.get('text', '').strip()}")
        with open(os.path.join(out_dir, "transcript.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        print(">> CLIPFARMER: transcript artifacts saved")
        return True
    except Exception as e:
        print(f">> CLIPFARMER: transcript save failed: {e}")
        return False


_BOT_KEYWORDS = {
    "cryptoid":  ["bitcoin", "btc", "ethereum", "eth", "crypto", "defi", "blockchain",
                  "altcoin", "solana", "nft", "web3", "wallet", "token", "coin"],
    "stockbot":  ["stock", "stocks", "equity", "nasdaq", "s&p", "spy", "earnings",
                  "fed", "inflation", "portfolio", "ticker", "dividend", "ipo", "bull",
                  "bear", "trading", "market", "shares", "wall street"],
    "pinkslip":  ["bet", "betting", "odds", "spread", "parlay", "nfl", "nba", "mlb",
                  "nhl", "game", "touchdown", "playoff", "sportsbook", "wager"],
    "higashop":  ["sell", "resell", "amazon", "etsy", "dropship", "product", "profit",
                  "arbitrage", "inventory", "listing", "ebay", "wholesale", "ecommerce"],
    "teacherbot": ["learn", "lesson", "tutorial", "how to", "step by step", "explain",
                   "education", "study", "course", "teach", "skill", "training"],
    "jamz":      ["music", "beat", "track", "rhythm", "audio", "sound", "song",
                  "producer", "bpm", "mix", "bass", "melody", "dj", "vibe"],
}

def _detect_relevant_bots(transcript_text: str) -> List[str]:
    """Return list of bot names relevant to this transcript. Always includes jarvisbot + robowright."""
    t = transcript_text.lower()
    bots = ["jarvisbot", "robowright"]
    for bot, keywords in _BOT_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            if bot not in bots:
                bots.append(bot)
    return bots


def _analysis_fallback(analysis: dict, segments: List[Dict]) -> dict:
    """
    Fill empty analysis fields from raw transcript text.
    Only touches fields that Ollama left blank — populated fields are unchanged.
    """
    transcript_text = " ".join(
        s.get("text", "").strip() for s in segments if s.get("text")
    ).strip()
    if not transcript_text:
        return analysis

    # Summary: first 2-3 meaningful sentences
    if not analysis.get("summary"):
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', transcript_text)
                     if len(s.strip()) > 15]
        analysis["summary"] = " ".join(sentences[:3])[:400]

    # Key insights: up to 3 distinct transcript sentences
    if not analysis.get("key_insights"):
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', transcript_text)
                     if len(s.strip()) > 20]
        analysis["key_insights"] = sentences[:3]

    # Bot tags: minimal entry for jarvisbot and robowright if still empty
    bot_tags = analysis.get("bot_tags", {})
    snippet = transcript_text[:200]
    for bot_id, angle in (("jarvisbot", "general clip"), ("robowright", "content strategy")):
        if bot_id in bot_tags and not bot_tags[bot_id]:
            bot_tags[bot_id] = [{"start_sec": 0, "end_sec": 0, "angle": angle, "note": snippet}]
    analysis["bot_tags"] = bot_tags
    return analysis


def _analyze_clips(segments: List[Dict], moments: List[Dict], title: str,
                   url: str, duration: int, out_dir: str, bots: List[str]) -> bool:
    """
    One Ollama call → analysis.json + analysis.md.
    Fails gracefully — never raises, never blocks clip output.
    """
    print(f">> CLIPFARMER ANALYZE: entered — segments={len(segments)} moments={len(moments)} bots={bots}")
    if not segments:
        print(">> CLIPFARMER ANALYZE: skipping (no transcript)")
        return False

    transcript_summary = _build_summary(segments, max_chars=5000)
    bot_list = ", ".join(bots)
    moment_hints = "; ".join(
        f"{m['start_sec']}s–{m['end_sec']}s ({m.get('reason', '')})" for m in moments
    )

    bot_tag_schema = {b: [{"start_sec": 0, "end_sec": 0, "angle": "...", "note": "..."}]
                      for b in bots}

    prompt = f"""You are analyzing a YouTube video for the HIGA HOUSE bot system.

Title: {title}
Duration: {duration}s
Clips already selected at: {moment_hints}

Bots to tag: {bot_list}

Timestamped transcript:
{transcript_summary}

Return ONLY a valid JSON object with this exact structure (no markdown, no extra text):
{{
  "summary": "2-3 sentence plain English summary",
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "important_sections": [
    {{"start_sec": 0, "end_sec": 0, "label": "...", "quote": "exact words from transcript"}}
  ],
  "bot_tags": {json.dumps(bot_tag_schema)}
}}

For bot_tags, fill in real observations for each bot based on the transcript.
Use integer seconds. Include 3-5 important sections and 2-3 tags per bot."""

    print(f">> CLIPFARMER ANALYZE: calling Ollama ({OLLAMA_MODEL}) timeout=120s prompt_len={len(prompt)}")
    raw = ""
    try:
        import httpx
        r = httpx.post(OLLAMA_URL,
                       json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "think": False},
                       timeout=120.0)
        print(f">> CLIPFARMER ANALYZE: Ollama status={r.status_code}")
        if r.status_code == 200:
            raw = r.json().get("response", "")
            print(f">> CLIPFARMER ANALYZE: raw response len={len(raw)} first80={raw[:80]!r}")
        else:
            print(f">> CLIPFARMER ANALYZE: non-200 body={r.text[:200]!r}")
    except Exception as e:
        print(f">> CLIPFARMER ANALYZE: Ollama call failed: {e}")

    # Parse JSON — try strict match first, then first {...} block
    data = None
    if raw:
        for label, pattern in [("greedy-dot", r"\{.*\}"), ("dotall", r"\{[\s\S]*\}")]:
            m = re.search(pattern, raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(0))
                    print(f">> CLIPFARMER ANALYZE: JSON parsed OK via {label}, keys={list(data.keys())}")
                    break
                except json.JSONDecodeError as je:
                    print(f">> CLIPFARMER ANALYZE: JSON parse failed ({label}): {je}")
    else:
        print(">> CLIPFARMER ANALYZE: raw is empty — skipping JSON parse")

    # Build the full analysis dict regardless of whether Ollama succeeded
    analysis = {
        "title": title,
        "url": url,
        "duration_sec": duration,
        "summary": data.get("summary", "") if data else "",
        "key_insights": data.get("key_insights", []) if data else [],
        "important_sections": data.get("important_sections", []) if data else [],
        "bot_tags": data.get("bot_tags", {b: [] for b in bots}) if data else {b: [] for b in bots},
    }
    print(f">> CLIPFARMER ANALYZE: analysis dict built — ollama_data={'yes' if data else 'no (fallback empty)'}")

    # Apply deterministic fallback if Ollama returned sparse output
    _is_sparse = (
        not analysis["summary"]
        or not analysis["key_insights"]
        or not any(analysis["bot_tags"].values())
    )
    if _is_sparse:
        analysis = _analysis_fallback(analysis, segments)
        print(">> CLIPFARMER ANALYZE: sparse Ollama output — deterministic fallback applied")

    analysis_json_path = os.path.join(out_dir, "analysis.json")
    analysis_md_path   = os.path.join(out_dir, "analysis.md")
    print(f">> CLIPFARMER ANALYZE: writing to {analysis_json_path}")
    try:
        # analysis.json
        with open(analysis_json_path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print(f">> CLIPFARMER ANALYZE: analysis.json written OK ({os.path.getsize(analysis_json_path)} bytes)")

        # analysis.md
        md = [f"# Analysis — {title}", "",
              f"**URL:** {url}  ", f"**Duration:** {duration}s  ",
              f"**Bots tagged:** {', '.join(bots)}", ""]

        md += ["## Summary", analysis["summary"] or "_No summary generated._", ""]

        if analysis["key_insights"]:
            md += ["## Key Insights"]
            md += [f"- {i}" for i in analysis["key_insights"]]
            md.append("")

        if analysis["important_sections"]:
            md.append("## Important Sections")
            for sec in analysis["important_sections"]:
                sm, ss = divmod(int(sec.get("start_sec", 0)), 60)
                em, es = divmod(int(sec.get("end_sec", 0)), 60)
                md.append(f"### [{sm:02d}:{ss:02d} – {em:02d}:{es:02d}] {sec.get('label', '')}")
                if sec.get("quote"):
                    md.append(f'> "{sec["quote"]}"')
                md.append("")

        for bot, tags in analysis["bot_tags"].items():
            if not tags:
                continue
            md.append(f"## Bot Tags — {bot}")
            for tag in tags:
                sm, ss = divmod(int(tag.get("start_sec", 0)), 60)
                em, es = divmod(int(tag.get("end_sec", 0)), 60)
                md.append(f"- **[{sm:02d}:{ss:02d} – {em:02d}:{es:02d}]** {tag.get('angle', '')}")
                if tag.get("note"):
                    md.append(f"  {tag['note']}")
            md.append("")

        with open(analysis_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")

        print(">> CLIPFARMER ANALYZE: analysis.md written OK")
        return True
    except Exception as e:
        print(f">> CLIPFARMER ANALYZE: write failed: {e}")
        return False


def _ingest_to_bot_memory(analysis: Dict, url: str) -> List[Tuple[str, str, str]]:
    """
    Write per-bot memory entries from analysis output.
    Returns memory_log: list of (bot_id, "saved"|"skipped", detail).
    """
    print(">> CLIPFARMER MEMORY: entering _ingest_to_bot_memory")
    try:
        from bot_memory import save_bot_memory
        print(">> CLIPFARMER MEMORY: bot_memory imported OK")
    except Exception as e:
        print(f">> CLIPFARMER MEMORY: bot_memory unavailable, skipping ingest: {e}")
        return []

    title = analysis.get("title", "untitled")
    summary = analysis.get("summary", "")
    insights = analysis.get("key_insights", [])
    bot_tags = analysis.get("bot_tags", {}) or {}

    print(f">> CLIPFARMER MEMORY: title={title!r} summary_len={len(summary)} insights={len(insights)} bot_ids={list(bot_tags.keys())}")

    insight_lines = [f"- {item}" for item in insights[:3] if str(item).strip()]
    memory_log: List[Tuple[str, str, str]] = []

    for bot_id, tags in bot_tags.items():
        tags = tags or []
        print(f">> CLIPFARMER MEMORY: processing {bot_id} — {len(tags)} tags")

        lines = [
            f"CLIPFARMER SOURCE: {title}",
            f"URL: {url}",
        ]
        if summary:
            lines.append(f"Summary: {summary}")
        if insight_lines:
            lines.append("Key insights:")
            lines.extend(insight_lines)

        if tags:
            lines.append("Moments:")
            for tag in tags:
                start = int(tag.get("start_sec", 0))
                end = int(tag.get("end_sec", 0))
                sm, ss = divmod(start, 60)
                em, es = divmod(end, 60)
                angle = str(tag.get("angle", "")).strip()
                note = str(tag.get("note", "")).strip()
                lines.append(f"[{sm:02d}:{ss:02d}–{em:02d}:{es:02d}] {angle} — {note}")
        elif bot_id != "jarvisbot":
            print(f">> CLIPFARMER MEMORY: skipping {bot_id} (empty tags, not jarvisbot)")
            memory_log.append((bot_id, "skipped", "no tags"))
            continue

        content = "\n".join(lines).strip()
        if not content:
            print(f">> CLIPFARMER MEMORY: skipping {bot_id} (empty content)")
            memory_log.append((bot_id, "skipped", "empty content"))
            continue

        print(f">> CLIPFARMER MEMORY: calling save_bot_memory for {bot_id} ({len(content)} chars)")
        save_bot_memory(
            bot_id,
            content,
            {
                "source": "clipfarmer",
                "url": url,
                "title": title,
            },
        )
        print(f">> CLIPFARMER: memory saved for {bot_id}")
        detail = f"{len(tags)} tags" if tags else "summary only"
        memory_log.append((bot_id, "saved", detail))

    return memory_log


def _emit_robowright_handoff(analysis: Dict) -> bool:
    """Save a lightweight handoff when a clip looks reusable for content packaging."""
    summary = str(analysis.get("summary", "")).strip()
    insights = [str(item).strip() for item in (analysis.get("key_insights", []) or []) if str(item).strip()]
    robowright_tags = (analysis.get("bot_tags", {}) or {}).get("robowright", []) or []
    if not (summary or insights or robowright_tags):
        return False

    lines = []
    if summary:
        lines.append(f"Summary: {summary}")
    if insights:
        lines.append("Key insights:")
        lines.extend(f"- {item}" for item in insights[:3])
    for tag in robowright_tags[:2]:
        angle = str(tag.get("angle", "")).strip()
        note = str(tag.get("note", "")).strip()
        detail = " — ".join(part for part in (angle, note) if part)
        if detail:
            lines.append(f"Robowright angle: {detail}")

    context = "\n".join(lines).strip()
    if not context:
        return False

    try:
        from loop_memory import save_handoff
        save_handoff(
            from_bot="clipfarmer",
            to_bot="robowright",
            topic=str(analysis.get("title", "untitled")).strip(),
            context=context,
            suggested_action="make_carousel",
        )
        print(">> CLIPFARMER HANDOFF: saved handoff for robowright")
        return True
    except Exception as e:
        print(f">> CLIPFARMER HANDOFF: save failed: {e}")
        return False


def _write_report(title: str, url: str, duration: int, landscape: bool,
                  transcript_method: str, clips_made: list,
                  analysis_data: Dict, memory_log: List[Tuple[str, str, str]],
                  out_dir: str) -> str:
    """
    Write report.md — the single human-readable run summary.
    Returns path on success, empty string on failure.
    """
    from datetime import datetime
    report_path = os.path.join(out_dir, "report.md")
    try:
        md = []

        # ── Header ────────────────────────────────────────────────────────────
        md += [
            f"# HIGA HOUSE CLIP REPORT — {title}",
            "",
            f"**Date:** {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}  ",
            f"**URL:** {url}  ",
            f"**Duration:** {_fmt_ts(duration)}  ",
            f"**Orientation:** {'landscape → portrait crop' if landscape else 'portrait'}  ",
            f"**Transcript:** {transcript_method}  ",
            "",
        ]

        # ── Key Insights ──────────────────────────────────────────────────────
        insights = analysis_data.get("key_insights", [])
        summary  = analysis_data.get("summary", "")
        if summary or insights:
            md.append("## Key Insights")
            if summary:
                md += [summary, ""]
            for item in insights:
                md.append(f"- {item}")
            md.append("")

        # ── Clips Selected ────────────────────────────────────────────────────
        if clips_made:
            md += ["## Clips Selected", ""]
            md.append("| File | Timecode | Notes |")
            md.append("|------|----------|-------|")
            for i, start, end, reason in clips_made:
                sm, ss = divmod(start, 60)
                em, es = divmod(end, 60)
                md.append(f"| clip_{i:02d}.mp4 | [{sm:02d}:{ss:02d} – {em:02d}:{es:02d}] | {reason} |")
            md.append("")

        # ── Important Sections ────────────────────────────────────────────────
        sections = analysis_data.get("important_sections", [])
        if sections:
            md.append("## Important Sections")
            md.append("")
            for sec in sections:
                sm, ss = divmod(int(sec.get("start_sec", 0)), 60)
                em, es = divmod(int(sec.get("end_sec", 0)), 60)
                md.append(f"### [{sm:02d}:{ss:02d} – {em:02d}:{es:02d}] {sec.get('label', '')}")
                if sec.get("quote"):
                    md.append(f'> "{sec["quote"]}"')
                md.append("")

        # ── Bot Highlights ────────────────────────────────────────────────────
        bot_tags = analysis_data.get("bot_tags", {})
        bots_with_tags = {b: t for b, t in bot_tags.items() if t}
        if bots_with_tags:
            md.append("## Bot Highlights")
            md.append("")
            for bot_id, tags in bots_with_tags.items():
                md.append(f"### {bot_id}")
                for tag in tags:
                    sm, ss = divmod(int(tag.get("start_sec", 0)), 60)
                    em, es = divmod(int(tag.get("end_sec", 0)), 60)
                    angle = str(tag.get("angle", "")).strip()
                    note  = str(tag.get("note", "")).strip()
                    md.append(f"- **[{sm:02d}:{ss:02d} – {em:02d}:{es:02d}]** {angle}")
                    if note:
                        md.append(f"  {note}")
                md.append("")

        # ── Memory Ingestion ──────────────────────────────────────────────────
        if memory_log:
            md.append("## Memory Ingestion")
            md.append("")
            for bot_id, status, detail in memory_log:
                icon = "✓" if status == "saved" else "—"
                md.append(f"- {icon} **{bot_id}**: {status} ({detail})")
            saved_count = sum(1 for _, s, _ in memory_log if s == "saved")
            md += ["", f"_{saved_count} of {len(memory_log)} bots received a ChromaDB memory entry._", ""]
        else:
            md += ["## Memory Ingestion", "", "_No memory ingestion (no analysis data or transcript)._", ""]

        # ── Footer ────────────────────────────────────────────────────────────
        md += ["---", f"_Generated by HIGA HOUSE clipfarmer — {out_dir}_", ""]

        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))

        print(f">> CLIPFARMER: report.md written ({os.path.getsize(report_path)} bytes)")
        return report_path

    except Exception as e:
        print(f">> CLIPFARMER: report.md write failed: {e}")
        return ""


def _fmt_ts(secs: int) -> str:
    m, s = divmod(secs, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ── main entry point ──────────────────────────────────────────────────────────

def farm_clips(url: str, n_clips: int = 5) -> str:
    """
    Full pipeline: download → transcript → moment selection → ffmpeg cuts.
    Returns a plain-text summary for the bot response.
    """
    video_id = _extract_video_id(url)
    out_dir  = os.path.join(CLIPS_BASE, video_id)
    os.makedirs(out_dir, exist_ok=True)

    print(f">> CLIPFARMER: starting pipeline for {video_id}")

    download_url, resolve_error = _normalize_clip_url(url)
    if resolve_error:
        return (
            "Clip failed — could not resolve the TikTok shortlink.\n"
            f"URL tried: {url}\n"
            "Tip: try the full TikTok video URL (tiktok.com/@user/video/...) instead of the shortlink."
        )

    # 1. Download
    print(">> CLIPFARMER: downloading…")
    source, title, duration, dl_error = _download_video(download_url, out_dir)
    if not source:
        kind, hint = _classify_download_error(dl_error)
        is_shortlink = _is_tiktok_shortlink(url)
        tip = (
            "Try the full TikTok video URL (tiktok.com/@user/video/...) instead of the shortlink."
            if is_shortlink else
            "Try a public post link, or provide a local file path."
        )
        return f"Clip failed — {hint}.\nURL tried: {url}\nTip: {tip}"
    print(f">> CLIPFARMER: '{title}' ({duration}s) saved to {source}")

    # 2. Transcript (three-tier: youtube_api → yt_dlp_subs → whisper → none)
    segments, transcript_method = _get_transcript(download_url, source)
    has_transcript = bool(segments)

    # Cap clip count for very short videos (< 90s) to avoid overlapping junk
    max_clips = max(1, duration // 25)
    n_clips = min(n_clips, max_clips)

    # 3. Moment selection
    moments = []
    if has_transcript:
        summary = _build_summary(segments)
        print(f">> CLIPFARMER: asking {OLLAMA_MODEL} to pick {n_clips} moments…")
        moments = _pick_moments(summary, n_clips, duration)
        print(f">> CLIPFARMER: Ollama picked {len(moments)} moments")

    if not moments:
        print(">> CLIPFARMER: falling back to equal-split")
        moments = _equal_split(duration, n_clips)

    # 4. Orientation
    w, h = _dimensions(source)
    landscape = w > h

    # 5. Cut clips
    clips_made = []
    for i, mo in enumerate(moments, 1):
        start, end = mo["start_sec"], mo["end_sec"]
        out_path = os.path.join(out_dir, f"clip_{i:02d}.mp4")
        print(f">> CLIPFARMER: cutting clip {i:02d} ({start}s–{end}s)…")
        if _cut_clip(source, start, end, out_path, landscape):
            clips_made.append((i, start, end, mo["reason"]))

    # 6. Analysis artifacts + report
    artifact_note = ""
    analysis_data: Dict = {}
    memory_log: List[Tuple[str, str, str]] = []

    if has_transcript:
        _save_transcript(segments, title, out_dir)
        transcript_text = " ".join(s.get("text", "") for s in segments)
        bots = _detect_relevant_bots(transcript_text)
        _analyze_clips(segments, moments, title, url, duration, out_dir, bots)
        artifact_note = "\n  transcript.json, transcript.md, analysis.json, analysis.md"
        analysis_path = os.path.join(out_dir, "analysis.json")
        print(f">> CLIPFARMER MEMORY: checking for analysis.json at {analysis_path}")
        print(f">> CLIPFARMER MEMORY: file exists = {os.path.isfile(analysis_path)}")
        try:
            with open(analysis_path, "r", encoding="utf-8") as f:
                analysis_data = json.load(f)
            bot_tags = analysis_data.get("bot_tags", {})
            print(f">> CLIPFARMER MEMORY: bot_tags keys = {list(bot_tags.keys())}")
            for bid, tags in bot_tags.items():
                print(f">> CLIPFARMER MEMORY:   {bid} → {len(tags or [])} tags")
            memory_log = _ingest_to_bot_memory(analysis_data, url)
            saved_count = sum(1 for _, s, _ in memory_log if s == "saved")
            print(f">> CLIPFARMER MEMORY: total saved = {saved_count}")
            _emit_robowright_handoff(analysis_data)
            if saved_count:
                artifact_note += f"\n  {saved_count} bot memory entries written"
        except Exception as e:
            print(f">> CLIPFARMER: memory ingest skipped: {e}")

    report_path = _write_report(
        title, url, duration, landscape, transcript_method,
        clips_made, analysis_data, memory_log, out_dir,
    )
    if report_path:
        artifact_note += "\n  report.md"

    # 7. Open output folder
    subprocess.Popen(["open", out_dir])

    # 8. Response
    if not clips_made:
        return (f"Downloaded '{title}' but clip cutting failed.\n"
                f"Source video is at: {source}")

    lines = [
        f"Clipped {len(clips_made)} moments from '{title}'.",
        f"Folder: {out_dir}",
        f"Source: {duration}s | {'landscape → portrait crop' if landscape else 'portrait, no crop'}",
        f"Transcript: {transcript_method}{' (used for moment selection)' if has_transcript else ' — equal split used'}",
        "",
    ]
    for i, start, end, reason in clips_made:
        sm, ss = divmod(start, 60)
        em, es = divmod(end, 60)
        lines.append(f"  clip_{i:02d}.mp4  [{sm:02d}:{ss:02d} – {em:02d}:{es:02d}]  {reason}")

    if artifact_note:
        lines.append(f"\nArtifacts:{artifact_note}")

    return "\n".join(lines)
