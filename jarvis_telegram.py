import os
import chromadb
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from chromadb.utils import embedding_functions
from llama_cpp import Llama

# --- CONFIGURATION ---
TOKEN = "YOUR_TOKEN_HERE"
ALLOWED_USER_ID = YOUR_ID_HERE 

# --- SETUP LOCAL AI ---
llm = Llama(model_path="models/Phi-3-mini-4k-instruct-q4.gguf", n_gpu_layers=-1, n_ctx=4096, verbose=False)
client = chromadb.PersistentClient(path="./jarvis_memory_db")
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = client.get_or_create_collection(name="research_docs", embedding_function=embedding_func)

def get_context(query):
    results = collection.query(query_texts=[query], n_results=3)
    return "\n".join(results['documents'][0]).replace("<|", "").strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    user_text = update.message.text
    pdf_context = get_context(user_text)
    
    # Improved Prompt for better "Researcher" personality
    prompt = f"<|system|>\nYou are Jarvis, the user's personal Sovereign AI. Use the following context from their private research to answer. Be professional and thorough.\n\nRESEARCH CONTEXT:\n{pdf_context}<|end|>\n<|user|>\n{user_text}<|end|>\n<|assistant|>\n"
    
    output = llm(prompt, max_tokens=1024, stop=["<|end|>"], repeat_penalty=1.2, temperature=0.7)
    response = output['choices'][0]['text'].strip()
    
    await update.message.reply_text(response)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
