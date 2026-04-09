content = open("server.py").read()

if "import re" not in content:
    content = content.replace("import datetime\n", "import datetime\nimport re\n")

if "from youtube_tools import" not in content:
    content = content.replace(
        "from fetch import extract_urls, fetch_url\n",
        "from fetch import extract_urls, fetch_url\nfrom youtube_tools import search_youtube, get_transcript, get_video_info, get_top_comments\n"
    )

insert_before = 'def chat(question, context="", mode="chat"):'
youtube_handler = '''def handle_youtube_request(question):
    q = question.lower().strip()

    url_match = re.search(r"(https?://(?:www\\.)?(?:youtube\\.com/watch\\?v=[A-Za-z0-9_-]{11}[^\\s]*|youtu\\.be/[A-Za-z0-9_-]{11}[^\\s]*))", question)
    has_url = bool(url_match)
    url = url_match.group(1) if has_url else ""

    if has_url and any(word in q for word in ["transcript", "full transcript", "exact transcript"]):
        transcript = get_transcript(url, max_chars=12000)
        if "error" in transcript:
            return f"I couldn't retrieve the transcript, sir. {transcript['error']}", "youtube"

        info = get_video_info(url)
        if "error" in info:
            return (
                f"Transcript:\\n\\n{transcript['transcript']}"
                + ("\\n\\nNote: transcript was truncated." if transcript.get("truncated") else "")
            ), "youtube"

        answer = (
            f"Title: {info['title']}\\n"
            f"Channel: {info['channel']}\\n"
            f"Published: {info['published_at']}\\n"
            f"URL: {info['url']}\\n\\n"
            f"Transcript:\\n{transcript['transcript']}"
        )
        if transcript.get("truncated"):
            answer += "\\n\\nNote: transcript was truncated."
        return answer, "youtube"

    if has_url and any(word in q for word in ["comments", "top comments", "best comments"]):
        info = get_video_info(url)
        comments = get_top_comments(url, max_results=5)

        if isinstance(comments, dict) and "error" in comments:
            return f"I couldn't retrieve the comments, sir. {comments['error']}", "youtube"

        lines = []
        for i, item in enumerate(comments, 1):
            lines.append(f"{i}. {item['author']} ({item['likes']} likes): {item['text']}")

        header = ""
        if "error" not in info:
            header = (
                f"Title: {info['title']}\\n"
                f"Channel: {info['channel']}\\n"
                f"Published: {info['published_at']}\\n"
                f"URL: {info['url']}\\n\\n"
            )

        return header + "Top comments:\\n" + "\\n\\n".join(lines), "youtube"

    if has_url and any(word in q for word in ["info", "details", "views", "likes", "description", "channel", "post date", "published", "about this video"]):
        info = get_video_info(url)
        if "error" in info:
            return f"I couldn't retrieve the video details, sir. {info['error']}", "youtube"

        comments = get_top_comments(url, max_results=3)
        comment_text = ""
        if isinstance(comments, list) and comments:
            comment_lines = [f"- {c['author']} ({c['likes']} likes): {c['text']}" for c in comments]
            comment_text = "\\nTop comments:\\n" + "\\n".join(comment_lines)

        return (
            f"Title: {info['title']}\\n"
            f"Channel: {info['channel']}\\n"
            f"Published: {info['published_at']}\\n"
            f"Views: {info['views']}\\n"
            f"Likes: {info['likes']}\\n"
            f"Comment count: {info['comments']}\\n"
            f"Duration: {info['duration']}\\n"
            f"URL: {info['url']}\\n\\n"
            f"Description:\\n{info['description'][:1200]}"
            f"{comment_text}"
        ), "youtube"

    if has_url:
        info = get_video_info(url)
        if "error" in info:
            return None, None

        transcript = get_transcript(url, max_chars=6000)
        comments = get_top_comments(url, max_results=3)

        answer = (
            f"Title: {info['title']}\\n"
            f"Channel: {info['channel']}\\n"
            f"Published: {info['published_at']}\\n"
            f"Views: {info['views']}\\n"
            f"Likes: {info['likes']}\\n"
            f"Comment count: {info['comments']}\\n"
            f"Duration: {info['duration']}\\n"
            f"URL: {info['url']}\\n\\n"
            f"Description:\\n{info['description'][:1200]}"
        )

        if isinstance(comments, list) and comments:
            answer += "\\n\\nTop comments:\\n" + "\\n".join(
                [f"- {c['author']} ({c['likes']} likes): {c['text']}" for c in comments]
            )

        if isinstance(transcript, dict) and "transcript" in transcript:
            answer += "\\n\\nTranscript excerpt:\\n" + transcript["transcript"][:3000]
            if transcript.get("truncated"):
                answer += "\\n\\nNote: transcript was truncated."

        return answer, "youtube"

    search_triggers = [
        "youtube", "videos about", "videos on", "find videos", "search youtube",
        "show me videos", "find me videos", "look up videos"
    ]
    if any(trigger in q for trigger in search_triggers):
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

        lines = []
        for i, item in enumerate(results, 1):
            lines.append(
                f"{i}. {item['title']}\\n"
                f"   Channel: {item['channel']}\\n"
                f"   Published: {item['published_at']}\\n"
                f"   URL: {item['url']}"
            )

        return "Top YouTube results:\\n\\n" + "\\n\\n".join(lines), "youtube"

    return None, None


'''

if "def handle_youtube_request(question):" not in content:
    content = content.replace(insert_before, youtube_handler + insert_before)

old_block = '''            # Check for Mac commands first
            mac_result = detect_mac_command(question)
            if mac_result:
                await websocket.send_json({
                    "type": "answer",
                    "text": mac_result,
                    "mode": "mac",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, speak, mac_result)
                continue

            await websocket.send_json({"type": "status", "text": "Analyzing..."})'''

new_block = '''            # Check for Mac commands first
            mac_result = detect_mac_command(question)
            if mac_result:
                await websocket.send_json({
                    "type": "answer",
                    "text": mac_result,
                    "mode": "mac",
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, speak, mac_result)
                continue

            yt_result, yt_mode = handle_youtube_request(question)
            if yt_result:
                await websocket.send_json({
                    "type": "answer",
                    "text": yt_result,
                    "mode": yt_mode,
                    "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
                })
                loop = asyncio.get_event_loop()
                loop.run_in_executor(None, speak, yt_result)
                continue

            await websocket.send_json({"type": "status", "text": "Analyzing..."})'''

content = content.replace(old_block, new_block)

with open("server.py", "w") as f:
    f.write(content)

print("Done")
