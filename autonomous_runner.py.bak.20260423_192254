"""
autonomous_runner.py — HIGA HOUSE Autonomous Task System
Runs jobs while you're away. YouTube batches, debates, news summaries.
"""
import asyncio, sqlite3, os, json, time, httpx, re
from datetime import datetime
from typing import Optional

DB_PATH        = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.db")
OLLAMA_URL     = "http://localhost:11434/api/generate"
MODEL          = "qwen3:8b"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID")

def init_jobs_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT, job_type TEXT,
        payload TEXT, status TEXT DEFAULT 'pending', result TEXT DEFAULT '',
        output_file TEXT DEFAULT '', error TEXT DEFAULT '',
        created TEXT, started TEXT, completed TEXT, reviewed INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS batches (
        id TEXT PRIMARY KEY, name TEXT, description TEXT,
        total_jobs INTEGER DEFAULT 0, done_jobs INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending', created TEXT, completed TEXT)""")
    conn.commit(); conn.close()

class JobManager:
    def create_batch(self, name, description=""):
        bid = f"batch_{int(time.time())}"
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO batches (id,name,description,status,created) VALUES (?,?,?,'pending',?)",
                  (bid, name, description, datetime.now().isoformat()))
        conn.commit(); conn.close(); return bid

    def add_job(self, batch_id, job_type, payload):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT INTO jobs (batch_id,job_type,payload,status,created) VALUES (?,?,?,'pending',?)",
                  (batch_id, job_type, json.dumps(payload), datetime.now().isoformat()))
        jid = c.lastrowid
        c.execute("UPDATE batches SET total_jobs=total_jobs+1 WHERE id=?", (batch_id,))
        conn.commit(); conn.close(); return jid

    def add_youtube_playlist(self, urls, batch_name=None):
        name = batch_name or f"YouTube Batch {datetime.now().strftime('%m/%d %H:%M')}"
        bid = self.create_batch(name, f"{len(urls)} videos")
        for url in urls:
            self.add_job(bid, "youtube_to_pdf", {"url": url})
        return bid

    def add_channel_batch(self, query, max_videos=10):
        bid = self.create_batch(f"Channel: {query}", f"Auto-scrape {max_videos} videos")
        self.add_job(bid, "channel_discovery", {"query": query, "max_videos": max_videos})
        return bid

    def get_next_job(self):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,batch_id,job_type,payload FROM jobs WHERE status='pending' ORDER BY id ASC LIMIT 1")
        row = c.fetchone(); conn.close()
        if row: return {"id":row[0],"batch_id":row[1],"job_type":row[2],"payload":json.loads(row[3])}
        return None

    def start_job(self, jid):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE jobs SET status='running',started=? WHERE id=?", (datetime.now().isoformat(), jid))
        conn.commit(); conn.close()

    def complete_job(self, jid, result, output_file=""):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE jobs SET status='done',result=?,output_file=?,completed=? WHERE id=?",
                  (result[:1000], output_file, datetime.now().isoformat(), jid))
        c.execute("SELECT batch_id FROM jobs WHERE id=?", (jid,))
        row = c.fetchone()
        if row:
            c.execute("UPDATE batches SET done_jobs=done_jobs+1 WHERE id=?", (row[0],))
            c.execute("SELECT total_jobs,done_jobs FROM batches WHERE id=?", (row[0],))
            b = c.fetchone()
            if b and b[0]==b[1]:
                c.execute("UPDATE batches SET status='done',completed=? WHERE id=?",
                          (datetime.now().isoformat(), row[0]))
        conn.commit(); conn.close()

    def fail_job(self, jid, error):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE jobs SET status='failed',error=?,completed=? WHERE id=?",
                  (error[:500], datetime.now().isoformat(), jid))
        conn.commit(); conn.close()

    def retry_job(self, jid):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("UPDATE jobs SET status='pending',error='',started='',completed='' WHERE id=?", (jid,))
        conn.commit(); conn.close()

    def get_review_queue(self, limit=20):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,batch_id,job_type,payload,status,result,output_file,error,created,completed FROM jobs WHERE status IN ('done','failed') AND reviewed=0 ORDER BY id DESC LIMIT ?", (limit,))
        rows = c.fetchall(); conn.close()
        return [{"id":r[0],"batch_id":r[1],"job_type":r[2],"payload":json.loads(r[3]),
                 "status":r[4],"result":r[5],"output_file":r[6],"error":r[7],
                 "created":r[8],"completed":r[9]} for r in rows]

    def get_all_batches(self):
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT id,name,description,total_jobs,done_jobs,status,created,completed FROM batches ORDER BY rowid DESC LIMIT 20")
        rows = c.fetchall(); conn.close()
        return [{"id":r[0],"name":r[1],"description":r[2],"total":r[3],
                 "done":r[4],"status":r[5],"created":r[6],"completed":r[7]} for r in rows]

async def handle_youtube_to_pdf(payload, jid, manager):
    url = payload.get("url","")
    print(f">> JOB #{jid}: youtube_to_pdf -> {url}")
    try:
        from youtube_tools import handle_youtube_request
        transcript, mode = handle_youtube_request(f"summarize this: {url}")
        if not transcript: return None, f"No transcript for {url}"
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(OLLAMA_URL, json={"model":MODEL,"stream":False,
                "prompt":f"Summarize this YouTube video into a clear report with key points and insights:\n\n{transcript[:3000]}"})
            summary = r.json().get("response","").strip()
        from pdf_bot import create_youtube_pdf
        pdf = create_youtube_pdf(payload.get("title") or url[-20:], summary)
        return pdf, f"PDF created: {os.path.basename(pdf)}"
    except Exception as e:
        return None, f"Error: {e}"

async def handle_channel_discovery(payload, jid, manager):
    query = payload.get("query",""); max_v = payload.get("max_videos",10)
    bid = payload.get("batch_id","")
    try:
        from youtube_tools import handle_youtube_request
        result, _ = handle_youtube_request(f"find me videos about {query}")
        urls = list(set(re.findall(r'https://www\.youtube\.com/watch\?v=[\w-]+', result or "")))[:max_v]
        for url in urls:
            manager.add_job(bid, "youtube_to_pdf", {"url":url,"title":f"Video from {query}"})
        return None, f"Discovered {len(urls)} videos from '{query}'"
    except Exception as e:
        return None, f"Error: {e}"

async def handle_debate_to_pdf(payload, jid, manager):
    topic = payload.get("topic","")
    try:
        from bot_orchestrator import orchestrator
        from pdf_bot import create_debate_pdf
        result = await orchestrator.run_debate(topic)
        pdf = create_debate_pdf(result)
        return pdf, f"Debate PDF: {topic}"
    except Exception as e:
        return None, f"Error: {e}"

async def notify_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id":TELEGRAM_CHAT,"text":message,"parse_mode":"Markdown"})
    except Exception as e:
        print(f">> NOTIFY ERROR: {e}")

class AutonomousRunner:
    def __init__(self):
        self.manager = JobManager()
        self._notified = {}

    async def run(self):
        init_jobs_db()
        print(">> AUTONOMOUS RUNNER: Started")
        while True:
            try:
                job = self.manager.get_next_job()
                if not job:
                    await asyncio.sleep(10); continue
                jid = job["id"]; jtype = job["job_type"]
                payload = job["payload"]; payload["batch_id"] = job["batch_id"]
                print(f">> RUNNER: Job #{jid} ({jtype})")
                self.manager.start_job(jid)
                try:
                    if jtype == "youtube_to_pdf":
                        f, r = await handle_youtube_to_pdf(payload, jid, self.manager)
                    elif jtype == "channel_discovery":
                        f, r = await handle_channel_discovery(payload, jid, self.manager)
                    elif jtype == "debate_to_pdf":
                        f, r = await handle_debate_to_pdf(payload, jid, self.manager)
                    else:
                        f, r = "", f"Unknown job: {jtype}"
                    self.manager.complete_job(jid, r or "Done", f or "")
                    print(f">> RUNNER: #{jid} complete — {r[:60]}")
                except Exception as e:
                    self.manager.fail_job(jid, str(e))
                await self._check_batch_notify(job["batch_id"])
                await asyncio.sleep(3)
            except Exception as e:
                print(f">> RUNNER ERROR: {e}"); await asyncio.sleep(15)

    async def _check_batch_notify(self, bid):
        for b in self.manager.get_all_batches():
            if b["id"]==bid and b["status"]=="done" and bid not in self._notified:
                self._notified[bid] = True
                await notify_telegram(f"✅ *Batch Complete*\n*{b['name']}*\n{b['done']}/{b['total']} jobs done\nType `/review` to see results")

runner = AutonomousRunner()

def queue_youtube_playlist(text):
    urls = re.findall(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+', text)
    if not urls: return "No YouTube URLs found."
    bid = runner.manager.add_youtube_playlist(urls)
    return f"✅ Queued {len(urls)} videos — batch {bid}\nType `/review` when done."

def queue_channel(name, max_videos=10):
    bid = runner.manager.add_channel_batch(name, max_videos)
    return f"✅ Channel '{name}' queued — up to {max_videos} videos\nType `/review` to check."
