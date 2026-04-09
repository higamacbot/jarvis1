import sqlite3
import json
from datetime import datetime

DB_PATH = "memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS conversations 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, role TEXT, content TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS preferences 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, value TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

def save_conversation(role, content):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO conversations (timestamp, role, content) VALUES (?, ?, ?)",
                   (datetime.now().isoformat(), role, content))
    conn.commit()
    conn.close()

def detect_and_save_preference(text):
    # Expanded trigger list for better "listening"
    triggers = ["i prefer", "i want", "i like", "i hate", "avoid", "always", "never", "my strategy", "remember that"]
    if any(trigger in text.lower() for trigger in triggers):
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        key = f"user_pref_{int(datetime.now().timestamp())}"
        cursor.execute("INSERT INTO preferences (key, value, timestamp) VALUES (?, ?, ?)",
                       (key, text, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    return False

def get_memory_context(limit=5):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get recent chat history
    cursor.execute("SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?", (limit,))
    history = cursor.fetchall()[::-1]
    
    # Get ALL saved preferences
    cursor.execute("SELECT value FROM preferences ORDER BY id DESC")
    prefs = cursor.fetchall()
    
    conn.close()
    
    context = "--- LONG-TERM USER PREFERENCES ---\n"
    if prefs:
        for p in prefs:
            context += f"- {p[0]}\n"
    else:
        context += "No specific preferences recorded yet.\n"
        
    context += "\n--- RECENT CONVERSATION ---\n"
    for role, content in history:
        context += f"{role.upper()}: {content}\n"
        
    return context

if __name__ == "__main__":
    init_db()
    print(">> MEMORY: Diagnostic check...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM preferences")
    print("PREFERENCES:", cursor.fetchall())
    cursor.execute("SELECT * FROM conversations LIMIT 5")
    print("CONVERSATIONS:", cursor.fetchall())
    conn.close()
