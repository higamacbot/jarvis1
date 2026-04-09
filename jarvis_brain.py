import os
import re
import json
import sqlite3
import datetime
import requests

BRAIN_DIR = os.path.expanduser("~/Documents/Obsidian Vault")
DB_PATH = os.path.join(os.path.dirname(__file__), "jarvis_brain.db")
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:latest"

os.makedirs(BRAIN_DIR, exist_ok=True)

def init_brain_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT UNIQUE,
            title TEXT,
            channel TEXT,
            url TEXT,
            published_at TEXT,
            views TEXT,
            likes TEXT,
            description TEXT,
            transcript TEXT,
            summary TEXT,
            tags TEXT,
            pdf_path TEXT,
            obsidian_path TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def ask_ollama(prompt):
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {"num_ctx": 8192}
        }, timeout=120)
        return resp.json().get("response", "").strip()
    except Exception as e:
        return f"Error: {e}"

def generate_summary_and_tags(title, channel, description, transcript):
    prompt = f"""You are JARVIS. Analyze this YouTube video and return a JSON object only, no extra text.

Title: {title}
Channel: {channel}
Description: {description[:300]}
Transcript: {transcript[:6000]}

Return this exact JSON format:
{{
  "summary": "3-5 sentence summary of the video",
  "key_points": ["point 1", "point 2", "point 3", "point 4", "point 5"],
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "sentiment": "positive/negative/neutral",
  "topics": ["main topic 1", "main topic 2"]
}}"""

    response = ask_ollama(prompt)
    try:
        clean = re.sub(r"```(?:json)?|```", "", response).strip()
        return json.loads(clean)
    except Exception:
        return {
            "summary": response[:500],
            "key_points": [],
            "tags": [],
            "sentiment": "neutral",
            "topics": []
        }

def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()[:80]

def write_obsidian_note(video_id, title, channel, url, published_at,
                        views, likes, description, summary, key_points,
                        tags, topics, sentiment, pdf_path):
    channel_dir = os.path.join(BRAIN_DIR, sanitize_filename(channel))
    os.makedirs(channel_dir, exist_ok=True)

    filename = sanitize_filename(title) + ".md"
    filepath = os.path.join(channel_dir, filename)

    tag_list = " ".join([f"#{t.replace(' ', '_')}" for t in tags])
    topic_links = " ".join([f"[[{t}]]" for t in topics])
    points_md = "\n".join([f"- {p}" for p in key_points])
    date_saved = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    note = f"""---
title: "{title}"
channel: "{channel}"
url: {url}
published: {published_at}
views: {views}
likes: {likes}
sentiment: {sentiment}
tags: {json.dumps(tags)}
date_saved: {date_saved}
---

# {title}

**Channel:** [[{channel}]]
**Published:** {published_at}
**Views:** {views} | **Likes:** {likes}
**URL:** {url}
**Topics:** {topic_links}
**Tags:** {tag_list}

---

## Summary
{summary}

---

## Key Points
{points_md}

---

## Description
{description[:500]}

---

## PDF Transcript
{pdf_path if pdf_path else "Not available"}

---
*Saved by JARVIS on {date_saved}*
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(note)

    return filepath

def save_to_brain(video_info, transcript_text, pdf_path=None):
    video_id = video_info.get("video_id", "")
    title = video_info.get("title", "Unknown")
    channel = video_info.get("channel", "Unknown")
    url = video_info.get("url", "")
    published_at = video_info.get("published_at", "")
    views = video_info.get("views", "N/A")
    likes = video_info.get("likes", "N/A")
    description = video_info.get("description", "")

    analysis = generate_summary_and_tags(title, channel, description, transcript_text)
    summary = analysis.get("summary", "")
    key_points = analysis.get("key_points", [])
    tags = analysis.get("tags", [])
    sentiment = analysis.get("sentiment", "neutral")
    topics = analysis.get("topics", [])

    obsidian_path = write_obsidian_note(
        video_id, title, channel, url, published_at,
        views, likes, description, summary, key_points,
        tags, topics, sentiment, pdf_path
    )

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO videos
        (video_id, title, channel, url, published_at, views, likes,
         description, transcript, summary, tags, pdf_path, obsidian_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        video_id, title, channel, url, published_at, views, likes,
        description, transcript_text[:50000], summary,
        json.dumps(tags), pdf_path, obsidian_path,
        datetime.datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    return {
        "summary": summary,
        "key_points": key_points,
        "tags": tags,
        "topics": topics,
        "sentiment": sentiment,
        "obsidian_path": obsidian_path
    }

def search_brain(query, limit=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT title, channel, url, summary, tags, created_at
        FROM videos
        WHERE title LIKE ? OR summary LIKE ? OR tags LIKE ? OR transcript LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_recent_brain(limit=10):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT title, channel, url, summary, tags, created_at
        FROM videos
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

init_brain_db()
