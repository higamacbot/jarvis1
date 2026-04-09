import subprocess
import re

APPS = {
    "safari": "Safari",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "spotify": "Spotify",
    "notes": "Notes",
    "terminal": "Terminal",
    "vscode": "Visual Studio Code",
    "finder": "Finder",
    "mail": "Mail",
    "calendar": "Calendar",
    "slack": "Slack",
    "discord": "Discord",
    "obsidian": "Obsidian",
    "music": "Music",
}

def open_app(app_name):
    name = app_name.lower().strip()
    mac_name = APPS.get(name, app_name.title())
    try:
        subprocess.Popen(["open", "-a", mac_name])
        return f"Opening {mac_name}, sir."
    except Exception:
        return f"Couldn't open {mac_name}, sir."

def open_url(url):
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        subprocess.Popen(["open", url])
        return f"Opening {url}, sir."
    except Exception:
        return "Failed to open the link, sir."

def search_youtube(query):
    clean = query.strip().replace(" ", "+")
    return open_url(f"https://www.youtube.com/results?search_query={clean}")

def detect_mac_command(text):
    if not text:
        return None

    t = text.lower().strip()

    # === INTENT CHECK (don't trigger on analysis requests) ===
    analysis_phrases = [
        "thoughts on", "what are your thoughts", "what do you think",
        "your thoughts", "opinion on", "analyze", "analyse", "summarize",
        "summary of", "what is this", "tell me about", "read this",
        "check this", "look at this", "is this", "review this"
    ]

    if any(phrase in t for phrase in analysis_phrases):
        return None

    # === URL DETECTION (improved) ===
    url_match = re.search(
        r'((https?://|www\.)\S+|\b[a-z0-9\-]+\.(com|org|net|io|ai)\b)',
        t
    )

    if url_match and any(kw in t for kw in ["open", "go to", "launch", "show me", "bring up"]):
        return open_url(url_match.group(1))

    # === APP ALIASES ===
    APP_ALIASES = {
        "browser": "safari",
        "code": "vscode",
        "vs code": "vscode",
        "files": "finder",
        "music app": "music"
    }

    for alias, real in APP_ALIASES.items():
        if alias in t:
            return open_app(real)

    # === APP LAUNCH ===
    for keyword in ["open", "launch", "start", "run"]:
        if keyword in t:
            for app_key in APPS:
                if app_key in t:
                    return open_app(app_key)

    # === YOUTUBE (safe trigger) ===
    if "youtube" in t and any(k in t for k in ["open", "play", "watch", "search", "find"]):
        yt_match = re.search(r"(?:open|play|watch|search|find)\s+(.+?)(?:\s+on youtube|$)", t)
        if yt_match:
            query = yt_match.group(1).strip().replace(" ", "+")
            return open_url(f"https://www.youtube.com/results?search_query={query}")
        return open_url("https://www.youtube.com")

    # === GOOGLE SEARCH ===
    if any(k in t for k in ["search for", "google", "look up"]):
        query = re.sub(r'.*(search for|google|look up)\s+', '', t).strip()
        if query:
            return open_url(f"https://www.google.com/search?q={query.replace(' ', '+')}")

    return None
