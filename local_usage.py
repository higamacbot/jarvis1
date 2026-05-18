import json
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional


CLAUDE_PROJECT_DIR = Path.home() / ".claude" / "projects" / "-Users-higabot1-jarvis1-1"
CODEX_LOG_DB = Path.home() / ".codex" / "logs_2.sqlite"


def _iso_to_local_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone().date()
    except ValueError:
        return None


def _compact_int(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}k"
    return str(value)


def collect_claude_usage(project_dir: Path, target_day: date) -> Dict[str, object]:
    project_dir = Path(project_dir)
    usage = {
        "connected": project_dir.exists(),
        "requests": 0,
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "scope": "today · jarvis1-1",
        "source": "local claude project logs",
        "label": "not connected",
        "detail": "project logs unavailable",
    }
    if not project_dir.exists():
        return usage

    seen_request_ids = set()
    for path in sorted(project_dir.glob("*.jsonl")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("type") != "assistant":
                        continue
                    if _iso_to_local_date(row.get("timestamp", "")) != target_day:
                        continue
                    request_id = row.get("requestId")
                    if not request_id or request_id in seen_request_ids:
                        continue
                    msg_usage = ((row.get("message") or {}).get("usage") or {})
                    seen_request_ids.add(request_id)
                    usage["requests"] += 1
                    usage["input_tokens"] += int(msg_usage.get("input_tokens", 0) or 0)
                    usage["cache_creation_input_tokens"] += int(msg_usage.get("cache_creation_input_tokens", 0) or 0)
                    usage["cache_read_input_tokens"] += int(msg_usage.get("cache_read_input_tokens", 0) or 0)
                    usage["output_tokens"] += int(msg_usage.get("output_tokens", 0) or 0)
        except OSError:
            continue

    usage["total_tokens"] = (
        usage["input_tokens"]
        + usage["cache_creation_input_tokens"]
        + usage["cache_read_input_tokens"]
        + usage["output_tokens"]
    )
    if usage["requests"]:
        usage["label"] = f"{usage['requests']} req · {_compact_int(usage['total_tokens'])} tok"
        cache_total = usage["cache_creation_input_tokens"] + usage["cache_read_input_tokens"]
        if cache_total:
            usage["detail"] = f"out {_compact_int(usage['output_tokens'])} · cache {_compact_int(cache_total)}"
        else:
            usage["detail"] = f"in {_compact_int(usage['input_tokens'])} · out {_compact_int(usage['output_tokens'])}"
    else:
        usage["label"] = "0 req · 0 tok"
        usage["detail"] = "today · jarvis1-1"
    return usage


def collect_codex_usage(log_db_path: Path, target_day: date) -> Dict[str, object]:
    log_db_path = Path(log_db_path)
    usage = {
        "connected": log_db_path.exists(),
        "requests": 0,
        "scope": "today · local",
        "source": "local codex logs",
        "label": "not connected",
        "detail": "local logs unavailable",
    }
    if not log_db_path.exists():
        return usage

    query = """
        SELECT feedback_log_body
        FROM logs
        WHERE target = 'codex_core::session::turn'
          AND feedback_log_body LIKE '%turn.id=%'
          AND date(ts, 'unixepoch', 'localtime') = ?
    """
    turn_id_pattern = re.compile(r"turn\.id=([A-Za-z0-9-]+)")
    try:
        conn = sqlite3.connect(log_db_path)
        cursor = conn.execute(query, (target_day.isoformat(),))
        turn_ids = set()
        for (body,) in cursor.fetchall():
            match = turn_id_pattern.search(body or "")
            if match:
                turn_ids.add(match.group(1))
        usage["requests"] = len(turn_ids)
        conn.close()
    except sqlite3.Error:
        return usage

    usage["label"] = f"{usage['requests']} req · local"
    usage["detail"] = "today · local logs"
    return usage


def build_local_usage_snapshot(target_day: Optional[date] = None) -> Dict[str, object]:
    target_day = target_day or datetime.now().astimezone().date()
    claude = collect_claude_usage(CLAUDE_PROJECT_DIR, target_day)
    codex = collect_codex_usage(CODEX_LOG_DB, target_day)
    total_requests = int(claude.get("requests", 0) or 0) + int(codex.get("requests", 0) or 0)
    return {
        "date": target_day.isoformat(),
        "claude_code": claude,
        "codex": codex,
        "requests": {
            "connected": claude["connected"] or codex["connected"],
            "total": total_requests,
            "label": f"{total_requests} total today",
            "detail": "claude + codex local requests",
        },
        "remaining": {
            "connected": False,
            "label": "local only",
            "detail": "no quota source",
        },
    }
