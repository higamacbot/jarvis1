import subprocess
from pathlib import Path
import sys

BRAIN_SCRIPT = Path(__file__).parent / "brain_v2.py"

def search_brain(query: str) -> str:
    if not BRAIN_SCRIPT.exists():
        return "Brain script not found."
    
    try:
        result = subprocess.run(
            [sys.executable, str(BRAIN_SCRIPT), query],
            capture_output=True,
            text=True,
            timeout=15
        )
        return result.stdout.strip()
    except:
        return "Brain search unavailable."
