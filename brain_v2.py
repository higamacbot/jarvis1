import os
import chromadb
from chromadb.utils import embedding_functions
from llama_cpp import Llama

# 1. Setup the Brain with high-temperature suppression
llm = Llama(
    model_path="models/Phi-3-mini-4k-instruct-q4.gguf",
    n_gpu_layers=-1, 
    n_ctx=2048,      
    verbose=False
)

client = chromadb.PersistentClient(path="./jarvis_memory_db")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_or_create_collection(name="research_docs", embedding_function=embedding_func)

def get_context(query):
    results = collection.query(query_texts=[query], n_results=2) # Reduced to 2 for stability
    context = "\n".join(results['documents'][0])
    # Clean up weird characters that might confuse the model
    return context.replace("<|", "").replace("|>", "").strip()

def ask_jarvis(question):
    context = get_context(question)
    
    # Strictly following Phi-3 Prompt Format
    prompt = f"<|system|>\nYou are Jarvis. Use the provided context to answer. Be concise.\nContext: {context}<|end|>\n<|user|>\n{question}<|end|>\n<|assistant|>\n"

    # Added repeat_penalty to stop the "IRS IRS IRS" loops
    output = llm(
        prompt, 
        max_tokens=256, 
        stop=["<|end|>", "User:"], 
        echo=False,
        repeat_penalty=1.2,
        temperature=0.7
    )
    return output['choices'][0]['text']

if __name__ == "__main__":
    print("\n[Jarvis Stabilized - Ready]")
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ['exit', 'quit']: break
        
        try:
            response = ask_jarvis(user_input)
            print(f"\nJarvis: {response.strip()}")
        except Exception as e:
            print(f"\nJarvis: I encountered a logic error: {e}")
