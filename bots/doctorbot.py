"""
Doctorbot — Software Engineer, Code Reviewer, Git Manager, Context Keeper
Owns JARVIS_CONTEXT.md and all GitHub commits for jarvis1-1
"""
import subprocess
import os
from datetime import datetime

SYSTEM_PROMPT = """You are Doctorbot, the software engineer and systems architect for Higa House.
You are also the official keeper of JARVIS_CONTEXT.md and all git operations.

Your responsibilities:
- Code review and debugging
- Git commits, pushes, and status checks
- Keeping JARVIS_CONTEXT.md accurate and up to date
- Logging mistakes and fixes in the timeline
- Ensuring no duplicate files get created (check before creating)

Rules:
- Always check existing files before suggesting new ones
- Never create news_scraper.py or market_scraper.py — fetch.py handles scraping
- Always use sys.path.insert(0, "/Users/higabot1/jarvis1-1") not sys.path.append('..')
- When asked for git status, run it and report accurately
- When logging a fix, add it to JARVIS_CONTEXT.md timeline with today's date

Speak like a senior engineer: precise, no fluff, direct."""

NAMESPACE = "doctorbot"
NAME = "Doctorbot"
COLOR = "#00FF88"
REPO_PATH = "/Users/higabot1/jarvis1-1"
CONTEXT_FILE = "/Users/higabot1/jarvis1-1/JARVIS_CONTEXT.md"


def git_status() -> str:
    """Get current git status"""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        return result.stdout.strip() or "Working tree clean."
    except Exception as e:
        return f"Git error: {e}"


def git_commit_and_push(message: str, files: list = None) -> str:
    """Stage, commit, and push files"""
    try:
        if files:
            subprocess.run(["git", "add"] + files, cwd=REPO_PATH, check=True)
        else:
            subprocess.run(["git", "add", "-A"], cwd=REPO_PATH, check=True)

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            return "Nothing new to commit."

        push = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        return f"✅ Committed & pushed: {message}"
    except Exception as e:
        return f"Git error: {e}"


def log_to_context(entry: str) -> str:
    """Append a timestamped entry to the JARVIS_CONTEXT.md timeline"""
    try:
        date_str = datetime.now().strftime("%b %d, %Y")
        log_line = f"\n### {date_str} — {entry}\n"
        with open(CONTEXT_FILE, "a") as f:
            f.write(log_line)
        return f"✅ Logged to JARVIS_CONTEXT.md: {entry}"
    except Exception as e:
        return f"Log error: {e}"


def read_context() -> str:
    """Read JARVIS_CONTEXT.md"""
    try:
        with open(CONTEXT_FILE, "r") as f:
            return f.read()
    except Exception as e:
        return f"Could not read context: {e}"


def get_untracked_files() -> str:
    """List untracked and modified files"""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        return result.stdout.strip() or "All clean."
    except Exception as e:
        return f"Git error: {e}"
