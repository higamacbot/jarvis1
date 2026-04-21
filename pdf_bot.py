"""
pdf_bot.py — HIGA HOUSE PDF Generator
Creates PDFs from debates, YouTube summaries, market reports, any text.
fpdf2 is already installed.
"""
import os
import time
from datetime import datetime

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def create_pdf_fpdf(title: str, content: str, filename: str = None) -> str:
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(0, 200, 150)
        pdf.cell(0, 12, "HIGA.HOUSE — JARVIS INTELLIGENCE REPORT", ln=True, align="C")
        pdf.set_font("Helvetica", size=9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 8, title)
        pdf.ln(4)
        pdf.set_draw_color(0, 200, 150)
        pdf.set_line_width(0.5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)
        pdf.set_font("Helvetica", size=10)
        pdf.set_text_color(30, 30, 30)
        clean = content.encode("latin-1", "replace").decode("latin-1")
        pdf.multi_cell(0, 6, clean)
        pdf.ln(8)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 5, "HIGA.HOUSE | Sovereign Intelligence Terminal", align="C")
        if not filename:
            filename = f"jarvis_report_{int(time.time())}.pdf"
        if not filename.endswith(".pdf"):
            filename += ".pdf"
        filepath = os.path.join(OUTPUT_DIR, filename)
        pdf.output(filepath)
        print(f">> PDF BOT: Created {filepath}")
        return filepath
    except Exception as e:
        print(f">> PDF BOT ERROR: {e}")
        filepath = os.path.join(OUTPUT_DIR, filename or f"report_{int(time.time())}.txt")
        with open(filepath.replace(".pdf",".txt"), "w") as f:
            f.write(f"{title}\n\n{content}")
        return filepath

def create_debate_pdf(debate_result: dict) -> str:
    topic = debate_result.get('topic', 'Unknown')
    content = f"""TOPIC: {topic}
DATE: {debate_result.get('created', datetime.now().isoformat())}

{'='*50}
CONSPIRACY SHAMAN
{'='*50}
{debate_result.get('shaman', '')}

{'='*50}
LIB MOM
{'='*50}
{debate_result.get('libmom', '')}

{'='*50}
MAGA DAD
{'='*50}
{debate_result.get('magadad', '')}

{'='*50}
AGREEMENTS
{'='*50}
{chr(10).join(f'- {a}' for a in debate_result.get('agreements', []))}

{'='*50}
DISAGREEMENTS
{'='*50}
{chr(10).join(f'- {d}' for d in debate_result.get('disagreements', []))}

{'='*50}
NARRATIVE
{'='*50}
{debate_result.get('narrative', '')}
"""
    return create_pdf_fpdf(f"DEBATE: {topic}", content, f"debate_{int(time.time())}.pdf")

def create_youtube_pdf(video_title: str, summary: str) -> str:
    return create_pdf_fpdf(f"VIDEO INTEL: {video_title}", summary, f"youtube_{int(time.time())}.pdf")

def create_market_pdf(market_data: dict, portfolio: dict) -> str:
    prices = "\n".join([f"- {k}: ${v['price']}" for k, v in market_data.items()])
    positions = "\n".join([f"- {p['symbol']}: ${p['value']} ({p['pl']})" for p in portfolio.get("positions", [])]) or "None"
    content = f"PRICES:\n{prices}\n\nEQUITY: ${portfolio.get('equity','N/A')}\n\nPOSITIONS:\n{positions}"
    return create_pdf_fpdf(f"MARKET REPORT {datetime.now().strftime('%Y-%m-%d')}", content, f"market_{int(time.time())}.pdf")

def list_pdfs() -> list:
    try:
        files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith((".pdf", ".txt"))]
        return sorted(files, reverse=True)[:20]
    except Exception:
        return []
