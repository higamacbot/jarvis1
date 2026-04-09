from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv
import os
from fpdf import FPDF
from jarvis_brain import save_to_brain

import re

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")


def get_youtube_client():
    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def extract_video_id(video_input):
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", video_input)
    return match.group(1) if match else video_input.strip()


def search_youtube(query, max_results=5):
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
                "video_id": video_id
            })
        return results
    except Exception as e:
        return {"error": str(e)}


def sanitize_filename(name):
    import re
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    return name.strip()[:80]

def save_transcript_pdf(video_id, title, channel, transcript_text):
    try:
        base_dir = os.path.join(os.path.dirname(__file__), "transcripts")
        channel_dir = os.path.join(base_dir, sanitize_filename(channel))
        os.makedirs(channel_dir, exist_ok=True)

        filename = sanitize_filename(title) + ".pdf"
        filepath = os.path.join(channel_dir, filename)

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

        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(0, 0, 0)

        # Split transcript into paragraphs for readability
        words = transcript_text.split()
        chunks = [" ".join(words[i:i+80]) for i in range(0, len(words), 80)]
        for chunk in chunks:
            pdf.multi_cell(0, 7, chunk)
            pdf.ln(2)

        pdf.output(filepath)
        return filepath
    except Exception as e:
        return None

def get_transcript(video_input, max_chars=12000):
    try:
        video_id = extract_video_id(video_input)
        ytt = YouTubeTranscriptApi()
        fetched = ytt.fetch(video_id)
        full_text = " ".join([t.text for t in fetched])

        # Get video info for PDF metadata
        try:
            info = get_video_info(video_input)
            title = info.get("title", video_id) if "error" not in info else video_id
            channel = info.get("channel", "Unknown") if "error" not in info else "Unknown"
        except Exception:
            title = video_id
            channel = "Unknown"

        # Save full transcript to PDF automatically
        pdf_path = save_transcript_pdf(video_id, title, channel, full_text)

        # Save to brain (SQLite + Obsidian)
        try:
            brain_result = save_to_brain(
                {
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published_at": info.get("published_at", "") if "error" not in info else "",
                    "views": info.get("views", "N/A") if "error" not in info else "N/A",
                    "likes": info.get("likes", "N/A") if "error" not in info else "N/A",
                    "description": info.get("description", "") if "error" not in info else ""
                },
                full_text,
                pdf_path
            )
        except Exception as e:
            brain_result = {}

        return {
            "video_id": video_id,
            "transcript": full_text[:max_chars],
            "truncated": len(full_text) > max_chars,
            "pdf_path": pdf_path,
            "brain": brain_result
        }
    except Exception as e:
        return {"error": str(e)}


def get_video_info(video_input):
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
            "video_id": video_id
        }
    except Exception as e:
        return {"error": str(e)}


def get_top_comments(video_input, max_results=5):
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
