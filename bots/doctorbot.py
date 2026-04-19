"""
Doctorbot — Software Engineer, Code Reviewer, Git Manager, Context Keeper
Owns JARVIS_CONTEXT.md and all GitHub commits for jarvis1-1
Auto-logs every commit and context access with timestamps
"""
import subprocess
import os
import json
from datetime import datetime

SYSTEM_PROMPT = """You are Doctorbot, the software engineer and systems architect for Higa House.
You own JARVIS_CONTEXT.md and all git operations for jarvis1-1.

Your responsibilities:
- Code review and debugging
- Git commits, pushes, and status checks
- Keeping JARVIS_CONTEXT.md accurate and up to date
- Logging every commit and context access with timestamps
- Reporting last commit time, last context update, repo health

Commands you respond to:
- "git status" — run and report what's changed
- "commit [message]" — stage all, commit, push, log to context
- "last commit" — report when and what was last committed
- "last context update" — report when JARVIS_CONTEXT.md was last touched
- "log [entry]" — append entry to JARVIS_CONTEXT.md timeline
- "read context" — summarize JARVIS_CONTEXT.md
- "repo health" — full status: last commit, untracked files, context age

Rules:
- Never create news_scraper.py or market_scraper.py
- Always use sys.path.insert(0, "/Users/higabot1/jarvis1-1") not sys.path.append('..')
- Always log to JARVIS_CONTEXT.md after every commit
- Speak like a senior engineer: precise, no fluff

Speak like a senior engineer: precise, no fluff, direct."""

NAMESPACE = "doctorbot"
NAME = "Doctorbot"
COLOR = "#00FF88"
REPO_PATH = "/Users/higabot1/jarvis1-1"
CONTEXT_FILE = "/Users/higabot1/jarvis1-1/JARVIS_CONTEXT.md"
STATUS_FILE = "/Users/higabot1/jarvis1-1/.doctorbot_status.json"


def _load_status() -> dict:
    """Load Doctorbot's internal status tracker"""
    try:
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "last_commit_time": None,
            "last_commit_message": None,
            "last_context_read": None,
            "last_context_write": None,
            "total_commits": 0,
            "session_start": datetime.now().isoformat()
        }


def _save_status(status: dict):
    """Save Doctorbot's internal status tracker"""
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)
    except Exception as e:
        print(f">> DOCTORBOT STATUS SAVE ERROR: {e}")


def _now() -> str:
    return datetime.now().strftime("%b %d, %Y @ %I:%M %p")


def git_status() -> str:
    """Get current git status"""
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        status = result.stdout.strip() or "Working tree clean."

        # Get last commit info
        last = subprocess.run(
            ["git", "log", "-1", "--format=%h %s (%cr)"],
            cwd=REPO_PATH, capture_output=True, text=True
        )
        last_commit = last.stdout.strip()

        return f"GIT STATUS:\n{status}\n\nLAST COMMIT: {last_commit}"
    except Exception as e:
        return f"Git error: {e}"


def git_commit_and_push(message: str, files: list = None) -> str:
    """Stage, commit, push, and auto-log to JARVIS_CONTEXT.md"""
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

        # Update status tracker
        status = _load_status()
        status["last_commit_time"] = _now()
        status["last_commit_message"] = message
        status["total_commits"] = status.get("total_commits", 0) + 1
        _save_status(status)

        # Auto-log to JARVIS_CONTEXT.md
        log_to_context(f"Git commit: {message}")

        return f"✅ Committed & pushed: {message}\nLogged to JARVIS_CONTEXT.md."
    except Exception as e:
        return f"Git error: {e}"


def log_to_context(entry: str) -> str:
    """Append a timestamped entry to the JARVIS_CONTEXT.md timeline"""
    try:
        timestamp = _now()
        log_line = f"\n### {timestamp} — {entry}\n"
        with open(CONTEXT_FILE, "a") as f:
            f.write(log_line)

        # Update status tracker
        status = _load_status()
        status["last_context_write"] = timestamp
        _save_status(status)

        return f"✅ Logged to JARVIS_CONTEXT.md at {timestamp}"
    except Exception as e:
        return f"Log error: {e}"


def read_context() -> str:
    """Read JARVIS_CONTEXT.md and record access time"""
    try:
        with open(CONTEXT_FILE, "r") as f:
            content = f.read()

        # Update status tracker
        status = _load_status()
        status["last_context_read"] = _now()
        _save_status(status)

        return content
    except Exception as e:
        return f"Could not read context: {e}"


def repo_health() -> str:
    """Full repo health report"""
    try:
        status = _load_status()

        # Git log
        last_commit = subprocess.run(
            ["git", "log", "-1", "--format=%h — %s — %cd", "--date=format:%b %d %Y %I:%M %p"],
            cwd=REPO_PATH, capture_output=True, text=True
        ).stdout.strip()

        # Untracked/modified files
        git_st = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO_PATH, capture_output=True, text=True
        ).stdout.strip() or "Clean"

        # Context file last modified
        ctx_mtime = datetime.fromtimestamp(
            os.path.getmtime(CONTEXT_FILE)
        ).strftime("%b %d, %Y @ %I:%M %p")

        report = f"""
╔══ DOCTORBOT REPO HEALTH ══════════════════════════
║ Last Commit:         {last_commit}
║ Last Context Write:  {status.get('last_context_write', 'Unknown')}
║ Last Context Read:   {status.get('last_context_read', 'Unknown')}
║ Context File Mtime:  {ctx_mtime}
║ Total Commits (session): {status.get('total_commits', 0)}
║ Git Status:          {git_st}
╚═══════════════════════════════════════════════════
"""
        return report.strip()
    except Exception as e:
        return f"Health check error: {e}"
