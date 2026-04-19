"""
J.A.R.V.I.S. YouTube Tools
Transcript fetching, video info, comments, search.
Stripped of jarvis_brain dependency — saves to memory.py instead.
"""

import os
import re
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
from fpdf import FPDF

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


# ─────────────────────────────────────────────────────────────────────────────
# CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def get_youtube_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def extract_video_id(video_input: str) -> str:
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", video_input)
    return match.group(1) if match else video_input.strip()


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def search_youtube(query: str, max_results: int = 5) -> list:
    try:
        youtube = get_youtube_client()
        response = youtube.search().list(
            q=query,
            part="snippet",
            maxResults=max_results,
            type="video"
        ).execute()

        results = []
        for item in response.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            results.append({
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "description": snippet["description"][:160],
                "published_at": snippet.get("publishedAt", "N/A"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
            })
        return results
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# VIDEO INFO
# ─────────────────────────────────────────────────────────────────────────────

def get_video_info(video_input: str) -> dict:
    try:
        video_id = extract_video_id(video_input)
        youtube = get_youtube_client()
        response = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id
        ).execute()

        if not response.get("items"):
            return {"error": "Video not found."}

        item = response["items"][0]
        snippet = item["snippet"]
        stats = item.get("statistics", {})

        return {
            "title": snippet["title"],
            "channel": snippet["channelTitle"],
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt", "N/A"),
            "views": stats.get("viewCount", "N/A"),
            "likes": stats.get("likeCount", "N/A"),
            "comments": stats.get("commentCount", "N/A"),
            "duration": item["contentDetails"]["duration"],
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "video_id": video_id,
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# TRANSCRIPT
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name.strip()[:80]


def get_obsidian_base_path() -> str:
    """Get the base path for saving transcripts, with Obsidian vault priority."""
    # Priority 1: /Users/higabot1/jarvis/brain
    vault1 = "/Users/higabot1/jarvis/brain"
    if os.path.exists(os.path.join(vault1, ".obsidian")):
        return os.path.join(vault1, "JARVIS", "YouTube Transcripts")
    
    # Priority 2: /Users/higabot1/Documents/Obsidian Vault
    vault2 = "/Users/higabot1/Documents/Obsidian Vault"
    if os.path.exists(os.path.join(vault2, ".obsidian")):
        return os.path.join(vault2, "JARVIS", "YouTube Transcripts")
    
    # Fallback: repo-local transcripts
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcripts")


def save_transcript_pdf(video_id: str, title: str, channel: str, transcript_text: str) -> str:
    try:
        base_dir = get_obsidian_base_path()
        channel_dir = os.path.join(base_dir, sanitize_filename(channel))
        os.makedirs(channel_dir, exist_ok=True)

        filepath = os.path.join(channel_dir, sanitize_filename(title) + ".pdf")

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 10, title)
        pdf.ln(2)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, f"Channel: {channel}", ln=True)
        pdf.cell(0, 8, f"Video ID: {video_id}", ln=True)
        pdf.cell(0, 8, f"URL: https://www.youtube.com/watch?v={video_id}", ln=True)
        pdf.ln(4)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 11)
        words = transcript_text.split()
        chunks = [" ".join(words[i:i+80]) for i in range(0, len(words), 80)]
        for chunk in chunks:
            pdf.multi_cell(0, 7, chunk)
            pdf.ln(2)

        pdf.output(filepath)
        return filepath
    except Exception as e:
        print(f">> PDF ERROR: {e}")
        return None


def save_transcript_markdown(video_id: str, title: str, channel: str, video_url: str, transcript_text: str, pdf_path: str) -> str:
    """Save a markdown note alongside the PDF."""
    try:
        base_dir = get_obsidian_base_path()
        channel_dir = os.path.join(base_dir, sanitize_filename(channel))
        os.makedirs(channel_dir, exist_ok=True)
        
        md_filepath = os.path.join(channel_dir, sanitize_filename(title) + ".md")
        
        markdown_content = f"""# {title}

**Channel:** {channel}
**Video URL:** {video_url}
**Video ID:** {video_id}

**PDF:** [{os.path.basename(pdf_path)}|{os.path.basename(pdf_path)}]

## Transcript

{transcript_text}

---
*Generated by JARVIS YouTube Tools*
"""
        
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return md_filepath
    except Exception as e:
        print(f">> MARKDOWN ERROR: {e}")
        return None


def get_transcript(video_input: str, max_chars: int = 12000) -> dict:
    try:
        video_id = extract_video_id(video_input)
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id)

        # youtube-transcript-api may return snippet objects rather than plain dicts.
        transcript_parts = []
        for item in fetched:
            if isinstance(item, dict):
                text = item.get("text", "")
            else:
                text = getattr(item, "text", "")
            if text:
                transcript_parts.append(text)

        full_text = " ".join(transcript_parts).strip()

        # Get video metadata for PDF and markdown
        info = get_video_info(video_input)
        title = info.get("title", video_id) if "error" not in info else video_id
        channel = info.get("channel", "Unknown") if "error" not in info else "Unknown"
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        pdf_path = save_transcript_pdf(video_id, title, channel, full_text)
        md_path = None
        if pdf_path:
            md_path = save_transcript_markdown(video_id, title, channel, video_url, full_text, pdf_path)

        return {
            "video_id": video_id,
            "title": title,
            "channel": channel,
            "transcript": full_text[:max_chars],
            "truncated": len(full_text) > max_chars,
            "pdf_path": pdf_path,
            "md_path": md_path,
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# COMMENTS
# ─────────────────────────────────────────────────────────────────────────────

def get_top_comments(video_input: str, max_results: int = 5) -> list:
    try:
        video_id = extract_video_id(video_input)
        youtube = get_youtube_client()
        response = youtube.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="relevance",
            textFormat="plainText"
        ).execute()

        comments = []
        for item in response.get("items", []):
            top = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author": top.get("authorDisplayName", "Unknown"),
                "text": top.get("textDisplay", "").strip(),
                "likes": top.get("likeCount", 0),
                "published_at": top.get("publishedAt", "N/A"),
            })
        return comments
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# ROUTER — called by main.py to detect and handle YouTube requests
# ─────────────────────────────────────────────────────────────────────────────

def handle_youtube_request(question: str) -> tuple[str, str]:
    q = question.lower().strip()
    url_match = re.search(
        r"(https?://(?:www\.)?(?:youtube\.com/watch\?v=[A-Za-z0-9_-]{11}[^\s]*|youtu\.be/[A-Za-z0-9_-]{11}[^\s]*))",
        question
    )
    has_url = bool(url_match)
    url = url_match.group(1) if has_url else ""

    # ── URL present: transcript request ──
    if has_url and any(w in q for w in ["transcript", "full transcript", "exact transcript"]):
        result = get_transcript(url, max_chars=12000)
        if "error" in result:
            return f"Couldn't retrieve the transcript, sir. {result['error']}", "youtube"
        text = (
            f"Title: {result['title']}\nChannel: {result['channel']}\n\n"
            f"Transcript:\n{result['transcript']}"
        )
        if result.get("truncated"):
            text += "\n\n[Transcript truncated at 12,000 characters]"
        if result.get("pdf_path"):
            text += f"\n\nPDF saved: {result['pdf_path']}"
        if result.get("md_path"):
            text += f"\nMarkdown saved: {result['md_path']}"
        return text, "youtube"

    # ── URL present: comments request ──
    if has_url and any(w in q for w in ["comments", "top comments", "best comments"]):
        comments = get_top_comments(url, max_results=5)
        if isinstance(comments, dict) and "error" in comments:
            return f"Couldn't retrieve comments, sir. {comments['error']}", "youtube"
        info = get_video_info(url)
        lines = [f"{i}. {c['author']} ({c['likes']} likes): {c['text']}"
                 for i, c in enumerate(comments, 1)]
        header = ""
        if "error" not in info:
            header = f"Title: {info['title']}\nChannel: {info['channel']}\n\n"
        return header + "Top comments:\n" + "\n\n".join(lines), "youtube"

    # ── URL present: info/details request ──
    if has_url and any(w in q for w in [
        "info", "details", "views", "likes", "description",
        "channel", "published", "about this video", "post date"
    ]):
        info = get_video_info(url)
        if "error" in info:
            return f"Couldn't retrieve video details, sir. {info['error']}", "youtube"
        return (
            f"Title: {info['title']}\n"
            f"Channel: {info['channel']}\n"
            f"Published: {info['published_at']}\n"
            f"Views: {info['views']}\n"
            f"Likes: {info['likes']}\n"
            f"Comments: {info['comments']}\n"
            f"Duration: {info['duration']}\n\n"
            f"Description:\n{info['description'][:1200]}"
        ), "youtube"

    # ── URL present: summarize (default) ──
    if has_url:
        info = get_video_info(url)
        transcript = get_transcript(url, max_chars=6000)
        comments = get_top_comments(url, max_results=3)

        context = ""
        if "error" not in info:
            context += (
                f"Title: {info['title']}\n"
                f"Channel: {info['channel']}\n"
                f"Published: {info['published_at']}\n"
                f"Views: {info['views']} | Likes: {info['likes']}\n\n"
                f"Description:\n{info['description'][:800]}\n\n"
            )
        if isinstance(transcript, dict) and "transcript" in transcript:
            context += f"Transcript:\n{transcript['transcript']}\n"
            if transcript.get("truncated"):
                context += "[truncated]\n"
            if transcript.get("pdf_path"):
                context += f"PDF saved: {transcript['pdf_path']}\n"
            if transcript.get("md_path"):
                context += f"Markdown saved: {transcript['md_path']}\n"
        if isinstance(comments, list) and comments:
            context += "\nTop comments:\n" + "\n".join(
                [f"- {c['author']}: {c['text']}" for c in comments]
            )

        return context, "youtube_summarize"

    # ── No URL: YouTube search request ──
    search_triggers = [
        "youtube", "videos about", "videos on", "find videos",
        "search youtube", "show me videos", "find me videos", "look up videos"
    ]
    if any(t in q for t in search_triggers):
        cleaned = q
        for trigger in [
            "find me videos about", "find videos about", "search youtube for",
            "show me videos about", "show me videos on", "look up videos about",
            "youtube videos about", "videos about", "videos on", "youtube"
        ]:
            cleaned = cleaned.replace(trigger, " ")
        cleaned = " ".join(cleaned.split()).strip()

        if not cleaned:
            return None, None

        results = search_youtube(cleaned, max_results=5)
        if isinstance(results, dict) and "error" in results:
            return f"YouTube search failed, sir. {results['error']}", "youtube"

        lines = [
            f"{i}. {r['title']}\n   Channel: {r['channel']}\n   Published: {r['published_at']}\n   URL: {r['url']}"
            for i, r in enumerate(results, 1)
        ]
        return "Top YouTube results:\n\n" + "\n\n".join(lines), "youtube"

    return None, None
