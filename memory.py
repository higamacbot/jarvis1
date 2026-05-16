"""
memory.py — JARVIS Memory Layer
SQLite (recent context) + ChromaDB (semantic search)
All original functions preserved. ChromaDB is additive only.
"""
import sqlite3
import os
import re
import time
import importlib.util

DB_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.db")
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

# ── ChromaDB (lazy init) ──────────────────────────────────────────────────────
_chroma_client     = None
_chroma_collection = None

# ── mem0 (lazy init, fully local: Ollama LLM + Ollama embedder + ChromaDB) ───
_mem0_client = None
_mem0_init_attempted = False
_MEM0_USER_ID = "higabot"
RULE_MEMORY_TRIGGERS = [
    "i prefer", "i like", "i don't like", "i dislike", "i want",
    "i avoid", "my strategy", "i trade", "i hold", "i invest",
    "remember that", "note that", "keep in mind",
    "do not sell", "don't sell", "do not buy", "don't buy",
    "i do not want", "i don't want", "price floor", "sell limit",
    "my floor", "my rule", "my limit for", "never sell",
]
RULE_QUERY_WORDS = (
    "remember", "price floor", "floor", "my rule", "did i say",
    "what did i tell", "what did i say", "my limit", "sell limit",
    "do not sell", "don't sell", "my instruction", "preference",
)
_MEMORY_STOPWORDS = {
    "the", "and", "for", "that", "with", "from", "what", "about",
    "your", "have", "this", "when", "into", "under", "over", "would",
    "should", "could", "please", "want", "need", "rule", "rules",
}
_MEM0_CONFIG = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen3:8b",
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434",
        },
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "mem0_jarvis",
            "path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_mem0"),
        },
    },
}

def _get_mem0():
    global _mem0_client, _mem0_init_attempted
    if _mem0_client is not None:
        return _mem0_client
    if _mem0_init_attempted:
        return None
    _mem0_init_attempted = True
    try:
        # mem0's Ollama provider can try to prompt interactively if the Python
        # `ollama` package is missing. In the server runtime that blocks the
        # websocket reply path, so fail fast and keep the fallback layers live.
        if importlib.util.find_spec("ollama") is None:
            print(">> MEM0 INIT SKIP (fallback to SQLite): missing Python package 'ollama'")
            return None
        from mem0 import Memory
        _mem0_client = Memory.from_config(_MEM0_CONFIG)
        print(">> MEM0: Initialized (local Ollama + nomic-embed-text + ChromaDB)")
        return _mem0_client
    except Exception as e:
        print(f">> MEM0 INIT SKIP (fallback to SQLite): {e}")
        return None

def mem0_add(user_msg: str, reply: str, user_id: str = _MEM0_USER_ID) -> None:
    """Store a conversation exchange into mem0. Falls back silently on any error."""
    try:
        m = _get_mem0()
        if not m:
            return
        messages = [
            {"role": "user",      "content": user_msg[:1000]},
            {"role": "assistant", "content": reply[:500]},
        ]
        m.add(messages, user_id=user_id)
    except Exception as e:
        print(f">> MEM0 ADD ERROR: {e}")

def mem0_search(query: str, user_id: str = _MEM0_USER_ID, limit: int = 5) -> str:
    """Search mem0 for semantically relevant past context. Returns '' if mem0 unavailable."""
    try:
        m = _get_mem0()
        if not m:
            return ""
        results = m.search(query, user_id=user_id, limit=limit)
        if not results:
            return ""
        lines = ["— MEM0 MEMORY —"]
        for r in results:
            mem_text = r.get("memory", "")
            if mem_text:
                lines.append(f"• {mem_text[:200]}")
        return "\n".join(lines) if len(lines) > 1 else ""
    except Exception as e:
        print(f">> MEM0 SEARCH ERROR: {e}")
        return ""

def _tokenize_memory_text(text: str) -> list:
    return [
        tok for tok in re.findall(r"[a-z0-9$]+", (text or "").lower())
        if len(tok) > 1 and tok not in _MEMORY_STOPWORDS
    ]

def is_rule_query(query: str) -> bool:
    q = (query or "").lower()
    return any(word in q for word in RULE_QUERY_WORDS)

def save_explicit_user_memory(user_msg: str) -> None:
    if any(t in (user_msg or "").lower() for t in RULE_MEMORY_TRIGGERS):
        save_preference(f"user_note_{int(time.time())}", user_msg.strip())

def _preference_sort_key(key: str) -> int:
    try:
        return int(str(key).rsplit("_", 1)[1])
    except Exception:
        return 0

def _score_preference_match(query: str, value: str) -> int:
    q = query or ""
    v = (value or "").lower()
    score = 0
    for token in _tokenize_memory_text(q):
        if token in v:
            score += 1
    for ticker in re.findall(r"\b[A-Z]{1,5}\b", q):
        if ticker.lower() in v:
            score += 3
    return score

def get_preference_context(query: str = "", limit: int = 6) -> str:
    try:
        prefs = get_all_preferences()
        rows = [
            (key, value)
            for key, value in prefs.items()
            if not str(key).startswith("usage_")
        ]
        if not rows:
            return ""
        scored = []
        for key, value in rows:
            score = _score_preference_match(query, value)
            scored.append((score, _preference_sort_key(key), value))
        if query:
            scored = [row for row in scored if row[0] > 0] or (
                sorted(scored, key=lambda row: row[1], reverse=True)[:limit]
                if is_rule_query(query) else []
            )
        scored = sorted(scored, key=lambda row: (row[0], row[1]), reverse=True)[:limit]
        if not scored:
            return ""
        lines = ["— USER RULES & PREFERENCES —"]
        for _, _, value in scored:
            lines.append(f"• {str(value)[:220]}")
        return "\n".join(lines)
    except Exception as e:
        print(f">> PREFERENCE CONTEXT ERROR: {e}")
        return ""

def build_memory_bundle(query: str, user_id: str = _MEM0_USER_ID,
                        recent_limit: int = 10, preference_limit: int = 6,
                        semantic_limit: int = 5) -> dict:
    return {
        "is_rule_query": is_rule_query(query),
        "rules": get_preference_context(query, preference_limit),
        "semantic": mem0_search(query, user_id=user_id, limit=semantic_limit),
        "recent": get_memory_context(recent_limit),
    }

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
