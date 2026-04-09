import os
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader

# 1. Setup Local Storage
client = chromadb.PersistentClient(path="./jarvis_memory_db")

# 2. Use a local embedding model (Runs 100% offline)
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

# 3. Create or load the collection
collection = client.get_or_create_collection(name="research_docs", embedding_function=embedding_func)

def ingest_pdf(file_path):
    """Reads a PDF and stores it in the vector database."""
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found.")
        return
        
    reader = PdfReader(file_path)
    filename = os.path.basename(file_path)
    
    print(f"Reading {filename}...")
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            # Store each page as a separate 'memory' block
            collection.add(
                documents=[text],
                metadatas=[{"source": filename, "page": i+1}],
                ids=[f"{filename}_p{i}"]
            )
    print(f"Successfully memorized: {filename}")

if __name__ == "__main__":
    # Point this to your history folder
    folder_path = "./transcripts/Predictive History"
    if os.path.exists(folder_path):
        print(f"Scanning {folder_path} for research papers...")
        for file in os.listdir(folder_path):
            if file.endswith(".pdf"):
                ingest_pdf(os.path.join(folder_path, file))
    else:
        print(f"Folder not found: {folder_path}. Please check your path.")
