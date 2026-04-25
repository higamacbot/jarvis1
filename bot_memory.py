import os
import time

CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

_client = None
_collections = {}

def _get_client():
    global _client
    if _client is None:
        import chromadb
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _client

def _get_collection(bot_id: str):
    if bot_id not in _collections:
        client = _get_client()
        _collections[bot_id] = client.get_or_create_collection(
            name=f"bot_{bot_id}",
            metadata={"hnsw:space": "cosine"}
        )
    return _collections[bot_id]

def save_bot_memory(bot_id: str, content: str, metadata: dict = None):
    try:
        col = _get_collection(bot_id)
        doc_id = f"{bot_id}_{int(time.time() * 1000)}"
        meta = dict(metadata or {})
        meta["bot"] = bot_id
        meta["preview"] = content[:300]
        col.add(documents=[content], ids=[doc_id], metadatas=[meta])
    except Exception as e:
        print(f">> BOT MEMORY SAVE ERROR ({bot_id}): {e}")

def search_bot_memory(bot_id: str, query: str, n_results: int = 3) -> str:
    try:
        col = _get_collection(bot_id)
        results = col.query(query_texts=[query], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        if not docs:
            return ""
        lines = [f"— {bot_id.upper()} MEMORY —"]
        for doc in docs:
            lines.append(f"• {doc[:220]}")
        return "\n".join(lines)
    except Exception as e:
        print(f">> BOT MEMORY SEARCH ERROR ({bot_id}): {e}")
        return ""

def get_bot_memory_summary(bot_id: str, topic: str) -> str:
    return search_bot_memory(bot_id, topic)

def extract_durable_takeaway(user_msg: str, reply: str) -> str:
    lower = reply.lower()
    markers = [
        "recommend", "signal", "hold", "buy", "sell", "reduce",
        "thesis", "takeaway", "risk", "support", "resistance",
        "watch", "plan", "decision"
    ]
    if not any(m in lower for m in markers):
        return ""
    reply_clean = " ".join(reply.split())
    return f"Topic: {user_msg[:140]}\nTakeaway: {reply_clean[:500]}"
