# J.A.R.V.I.S. — Sovereign Intelligence Terminal

A locally-hosted AI assistant with live market data, portfolio tracking, and YouTube research.

## Features
- Live crypto prices (Binance)
- Alpaca paper trading portfolio
- YouTube transcript and summarization
- SQLite memory across sessions
- Local LLM via Ollama (qwen3:8b)
- macOS voice output

## Setup
1. Install Ollama and pull qwen3:8b
2. Clone repo and activate venv
3. Copy .env.example to .env and add keys
4. Create keys.py with Alpaca credentials
5. Run: python main.py
