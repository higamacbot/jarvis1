from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Sample notes (replace with your Obsidian notes)
notes = [
    "Trump strategy on Iran and oil sanctions",
    "Geopolitics and game theory analysis",
    "US presidents and foreign policy"
]

# Generate embeddings for notes
note_embeddings = [model.encode(note) for note in notes]

# Safe query parsing
def clean_query(query):
    query = query.strip("?. ").lower()
    if query.startswith("for "):
        query = query[4:]
    return query

# Semantic search
def search_brain(query, top_k=2):
    query = clean_query(query)
    query_emb = model.encode(query)
    sims = cosine_similarity([query_emb], note_embeddings)[0]
    best_idx = np.argsort(sims)[::-1][:top_k]
    return [notes[i] for i in best_idx]

# Test
user_query = "Trump Iran"
results = search_brain(user_query)
print("Top matches:")
for r in results:
    print("-", r)
