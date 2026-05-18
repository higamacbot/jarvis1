import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from local_usage import collect_claude_usage, collect_codex_usage


class LocalUsageTests(unittest.TestCase):
    def test_collect_claude_usage_deduplicates_request_ids_and_sums_tokens(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "claude-project"
            project_dir.mkdir()
            log_path = project_dir / "session.jsonl"

            rows = [
                {
                    "type": "assistant",
                    "requestId": "req-1",
                    "timestamp": "2026-05-17T14:01:00Z",
                    "message": {
                        "usage": {
                            "input_tokens": 100,
                            "cache_creation_input_tokens": 20,
                            "cache_read_input_tokens": 30,
                            "output_tokens": 40,
                        }
                    },
                },
                {
                    "type": "assistant",
                    "requestId": "req-1",
                    "timestamp": "2026-05-17T14:01:01Z",
                    "message": {
                        "usage": {
                            "input_tokens": 100,
                            "cache_creation_input_tokens": 20,
                            "cache_read_input_tokens": 30,
                            "output_tokens": 40,
                        }
                    },
                },
                {
                    "type": "assistant",
                    "requestId": "req-2",
                    "timestamp": "2026-05-17T15:05:00Z",
                    "message": {
                        "usage": {
                            "input_tokens": 50,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 10,
                            "output_tokens": 25,
                        }
                    },
                },
                {
                    "type": "assistant",
                    "requestId": "req-old",
                    "timestamp": "2026-05-16T23:59:00Z",
                    "message": {
                        "usage": {
                            "input_tokens": 999,
                            "cache_creation_input_tokens": 0,
                            "cache_read_input_tokens": 0,
                            "output_tokens": 999,
                        }
                    },
                },
            ]
            log_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

            usage = collect_claude_usage(project_dir, date(2026, 5, 17))

            self.assertTrue(usage["connected"])
            self.assertEqual(usage["requests"], 2)
            self.assertEqual(usage["input_tokens"], 150)
            self.assertEqual(usage["cache_creation_input_tokens"], 20)
            self.assertEqual(usage["cache_read_input_tokens"], 40)
            self.assertEqual(usage["output_tokens"], 65)
            self.assertEqual(usage["total_tokens"], 275)

    def test_collect_codex_usage_counts_today_submission_dispatch_events_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "logs.sqlite"
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER NOT NULL,
                    ts_nanos INTEGER NOT NULL,
                    level TEXT NOT NULL,
                    target TEXT NOT NULL,
                    feedback_log_body TEXT,
                    module_path TEXT,
                    file TEXT,
                    line INTEGER,
                    thread_id TEXT,
                    process_uuid TEXT,
                    estimated_bytes INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            rows = [
                (
                    1779037340,
                    1,
                    "INFO",
                    "codex_core::session::turn",
                    'session_loop:submission_dispatch{otel.name="op.dispatch.user_input_with_turn_context"}:turn{turn.id=turn-1}:run_turn: post sampling token usage turn_id=turn-1 total_usage_tokens=120',
                ),
                (
                    1779037341,
                    2,
                    "INFO",
                    "codex_core::session::turn",
                    'session_loop:submission_dispatch{otel.name="op.dispatch.user_input_with_turn_context"}:turn{turn.id=turn-1}:run_turn: post sampling token usage turn_id=turn-1 total_usage_tokens=140',
                ),
                (
                    1779037342,
                    3,
                    "INFO",
                    "codex_core::session::turn",
                    'session_loop:submission_dispatch{otel.name="op.dispatch.user_input_with_turn_context"}:turn{turn.id=turn-2}:run_turn: post sampling token usage turn_id=turn-2 total_usage_tokens=80',
                ),
                (
                    1778950000,
                    4,
                    "INFO",
                    "codex_core::session::turn",
                    'session_loop:submission_dispatch{otel.name="op.dispatch.user_input_with_turn_context"}:turn{turn.id=turn-old}:run_turn: post sampling token usage turn_id=turn-old total_usage_tokens=300',
                ),
            ]
            conn.executemany(
                """
                INSERT INTO logs (
                    ts, ts_nanos, level, target, feedback_log_body,
                    module_path, file, line, thread_id, process_uuid, estimated_bytes
                ) VALUES (?, ?, ?, ?, ?, '', '', 0, '', '', 0)
                """,
                rows,
            )
            conn.commit()
            conn.close()

            usage = collect_codex_usage(db_path, date(2026, 5, 17))

            self.assertTrue(usage["connected"])
            self.assertEqual(usage["requests"], 2)


if __name__ == "__main__":
    unittest.main()
