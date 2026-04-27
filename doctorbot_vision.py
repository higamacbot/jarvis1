"""
doctorbot_vision.py — Doctorbot Screen Vision + Auto-Fix Pipeline
Screenshots screen, reads errors with Gemini Vision, writes fixes, pushes to GitHub.
INSTALL: pip3 install pyautogui pillow --break-system-packages
"""
import os, sys, base64, subprocess, py_compile, tempfile, glob
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/Users/higabot1/jarvis1-1")

REPO_PATH     = "/Users/higabot1/jarvis1-1"
DRAFTS_DIR    = "/Users/higabot1/jarvis1-1/drafts"
SCREENSHOTS   = "/Users/higabot1/jarvis1-1/screenshots"
GEMINI_KEY    = os.getenv("GEMINI_API_KEY")
GEMINI_VISION = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
OLLAMA_URL    = "http://localhost:11434/api/generate"
MODEL         = "qwen3:8b"

os.makedirs(DRAFTS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS, exist_ok=True)


def take_screenshot(label: str = "doctorbot") -> str:
    try:
        import pyautogui
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOTS, f"{timestamp}_{label}.png")
        pyautogui.screenshot().save(path)
        print(f">> DOCTORBOT VISION: Screenshot saved to {path}")
        return path
    except Exception as e:
        return f"Screenshot failed: {e}"


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


async def read_screen_with_gemini(image_path: str, question: str = None) -> str:
    import httpx
    if not GEMINI_KEY:
        return "Gemini API key not set"
    if not os.path.exists(image_path):
        return f"Screenshot not found: {image_path}"
    prompt = question or (
        "You are Doctorbot, a senior software engineer. "
        "Look at this Mac terminal/code screenshot. Extract: "
        "1. Exact error messages "
        "2. File and line number "
        "3. Error type (SyntaxError, ImportError, etc.) "
        "4. Any stack trace "
        "5. Visible code. Be precise and quote exact error text."
    )
    image_data = encode_image_base64(image_path)
    try:
        async with httpx.AsyncClient(timeout=30.0) as h:
            r = await h.post(
                f"{GEMINI_VISION}?key={GEMINI_KEY}",
                json={"contents": [{"parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/png", "data": image_data}}
                ]}]}
            )
            data = r.json()
            if "candidates" in data:
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return f"Gemini Vision error: {data.get('error', data)}"
    except Exception as e:
        return f"Vision API error: {e}"


def read_project_file(filepath: str) -> str:
    candidates = [
        os.path.join(REPO_PATH, filepath),
        os.path.join(REPO_PATH, "bots", filepath),
        os.path.join(REPO_PATH, "frontend", filepath),
        filepath,
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as f:
                return f.read()
    return f"File not found: {filepath}"


def scan_all_files_for_errors() -> dict:
    errors = {}
    clean = []
    for filepath in glob.glob(f"{REPO_PATH}/**/*.py", recursive=True):
        if "__pycache__" in filepath or ".bak" in filepath:
            continue
        try:
            py_compile.compile(filepath, doraise=True)
            clean.append(os.path.basename(filepath))
        except py_compile.PyCompileError as e:
            errors[filepath] = str(e)
    return {"errors": errors, "clean": clean}


async def generate_fix(error_description: str, file_content: str, filename: str) -> str:
    import httpx
    system_prompt = """You are Doctorbot, senior software engineer for HIGA HOUSE JARVIS.
Fix Python errors. Rules:
- Use sys.path.insert(0, "/Users/higabot1/jarvis1-1") not sys.path.append("..")
- Never hardcode API keys, use os.getenv()
- Use async/await for httpx calls
- Add error handling
- Output ONLY the complete fixed Python file, no markdown"""

    user_prompt = f"File: {filename}\n\nERROR:\n{error_description}\n\nCURRENT FILE:\n{file_content[:4000]}\n\nReturn the complete fixed file:"

    if GEMINI_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as h:
                r = await h.post(
                    f"{GEMINI_VISION}?key={GEMINI_KEY}",
                    json={"contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}]}
                )
                data = r.json()
                if "candidates" in data:
                    result = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    for fence in ["```python", "```"]:
                        result = result.replace(fence, "").strip()
                    return result
        except Exception as e:
            print(f">> GEMINI FIX ERROR: {e}")

    try:
        async with httpx.AsyncClient(timeout=120.0) as h:
            r = await h.post(OLLAMA_URL, json={
                "model": MODEL,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False
            })
            return r.json().get("response", "").strip()
    except Exception as e:
        return f"Fix generation failed: {e}"


def write_and_test_fix(filepath: str, fixed_content: str) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{filepath}.bak.{timestamp}"
    try:
        with open(filepath) as f:
            original = f.read()
        with open(backup_path, "w") as f:
            f.write(original)
    except Exception as e:
        return {"success": False, "error": f"Backup failed: {e}"}
    try:
        with open(filepath, "w") as f:
            f.write(fixed_content)
    except Exception as e:
        return {"success": False, "error": f"Write failed: {e}"}
    try:
        py_compile.compile(filepath, doraise=True)
        return {"success": True, "filepath": filepath, "backup": backup_path, "status": "Compiles clean"}
    except py_compile.PyCompileError as e:
        with open(backup_path) as f:
            original = f.read()
        with open(filepath, "w") as f:
            f.write(original)
        return {"success": False, "error": f"Fix didn't compile, original restored: {e}"}


def git_commit_fix(filepath: str, error_summary: str) -> str:
    try:
        subprocess.run(["git", "add", filepath], cwd=REPO_PATH, check=True, capture_output=True)
        short_error = error_summary[:60].replace('"', "'")
        message = f"fix(doctorbot): auto-fix — {short_error}"
        result = subprocess.run(["git", "commit", "-m", message], cwd=REPO_PATH, capture_output=True, text=True)
        if "nothing to commit" in result.stdout:
            return "Nothing new to commit"
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_PATH, check=True, capture_output=True)
        try:
            from bots.doctorbot import log_to_context
            log_to_context(f"Auto-fix committed: {message}")
        except Exception:
            pass
        return f"Fix committed and pushed: {message}"
    except Exception as e:
        return f"Git error: {e}"


def get_github_diff() -> str:
    try:
        result = subprocess.run(["git", "diff", "HEAD~1", "--stat"], cwd=REPO_PATH, capture_output=True, text=True)
        return result.stdout.strip() or "No recent changes"
    except Exception as e:
        return f"Diff error: {e}"


async def doctorbot_see_and_fix(target_file: str = None, auto_push: bool = False) -> str:
    report = [f"DOCTORBOT VISION — {datetime.now().strftime('%I:%M %p')}"]
    report.append("=" * 50)
    report.append("\nTaking screenshot...")
    screenshot_path = take_screenshot("error_scan")
    if "failed" in screenshot_path.lower():
        return f"Screenshot failed: {screenshot_path}"
    report.append(f"Screenshot: {screenshot_path}")
    report.append("\nReading screen with Gemini Vision...")
    screen_description = await read_screen_with_gemini(screenshot_path)
    report.append(f"Screen reading:\n{screen_description[:300]}...")
    if target_file:
        filepath = os.path.join(REPO_PATH, target_file)
        if not os.path.exists(filepath):
            filepath = os.path.join(REPO_PATH, "bots", target_file)
    else:
        filepath = ""
        for f in glob.glob(f"{REPO_PATH}/**/*.py", recursive=True):
            if "__pycache__" in f or ".bak" in f:
                continue
            try:
                content = open(f).read()
                if any(kw in content for kw in screen_description.split()[:5]):
                    filepath = f
                    break
            except Exception:
                pass
    if not filepath or not os.path.exists(filepath):
        report.append("\nCould not find file to fix. Run: find bugs")
        return "\n".join(report)
    filename = os.path.basename(filepath)
    report.append(f"\nTargeting: {filename}")
    file_content = read_project_file(filepath)
    report.append("\nGenerating fix...")
    fixed_content = await generate_fix(screen_description, file_content, filename)
    if "failed" in fixed_content.lower() and len(fixed_content) < 100:
        report.append(f"Fix generation failed: {fixed_content}")
        return "\n".join(report)
    report.append("\nWriting and testing fix...")
    result = write_and_test_fix(filepath, fixed_content)
    if result["success"]:
        report.append(f"Fix applied and compiles clean!")
        report.append(f"Backup at: {result['backup']}")
        if auto_push:
            report.append("\nPushing to GitHub...")
            git_result = git_commit_fix(filepath, screen_description[:60])
            report.append(git_result)
        else:
            report.append("\nTo push: type 'push fix'")
    else:
        report.append(f"Fix failed: {result['error']}")
    return "\n".join(report)


async def doctorbot_scan_and_fix_all(auto_push: bool = False) -> str:
    report = [f"DOCTORBOT FULL SCAN — {datetime.now().strftime('%I:%M %p')}"]
    scan = scan_all_files_for_errors()
    errors = scan["errors"]
    clean = scan["clean"]
    report.append(f"\nClean files: {len(clean)}")
    report.append(f"Files with errors: {len(errors)}")
    if not errors:
        report.append("\nAll files compile clean. Nothing to fix.")
        return "\n".join(report)
    fixed_files = []
    failed_files = []
    for filepath, error_text in errors.items():
        filename = os.path.basename(filepath)
        report.append(f"\nFixing {filename}...")
        report.append(f"   Error: {error_text[:80]}")
        file_content = read_project_file(filepath)
        fixed_content = await generate_fix(error_text, file_content, filename)
        result = write_and_test_fix(filepath, fixed_content)
        if result["success"]:
            report.append(f"   Fixed!")
            fixed_files.append(filepath)
        else:
            report.append(f"   Failed: {result['error'][:80]}")
            failed_files.append(filepath)
    if fixed_files and auto_push:
        try:
            subprocess.run(["git", "add"] + fixed_files, cwd=REPO_PATH, check=True)
            msg = f"fix(doctorbot): auto-fix {len(fixed_files)} files"
            subprocess.run(["git", "commit", "-m", msg], cwd=REPO_PATH, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=REPO_PATH, check=True)
            from bots.doctorbot import log_to_context
            log_to_context(f"Auto-fix batch: {len(fixed_files)} files fixed and pushed")
            report.append(f"\nPushed to GitHub!")
        except Exception as e:
            report.append(f"\nPush failed: {e}")
    report.append(f"\nSUMMARY: Fixed={len(fixed_files)} Failed={len(failed_files)}")
    return "\n".join(report)


async def doctorbot_write_code(prompt: str, filename: str = None) -> str:
    import httpx
    system = """You are Doctorbot, senior software engineer for HIGA HOUSE JARVIS.
Write clean working Python. Rules: sys.path.insert not append, os.getenv for keys,
async/await for httpx, error handling, docstring. Output ONLY raw Python code."""
    code = ""
    if GEMINI_KEY:
        try:
            async with httpx.AsyncClient(timeout=30.0) as h:
                r = await h.post(
                    f"{GEMINI_VISION}?key={GEMINI_KEY}",
                    json={"contents": [{"parts": [{"text": f"{system}\n\nWrite code for: {prompt}"}]}]}
                )
                data = r.json()
                if "candidates" in data:
                    code = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    for fence in ["```python", "```"]:
                        code = code.replace(fence, "").strip()
        except Exception as e:
            print(f">> GEMINI CODE ERROR: {e}")
    if not code:
        try:
            async with httpx.AsyncClient(timeout=120.0) as h:
                r = await h.post(OLLAMA_URL, json={"model": MODEL, "prompt": f"{system}\n\nWrite code for: {prompt}", "stream": False})
                code = r.json().get("response", "").strip()
        except Exception as e:
            return f"Code generation failed: {e}"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_name = prompt[:30].replace(" ", "_").replace("/", "_")
    if not filename:
        filename = f"{timestamp}_{safe_name}.py"
    filepath = os.path.join(DRAFTS_DIR, filename)
    with open(filepath, "w") as f:
        f.write(f'''"""\nGenerated by Doctorbot\nPrompt: {prompt}\nDate: {datetime.now()}\n"""\n\n''')
        f.write(code)
    try:
        py_compile.compile(filepath, doraise=True)
        compile_status = "Compiles clean"
    except py_compile.PyCompileError as e:
        compile_status = f"Syntax error: {e}"
    return f"CODE WRITTEN\nFile: {filepath}\nStatus: {compile_status}\n\nPREVIEW:\n{code[:400]}..."


async def doctorbot_apply_draft(filename: str, target_file: str) -> str:
    draft_path = os.path.join(DRAFTS_DIR, filename)
    target_path = os.path.join(REPO_PATH, target_file)
    if not os.path.exists(draft_path):
        return f"Draft not found: {filename}"
    if not os.path.exists(target_path):
        return f"Target not found: {target_file}"
    with open(draft_path) as f:
        draft = f.read()
    with open(target_path) as f:
        target = f.read()
    backup = f"{target_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with open(backup, "w") as f:
        f.write(target)
    with open(target_path, "a") as f:
        f.write(f"\n\n# === DOCTORBOT ADDITION {datetime.now()} ===\n")
        f.write(draft)
    try:
        py_compile.compile(target_path, doraise=True)
        return f"Draft applied to {target_file} — compiles clean\nBackup at: {backup}"
    except py_compile.PyCompileError as e:
        with open(backup) as f:
            original = f.read()
        with open(target_path, "w") as f:
            f.write(original)
        return f"Applied draft breaks compile — original restored\nError: {e}"
