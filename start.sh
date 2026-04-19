#!/bin/bash
cd /Users/higabot1/jarvis1-1
pkill -f "main.py" 2>/dev/null
pkill -f "briefing_scheduler.py" 2>/dev/null
sleep 1
nohup python3 main.py > jarvis.log 2>&1 &
nohup python3 briefing_scheduler.py > briefing.log 2>&1 &
echo "✅ HIGA HOUSE online"
echo "🌐 UI: http://localhost:8000"
echo "📋 Logs: tail -f jarvis.log | tail -f briefing.log"
