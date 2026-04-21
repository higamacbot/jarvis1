"""
memory.py — JARVIS Memory Layer
SQLite (recent context) + ChromaDB (semantic search)
All original functions preserved. ChromaDB is additive only.
"""
import sqlite3
import os

DB_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.db")
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

# ── ChromaDB (lazy init) ──────────────────────────────────────────────────────
_chroma_client     = None
_chroma_collection = None

def _get_chroma():
    global _chroma_client, _chroma_collection
    if _chroma_client is None:
        try:
            import chromadb
            _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
            _chroma_collection = _chroma_client.get_or_create_collection(
                name="jarvis_memory",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            print(f">> CHROMA INIT ERROR: {e}")
            return None
    return _chroma_collection

# ── SQLite ────────────────────────────────────────────────────────────────────
def init_db():
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            role      TEXT,
            content   TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preferences (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f">> MEMORY: SQLite ready")
    print(f">> MEMORY: ChromaDB ready at {CHROMA_DIR}")

def save_conversation(role: str, content: str):
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversation (role, content) VALUES (?, ?)", (role, content)
        )
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        # Also save to ChromaDB for semantic search
        col = _get_chroma()
        if col:
            col.add(
                documents=[f"{role.upper()}: {content}"],
                ids=[f"msg_{row_id}"],
                metadatas=[{"role": role, "content": content[:500]}],
            )
    except Exception as e:
        print(f">> MEMORY ERROR: {e}")

def get_memory_context(limit: int = 10) -> str:
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM conversation ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()[::-1]
        conn.close()
        context = "— PAST CONVERSATION MEMORY —\n"
        for role, content in rows:
            context += f"{role.upper()}: {content}\n"
        return context
    except Exception:
        return ""

def semantic_search(query: str, n_results: int = 5) -> str:
    """Search ALL past conversations by meaning, not just recency."""
    try:
        col = _get_chroma()
        if not col:
            return ""
        results = col.query(query_texts=[query], n_results=n_results)
        docs    = results.get("documents", [[]])[0]
        if not docs:
            return ""
        lines = ["— SEMANTIC MEMORY —"]
        for doc in docs:
            lines.append(f"• {doc[:200]}")
        return "\n".join(lines)
    except Exception as e:
        print(f">> SEMANTIC SEARCH ERROR: {e}")
        return ""

def save_preference(key: str, value: str):
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)", (key, value)
        )
        conn.commit()
        conn.close()
        col = _get_chroma()
        if col:
            col.add(
                documents=[f"USER PREFERENCE: {key} = {value}"],
                ids=[f"pref_{key}"],
                metadatas=[{"type": "preference", "key": key}],
            )
    except Exception as e:
        print(f">> PREFERENCE ERROR: {e}")

def get_all_preferences() -> dict:
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM preferences")
        rows   = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}

def extract_summary(text: str) -> str:
    if len(text) > 500:
        return text[:500] + "…"
    return text
