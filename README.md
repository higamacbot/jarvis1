# HIGA HOUSE — J.A.R.V.I.S. Multi-Agent Intelligence Terminal

A locally-hosted multi-agent AI system running on Mac Mini M4.

## Architecture
- **FastAPI** server on port 8000 with WebSocket endpoints
- **Ollama** (qwen3:8b) as the local LLM backbone
- **11 specialized agents** in HIGA HOUSE UI
- **3 debate bots** — Shaman, Lib Mom, MAGA Dad
- **ChromaDB** semantic memory per bot
- **SQLite** conversation + task queue storage

## Agents
| Bot | Role |
|-----|------|
| JARVIS | Chief of staff, command center |
| STOCKBOT | Alpaca paper trading, SMA autopilot |
| CRYPTOID | Multi-broker crypto ($466 real portfolio) |
| PINKSLIP | Sports betting intelligence |
| DOCTORBOT | Code review, bug scan, brainstorm |
| ULTRON | Security monitoring |
| ROBOWRIGHT | Viral video strategist, script writer |
| JAMZ | Beat design, DJ sets, Suno/Udio prompts |
| HIGASHOP | E-commerce, Etsy/Fiverr ops |
| TECHNOID | Hardware monitoring |
| TEACHERBOT | Education, lesson plans |
| SHAMAN | Conspiracy room debate bot |
| LIB MOM | Progressive debate bot |
| MAGA DAD | Patriot debate bot |

## Features
- Real portfolio tracking: Webull, Robinhood, Coinbase, Acorns, Alpaca, Kraken
- YouTube transcripts → PDF → Obsidian vault
- Live AP/BBC headlines in 5AM/5PM briefings
- Autonomous job queue (/queue, /review, /batches)
- Debate arena with colored per-persona responses
- Bot memory namespaces via ChromaDB
- Telegram briefings and commands
- Mac system control via mac_tools

## Launch
```bash
cd /Users/higabot1/jarvis1-1
bash start.sh
# Open http://localhost:8000/house
```

## Commands
- `/brief` — full agent briefing
- `/queue [YouTube URLs]` — batch transcript jobs
- `/queue channel [name]` — scrape full channel
- `/review` — see completed jobs
- `/pipeline [query]` — manual YouTube intel run
- `/debate [topic]` — trigger all 3 debate bots
- `/assign [bot] [task]` — assign task to any bot

## Stack
Python 3.9 | FastAPI | Ollama | ChromaDB | SQLite | Alpaca SDK | FPDF2 | yt-dlp
