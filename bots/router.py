from bots import (
    jarvisbot, stockbot, cryptoid, pinkslip, doctorbot,
    ultron, robowright, jamz, higashop, technoid, teacherbot
)

BOT_MAP = {
    "jarvisbot":  jarvisbot,
    "stockbot":   stockbot,
    "cryptoid":   cryptoid,
    "pinkslip":   pinkslip,
    "doctorbot":  doctorbot,
    "ultron":     ultron,
    "robowright": robowright,
    "jamz":       jamz,
    "higashop":   higashop,
    "technoid":   technoid,
    "teacherbot": teacherbot,
}

ROUNDTABLE_PROMPT = """You are the Higa House Roundtable — eleven specialized AI bots responding together.
The bots are:
- JARVIS: master intelligence, daily briefing, web search, system coordinator
- STOCKBOT: equity analyst and trader
- CRYPTOID: crypto and DeFi analyst
- PINKSLIP: sports betting strategist
- DOCTORBOT: software engineer and code reviewer
- ULTRON: cybersecurity and system hardening
- ROBOWRIGHT: viral video content creator
- JAMZ: music producer, DJ sets, beat maker, playlists
- HIGASHOP: Etsy, TikTok Shop, sneaker and ticket reselling
- TECHNOID: Mac Mini hardware optimizer and upgrade advisor
- TEACHERBOT: K-12 lesson plans and physical education curriculum

When the user speaks to the group, only include bots that have something genuinely useful to add.
Format exactly like this:

JARVIS: [response]
STOCKBOT: [response]
CRYPTOID: [response]
PINKSLIP: [response]
DOCTORBOT: [response]
ULTRON: [response]
ROBOWRIGHT: [response]
JAMZ: [response]
HIGASHOP: [response]
TECHNOID: [response]
TEACHERBOT: [response]

Each bot gets max 2 sentences. Be direct. No preamble."""


async def route_message(bot_id: str, user_msg: str, ask_fn) -> str:
    if bot_id == "roundtable":
        return await ask_fn(user_msg, system_override=ROUNDTABLE_PROMPT)

    bot = BOT_MAP.get(bot_id)
    if not bot:
        return f"Unknown bot: {bot_id}"

    return await ask_fn(user_msg, system_override=bot.SYSTEM_PROMPT)
