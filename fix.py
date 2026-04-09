content = open("server.py").read()

insert_before = 'def extract_sources_block(answer):'
helper = '''def web_memory_ttl_minutes(question):
    q = question.lower()
    if any(word in q for word in ["crypto", "bitcoin", "btc", "ethereum", "eth", "solana", "token"]):
        return 30
    if any(word in q for word in ["stock", "stocks", "market", "markets", "shares", "earnings", "nasdaq", "nyse", "dow", "s&p"]):
        return 60
    return 180


'''

if "def web_memory_ttl_minutes(question):" not in content:
    content = content.replace(insert_before, helper + insert_before)

old = '''    if mode == "web":
        recent_web = get_recent_web_memory(question, mode="web", max_age_minutes=180, limit=2)
        if recent_web and not context.strip():
            remembered = []
            for q, s, t, m, sources, saved_context in recent_web:
                remembered.append(f"- {t}: {s}")
            prompt += "Recent source-backed findings:\\n" + "\\n".join(remembered[:2]) + "\\n\\n"'''

new = '''    if mode == "web":
        ttl = web_memory_ttl_minutes(question)
        recent_web = get_recent_web_memory(question, mode="web", max_age_minutes=ttl, limit=2)
        if recent_web and not context.strip():
            remembered = []
            for q, s, t, m, sources, saved_context in recent_web:
                remembered.append(f"- {t}: {s}")
            prompt += "Recent source-backed findings:\\n" + "\\n".join(remembered[:2]) + "\\n\\n"'''

content = content.replace(old, new)

with open("server.py", "w") as f:
    f.write(content)

print("Done")
