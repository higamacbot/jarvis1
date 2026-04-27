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
    "imovie": "iMovie",
    "garageband": "GarageBand",
    "garage band": "GarageBand",
    "finalcut": "Final Cut Pro",
    "final cut": "Final Cut Pro",
    "logic": "Logic Pro",
    "logicpro": "Logic Pro",
    "quicktime": "QuickTime Player",
    "photos": "Photos",
    "capcut": "CapCut",
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

    # === CREATIVE APP SHORTCUTS ===
    if any(k in t for k in ["imovie", "i movie"]):
        return open_imovie()
    if any(k in t for k in ["garageband", "garage band", "garage"]):
        return open_garageband()
    if any(k in t for k in ["final cut", "finalcut"]):
        return open_final_cut()
    if any(k in t for k in ["logic pro", "logic"]) and "open" in t:
        return open_logic_pro()

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


# ── CREATIVE APP LAUNCHERS ────────────────────────────────────────────────────

def open_imovie(project_path: str = None) -> str:
    """Open iMovie, optionally with a project file."""
    try:
        if project_path:
            subprocess.Popen(["open", "-a", "iMovie", project_path])
            return f"Opening iMovie with project: {project_path}"
        else:
            subprocess.Popen(["open", "-a", "iMovie"])
            return "Opening iMovie, sir. Ready for editing."
    except Exception as e:
        return f"Could not open iMovie: {e}"

def open_garageband(template_path: str = None) -> str:
    """Open GarageBand, optionally with a template file."""
    try:
        if template_path:
            subprocess.Popen(["open", "-a", "GarageBand", template_path])
            return f"Opening GarageBand with: {template_path}"
        else:
            subprocess.Popen(["open", "-a", "GarageBand"])
            return "Opening GarageBand, sir. Ready to produce."
    except Exception as e:
        return f"Could not open GarageBand: {e}"

def open_final_cut(project_path: str = None) -> str:
    """Open Final Cut Pro."""
    try:
        if project_path:
            subprocess.Popen(["open", "-a", "Final Cut Pro", project_path])
        else:
            subprocess.Popen(["open", "-a", "Final Cut Pro"])
        return "Opening Final Cut Pro, sir."
    except Exception as e:
        return f"Could not open Final Cut Pro: {e}. Do you have it installed?"

def open_logic_pro() -> str:
    """Open Logic Pro."""
    try:
        subprocess.Popen(["open", "-a", "Logic Pro"])
        return "Opening Logic Pro, sir."
    except Exception as e:
        return f"Could not open Logic Pro: {e}. Do you have it installed?"

def reveal_in_finder(path: str) -> str:
    """Reveal a file or folder in Finder."""
    try:
        subprocess.Popen(["open", "-R", path])
        return f"Revealing in Finder: {path}"
    except Exception as e:
        return f"Could not reveal in Finder: {e}"

def create_garageband_template(beat_name: str, bpm: int = 120, output_dir: str = None) -> str:
    """
    Create a GarageBand-compatible project starter note.
    GarageBand projects are .band bundles — we create a setup note
    and open GarageBand so the user can create the project manually.
    Returns instructions + opens GarageBand.
    """
    import os
    from datetime import datetime

    if output_dir is None:
        output_dir = os.path.expanduser("~/Music/GarageBand Projects")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = beat_name.replace(" ", "_")[:30]
    note_path = os.path.join(output_dir, f"{timestamp}_{safe_name}_setup.txt")

    setup_note = f"""GARAGEBAND SETUP — {beat_name}
Generated by HIGA HOUSE JAMZ
Date: {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}

PROJECT SETTINGS:
  Name: {beat_name}
  BPM: {bpm}
  Time Signature: 4/4
  Key: (see beat design file in ~/jarvis1-1/beats/)

QUICK SETUP STEPS:
1. Open GarageBand
2. New Project → Empty Project
3. Set BPM to {bpm} in the transport bar
4. Add Software Instrument track → Drummer (for drums)
5. Add Software Instrument track → Bass (for bassline)
6. Add Software Instrument track → Synthesizer (for lead)
7. Import any samples from ~/jarvis1-1/beats/ folder

BEAT REFERENCE:
See the full beat design in ~/jarvis1-1/beats/ for drum patterns,
bassline notes, and layer suggestions.
"""

    with open(note_path, 'w') as f:
        f.write(setup_note)

    # Open GarageBand
    open_garageband()

    return f"GarageBand opened. Setup note saved to:\n{note_path}\n\nSet BPM to {bpm} in the transport bar when GarageBand loads."

def create_imovie_script_package(title: str, script: str, output_dir: str = None) -> str:
    """
    Save a video script as a production package and open iMovie.
    Creates a folder with the script, shot list, and b-roll notes.
    """
    import os
    from datetime import datetime

    if output_dir is None:
        output_dir = os.path.expanduser("~/Movies/HIGA HOUSE Productions")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_title = title.replace(" ", "_")[:40]
    project_dir = os.path.join(output_dir, f"{timestamp}_{safe_title}")
    os.makedirs(project_dir, exist_ok=True)

    # Save script
    script_path = os.path.join(project_dir, "script.md")
    with open(script_path, 'w') as f:
        f.write(f"# {title}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}\n\n")
        f.write(script)

    # Save shot list
    shot_list_path = os.path.join(project_dir, "shot_list.md")
    with open(shot_list_path, 'w') as f:
        f.write(f"# Shot List — {title}\n\n")
        f.write("## Shots to Film\n\n")
        f.write("| # | Shot | Duration | Notes |\n")
        f.write("|---|------|----------|-------|\n")
        f.write("| 1 | Hook shot | 0-3s | High energy opener |\n")
        f.write("| 2 | Main content | 3-60s | Core of the video |\n")
        f.write("| 3 | CTA outro | 60-90s | Call to action |\n\n")
        f.write("## B-Roll List\n\n")
        f.write("- Screen recordings\n- Phone footage\n- Stock footage\n")

    # Open iMovie
    open_imovie()

    return f"""iMovie opened. Production package created at:
📁 {project_dir}

Files:
  📄 script.md — full script
  🎬 shot_list.md — shots to film

Open iMovie → New Movie → Import your footage
Use the script as your teleprompter guide."""
