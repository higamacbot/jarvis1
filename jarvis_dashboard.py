import os, datetime, pytz, yfinance as yf
from flask import Flask, jsonify, render_template_string
from flask_cors import CORS 
from alpaca.trading.client import TradingClient

# --- CONFIGURATION ---
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "AAPL", "TSLA", "NVDA", "VOO", "CL=F"]

app = Flask(__name__)
CORS(app) 
client = TradingClient(ALPACA_KEY, ALPACA_SECRET, paper=True)
CST = pytz.timezone("America/Chicago")

def get_portfolio_data():
    try:
        acct = client.get_account()
        pos = client.get_all_positions()
        return {
            "equity": float(acct.equity),
            "day_pl": float(acct.equity) - float(acct.last_equity),
            "pos_count": len(pos),
            "positions": [{"symbol": p.symbol, "val": float(p.market_value), "pl": float(p.unrealized_pl)} for p in pos]
        }
    except:
        return {"equity": 0.0, "day_pl": 0.0, "positions": []}

def get_market_data():
    results = []
    for t in TICKERS:
        try:
            d = yf.Ticker(t).history(period="1d")
            if d.empty: continue
            price = d['Close'].iloc[-1]
            change = ((price - d['Open'].iloc[0]) / d['Open'].iloc[0]) * 100
            results.append({"symbol": t, "price": round(price, 2), "change": round(change, 2)})
        except: continue
    return results

@app.route('/api/data')
def api_data():
    return jsonify({
        "portfolio": get_portfolio_data(),
        "markets": get_market_data(),
        "news": "System integrated. Monitoring global markets.",
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
