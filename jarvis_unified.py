import os, asyncio, subprocess, chromadb, threading, re, datetime
import yfinance as yf
import trafilatura
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
from chromadb.utils import embedding_functions
from llama_cpp import Llama

# --- CONFIG ---
TOKEN = "8698860518:AAEEDckZXlW68yJ4kfxSMix1Vb5x6drB-gI" 
ALLOWED_USER_ID = 7343414006          
NEWS_SOURCES = [
    "https://www.reuters.com/world/",
    "https://www.zerohedge.com"
]
TICKERS = ["BTC-USD", "ETH-USD", "GC=F", "NVDA", "SPY"] 

# --- GLOBAL ENGINE ---
llm = None
collection = None
last_sent_date = None # Guard for daily briefings

def initialize_brain():
    global llm, collection
    if llm is None:
        print("🚀 [M4 CORE] Activating Sovereign Intelligence Agent...")
        llm = Llama(model_path="models/Phi-3-mini-4k-instruct-q4.gguf", n_gpu_layers=-1, n_ctx=4096, verbose=False)
        client = chromadb.PersistentClient(path="./jarvis_memory_db")
        embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        collection = client.get_or_create_collection(name="research_docs", embedding_function=embedding_func)

def get_market_data():
    report = f"📈 **MARKET REPORT: {datetime.datetime.now().strftime('%b %d, %Y')}**\n"
    for ticker in TICKERS:
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="1d")
            price = hist['Close'].iloc[-1]
            open_p = hist['Open'].iloc[0]
            change = ((price - open_p) / open_p) * 100
            report += f"{'🟢' if change >= 0 else '🔴'} {ticker}: ${price:,.2f} ({change:+.2f}%)\n"
        except Exception: continue
    return report

def scrape_clean_news():
    cleaned_news = ""
    for url in NEWS_SOURCES:
        try:
            downloaded = trafilatura.fetch_url(url)
            text = trafilatura.extract(downloaded, include_comments=False, no_fallback=True)
            if text: cleaned_news += f"\n[SOURCE: {url}]\n{text[:1500]}\n"
        except: continue
    return cleaned_news

def ask_jarvis_logic(question, context_override=None):
    if llm is None: initialize_brain()
    if not context_override:
        try:
            results = collection.query(query_texts=[question], n_results=2)
            context_override = "\n".join(results['documents'][0])
        except: context_override = ""
    
    prompt = f"<|system|>\nYou are Jarvis. Today is April 7, 2026. Summarize the intel precisely.\nCONTEXT:\n{context_override}<|end|>\n<|user|>\n{question}<|end|>\n<|assistant|>\n"
    output = llm(prompt, max_tokens=1024, stop=["<|end|>"], temperature=0.1)
    return output['choices'][0]['text'].strip()

# --- THE HEARTBEAT (DAILY ROUTINE) ---
async def daily_routine(app):
    global last_sent_date
    while True:
        now = datetime.datetime.now()
        # Briefing scheduled for 08:00
        if now.hour == 8 and now.minute == 0 and last_sent_date != now.date():
            last_sent_date = now.date()
            markets = get_market_data()
            news = scrape_clean_news()
            summary = await asyncio.to_thread(ask_jarvis_logic, "Summarize the 3 most critical headlines.", context_override=news)
            report = f"🌅 **SOVEREIGN BRIEFING**\n\n{markets}\n\n📰 **ANALYSIS:**\n{summary}"
            await app.bot.send_message(chat_id=ALLOWED_USER_ID, text=report, parse_mode="Markdown")
        await asyncio.sleep(30) 

# --- COMMAND HANDLERS ---
async def manual_brief(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    await update.message.reply_text("🔄 Gathering real-time intelligence...")
    markets = get_market_data()
    news = scrape_clean_news()
    analysis = await asyncio.to_thread(ask_jarvis_logic, "Analyze today's news vs market movements.", context_override=news)
    await update.message.reply_text(f"{markets}\n\n🧠 **INTEL:**\n{analysis}", parse_mode="Markdown")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ALLOWED_USER_ID: return
    res = await asyncio.to_thread(ask_jarvis_logic, update.message.text)
    await update.message.reply_text(res)

async def main():
    initialize_brain()
    subprocess.Popen(["python", "server.py"])
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("brief", manual_brief))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_chat))
    
    await app.initialize()
    await app.start()
    print("🌐 Jarvis Core Active | /brief command ready")
    
    asyncio.create_task(daily_routine(app))
    await app.updater.start_polling()
    while True: await asyncio.sleep(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        os._exit(0)
