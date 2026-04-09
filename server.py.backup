import os, datetime, threading, asyncio, psutil, subprocess, requests, uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pyttsx3

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- NON-BLOCKING VOICE ---
def speak_in_background(text):
    def _do_speak():
        try:
            engine = pyttsx3.init()
            # Set voice to Daniel if available
            voices = engine.getProperty('voices')
            for v in voices:
                if "Daniel" in v.name:
                    engine.setProperty('voice', v.id)
                    break
            engine.say(text)
            engine.runAndWait()
            # Stop engine properly to release resources
            engine.stop()
        except: pass
    
    threading.Thread(target=_do_speak, daemon=True).start()

# --- ROUTES ---
@app.get("/")
async def read_index(): return FileResponse("static/index.html")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            question = data.get("message", "").lower()
            
            # Import logic from the unified script
            from jarvis_unified import ask_jarvis_logic
            
            # 1. Get the Answer
            res = await asyncio.to_thread(ask_jarvis_logic, question)
            
            # 2. SEND TO SAFARI IMMEDIATELY (Fixes the "Processing" hang)
            await websocket.send_json({"type": "answer", "text": res, "mode": "chat"})
            
            # 3. SPEAK IN BACKGROUND
            speak_in_background(res)
            
    except WebSocketDisconnect: pass

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")
