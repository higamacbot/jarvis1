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


# ─────────────────────────────────────────────────────────────────────────────
# CODE INTELLIGENCE — Review, Bug Scan, Brainstorm
# ─────────────────────────────────────────────────────────────────────────────

import ast
import httpx
import asyncio

BRAINSTORM_DIR = "/Users/higabot1/jarvis1-1/brainstorm"
OLLAMA_URL     = "http://localhost:11434/api/generate"
MODEL          = "qwen3:8b"
PROJECT_PATH   = "/Users/higabot1/jarvis1-1"

# OpenClaw placeholder — wire in when API key available
OPENCLAW_API_KEY = None  # os.getenv("OPENCLAW_API_KEY")
OPENCLAW_URL     = "https://api.openclaw.ai/v1/complete"  # update when confirmed


def scan_for_bugs() -> str:
    """Run py_compile on all .py files and return error report."""
    import py_compile, glob
    files = glob.glob(f"{PROJECT_PATH}/**/*.py", recursive=True)
    errors = []
    clean  = []
    for f in files:
        if "__pycache__" in f:
            continue
        try:
            py_compile.compile(f, doraise=True)
            clean.append(os.path.basename(f))
        except py_compile.PyCompileError as e:
            errors.append(f"❌ {f.replace(PROJECT_PATH,'')}: {e}")

    report = f"BUG SCAN — {len(files)} files checked\n\n"
    if errors:
        report += "ERRORS FOUND:\n" + "\n".join(errors)
    else:
        report += f"✅ All {len(clean)} files compile clean."
    return report


def scan_imports() -> str:
    """Check all imports in main.py and router.py resolve."""
    import importlib, glob
    results = []
    py_files = [
        f"{PROJECT_PATH}/main.py",
        f"{PROJECT_PATH}/bots/router.py",
        f"{PROJECT_PATH}/bot_orchestrator.py",
    ]
    for filepath in py_files:
        if not os.path.exists(filepath):
            continue
        try:
            with open(filepath) as f:
                tree = ast.parse(f.read())
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
            results.append(f"📄 {os.path.basename(filepath)}: {len(imports)} imports parsed OK")
        except SyntaxError as e:
            results.append(f"❌ {os.path.basename(filepath)}: SyntaxError — {e}")
        except Exception as e:
            results.append(f"⚠️ {os.path.basename(filepath)}: {e}")
    return "\n".join(results)


def read_file_for_review(filename: str) -> str:
    """Read a project file for review."""
    # Allow relative or basename
    candidates = [
        filename,
        os.path.join(PROJECT_PATH, filename),
        os.path.join(PROJECT_PATH, "bots", filename),
        os.path.join(PROJECT_PATH, "frontend", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
    return None


async def review_file(filename: str) -> str:
    """Send file to Ollama for code review and suggestions."""
    content = read_file_for_review(filename)
    if not content:
        return f"❌ File not found: {filename}. Try: main.py, router.py, bot_orchestrator.py"

    lines = content.split("\n")
    preview = "\n".join(lines[:200])  # first 200 lines to stay within context

    prompt = f"""You are Doctorbot, a senior software engineer reviewing Python code for the JARVIS HIGA HOUSE project.

Review this file ({filename}) and provide:
1. Any bugs or errors you spot
2. Any risky patterns (hardcoded values, missing error handling, etc.)
3. 2-3 specific improvement suggestions
4. Format each suggestion as: "SUGGESTION: [what] — [exact fix or command to run]"

Be concise and specific. Do not rewrite the whole file.

FILE: {filename}
---
{preview}
---
Your review:"""

    try:
        async with httpx.AsyncClient(timeout=120.0) as h:
            r = await h.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            })
            return r.json().get("response", "No response from Ollama.").strip()
    except Exception as e:
        return f"Review failed: {e}"


async def brainstorm(topic: str) -> str:
    """Generate feature ideas via Ollama and save to brainstorm/ folder."""
    os.makedirs(BRAINSTORM_DIR, exist_ok=True)

    # Read context for grounding
    try:
        with open(CONTEXT_FILE) as f:
            context_summary = f.read()[:2000]
    except:
        context_summary = "JARVIS HIGA HOUSE — multi-agent AI system on Mac Mini"

    prompt = f"""You are Doctorbot brainstorming new features for the JARVIS HIGA HOUSE system.

Project context:
{context_summary}

Brainstorm topic: {topic}

Generate 5-7 concrete, buildable feature ideas. For each idea:
- Name it
- Describe it in 2 sentences
- List what files would need to change
- Rate effort: LOW / MEDIUM / HIGH

Be specific to this actual project, not generic."""

    try:
        async with httpx.AsyncClient(timeout=120.0) as h:
            r = await h.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            })
            ideas = r.json().get("response", "No response.").strip()
    except Exception as e:
        return f"Brainstorm failed: {e}"

    # Save to brainstorm folder
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    safe_topic = topic.replace(" ", "_")[:40]
    filepath = os.path.join(BRAINSTORM_DIR, f"{timestamp}_{safe_topic}.md")
    with open(filepath, "w") as f:
        f.write(f"# Brainstorm: {topic}\n")
        f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}\n\n")
        f.write(ideas)

    return f"💡 BRAINSTORM: {topic}\n\n{ideas}\n\n📁 Saved to: brainstorm/{os.path.basename(filepath)}"


# OpenClaw integration — placeholder, wire in when API key available
async def review_file_openclaw(filename: str) -> str:
    if not OPENCLAW_API_KEY:
        return "OpenClaw not configured yet. Add OPENCLAW_API_KEY to .env when ready."
    # TODO: implement when API confirmed
    return "OpenClaw integration pending API key."


# ─────────────────────────────────────────────────────────────────────────────
# DRAFT WRITER — Doctorbot writes improvement drafts for human review
# ─────────────────────────────────────────────────────────────────────────────

import httpx as _httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "qwen3:8b"
DRAFTS_DIR = "/Users/higabot1/jarvis1-1/drafts"

async def _ask_doctor(prompt: str, timeout: float = 120.0) -> str:
    """Internal Ollama call for Doctorbot drafts."""
    try:
        async with _httpx.AsyncClient(timeout=timeout) as h:
            r = await h.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False
            })
            return r.json().get("response", "").strip()
    except Exception as e:
        return f"Doctorbot error: {e}"


def _save_draft(title: str, content: str) -> str:
    """Save a draft file and return the path."""
    import os
    from datetime import datetime
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe = title.replace(" ", "_")[:40]
    path = os.path.join(DRAFTS_DIR, f"{timestamp}_{safe}.md")
    with open(path, "w") as f:
        f.write(f"# DOCTORBOT DRAFT: {title}\n")
        f.write(f"**Generated:** {datetime.now().strftime('%B %d, %Y @ %I:%M %p')}\n\n")
        f.write(content)
    return path


def read_current_file(filename: str) -> str:
    """Read a project file for analysis."""
    import os
    candidates = [
        os.path.join(REPO_PATH, filename),
        os.path.join(REPO_PATH, "bots", filename),
        os.path.join(REPO_PATH, "frontend", filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
    return f"File not found: {filename}"


async def draft_improvement(filename: str) -> str:
    """
    Doctorbot reads a file and writes an improvement draft.
    Draft is saved to drafts/ folder — paste it here for review.

    Usage in HIGA HOUSE Doctorbot room:
    draft improvement main.py
    draft improvement bots/router.py
    draft improvement briefing_scheduler.py
    """
    content = read_current_file(filename)
    if "not found" in content:
        return content

    prompt = f"""You are Doctorbot, senior software engineer for HIGA HOUSE JARVIS.

Analyze this file and write a structured improvement draft.

CODEBASE RULES:
- sys.path.insert(0, "/Users/higabot1/jarvis1-1") not sys.path.append("..")
- os.getenv() for all API keys, never hardcode
- async/await for httpx calls
- No news_scraper.py or market_scraper.py
- pdf_safe_text() for all FPDF content

FILE: {filename}
---
{content[:5000]}
---

Write a draft with these exact sections:

## ISSUES FOUND
[List each bug or risk with file + line reference]

## SUGGESTED IMPROVEMENTS
[For each improvement, write the EXACT old code and new code to paste]

## PASTE THIS TO FIX
[Ready-to-run terminal commands the user can copy-paste]

## PRIORITY
[HIGH / MEDIUM / LOW and why]

Be specific. Reference exact line numbers. Write code the user can actually paste."""

    result = await _ask_doctor(prompt)
    path = _save_draft(f"improvement_{filename.replace('/', '_')}", result)

    return f"""📋 DOCTORBOT DRAFT WRITTEN
File analyzed: {filename}
Draft saved: {path}

{result[:800]}...

---
NEXT STEP: Copy the draft contents and paste them to Claude for review.
Run this to see the full draft:
  cat {path}"""


async def draft_new_feature(description: str) -> str:
    """
    Doctorbot designs a new feature and writes the implementation draft.

    Usage:
    draft feature add weather bot to HIGA HOUSE
    draft feature wire pinkslip to live odds API
    draft feature add voice input to JARVIS
    """
    prompt = f"""You are Doctorbot, senior software engineer for HIGA HOUSE JARVIS.

Design and write an implementation draft for this feature:
{description}

SYSTEM CONTEXT:
- FastAPI server (main.py) on port 8000
- 15 bots routed via bots/router.py
- Ollama qwen3:8b as LLM backend
- SQLite + ChromaDB memory
- mac_tools.py for Mac control
- fetch.py for web scraping (DO NOT create news_scraper.py)
- multi_broker_portfolio.py for real portfolio data
- briefing_scheduler.py for 5AM/5PM briefings
- autonomous_runner.py for background jobs

Write the draft with these sections:

## FEATURE: {description}

## FILES TO CHANGE
[List each file and exactly what changes]

## NEW CODE TO ADD
[Write the actual Python code, ready to paste]

## ROUTER CHANGES
[Exact addition to bots/router.py if needed]

## TERMINAL COMMANDS
[Step by step paste-ready commands to deploy]

## TEST COMMAND
[How to verify it works after deployment]"""

    result = await _ask_doctor(prompt, timeout=120.0)
    path = _save_draft(f"feature_{description[:40].replace(' ', '_')}", result)

    return f"""💡 DOCTORBOT FEATURE DRAFT
Feature: {description}
Draft saved: {path}

{result[:800]}...

---
NEXT STEP: Paste the draft to Claude for review before deploying."""


async def draft_bug_fix(description: str) -> str:
    """
    Doctorbot investigates a bug and writes the fix draft.

    Usage:
    draft fix roundtable timeout
    draft fix crypto showing wrong values
    draft fix briefing crypto section blank
    """
    # First scan for compile errors
    bugs = scan_for_bugs()

    prompt = f"""You are Doctorbot, senior software engineer for HIGA HOUSE JARVIS.

Investigate this bug and write a fix draft:
BUG: {description}

CURRENT COMPILE STATUS:
{bugs}

CODEBASE RULES:
- sys.path.insert(0, "/Users/higabot1/jarvis1-1") not sys.path.append("..")
- os.getenv() for keys, never hardcode
- async/await for httpx, timeout=240 for roundtable
- Roundtable timeout was previously hardcoded at 120s causing Neural Link Error

Write the fix draft with these sections:

## BUG ANALYSIS
[What is likely causing this bug]

## FILES TO CHECK
[Which files to look at and what to look for]

## THE FIX
[Exact old code and new code, ready to paste]

## TERMINAL COMMANDS
[Step by step paste-ready fix commands]

## HOW TO VERIFY
[How to confirm the bug is fixed]"""

    result = await _ask_doctor(prompt, timeout=120.0)
    path = _save_draft(f"bugfix_{description[:40].replace(' ', '_')}", result)

    return f"""🔧 DOCTORBOT BUG FIX DRAFT
Bug: {description}
Draft saved: {path}

{result[:800]}...

---
NEXT STEP: Paste the draft to Claude for review before applying."""


async def draft_session_summary() -> str:
    """
    Doctorbot reads JARVIS_CONTEXT.md and writes a session summary
    with the top 5 things to work on next.

    Usage:
    draft summary
    """
    try:
        with open(CONTEXT_FILE) as f:
            context = f.read()[-3000:]  # last 3000 chars = recent history
    except Exception as e:
        context = f"Could not read context: {e}"

    prompt = f"""You are Doctorbot, senior software engineer for HIGA HOUSE JARVIS.

Read this project context and write a session summary with next steps.

RECENT CONTEXT:
{context}

Write the summary with these sections:

## WHAT WAS BUILT (last sessions)
[Bullet list of completed features]

## CURRENT SYSTEM STATUS
[What's working, what's not]

## TOP 5 NEXT STEPS (priority order)
[Each with: what it is, why it matters, estimated effort]

## PASTE THIS TO START NEXT SESSION
[The first terminal command to run to continue work]

## OPEN BUGS TO FIX
[Any known issues from the context]"""

    result = await _ask_doctor(prompt, timeout=120.0)
    path = _save_draft("session_summary", result)

    return f"""📊 DOCTORBOT SESSION SUMMARY
Draft saved: {path}

{result[:1000]}...

---
NEXT STEP: Paste this summary to Claude at the start of your next session."""


def list_drafts() -> str:
    """List all drafts in the drafts folder."""
    import os, glob
    from datetime import datetime
    drafts = sorted(glob.glob(f"{DRAFTS_DIR}/*.md"), reverse=True)
    if not drafts:
        return "No drafts yet. Try: draft improvement main.py"
    lines = [f"📋 DRAFTS ({len(drafts)} files):"]
    for d in drafts[:10]:
        size = os.path.getsize(d)
        name = os.path.basename(d)
        lines.append(f"  {name} ({size} bytes)")
    lines.append(f"\nTo read a draft: cat {DRAFTS_DIR}/[filename]")
    lines.append(f"To send to Claude: copy the full output of cat [filename]")
    return "\n".join(lines)
