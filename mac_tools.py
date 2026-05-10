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

def create_garageband_template(beat_name: str, bpm: int = 120, key: str = "C",
                               output_dir: str = None) -> str:
    """
    Generate a real .mid file for the beat and open it directly in GarageBand.
    GarageBand will create a new project from the MIDI file automatically.
    Also saves a companion setup note with the full beat spec.
    """
    import os
    from datetime import datetime

    if output_dir is None:
        output_dir = os.path.expanduser("~/Music/GarageBand Projects")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = beat_name.replace(" ", "_")[:30]

    # Generate MIDI file
    try:
        import sys
        sys.path.insert(0, "/Users/higabot1/jarvis1-1")
        from bots.jamz_midi import generate_midi
        midi_path = generate_midi(bpm=bpm, key=key, bars=4, output_dir=output_dir,
                                  filename=f"{timestamp}_{safe_name}.mid")
        midi_status = f"MIDI file: {midi_path}"
    except Exception as e:
        midi_path = None
        midi_status = f"MIDI generation failed: {e}"

    # Companion setup note
    note_path = os.path.join(output_dir, f"{timestamp}_{safe_name}_setup.txt")
    setup_note = f"""GARAGEBAND SETUP — {beat_name}
Generated by HIGA HOUSE JAMZ
Date: {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}

PROJECT SETTINGS:
  Name: {beat_name}
  BPM: {bpm}
  Key: {key}
  Time Signature: 4/4

MIDI FILE: {midi_path or 'not generated'}

NEXT STEPS:
1. GarageBand opens the .mid file as a new project automatically
2. Confirm BPM is set to {bpm} in the transport bar
3. Add Software Instrument tracks for lead and pads
4. Reference the beat design in ~/jarvis1-1/beats/ for layers
"""
    with open(note_path, "w") as f:
        f.write(setup_note)

    # Open GarageBand — with MIDI file if generated, bare otherwise
    if midi_path:
        subprocess.Popen(["open", "-a", "GarageBand", midi_path])
        action = f"GarageBand opening with MIDI file — project will be created automatically."
    else:
        subprocess.Popen(["open", "-a", "GarageBand"])
        action = f"GarageBand opened. {midi_status}"

    return f"{action}\n\nBPM: {bpm} | Key: {key}\nMIDI: {midi_path or 'unavailable'}\nSetup note: {note_path}"

def create_imovie_script_package(title: str, script: str, output_dir: str = None) -> str:
    """
    Save a video script as a production package, reveal it in Finder, and open iMovie.
    Creates: script.md, shot_list.md, sora_prompts.md, prompts.json, and media folders.
    """
    import os
    import re
    import json
    import glob
    from datetime import datetime
    from bots.robowright_assets import build_shot_prompts, write_sora_prompts_markdown, write_prompts_json

    if output_dir is None:
        output_dir = os.path.expanduser("~/Movies/HIGA HOUSE Productions")
    os.makedirs(output_dir, exist_ok=True)

    safe_title = re.sub(r'[^a-z0-9]+', '_', title.lower().strip()).strip('_')[:40]
    project_dir = os.path.join(output_dir, safe_title)
    is_new = not os.path.isdir(project_dir)
    os.makedirs(project_dir, exist_ok=True)

    media_dir = os.path.join(project_dir, "media")
    generated_dir = os.path.join(media_dir, "generated")
    source_dir = os.path.join(media_dir, "source")
    os.makedirs(media_dir, exist_ok=True)
    os.makedirs(source_dir, exist_ok=True)
    # Always wipe and refresh generated/ so stale clips don't accumulate
    if os.path.isdir(generated_dir):
        import shutil as _shutil
        _shutil.rmtree(generated_dir)
    os.makedirs(generated_dir, exist_ok=True)

    with open(os.path.join(media_dir, "DROP_FOOTAGE_HERE.txt"), "w") as f:
        f.write(f"Drop your video clips, screen recordings, and audio here.\n"
                f"Then in iMovie: File → Import Media → select this folder.\n\n"
                f"Project: {title}\nCreated: {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}\n")

    beats_dir = os.path.expanduser("~/jarvis1-1/beats")
    recent_beats = sorted(glob.glob(os.path.join(beats_dir, "*.mid")), reverse=True)
    beat_note = ""
    if recent_beats:
        import shutil
        beat_src = recent_beats[0]
        beat_dst = os.path.join(source_dir, os.path.basename(beat_src))
        try:
            shutil.copy2(beat_src, beat_dst)
            beat_note = f"\n  🎵 Latest JAMZ beat copied: {os.path.basename(beat_src)}"
        except Exception:
            pass

    script_path = os.path.join(project_dir, "script.md")
    with open(script_path, "w") as f:
        f.write(f"# {title}\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}\n\n")
        f.write(script)

    prompts = build_shot_prompts(title, script)

    shot_list_path = os.path.join(project_dir, "shot_list.md")
    with open(shot_list_path, "w") as f:
        f.write(f"# Shot List — {title}\n\n")
        f.write("| # | Purpose | Duration | Visual | Camera |\n")
        f.write("|---|---------|----------|--------|--------|\n")
        for shot in prompts:
            visual = shot["visual"].replace("|", "/")
            camera = shot["camera"].replace("|", "/")
            f.write(f"| {shot['shot']} | {shot['purpose']} | {shot['duration_sec']}s | {visual} | {camera} |\n")
        f.write("\n## B-Roll\n- Screen recordings\n- Phone footage\n- Stock footage\n")

    sora_md_path = os.path.join(project_dir, "sora_prompts.md")
    prompts_json_path = os.path.join(project_dir, "prompts.json")
    write_sora_prompts_markdown(title, prompts, sora_md_path)
    write_prompts_json(prompts, prompts_json_path)

    try:
        from bots.video_asset_generator import generate_stub_assets
        generate_stub_assets(generated_dir, prompts, title)
        asset_note = f"\n  media/generated/generation_manifest.json\n  media/generated/shot_01.txt … shot_{len(prompts):02d}.txt"
    except Exception as e:
        asset_note = f"\n  (stub asset generation skipped: {e})"

    clip_paths = []
    fcpxml_path = None
    try:
        from bots.placeholder_clip_generator import generate_placeholder_clips
        from bots.fcpxml_generator import generate_fcpxml
        clip_paths = generate_placeholder_clips(prompts, generated_dir)
        if clip_paths:
            fcpxml_path = generate_fcpxml(title, prompts, clip_paths, project_dir)
    except Exception as e:
        print(f">> ROBOWRIGHT: rough cut generation failed: {e}")

    # Update draft registry
    registry_path = os.path.join(output_dir, "draft_registry.json")
    try:
        registry = json.loads(open(registry_path).read()) if os.path.exists(registry_path) else {}
    except Exception:
        registry = {}
    registry[safe_title] = {
        "title": title,
        "project_dir": project_dir,
        "fcpxml_path": fcpxml_path or "",
        "last_updated": datetime.now().isoformat(),
    }
    try:
        with open(registry_path, "w") as _rf:
            json.dump(registry, _rf, indent=2)
    except Exception as e:
        print(f">> ROBOWRIGHT: registry write failed: {e}")

    draft_label = "new draft" if is_new else "existing draft refreshed"
    subprocess.Popen(["open", project_dir])
    if fcpxml_path:
        subprocess.Popen(["open", "-a", "iMovie", fcpxml_path])
        try:
            from bots.imovie_automation import automate_imovie_new_project
            automate_imovie_new_project(delay_secs=2.5)
        except Exception as _e:
            print(f">> ROBOWRIGHT: imovie_automation unavailable: {_e}")
        imovie_note = f"\n  project.fcpxml ({len(clip_paths)} clips in timeline)"
    else:
        subprocess.Popen(["open", "-a", "iMovie"])
        imovie_note = ""

    return (f"iMovie opening with rough cut timeline ({draft_label}).\nProduction folder:\n{project_dir}\n\n"
            f"Files:\n  script.md\n  shot_list.md\n  sora_prompts.md\n  prompts.json\n  media/generated/\n  media/source/{beat_note}{asset_note}{imovie_note}\n\n"
            f"Press play in iMovie to preview the rough cut.")
