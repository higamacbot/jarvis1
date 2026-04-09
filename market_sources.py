MARKET_SOURCES = {
    "stocks": {
        "main": [
            {"name": "Bloomberg", "url": "https://www.bloomberg.com/markets"},
            {"name": "CNBC", "url": "https://www.cnbc.com/markets/"},
        ],
        "political": [
            {"name": "Capitol Trades", "url": "https://www.capitoltrades.com/press"},
            {"name": "Unusual Whales", "url": "https://unusualwhales.com/"},
        ],
        "underground": [
            {"name": "Quiver Quant", "url": "https://www.quiverquant.com/congresstrading/"},
            {"name": "Reuters Markets", "url": "https://www.reuters.com/markets/"},
        ],
        "war": [
            {"name": "Fox Business", "url": "https://www.foxbusiness.com/markets"},
        ],
    },
    "crypto": {
        "news": [
            {"name": "CoinDesk", "url": "https://www.coindesk.com/"},
            {"name": "The Block", "url": "https://www.theblock.co/latest-crypto-news"},
        ],
        "onchain": [],
        "market": [],
        "signals": [],
    },
}

STOCK_TRIGGERS = [
    "stock", "stocks", "market", "markets", "shares", "equity", "equities",
    "nasdaq", "nyse", "dow", "s&p", "earnings",
]

CRYPTO_TRIGGERS = [
    "crypto", "bitcoin", "btc", "ethereum", "eth", "sol", "solana",
    "xrp", "doge", "altcoin", "altcoins", "defi", "token", "tokens",
]

def get_stock_sources():
    groups = MARKET_SOURCES["stocks"]
    return groups["main"] + groups["political"] + groups["underground"] + groups["war"]

def get_crypto_sources():
    groups = MARKET_SOURCES["crypto"]
    return groups["news"] + groups["onchain"] + groups["market"] + groups["signals"]
