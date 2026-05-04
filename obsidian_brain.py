"""
obsidian_brain.py — all 11 bots write notes to /Users/higabot1/jarvis/brain

Usage in any bot:
    from obsidian_brain import note, daily_log
    note("cryptoid", "BTC hold signal", body="P/L +$56.46", tags=["crypto","btc"])
"""
from __future__ import annotations
import os, re
from datetime import datetime
from pathlib import Path
from typing import Iterable

VAULT = Path(os.getenv("OBSIDIAN_VAULT", "/Users/higabot1/jarvis/brain"))
KNOWN_BOTS = {
    "jarvisbot","stockbot","cryptoid","pinkslip","doctorbot",
    "ultron","robowright","jamz","higashop","technoid","teacherbot",
    "shaman","libmom","magadad",
}
_slug_re = re.compile(r"[^a-z0-9]+")

def _slug(s: str) -> str:
    return _slug_re.sub("-", s.lower()).strip("-")[:80] or "note"

def _frontmatter(bot: str, title: str, tags: Iterable[str]) -> str:
    ts = datetime.now().isoformat(timespec="seconds")
    tag_list = ", ".join(f'"{t}"' for t in [bot, *tags])
    return f'---\nbot: "{bot}"\ntitle: "{title}"\ncreated: "{ts}"\ntags: [{tag_list}]\n---\n\n'

def note(bot: str, title: str, body: str = "", tags: Iterable[str] = (), subfolder: str | None = None) -> Path:
    bot = bot.lower().strip()
    bot_dir = VAULT / (bot if bot in KNOWN_BOTS else f"_misc/{bot}")
    if subfolder:
        bot_dir = bot_dir / _slug(subfolder)
    bot_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = bot_dir / f"{stamp}_{_slug(title)}.md"
    path.write_text(_frontmatter(bot, title, tags) + f"# {title}\n\n{body}\n")
    idx = VAULT / "_index.md"
    idx.parent.mkdir(parents=True, exist_ok=True)
    with idx.open("a") as f:
        f.write(f"- {datetime.now():%Y-%m-%d %H:%M} · **{bot}** · {title}\n")
    return path

def daily_log(bot: str, line: str) -> Path:
    bot = bot.lower().strip()
    day = datetime.now().strftime("%Y-%m-%d")
    path = VAULT / bot / "daily" / f"{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_frontmatter(bot, f"{bot} daily {day}", ["daily"]))
    with path.open("a") as f:
        f.write(f"- {datetime.now():%H:%M:%S} — {line}\n")
    return path

if __name__ == "__main__":
    p = note("jarvisbot", "Smoke test", body="HIGA HOUSE online", tags=["test"])
    print(f"wrote {p}")
