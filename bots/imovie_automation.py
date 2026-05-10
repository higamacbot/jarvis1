import subprocess
import threading

# AppleScript that waits for iMovie to be frontmost, then walks every window
# and sheet looking for a "New Project" button to click.
# Targets both the description attribute (used by most macOS controls) and
# the name attribute (used by some), so it covers both dialog buttons and
# toolbar buttons regardless of how iMovie labels them.
_CLICK_SCRIPT = """\
tell application "System Events"
    set frontmost of process "iMovie" to true

    -- Wait up to 5s for iMovie to be frontmost
    repeat 10 times
        if (name of first application process whose frontmost is true) is "iMovie" then exit repeat
        delay 0.5
    end repeat

    tell process "iMovie"

        -- PHASE 1: dismiss the "Open Library" dialog (4 iterations = 2s, quick check)
        repeat 4 times
            try
                repeat with w in windows
                    repeat with btn in buttons of w
                        set bLabel to ""
                        try
                            set bLabel to name of btn
                        end try
                        if bLabel is missing value then set bLabel to ""
                        if bLabel is "" then
                            try
                                set bLabel to description of btn
                            end try
                        end if
                        if bLabel is missing value then set bLabel to ""
                        if bLabel is "Choose" then
                            click btn
                            return "clicked: Choose (library accepted)"
                        end if
                    end repeat
                end repeat
            end try
            delay 0.5
        end repeat

        -- PHASE 2: find "create project" button (real label found via UI probe)
        -- Use ignoring case to avoid shell subprocess per element
        delay 1.0
        repeat 16 times
            try
                set allUI to entire contents of (front window)
                repeat with el in allUI
                    if (class of el) is button then
                        set bLabel to ""
                        try
                            set bLabel to description of el
                        end try
                        if bLabel is missing value then set bLabel to ""
                        if bLabel is "" then
                            try
                                set bLabel to name of el
                            end try
                        end if
                        if bLabel is missing value then set bLabel to ""
                        ignoring case
                            if bLabel contains "new project" or bLabel contains "new movie" or bLabel contains "create project" then
                                click el
                                return "clicked: " & bLabel
                            end if
                        end ignoring
                    end if
                end repeat
            end try
            delay 0.5
        end repeat

    end tell
end tell

-- Debug: report all button descriptions visible right now
set found to {}
try
    tell process "iMovie"
        set allUI to entire contents of (front window)
        repeat with el in allUI
            if (class of el) is button then
                set bLabel to ""
                try
                    set bLabel to description of el
                end try
                if bLabel is missing value then set bLabel to ""
                if bLabel is "" then
                    try
                        set bLabel to name of el
                    end try
                end if
                if bLabel is missing value then set bLabel to ""
                if bLabel is not "" then
                    set end of found to bLabel
                end if
            end if
        end repeat
    end tell
end try
if (count found) > 0 then
    return "no match — visible buttons: " & (found as string)
end if
return "no create-project button found after 8s (no buttons visible)"
"""


def _run_automation() -> str:
    """Execute the AppleScript and return a status string."""
    try:
        r = subprocess.run(
            ["osascript", "-e", _CLICK_SCRIPT],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            result = r.stdout.strip()
            print(f">> ROBOWRIGHT IMOVIE: {result}")
            return result
        err = r.stderr.strip()
        if "-1719" in err or "assistive access" in err.lower():
            print(
                ">> ROBOWRIGHT IMOVIE: Accessibility not granted. "
                "To enable: System Preferences → Privacy & Security → Accessibility "
                "→ add Terminal (or whichever app launched this server)."
            )
            return "accessibility_not_granted"
        print(f">> ROBOWRIGHT IMOVIE: osascript error: {err[:200]}")
        return f"osascript_error: {err[:100]}"
    except subprocess.TimeoutExpired:
        print(">> ROBOWRIGHT IMOVIE: automation timed out after 15s")
        return "timed_out"
    except Exception as e:
        print(f">> ROBOWRIGHT IMOVIE: unexpected error: {e}")
        return f"error: {e}"


def automate_imovie_new_project(delay_secs: float = 2.5) -> None:
    """
    Fire-and-forget: wait delay_secs for iMovie to finish opening,
    then attempt to click 'New Project'. Runs in a daemon thread so it
    never blocks the bot response. Fails gracefully on any error.
    """
    def _worker():
        import time
        time.sleep(delay_secs)
        _run_automation()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
