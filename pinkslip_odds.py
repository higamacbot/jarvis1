"""
pinkslip_odds.py — live sports odds via the-odds-api.com free tier (500 req/mo)
Add ODDS_API_KEY to .env — get free key at https://the-odds-api.com
"""
from __future__ import annotations
import os, asyncio
from typing import Any
import httpx
from dotenv import load_dotenv
load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
BASE = "https://api.the-odds-api.com/v4"
DEFAULT_SPORTS = ["americanfootball_nfl","basketball_nba","baseball_mlb","icehockey_nhl","mma_mixed_martial_arts"]

class OddsAPIError(RuntimeError): pass

async def get_odds(sport: str, regions: str = "us", markets: str = "h2h,spreads", timeout: float = 15.0) -> list[dict[str, Any]]:
    if not ODDS_API_KEY or ODDS_API_KEY == "your_key_here":
        raise OddsAPIError("ODDS_API_KEY missing in .env — get free key at https://the-odds-api.com")
    params = {"apiKey": ODDS_API_KEY, "regions": regions, "markets": markets, "oddsFormat": "american", "dateFormat": "iso"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(f"{BASE}/sports/{sport}/odds", params=params)
    if r.status_code == 401: raise OddsAPIError("invalid ODDS_API_KEY")
    if r.status_code == 429: raise OddsAPIError("odds-api quota exhausted")
    r.raise_for_status()
    print(f">> ODDS API: {sport} ok, {r.headers.get('x-requests-remaining','?')} req remaining")
    return r.json()

def _best_h2h(bookmakers: list[dict]) -> dict[str, float]:
    best: dict[str, float] = {}
    for bk in bookmakers:
        for mkt in bk.get("markets", []):
            if mkt["key"] != "h2h": continue
            for o in mkt["outcomes"]:
                if o["name"] not in best or o["price"] > best[o["name"]]:
                    best[o["name"]] = o["price"]
    return best

def format_odds_message(events: list[dict], limit: int = 6) -> str:
    if not events: return "📋 PINKSLIP: no games on the board."
    lines = ["📋 *PINKSLIP — live odds*", ""]
    for ev in events[:limit]:
        best = _best_h2h(ev.get("bookmakers", []))
        if not best: continue
        parts = [f"{t} {('+' if p > 0 else '')}{p}" for t, p in best.items()]
        lines.append(f"• {ev['away_team']} @ {ev['home_team']} — {' / '.join(parts)}")
    return "\n".join(lines)

async def get_all_default(limit_per_sport: int = 4) -> str:
    blocks = []
    for sport in DEFAULT_SPORTS:
        try:
            evs = await get_odds(sport)
            if evs: blocks.append(f"*{sport}*\n" + format_odds_message(evs, limit_per_sport))
        except OddsAPIError as e: blocks.append(f"_{sport}: {e}_")
        except Exception as e: blocks.append(f"_{sport}: {type(e).__name__}_")
    return "\n\n".join(blocks) or "📋 PINKSLIP: no odds available."

if __name__ == "__main__":
    print(asyncio.run(get_all_default()))
