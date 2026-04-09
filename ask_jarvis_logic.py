def ask_jarvis_logic(question: str, context: str = None):
    if llm is None:
        initialize_brain()

    # WE ARE HARDENING THE PROMPT HERE:
    prompt = (
        f"<|system|>\n"
        f"You are Jarvis, a high-level sovereign intelligence officer. "
        f"Do not give generic definitions. Be cold, analytical, and specific. "
        f"Analyze the provided news context for military escalations, ceasefire terms, and specific market movers. "
        f"If the context is poor, state that and analyze the Market Data trends instead.\n"
        f"CONTEXT:\n{context}<|end|>\n"
        f"<|user|>\n{question}<|end|>\n"
        f"<|assistant|>\n"
    )

    output = llm(
        prompt,
        max_tokens=1024,
        stop=["<|end|>"],
        temperature=0.1
    )

    return output['choices'][0]['text'].strip()
