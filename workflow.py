import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.db")

TEMPLATES = {
    "clip_to_carousel": [
        {"bot_id": "clipfarmer", "task": "clip this: {input}", "action": "clip_analysis_complete"},
        {"bot_id": "robowright", "task": "carousel from handoff", "action": "carousel_complete"},
    ],
    "adversarial_review": [
        {"bot_id": "jarvisbot", "task": "draft: {input}", "action": "draft_complete"},
        {"bot_id": "doctorbot", "task": "challenge: {input}", "action": "challenge_complete"},
        {"bot_id": "jarvisbot", "task": "verdict: {input}", "action": "verdict_complete"},
    ],
}


def init_workflow_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                current_step INTEGER NOT NULL DEFAULT 0,
                input_text TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                step_index INTEGER NOT NULL,
                bot_id TEXT NOT NULL,
                task_text TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT NOT NULL DEFAULT '',
                completed_at TEXT,
                FOREIGN KEY(job_id) REFERENCES workflow_jobs(id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_workflow(template_name: str, input_text: str) -> int:
    init_workflow_db()
    template = TEMPLATES[template_name]
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO workflow_jobs (name, status, current_step, input_text, created_at, updated_at)
            VALUES (?, 'running', 0, ?, ?, ?)
            """,
            (template_name, (input_text or "").strip()[:500], now, now),
        )
        job_id = c.lastrowid
        for idx, step in enumerate(template):
            task_text = step["task"].format(input=(input_text or "").strip())
            status = "running" if idx == 0 else "pending"
            c.execute(
                """
                INSERT INTO workflow_steps (job_id, step_index, bot_id, task_text, action, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (job_id, idx, step["bot_id"], task_text[:500], step["action"], status),
            )
        conn.commit()
        job_id = int(job_id)
    finally:
        conn.close()
    try:
        from bot_orchestrator import log_bot_activity
        log_bot_activity("jarvisbot", "task_start", f"workflow {job_id} started: {template_name}")
        current = get_current_step(job_id)
        if current:
            log_bot_activity(
                current["bot_id"],
                "task_start",
                f"workflow step {int(current['step_index']) + 1}: {current['task_text'][:80]}",
            )
    except Exception:
        pass
    return job_id


def get_current_step(job_id: int) -> Optional[Dict]:
    init_workflow_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT ws.*, wj.name, wj.status AS job_status, wj.input_text
            FROM workflow_steps ws
            JOIN workflow_jobs wj ON wj.id = ws.job_id
            WHERE ws.job_id = ? AND ws.status = 'running'
            ORDER BY ws.step_index ASC
            LIMIT 1
            """,
            (job_id,),
        )
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_active_job(template_name: str, input_text: str = "") -> Optional[Dict]:
    init_workflow_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        if input_text:
            c.execute(
                """
                SELECT *
                FROM workflow_jobs
                WHERE name = ? AND status = 'running' AND input_text = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (template_name, input_text[:500]),
            )
        else:
            c.execute(
                """
                SELECT *
                FROM workflow_jobs
                WHERE name = ? AND status = 'running'
                ORDER BY id DESC
                LIMIT 1
                """,
                (template_name,),
            )
        row = c.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_active_workflows(limit: int = 10) -> List[Dict]:
    init_workflow_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT id, name, status, current_step, input_text, created_at, updated_at
            FROM workflow_jobs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        jobs = [dict(row) for row in c.fetchall()]
        for job in jobs:
            c.execute(
                """
                SELECT COUNT(*)
                FROM workflow_steps
                WHERE job_id = ?
                """,
                (job["id"],),
            )
            job["total_steps"] = c.fetchone()[0]
        return jobs
    finally:
        conn.close()


def advance_workflow(job_id: int, completing_bot: str, action: str, result: str) -> Optional[Dict]:
    init_workflow_db()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        c = conn.cursor()
        c.execute(
            """
            SELECT *
            FROM workflow_steps
            WHERE job_id = ? AND status = 'running'
            ORDER BY step_index ASC
            LIMIT 1
            """,
            (job_id,),
        )
        row = c.fetchone()
        if not row:
            return None
        current = dict(row)
        if current["bot_id"] != completing_bot or current["action"] != action:
            return None

        c.execute(
            """
            UPDATE workflow_steps
            SET status = 'done', result = ?, completed_at = ?
            WHERE id = ?
            """,
            ((result or "").strip()[:500], now, current["id"]),
        )
        next_index = int(current["step_index"]) + 1
        c.execute(
            """
            SELECT id
            FROM workflow_steps
            WHERE job_id = ? AND step_index = ?
            LIMIT 1
            """,
            (job_id, next_index),
        )
        next_row = c.fetchone()
        if next_row:
            c.execute(
                "UPDATE workflow_steps SET status = 'running' WHERE id = ?",
                (next_row["id"],),
            )
            c.execute(
                """
                UPDATE workflow_jobs
                SET current_step = ?, updated_at = ?, status = 'running'
                WHERE id = ?
                """,
                (next_index, now, job_id),
            )
        else:
            c.execute(
                """
                UPDATE workflow_jobs
                SET current_step = ?, updated_at = ?, status = 'done'
                WHERE id = ?
                """,
                (next_index, now, job_id),
            )
        conn.commit()
    finally:
        conn.close()

    try:
        from bot_orchestrator import log_bot_activity
        next_step = get_current_step(job_id)
        if next_step:
            log_bot_activity(
                next_step["bot_id"],
                "task_start",
                f"workflow step {int(next_step['step_index']) + 1}: {next_step['task_text'][:80]}",
            )
        else:
            log_bot_activity("jarvisbot", "task_complete", f"workflow {job_id} complete")
    except Exception:
        pass

    return get_current_step(job_id)


def fail_workflow(job_id: int, message: str) -> None:
    init_workflow_db()
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            """
            UPDATE workflow_jobs
            SET status = 'failed', updated_at = ?
            WHERE id = ?
            """,
            (now, job_id),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        from bot_orchestrator import log_bot_activity
        log_bot_activity("jarvisbot", "error", f"workflow {job_id} failed: {(message or '').strip()[:80]}")
    except Exception:
        pass
