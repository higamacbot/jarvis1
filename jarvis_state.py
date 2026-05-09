"""
jarvis_state.py - HIGA HOUSE Shared State Bus
Single source of truth for all bot context.
Refreshes every 60 seconds. Bots read from this instead of fetching independently.

Usage in any bot or router:
    from jarvis_state import get_state
    state = await get_state()
    portfolio = state["portfolio"]
    crypto = state["crypto"]
"""
import asyncio
import os
import time
import httpx
import psutil
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL  = "http://localhost:11434/api/generate"
ALPACA_BASE = "https://paper-api.alpaca.markets/v2"

_cache: dict = {}
_cache_time: float = 0
CACHE_TTL = 60  # seconds

async def _fetch_portfolio() -> dict:
    try:
        import keys
        key    = keys.ALPACA_KEY
        secret = keys.ALPACA_SECRET
    except Exception:
        key    = os.getenv("ALPACA_KEY", "")
        secret = os.getenv("ALPACA_SECRET", "")
    if not key or not secret:
        return {}
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    try:
        async with httpx.AsyncClient(timeout=10, headers=headers) as h:
            acct = (await h.get(f"{ALPACA_BASE}/account")).json()
            pos  = (await h.get(f"{ALPACA_BASE}/positions")).json()
            equity   = float(acct.get("equity", 0))
            last_eq  = float(acct.get("last_equity", equity))
            return {
                "equity":       equity,
                "day_pl":       equity - last_eq,
                "buying_power": float(acct.get("buying_power", 0)),
                "positions": [
                    {
                        "symbol": p["symbol"],
                        "value":  float(p["market_value"]),
                        "pl":     float(p["unrealized_pl"]),
                        "pl_pct": float(p.get("unrealized_plpc", 0)) * 100,
                    }
                    for p in (pos if isinstance(pos, list) else [])
                ]
            }
    except Exception as e:
        print(f">> STATE: portfolio error: {e}")
        return {}

async def _fetch_crypto() -> dict:
    try:
        from briefing_scheduler import get_real_crypto, get_crypto_prices
        total, lines, wb, cb, kr = get_real_crypto()
        prices = await get_crypto_prices()
        return {
            "total":  total,
            "lines":  lines,
            "webull": wb,
            "coinbase": cb,
            "kraken": kr,
            "prices": prices,
        }
    except Exception as e:
        print(f">> STATE: crypto error: {e}")
        return {}

def _fetch_system() -> dict:
    try:
        cpu  = psutil.cpu_percent(interval=0.3)
        ram  = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net  = psutil.net_io_counters()
        boot = datetime.fromtimestamp(psutil.boot_time())
        uptime_h = int((datetime.now() - boot).total_seconds() // 3600)
        return {
            "cpu_pct":    cpu,
            "ram_used_gb": round(ram.used / 1e9, 1),
            "ram_total_gb": round(ram.total / 1e9, 1),
            "ram_pct":    ram.percent,
            "disk_pct":   disk.percent,
            "disk_used_gb": round(disk.used / 1e9, 1),
            "net_sent_mb":  round(net.bytes_sent / 1e6, 1),
            "net_recv_mb":  round(net.bytes_recv / 1e6, 1),
            "uptime_hours": uptime_h,
        }
    except Exception as e:
        print(f">> STATE: system error: {e}")
        return {}

def _fetch_repo() -> dict:
    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd="/Users/higabot1/jarvis1-1",
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        last_commit = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd="/Users/higabot1/jarvis1-1",
            capture_output=True, text=True, timeout=5
        ).stdout.strip()
        return {
            "dirty":       bool(status),
            "dirty_files": status or "clean",
            "last_commit": last_commit,
        }
    except Exception as e:
        print(f">> STATE: repo error: {e}")
        return {}

def _fetch_jobs() -> dict:
    try:
        import sqlite3
        conn = sqlite3.connect("/Users/higabot1/jarvis1-1/jarvis_memory.db")
        conn.row_factory = sqlite3.Row
        pending = conn.execute(
            "SELECT count(*) as n FROM jobs WHERE status='pending'"
        ).fetchone()
        recent = conn.execute(
            "SELECT job_type, status, created FROM jobs ORDER BY id DESC LIMIT 5"
        ).fetchall()
        conn.close()
        return {
            "pending_count": pending["n"] if pending else 0,
            "recent": [dict(r) for r in recent],
        }
    except Exception:
        return {"pending_count": 0, "recent": []}

async def _build_state() -> dict:
    portfolio, crypto = await asyncio.gather(
        _fetch_portfolio(),
        _fetch_crypto(),
    )
    system = _fetch_system()
    repo   = _fetch_repo()
    jobs   = _fetch_jobs()
    return {
        "timestamp":  datetime.now().isoformat(),
        "portfolio":  portfolio,
        "crypto":     crypto,
        "system":     system,
        "repo":       repo,
        "jobs":       jobs,
    }

async def get_state(force_refresh: bool = False) -> dict:
    """Get current HIGA HOUSE state. Cached for 60s."""
    global _cache, _cache_time
    now = time.monotonic()
    if force_refresh or not _cache or (now - _cache_time) > CACHE_TTL:
        _cache = await _build_state()
        _cache_time = now
        print(f">> STATE: refreshed at {datetime.now().strftime('%H:%M:%S')}")
    return _cache

def get_state_sync() -> dict:
    """Sync wrapper for use outside async context."""
    return asyncio.run(get_state())

def format_portfolio_context(state: dict) -> str:
    p = state.get("portfolio", {})
    if not p:
        return "Portfolio: unavailable"
    pos_lines = "\n".join([
        f"  {pos['symbol']}: ${pos['value']:,.2f} (P/L: {pos['pl']:+,.2f})"
        for pos in p.get("positions", [])
    ])
    return (
        f"STOCKS (Alpaca paper):\n"
        f"  Equity: ${p.get('equity', 0):,.2f} | "
        f"Day P/L: {p.get('day_pl', 0):+,.2f} | "
        f"Buying Power: ${p.get('buying_power', 0):,.2f}\n"
        f"{pos_lines}"
    )

def format_crypto_context(state: dict) -> str:
    c = state.get("crypto", {})
    if not c:
        return "Crypto: unavailable"
    return (
        f"CRYPTO (Total: ${c.get('total', 0):.2f}):\n"
        f"{c.get('lines', '')}\n"
        f"  Webull: ${c.get('webull', 0):.2f} | "
        f"Coinbase: ${c.get('coinbase', 0):.2f} | "
        f"Kraken: ${c.get('kraken', 0):.2f}"
    )

def format_system_context(state: dict) -> str:
    s = state.get("system", {})
    if not s:
        return "System: unavailable"
    return (
        f"SYSTEM: CPU {s.get('cpu_pct', 0):.0f}% | "
        f"RAM {s.get('ram_used_gb', 0):.1f}GB/{s.get('ram_total_gb', 0):.1f}GB | "
        f"Disk {s.get('disk_pct', 0):.0f}% | "
        f"Uptime {s.get('uptime_hours', 0)}h"
    )

def format_full_context(state: dict) -> str:
    return "\n\n".join([
        format_portfolio_context(state),
        format_crypto_context(state),
        format_system_context(state),
    ])
