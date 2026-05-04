"""
review_dashboard.py — adds /review.html and /api/review/* to JARVIS.
Wire-up in main.py:
    from review_dashboard import register_review_routes
    register_review_routes(app)
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parent
REVIEW_HTML = ROOT / "static" / "review.html"
DB_PATH = ROOT / "jarvis_memory.db"

def _pending_jobs(limit: int = 50) -> list[dict]:
    if not DB_PATH.exists(): return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, batch_id, job_type, payload, status, created FROM jobs WHERE status IN ('pending','running') ORDER BY id ASC LIMIT ?",
            (limit,)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]

def register_review_routes(app: FastAPI) -> None:
    @app.get("/review.html", response_class=HTMLResponse)
    async def review_page():
        if REVIEW_HTML.exists():
            return HTMLResponse(REVIEW_HTML.read_text())
        return HTMLResponse("<h1>review.html missing</h1><p>Place it at static/review.html</p>", status_code=404)

    @app.get("/api/review/queue")
    async def review_queue():
        try:
            from autonomous_runner import JobManager
            mgr = JobManager()
            recent = mgr.get_recent_completed(limit=25) if hasattr(mgr, 'get_recent_completed') else []
            batches = mgr.get_batches() if hasattr(mgr, 'get_batches') else []
            return JSONResponse({"pending": _pending_jobs(), "recent": recent, "batches": batches})
        except Exception as e:
            return JSONResponse({"error": str(e), "pending": [], "recent": [], "batches": []})

    @app.get("/api/review/drafts")
    async def review_drafts():
        drafts_dir = ROOT / "drafts"
        if not drafts_dir.exists():
            return JSONResponse({"drafts": []})
        items = []
        for p in sorted(drafts_dir.glob("*.md"), reverse=True)[:50]:
            items.append({"name": p.name, "size": p.stat().st_size, "preview": p.read_text(errors="ignore")[:600]})
        return JSONResponse({"drafts": items})
