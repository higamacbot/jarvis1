#!/bin/bash
echo "Starting JARVIS..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "Warning: Ollama is not responding on localhost:11434"
fi
cd ~/jarvis
source venv/bin/activate
python server.py
