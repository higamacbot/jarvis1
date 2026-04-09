NEWS_SOURCES = {
    "sites": [
        {"name": "AP", "url": "https://apnews.com/"},
        {"name": "BBC", "url": "https://www.bbc.com/news"},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/"},
        {"name": "Fox", "url": "https://www.foxnews.com/"},
        {"name": "CNN", "url": "https://www.cnn.com/"},
        {"name": "KSLA", "url": "https://www.ksla.com/"},
        {"name": "KALB", "url": "https://www.kalb.com/"},
        {"name": "New York Post", "url": "https://nypost.com/"},
        {"name": "Infowars", "url": "https://www.infowars.com/"},
    ],
    "youtube": [],
}

NEWS_TRIGGERS = [
    "news",
    "headlines",
    "current events",
    "what's happening",
    "what is happening",
    "what happened today",
    "what's in the news",
    "today's news",
    "latest news",
]

def get_site_sources():
    return NEWS_SOURCES["sites"]

def get_youtube_sources():
    return NEWS_SOURCES["youtube"]
