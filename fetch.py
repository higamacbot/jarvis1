import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def extract_urls(text):
    pattern = r"(https?://\S+|www\.\S+)"
    return re.findall(pattern, text)


def _get_soup(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _clean_text(soup):
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 30]
    return "\n".join(lines[:100])


def fetch_url(url):
    try:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        soup = _get_soup(url)
        return _clean_text(soup)
    except Exception as e:
        return f"Could not fetch URL: {e}"


def _same_site(base_netloc, candidate_netloc):
    base = base_netloc.replace("www.", "")
    cand = candidate_netloc.replace("www.", "")
    return cand == base or cand.endswith("." + base) or base.endswith("." + cand)


def extract_article_url(home_url, preferred_keywords=None):
    try:
        soup = _get_soup(home_url)
        base_netloc = urlparse(home_url).netloc
        best_url = ""

        best_score = -999
        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            full_url = urljoin(home_url, href)
            parsed = urlparse(full_url)

            if parsed.scheme not in ("http", "https"):
                continue
            if not _same_site(base_netloc, parsed.netloc):
                continue

            path = parsed.path.strip("/")
            if not path:
                continue

            lower = full_url.lower()
            score = 0

            if "/2026/" in lower:
                score += 8
            elif "/2025/" in lower:
                score += 3
            elif re.search(r"/20\d{2}/", lower):
                score -= 2

            if re.search(r"/2026/\d{2}/\d{2}/", lower):
                score += 6
            elif re.search(r"/2025/\d{2}/\d{2}/", lower):
                score += 2
            elif re.search(r"/\d{4}/\d{2}/\d{2}/", lower):
                score -= 2

            if any(token in lower for token in ["/article", "/story", "/politics/", "/world/", "/us/", "/news/"]):
                score += 2
            if len(path.split("/")) >= 2:
                score += 1

            if preferred_keywords and any(keyword in lower for keyword in preferred_keywords):
                score += 6

            text = link.get_text(" ", strip=True)
            if len(text) >= 25:
                score += 1

            if any(token in lower for token in ["/video", "/videos", "/live", "/search", "/tag/", "/tags/", "/topic/", "/topics/", "/category", "/categories"]):
                score -= 3

            if score > best_score:
                best_score = score
                best_url = full_url

        return best_url or home_url
    except Exception:
        return home_url


def fetch_crypto_article_context(home_url):
    preferred_keywords = ["crypto", "bitcoin", "btc", "ethereum", "eth", "token", "blockchain", "defi", "solana", "xrp"]

    try:
        article_url = extract_article_url(home_url, preferred_keywords=preferred_keywords)
        if not article_url:
            return home_url, fetch_url(home_url)

        url_lower = article_url.lower()
        if not any(keyword in url_lower for keyword in preferred_keywords):
            return home_url, fetch_url(home_url)

        text = fetch_url(article_url)
        if text.startswith("Could not") or len(text.strip()) < 200:
            return home_url, fetch_url(home_url)

        return article_url, text
    except Exception:
        return home_url, fetch_url(home_url)


def fetch_source_context(home_url, preferred_keywords=None):
    article_url = extract_article_url(home_url, preferred_keywords)
    text = fetch_url(article_url)

    if text.startswith("Could not") or len(text.strip()) < 200:
        fallback = fetch_url(home_url)
        if not fallback.startswith("Could not"):
            return home_url, fallback
    return article_url, text
