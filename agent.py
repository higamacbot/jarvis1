import os
import requests
import datetime
import textwrap
from tools import dispatch
from memory import init_db, save_memory, search_memory, get_recent

# Initialize DB on startup
init_db()

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3:latest"
CONTEXT_WINDOW = 8192
MAX_HISTORY = 5

# ---------- SESSION MEMORY ----------
conversation_history = []

def add_to_history(question, summary):
    if summary and len(summary.split()) >= 5 and not summary.startswith("Ollama Error"):
        conversation_history.append({"question": question, "summary": summary})
        if len(conversation_history) > MAX_HISTORY:
            conversation_history.pop(0)

def build_history_context():
    if not conversation_history:
        return ""
    lines = ["Recent conversation:"]
    for turn in conversation_history:
        lines.append(f"- Q: {turn['question']}")
        lines.append(f"  A: {turn['summary']}")
    history_text = "\n".join(lines)
    history_text = history_text.replace("SUMMARY:", "").replace("ANSWER:", "")
    return history_text


# ---------- SAVE ----------
def save_to_file(mode, question, answer):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = "research_notes.md"
    try:
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"\n## {timestamp}\n")
            f.write(f"Mode: {mode}\n")
            f.write(f"Q: {question}\n")
            f.write(f"A:\n{answer}\n")
            f.write("\n---\n")
        print(f"Saved to {filename}")
    except Exception as e:
        print(f"Save error: {e}")


# ---------- OLLAMA ----------
def ask_ollama(prompt, system="You are a helpful assistant."):
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": f"System: {system}\n\nUser: {prompt}",
                "stream": False,
                "options": {"num_ctx": CONTEXT_WINDOW}
            },
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return data.get("response", "").strip()
        return ""
    except Exception as e:
        return f"Ollama Error: {e}"


# ---------- CHAT ----------
def chat(question, context="", mode="chat"):
    # Build session history
    history = build_history_context()

    # Build long-term memory context
    memory_context = ""
    past = search_memory(question)
    recent = get_recent()

    seen = set()
    for q, s, t in past + recent:
        if q not in seen:
            seen.add(q)
            memory_context += f"[Past] Q: {q}\n       A: {s}\n\n"

    prompt = ""
    if memory_context:
        prompt += f"Long-term memory:\n{memory_context[:1500]}\n\n"
    if history:
        prompt += history[:1500] + "\n\n"
    if context and context.strip():
        prompt += f"Context:\n{context[:4000]}\n\n"

    prompt += f"""Question: {question}

Respond in this format exactly:
ANSWER:
<your full answer here>
SUMMARY:
<1 sentence summary>"""

    raw = ask_ollama(
        prompt,
        "You are a helpful research assistant. Use memory and context when relevant."
    )

    if raw.startswith("Ollama Error"):
        return raw

    answer, summary = raw, ""
    try:
        if "SUMMARY:" in raw:
            before, after = raw.split("SUMMARY:", 1)
            summary = after.strip()
            if "ANSWER:" in before:
                answer = before.split("ANSWER:", 1)[1].strip()
            else:
                answer = before.strip()
        else:
            answer = raw.strip()
            summary = raw[:200]
    except:
        answer = raw
        summary = raw[:200]

    # Save to both session and long-term memory
    add_to_history(question, summary)
    save_memory(question, summary)

    return answer


# ---------- MAIN ----------
def main():
    print("\n=== AI Assistant ===")
    print("Type your question. Commands: history, quit\n")

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "quit":
            break

        elif user_input.lower() == "history":
            print("\n--- Session History ---")
            if not conversation_history:
                print("No history yet.")
            else:
                for i, h in enumerate(conversation_history, 1):
                    print(f"{i}. Q: {h['question']}")
                    print(f"   A: {h['summary']}\n")
            continue

        elif user_input.lower() == "memory":
            print("\n--- Long-term Memory ---")
            recent = get_recent(5)
            if not recent:
                print("No memory yet.")
            else:
                for i, (q, s, t) in enumerate(recent, 1):
                    print(f"{i}. [{t}] Q: {q}")
                    print(f"   A: {s}\n")
            continue

        mode, context = dispatch(user_input, ask_ollama)
        answer = chat(user_input, context, mode)

        print(f"\nAssistant:")
        print(textwrap.fill(answer, 80))
        print()

        save_to_file(mode, user_input, answer)


if __name__ == "__main__":
    main()
