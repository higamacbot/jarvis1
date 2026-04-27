"""
pc_control.py — HIGA HOUSE Computer Control
Lets bots perform real actions on the Mac.
REQUIRES: pip install pyautogui pillow
"""
import subprocess, os, time
from datetime import datetime

SCREENSHOTS_DIR = os.path.expanduser("~/jarvis1-1/screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

try:
    import pyautogui
    pyautogui.PAUSE = 0.5
    pyautogui.FAILSAFE = True
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print(">> PC CONTROL: pyautogui not installed - run: pip install pyautogui pillow")

# ── SCREEN ────────────────────────────────────────────────────────────────────

def take_screenshot(label: str = "screen") -> str:
    if not PYAUTOGUI_AVAILABLE:
        return "pyautogui not installed"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCREENSHOTS_DIR, f"{timestamp}_{label}.png")
    pyautogui.screenshot().save(path)
    return path

def get_screen_size() -> tuple:
    if not PYAUTOGUI_AVAILABLE:
        return (1920, 1080)
    return pyautogui.size()

# ── MOUSE ─────────────────────────────────────────────────────────────────────

def click(x: int, y: int, button: str = "left") -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.click(x, y, button=button)
    return f"Clicked {button} at ({x}, {y})"

def double_click(x: int, y: int) -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.doubleClick(x, y)
    return f"Double-clicked at ({x}, {y})"

def move_to(x: int, y: int) -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.moveTo(x, y, duration=0.3)
    return f"Moved to ({x}, {y})"

def scroll(x: int, y: int, clicks: int = 3) -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.scroll(clicks, x=x, y=y)
    return f"Scrolled {clicks} at ({x}, {y})"

# ── KEYBOARD ──────────────────────────────────────────────────────────────────

def type_text(text: str, interval: float = 0.05) -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.write(text, interval=interval)
    return f"Typed: {text[:50]}"

def press_key(key: str) -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.press(key)
    return f"Pressed: {key}"

def hotkey(*keys) -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"

def cmd(key: str) -> str:
    if not PYAUTOGUI_AVAILABLE: return "pyautogui not installed"
    pyautogui.hotkey('command', key)
    return f"CMD+{key}"

# ── APPS ──────────────────────────────────────────────────────────────────────

def open_app(app_name: str) -> str:
    subprocess.Popen(["open", "-a", app_name])
    time.sleep(1.5)
    return f"Opened {app_name}"

def quit_app(app_name: str) -> str:
    subprocess.run(["osascript", "-e", f'quit app "{app_name}"'])
    return f"Quit {app_name}"

def open_url(url: str, browser: str = "Safari") -> str:
    if not url.startswith("http"):
        url = "https://" + url
    subprocess.Popen(["open", "-a", browser, url])
    time.sleep(2)
    return f"Opened {url}"

# ── TERMINAL ──────────────────────────────────────────────────────────────────

ALLOWED_COMMANDS = [
    "python3", "git", "ls", "cat", "echo", "grep",
    "brew", "pip", "curl", "open", "say", "mkdir",
    "cp", "mv", "rm", "tail", "head", "wc", "find"
]

def run_command(command: str, timeout: int = 30) -> str:
    first_word = command.strip().split()[0]
    if first_word not in ALLOWED_COMMANDS:
        return f"Command '{first_word}' not allowed. Allowed: {', '.join(ALLOWED_COMMANDS)}"
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True,
            text=True, timeout=timeout,
            cwd="/Users/higabot1/jarvis1-1"
        )
        return result.stdout.strip() or result.stderr.strip() or "Done."
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"

# ── FILES ─────────────────────────────────────────────────────────────────────

def open_file(path: str) -> str:
    subprocess.Popen(["open", path])
    return f"Opened: {path}"

def reveal_in_finder(path: str) -> str:
    subprocess.Popen(["open", "-R", path])
    return f"Revealed: {path}"

def read_file(path: str, max_chars: int = 2000) -> str:
    try:
        with open(path) as f:
            return f.read()[:max_chars]
    except Exception as e:
        return f"Read error: {e}"

def write_file(path: str, content: str) -> str:
    try:
        with open(path, 'w') as f:
            f.write(content)
        return f"Written: {path}"
    except Exception as e:
        return f"Write error: {e}"

# ── SPEAK ─────────────────────────────────────────────────────────────────────

def speak(text: str) -> str:
    clean = text[:200].replace('"', '')
    subprocess.Popen(["say", clean])
    return f"Speaking: {clean[:50]}"

# ── BOT TASK SEQUENCES ────────────────────────────────────────────────────────

def doctorbot_run_health_check() -> str:
    return run_command(
        "python3 -m py_compile main.py bots/router.py bot_orchestrator.py "
        "autonomous_runner.py briefing_scheduler.py && echo 'ALL CLEAN'"
    )

def doctorbot_git_status() -> str:
    return run_command("git status --short && git log --oneline -3")

def robowright_open_last_project() -> str:
    import glob
    projects = sorted(glob.glob(
        os.path.expanduser("~/Movies/HIGA HOUSE Productions/*/script.md")
    ), reverse=True)
    if projects:
        open_file(projects[0])
        open_app("iMovie")
        return f"Opened latest project: {os.path.dirname(projects[0])}"
    return "No projects found in ~/Movies/HIGA HOUSE Productions"

def jamz_open_last_beat() -> str:
    import glob, re
    beats = sorted(glob.glob("/Users/higabot1/jarvis1-1/beats/*.md"), reverse=True)
    if beats:
        content = read_file(beats[0])
        bpm_match = re.search(r'BPM[:\s\*]+(\d+)', content)
        bpm = bpm_match.group(1) if bpm_match else "120"
        open_file(beats[0])
        open_app("GarageBand")
        return f"Opened latest beat: {os.path.basename(beats[0])}\nBPM: {bpm} — set this in GarageBand transport bar"
    return "No beats found"

def jarvis_screenshot_status() -> str:
    path = take_screenshot("jarvis_status")
    return f"Screenshot saved: {path}"
