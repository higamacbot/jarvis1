import os
import re
import sqlite3
from typing import Dict, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.db")


def init_loop_memory_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS pattern_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                input_sample TEXT,
                output_sample TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS bot_handoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_bot TEXT NOT NULL,
                to_bot TEXT NOT NULL,
                topic TEXT,
                context TEXT,
                suggested_action TEXT,
                consumed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def save_pattern(bot_id: str, task_type: str, input_text: str, output_text: str) -> None:
    init_loop_memory_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO pattern_memory (bot_id, task_type, input_sample, output_sample)
            VALUES (?, ?, ?, ?)
            """,
            (
                bot_id,
                task_type,
                (input_text or "").strip()[:200],
                (output_text or "").strip()[:300],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def find_similar_pattern(bot_id: str, task_type: str, query: str, n: int = 3) -> List[Dict]:
    init_loop_memory_db()
    tokens = []
    for token in re.findall(r"[a-z0-9]+", (query or "").lower()):
        if len(token) >= 4 and token not in tokens:
            tokens.append(token)
    tokens = tokens[:3]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        if tokens:
            clauses = []
            params = [bot_id, task_type]
            for token in tokens:
                like = f"%{token}%"
                clauses.append("(lower(input_sample) LIKE ? OR lower(output_sample) LIKE ?)")
                params.extend([like, like])
            params.append(n)
            c.execute(
                f"""
                SELECT id, bot_id, task_type, input_sample, output_sample, created_at
                FROM pattern_memory
                WHERE bot_id = ? AND task_type = ? AND ({' OR '.join(clauses)})
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            )
        else:
            c.execute(
                """
                SELECT id, bot_id, task_type, input_sample, output_sample, created_at
                FROM pattern_memory
                WHERE bot_id = ? AND task_type = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (bot_id, task_type, n),
            )
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


def save_handoff(from_bot: str, to_bot: str, topic: str, context: str, suggested_action: str = "") -> None:
    init_loop_memory_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO bot_handoffs (from_bot, to_bot, topic, context, suggested_action)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                from_bot,
                to_bot,
                (topic or "").strip()[:200],
                (context or "").strip()[:500],
                (suggested_action or "").strip()[:100],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    try:
        from bot_orchestrator import update_bot_activity, log_bot_activity
        short_topic = (topic or "").strip()[:40]
        update_bot_activity(from_bot, f"→ {to_bot}: handoff sent")
        log_bot_activity(
            from_bot, "handoff",
            f"→ {to_bot}: {short_topic}",
            from_bot=from_bot, to_bot=to_bot,
        )
    except Exception:
        pass


def get_pending_handoffs(bot_id: str) -> List[Dict]:
    init_loop_memory_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, from_bot, to_bot, topic, context, suggested_action, consumed, created_at
            FROM bot_handoffs
            WHERE to_bot = ? AND consumed = 0
            ORDER BY id ASC
            """,
            (bot_id,),
        )
        return [dict(row) for row in c.fetchall()]
    finally:
        conn.close()


def consume_handoff(handoff_id: int) -> None:
    init_loop_memory_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("UPDATE bot_handoffs SET consumed = 1 WHERE id = ?", (handoff_id,))
        conn.commit()
    finally:
        conn.close()
