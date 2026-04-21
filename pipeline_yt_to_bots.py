"""
pipeline_yt_to_bots.py — YouTube -> Stockbot/Cryptoid Pipeline
Scrapes video transcripts, extracts tickers/coins, routes to correct bots.
Runs every 6 hours automatically.
"""
import asyncio
import re
import os
import httpx
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "qwen3:8b"

STOCK_TICKERS = [
    "AAPL","NVDA","TSLA","MSFT","AMZN","GOOGL","META","SPY","QQQ",
    "AMD","INTC","NFLX","DIS","BA","JPM","GS","V","MA","UBER","PYPL","VOO"
]
CRYPTO_COINS = [
    "BTC","ETH","SOL","DOGE","SHIB","PEPE","BNB","XRP","ADA",
    "AVAX","MATIC","DOT","LINK","LTC","BCH","NEAR"
]

AUTO_SCRAPE_QUERIES = [
    "stock market analysis today",
    "bitcoin crypto news today",
    "best stocks to buy this week",
    "crypto market update",
]

def extract_tickers(text: str) -> dict:
    text_upper = text.upper()
    found_stocks = [t for t in STOCK_TICKERS if re.search(rf'\b{t}\b', text_upper)]
    found_crypto = [c for c in CRYPTO_COINS if re.search(rf'\b{c}\b', text_upper)]
    return {"stocks": list(set(found_stocks)), "crypto": list(set(found_crypto))}

async def summarize_for_bot(transcript: str, bot_type: str, tickers: list) -> str:
    ticker_str = ", ".join(tickers) if tickers else "general market"
    prompt = f"""You are analyzing a video transcript for the {bot_type} bot.
Focus only on: {ticker_str}
Extract:
1. Any price predictions or targets mentioned
2. Buy/sell signals or recommendations
3. Key news or catalysts discussed
4. Sentiment (bullish/bearish/neutral)

Transcript (first 2000 chars):
{transcript[:2000]}

Give a concise 3-5 bullet point summary:"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(OLLAMA_URL, json={
                "model": MODEL, "prompt": prompt, "stream": False
            })
            return r.json().get("response", "").strip()
    except Exception as e:
        return f"Summary failed: {e}"

async def run_youtube_pipeline(query: str = None):
    """Main pipeline: scrape YouTube -> extract tickers -> route to correct bots."""
    from youtube_tools import handle_youtube_request
    from bot_orchestrator import orchestrator

    queries = [query] if query else AUTO_SCRAPE_QUERIES[:2]

    for q in queries:
        print(f">> PIPELINE: Scraping YouTube for '{q}'")
        orchestrator.update_status("jarvisbot", "yellow", f"YT Pipeline: {q}")

        try:
            result, mode = handle_youtube_request(f"summarize {q}")
            if not result:
                continue

            found = extract_tickers(result)
            print(f">> PIPELINE: stocks={found['stocks']} crypto={found['crypto']}")

            # Route to stockbot if stocks found
            if found["stocks"]:
                orchestrator.update_status("stockbot", "yellow", f"YT intel: {found['stocks']}")
                summary = await summarize_for_bot(result, "stock", found["stocks"])
                task_id = orchestrator.assign_task(
                    "stockbot",
                    f"YouTube stock intel for {found['stocks']}: {summary[:300]}"
                )
                orchestrator.complete_task(task_id, summary, "stockbot")
                print(f">> PIPELINE: Routed stock intel to stockbot")

            # Route to cryptoid if coins found
            if found["crypto"]:
                orchestrator.update_status("cryptoid", "yellow", f"YT crypto intel: {found['crypto']}")
                summary = await summarize_for_bot(result, "crypto", found["crypto"])
                task_id = orchestrator.assign_task(
                    "cryptoid",
                    f"YouTube crypto intel for {found['crypto']}: {summary[:300]}"
                )
                orchestrator.complete_task(task_id, summary, "cryptoid")
                print(f">> PIPELINE: Routed crypto intel to cryptoid")

            # Route geopolitical content to debate bots
            geo_keywords = ["war","iran","china","russia","oil","sanctions","geopolit","trump","military"]
            if any(k in result.lower() for k in geo_keywords):
                orchestrator.update_status("shaman", "yellow", f"YT geopolitical intel incoming")
                task_id = orchestrator.assign_task("shaman", f"Geopolitical intel from YouTube: {result[:400]}")
                orchestrator.complete_task(task_id, result[:400], "shaman")
                print(f">> PIPELINE: Routed geopolitical intel to debate bots")

            orchestrator.update_status("jarvisbot", "green", f"Pipeline complete: {q}")

        except Exception as e:
            print(f">> PIPELINE ERROR: {e}")
            orchestrator.update_status("jarvisbot", "red", f"Pipeline error: {e}")

        await asyncio.sleep(5)

async def run_pipeline_scheduler():
    """Runs the YouTube pipeline every 6 hours automatically."""
    print(">> PIPELINE SCHEDULER: Started — runs every 6 hours")
    while True:
        await run_youtube_pipeline()
        await asyncio.sleep(6 * 60 * 60)
