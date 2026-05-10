"""
clipfarmer.py — YouTube → short-form clip pipeline.

Pipeline: yt-dlp download → timestamped transcript → Ollama moment selection → ffmpeg cut.
Falls back to equal-segment split if transcript or Ollama is unavailable.
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

def _extract_video_id(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else re.sub(r"[^A-Za-z0-9_-]", "_", url)[-20:]


def _download_video(url: str, out_dir: str) -> Tuple[Optional[str], str, int]:
    """yt-dlp download. Returns (local_path, title, duration_secs)."""
    try:
        import yt_dlp
        ydl_opts = {
            "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": os.path.join(out_dir, "source.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title    = info.get("title", "untitled")
            duration = int(info.get("duration", 0))
        for ext in ("mp4", "mkv", "webm"):
            path = os.path.join(out_dir, f"source.{ext}")
            if os.path.isfile(path):
                return path, title, duration
        return None, title, duration
    except Exception as e:
        print(f">> CLIPFARMER: download failed: {e}")
        return None, "", 0


def _get_segments(video_id: str) -> List[Dict]:
    """Fetch timestamped transcript segments. Returns [] on failure."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id)
        # FetchedTranscript is iterable; each item is a FetchedTranscriptSnippet
        # with .text, .start, .duration attributes (no to_dict in current API version)
        return [{"text": s.text, "start": s.start, "duration": s.duration}
                for s in fetched]
    except Exception as e:
        print(f">> CLIPFARMER: transcript unavailable: {e}")
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

    # 1. Download
    print(">> CLIPFARMER: downloading…")
    source, title, duration = _download_video(url, out_dir)
    if not source:
        return f"Download failed for {url}. The video may be private or geo-restricted."
    print(f">> CLIPFARMER: '{title}' ({duration}s) saved to {source}")

    # 2. Transcript
    segments = _get_segments(video_id)
    has_transcript = bool(segments)

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

    # 6. Open output folder
    subprocess.Popen(["open", out_dir])

    # 7. Response
    if not clips_made:
        return (f"Downloaded '{title}' but clip cutting failed.\n"
                f"Source video is at: {source}")

    lines = [
        f"Clipped {len(clips_made)} moments from '{title}'.",
        f"Folder: {out_dir}",
        f"Source: {duration}s | {'landscape → portrait crop' if landscape else 'portrait, no crop'}",
        f"Transcript: {'used for moment selection' if has_transcript else 'unavailable — equal split used'}",
        "",
    ]
    for i, start, end, reason in clips_made:
        sm, ss = divmod(start, 60)
        em, es = divmod(end, 60)
        lines.append(f"  clip_{i:02d}.mp4  [{sm:02d}:{ss:02d} – {em:02d}:{es:02d}]  {reason}")

    return "\n".join(lines)
