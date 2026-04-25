#!/usr/bin/env python3
"""
HIGABOT Trading Dashboard Server
Combines Alpaca and Kraken data for unified trading view
"""

import os
import asyncio
import subprocess
import json
from datetime import datetime
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
from alpaca.trading.client import TradingClient

app = FastAPI(title="HIGABOT Trading Dashboard")

# Load API keys
def load_keys():
    """Load API keys from environment or keys.txt file"""
    keys = {}
    
    # Try environment variables first
    keys['ALPACA_KEY'] = os.getenv("ALPACA_KEY")
    keys['ALPACA_SECRET'] = os.getenv("ALPACA_SECRET")
    keys['KRAKEN_KEY'] = os.getenv("KRAKEN_KEY")
    keys['KRAKEN_SECRET'] = os.getenv("KRAKEN_SECRET")
    
    # Fall back to keys.txt file
    if not all([keys['KRAKEN_KEY'], keys['KRAKEN_SECRET']]):
        try:
            with open("keys.txt", "r") as f:
                for line in f:
                    if line.strip() and not line.startswith("#"):
                        key, value = line.strip().split("=", 1)
                        if key == "KRAKEN_KEY":
                            keys['KRAKEN_KEY'] = value
                        elif key == "KRAKEN_SECRET":
                            keys['KRAKEN_SECRET'] = value
        except FileNotFoundError:
            print("Warning: keys.txt not found")
    
    return keys

keys = load_keys()

# Alpaca setup
if keys['ALPACA_KEY'] and keys['ALPACA_SECRET']:
    alpaca_client = TradingClient(keys['ALPACA_KEY'], keys['ALPACA_SECRET'], paper=True)
else:
    print("Warning: Alpaca keys not found")
    alpaca_client = None

async def get_alpaca_data():
    """Fetch Alpaca portfolio data"""
    if not alpaca_client:
        return {"equity": 0, "day_pl": 0, "positions": [], "error": "Alpaca keys not configured"}
    
    try:
        account = alpaca_client.get_account()
        positions = alpaca_client.get_all_positions()
        
        return {
            "equity": float(account.equity),
            "day_pl": float(account.equity) - float(account.last_equity) if account.last_equity else 0,
            "buying_power": float(account.buying_power),
            "positions": [
                {
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl)
                }
                for pos in positions
            ]
        }
    except Exception as e:
        print(f"Alpaca error: {e}")
        return {"equity": 0, "day_pl": 0, "positions": [], "error": str(e)}

async def get_kraken_data():
    """Fetch Kraken paper trading data via CLI"""
    try:
        # Get portfolio status
        result = subprocess.run(
            ["kraken", "paper", "status", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return {"equity": 0, "positions": []}
        
        data = json.loads(result.stdout)
        
        # Get balance for positions
        balance_result = subprocess.run(
            ["kraken", "paper", "balance", "-o", "json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        positions = []
        if balance_result.returncode == 0:
            balance_data = json.loads(balance_result.stdout)
            for asset, info in balance_data.items():
                if asset != "USD" and float(info.get("available", 0)) > 0:
                    positions.append({
                        "symbol": asset,
                        "volume": float(info.get("available", 0)),
                        "unrealized_pl": 0  # Kraken paper doesn't track P&L the same way
                    })
        
        return {
            "equity": data.get("current_value", 0),
            "unrealized_pl": data.get("unrealized_pl", 0),
            "positions": positions
        }
    except Exception as e:
        print(f"Kraken error: {e}")
        return {"equity": 0, "positions": []}

async def get_crypto_prices():
    """Fetch live crypto prices"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,dogecoin&vs_currencies=usd"
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "BTC": data["bitcoin"]["usd"],
                    "ETH": data["ethereum"]["usd"],
                    "DOGE": data["dogecoin"]["usd"],
                    "timestamp": datetime.now().isoformat()
                }
    except Exception as e:
        print(f"Price error: {e}")
    return {}

@app.get("/api/alpaca")
async def alpaca_endpoint():
    """Alpaca portfolio data endpoint"""
    data = await get_alpaca_data()
    return data

@app.get("/api/kraken")
async def kraken_endpoint():
    """Kraken portfolio data endpoint"""
    data = await get_kraken_data()
    return data

@app.get("/api/prices")
async def prices_endpoint():
    """Live crypto prices endpoint"""
    data = await get_crypto_prices()
    return data

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML"""
    try:
        with open("index.html", "r") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)

if __name__ == "__main__":
    import uvicorn
    
    print("ð HIGABOT Trading Dashboard Server")
    print("=" * 50)
    print("Starting server on http://localhost:3000")
    print("Combined Alpaca + Kraken trading view")
    print("Auto-refresh every 30 seconds")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=3000)
