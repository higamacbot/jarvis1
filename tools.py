import json
import os

from pypdf import PdfReader

from fetch import fetch_source_context, fetch_url, fetch_crypto_article_context
from news_sources import NEWS_TRIGGERS, get_site_sources
from market_sources import STOCK_TRIGGERS, CRYPTO_TRIGGERS, get_stock_sources, get_crypto_sources


def is_news_query(question):
    q = question.lower()
    return any(t in q for t in NEWS_TRIGGERS)


def is_stock_query(question):
    q = question.lower()
    return any(t in q for t in STOCK_TRIGGERS)


def is_crypto_query(question):
    q = question.lower()
    return any(t in q for t in CRYPTO_TRIGGERS)


def search_web(query):
    return ""


def search_news_sources(query, max_sources=4):
    collected = []

    for source in get_site_sources():
        article_url, text = fetch_source_context(source["url"])
        if text and not text.startswith("Could not"):
            snippet = text[:1200].strip()
            if snippet:
                collected.append(
                    f'Source: {source["name"]}\n'
                    f'URL: {article_url}\n'
                    f'Content:\n{snippet}'
                )

        if len(collected) >= max_sources:
            break

    return "\n\n".join(collected)


def extract_stock_signal_lines(text, limit=5):
    keywords = [
        "trade", "trades", "stock", "stocks", "shares", "congress",
        "senator", "representative", "insider", "short interest",
        "bill", "options", "dark pool", "tesla", "ai", "iran",
        "surge", "rises", "falls", "drops", "buys", "sells", "disclosed"
    ]
    bad_phrases = [
        "newsletter", "pricing", "api", "docs", "documentation",
        "community", "courses", "education", "join our", "live trade rooms",
        "search stocks, politicians, and more", "trusted source for media outlets",
        "industry leading resource", "track the forces that move the markets",
        "access quiver's data directly", "options flow, dark pool & stock market data",
        "congress trading - quiver quantitative", "what's trading on capitol hill"
    ]

    lines = []
    seen = set()

    for line in text.splitlines():
        s = line.strip()
        lower = s.lower()
        if len(s) < 35:
            continue
        if any(bad in lower for bad in bad_phrases):
            continue
        if not any(key in lower for key in keywords):
            continue
        if lower in seen:
            continue

        seen.add(lower)
        lines.append(s)

        if len(lines) >= limit:
            break

    return lines


def extract_market_update_lines(text, limit=4):
    bad_phrases = [
        "traders work on the floor",
        "getty images",
        "photo",
        "pictured",
        "in new york city"
    ]

    lines = []
    seen = set()

    for line in text.splitlines():
        s = line.strip()
        lower = s.lower()
        if len(s) < 55:
            continue
        if any(bad in lower for bad in bad_phrases):
            continue
        if lower in seen:
            continue

        seen.add(lower)
        lines.append(s)

        if len(lines) >= limit:
            break

    return lines


def search_stock_sources(query, max_sources=7):
    updates = []

    for source in get_stock_sources():
        name = source["name"]
        url = source["url"]
        bullet = ""

        if name in {"Bloomberg", "CNBC", "Reuters Markets", "Fox Business"}:
            article_url, text = fetch_source_context(url)
            if text and not text.startswith("Could not"):
                lines = extract_market_update_lines(text, limit=3)
                if lines:
                    bullet = lines[0]
                    url = article_url

        elif name in {"Capitol Trades", "Quiver Quant", "Unusual Whales", "Penny Stock Dream", "Bullish Bears"}:
            text = fetch_url(url)
            if text and not text.startswith("Could not"):
                lines = extract_stock_signal_lines(text, limit=5)

                filtered = []
                bad_daily_phrases = [
                    "the stock trading on congressional knowledge act requires",
                    "publicly file and disclose any financial transaction within 45 days",
                    "congress trading - quiver quantitative",
                    "why traders like you are joining",
                    "educational stock trading community",
                    "options flow, dark pool & stock market data",
                ]

                for line in lines:
                    lower = line.lower()
                    if any(bad in lower for bad in bad_daily_phrases):
                        continue
                    filtered.append(line)

                if filtered:
                    bullet = filtered[0]

        if bullet:
            updates.append(
                f"Stock Source Update: {name}\n"
                f"URL: {url}\n"
                f"Bullet: {bullet}"
            )

        if len(updates) >= max_sources:
            break

    return "\n\n".join(updates)

def extract_crypto_update_lines(text, limit=3):
    bad_phrases = [
        "getty images",
        "photo",
        "pictured",
        "advertisement",
        "sign up",
        "newsletter",
        "pricing",
        "api",
        "learn more"
    ]

    lines = []
    seen = set()

    for line in text.splitlines():
        s = line.strip()
        lower = s.lower()
        if len(s) < 45:
            continue
        if any(bad in lower for bad in bad_phrases):
            continue
        if lower in seen:
            continue

        seen.add(lower)
        lines.append(s)

        if len(lines) >= limit:
            break

    return lines


def search_crypto_sources(query, max_sources=5):
    updates = []
    seen_urls = set()

    for source in get_crypto_sources():
        name = source["name"]

        if name in {"CoinDesk", "The Block"}:
            article_url, text = fetch_crypto_article_context(source["url"])
            url = article_url
            if not text or text.startswith("Could not"):
                continue

            lines = extract_crypto_update_lines(text, limit=3)
            if not lines:
                continue

            bullet = lines[0]

        else:
            text = fetch_url(source["url"])
            url = source["url"]
            if not text or text.startswith("Could not"):
                continue

            lines = extract_stock_signal_lines(text, limit=3)
            filtered = []
            bad_daily_phrases = [
                "pricing", "api", "docs", "documentation", "academy",
                "learn", "playbook", "dashboard", "track", "analytics"
            ]
            for line in lines:
                lower = line.lower()
                if any(bad in lower for bad in bad_daily_phrases):
                    continue
                filtered.append(line)

            if not filtered:
                continue

            bullet = filtered[0]

        if url in seen_urls:
            continue

        updates.append(
            f"Crypto Source Update: {name}\n"
            f"URL: {url}\n"
            f"Bullet: {bullet}"
        )
        seen_urls.add(url)

        if len(updates) >= max_sources:
            break

    return "\n\n".join(updates)

def load_pdf(path):
    if not os.path.exists(path):
        print("File not found.")
        return ""
    try:
        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
        return text
    except Exception as e:
        print(f"PDF error: {e}")
        return ""


def dispatch(question, ollama_func):
    decision_prompt = f"""You are a tool dispatcher for an AI assistant.

Given the user's question, decide which tool to use.

Question: {question}

Reply with valid JSON only, no explanation, no markdown:
{{"tool": "web", "reason": "needs current info"}}
{{"tool": "pdf", "reason": "references a document"}}
{{"tool": "chat", "reason": "can answer from knowledge"}}

JSON:"""

    raw = ollama_func(
        decision_prompt,
        "You are a tool dispatcher. Reply with valid JSON only."
    ).strip()

    tool = "chat"
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        tool = data.get("tool", "chat").lower()
        if tool not in ["web", "pdf", "chat"]:
            tool = "chat"
    except Exception:
        if "web" in raw.lower():
            tool = "web"
        elif "pdf" in raw.lower():
            tool = "pdf"

    print(f"[Tool: {tool}]")

    context = ""
    if tool == "web":
        print("Searching web...")
        if is_crypto_query(question):
            context = search_crypto_sources(question)
        elif is_stock_query(question):
            context = search_stock_sources(question)
        elif is_news_query(question):
            context = search_news_sources(question)
        else:
            context = search_web(question)

        if not context.strip():
            print("Web returned nothing, falling back to chat.")
            tool = "chat"

    elif tool == "pdf":
        path = input("PDF path: ").strip()
        context = load_pdf(path)

    return tool, context
