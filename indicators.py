import re
from typing import Optional
import pandas as pd
import yfinance as yf

INDICATOR_TRIGGERS = [
    "rsi", "overbought", "oversold", "moving average", "sma", "macd",
    "technical", "technicals", "technical analysis", "chart", "signal",
    "momentum", "trend", "crossover", "analyze", "analysis",
    "bullish", "bearish", "indicator", "volume",
]

NAME_TO_TICKER = {
    "nvidia": "NVDA", "apple": "AAPL", "tesla": "TSLA",
    "amazon": "AMZN", "google": "GOOGL", "microsoft": "MSFT",
    "meta": "META", "netflix": "NFLX", "amd": "AMD",
    "paypal": "PYPL", "vanguard": "VOO", "palantir": "PLTR",
}

def is_indicator_request(message: str) -> bool:
    msg = message.lower()
    return any(t in msg for t in INDICATOR_TRIGGERS)

def is_portfolio_scan(message: str) -> bool:
    msg = message.lower()
    return any(t in msg for t in ["all my positions","all positions","my portfolio","portfolio analysis","scan my positions","all stocks"])

def extract_ticker(message: str) -> Optional[str]:
    msg = message.lower()
    for name, ticker in NAME_TO_TICKER.items():
        if name in msg:
            return ticker
    match = re.search(r"\b([A-Z]{2,5})\b", message)
    if match:
        skip = {"RSI","SMA","THE","AND","FOR","BUY","SELL","GET","MACD"}
        if match.group(1) not in skip:
            return match.group(1)
    skip_words = {"rsi","sma","the","and","for","buy","sell","get","my","all","is","are","was","give","me","on","of","in","at","an","a","to","do","it","its","be","by","or","if","what","how","can","you","your","this","that","with","macd"}
    words = re.findall(r"\b([a-zA-Z]{2,5})\b", msg)
    for word in words:
        if word.lower() not in skip_words:
            return word.upper()
    return None

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 1)

def calculate_macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return {"macd": round(float(macd.iloc[-1]),3), "signal": round(float(signal.iloc[-1]),3), "histogram": round(float(histogram.iloc[-1]),3)}

def calculate_volume_signal(df):
    if "Volume" not in df.columns or len(df) < 5: return "unknown"
    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    curr_vol = df["Volume"].iloc[-1]
    if avg_vol == 0: return "unknown"
    ratio = curr_vol / avg_vol
    if ratio > 2.0: return f"HIGH ({ratio:.1f}x avg) ⚡"
    elif ratio > 1.3: return f"above avg ({ratio:.1f}x)"
    elif ratio < 0.5: return f"LOW ({ratio:.1f}x avg)"
    return f"normal ({ratio:.1f}x avg)"

def interpret_rsi(rsi):
    if rsi >= 75: return f"{rsi} — Strongly overbought 🔴"
    elif rsi >= 70: return f"{rsi} — Overbought ⚠️"
    elif rsi <= 25: return f"{rsi} — Strongly oversold 🟢"
    elif rsi <= 30: return f"{rsi} — Oversold 👀"
    elif rsi >= 55: return f"{rsi} — Bullish momentum"
    elif rsi <= 45: return f"{rsi} — Bearish momentum"
    return f"{rsi} — Neutral"

def interpret_sma(sma9, sma21, price):
    if sma9 > sma21:
        pct = ((sma9-sma21)/sma21)*100
        return f"SMA9 ${sma9:.2f} > SMA21 ${sma21:.2f} — Bullish ({pct:.1f}% spread) 📈"
    else:
        pct = ((sma21-sma9)/sma21)*100
        return f"SMA9 ${sma9:.2f} < SMA21 ${sma21:.2f} — Bearish ({pct:.1f}% spread) 📉"

def interpret_macd(macd_data):
    macd = macd_data["macd"]
    sig = macd_data["signal"]
    hist = macd_data["histogram"]
    if macd > sig and hist > 0: return f"MACD {macd:.3f} > Signal {sig:.3f} — Bullish 📈"
    elif macd < sig and hist < 0: return f"MACD {macd:.3f} < Signal {sig:.3f} — Bearish 📉"
    return f"MACD {macd:.3f} / Signal {sig:.3f} — Neutral"

def generate_verdict(rsi, sma9, sma21, macd_data):
    bull = 0
    bear = 0
    if rsi <= 30: bull += 2
    elif rsi <= 45: bull += 1
    elif rsi >= 70: bear += 2
    elif rsi >= 55: bear += 1
    if sma9 > sma21: bull += 1
    else: bear += 1
    if macd_data["histogram"] > 0: bull += 1
    else: bear += 1
    total = bull + bear
    if total == 0: return "⚪ NEUTRAL — Insufficient data."
    pct = bull / total
    if pct >= 0.75: return "🟢 BULLISH — Multiple indicators aligned upward."
    elif pct >= 0.6: return "🟡 LEANING BULLISH — More signals positive than negative."
    elif pct <= 0.25: return "🔴 BEARISH — Multiple indicators aligned downward."
    elif pct <= 0.4: return "🟡 LEANING BEARISH — More signals negative than positive."
    return "⚪ NEUTRAL — Mixed signals."

def analyze_ticker(symbol, period="3mo"):
    symbol = symbol.upper().strip()
    try:
        df = yf.Ticker(symbol).history(period=period)
        if df.empty or len(df) < 30:
            return f"Insufficient data for {symbol}, sir."
        close = df["Close"]
        price = round(float(close.iloc[-1]), 2)
        rsi = calculate_rsi(close)
        sma9 = round(float(close.rolling(9).mean().iloc[-1]), 2)
        sma21 = round(float(close.rolling(21).mean().iloc[-1]), 2)
        sma50 = round(float(close.rolling(50).mean().iloc[-1]), 2) if len(df) >= 50 else None
        macd_data = calculate_macd(close)
        vol_sig = calculate_volume_signal(df)
        recent_sma9 = close.rolling(9).mean().tail(3)
        recent_sma21 = close.rolling(21).mean().tail(3)
        crossover = ""
        if len(recent_sma9) >= 2:
            if recent_sma9.iloc[-2] <= recent_sma21.iloc[-2] and recent_sma9.iloc[-1] > recent_sma21.iloc[-1]:
                crossover = " ⚡ GOLDEN CROSS (bullish crossover)"
            elif recent_sma9.iloc[-2] >= recent_sma21.iloc[-2] and recent_sma9.iloc[-1] < recent_sma21.iloc[-1]:
                crossover = " ⚡ DEATH CROSS (bearish crossover)"
        verdict = generate_verdict(rsi, sma9, sma21, macd_data)
        lines = [
            f"📊 *{symbol} TECHNICAL ANALYSIS*",
            f"Price: `${price}`",
            f"",
            f"*RSI(14):* {interpret_rsi(rsi)}",
            f"*SMA:* {interpret_sma(sma9, sma21, price)}{crossover}",
        ]
        if sma50:
            ab = "above" if price > sma50 else "below"
            lines.append(f"*SMA50:* `${sma50}` — Price is {ab} 50-day average")
        lines += [
            f"*MACD:* {interpret_macd(macd_data)}",
            f"*Volume:* {vol_sig}",
            f"",
            f"*Verdict:* {verdict}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Could not analyze {symbol}, sir. Error: {e}"

def analyze_portfolio(symbols):
    if not symbols: return "No symbols provided, sir."
    lines = ["📊 *PORTFOLIO TECHNICAL SCAN*", ""]
    alerts = []
    for symbol in symbols:
        try:
            df = yf.Ticker(symbol).history(period="1mo")
            if df.empty or len(df) < 15:
                lines.append(f"• {symbol}: insufficient data")
                continue
            close = df["Close"]
            rsi = calculate_rsi(close)
            sma9 = float(close.rolling(9).mean().iloc[-1])
            sma21 = float(close.rolling(21).mean().iloc[-1])
            trend = "📈" if sma9 > sma21 else "📉"
            price = round(float(close.iloc[-1]), 2)
            rsi_label = ""
            if rsi >= 70:
                rsi_label = " ⚠️ OVERBOUGHT"
                alerts.append(f"{symbol} overbought (RSI {rsi})")
            elif rsi <= 30:
                rsi_label = " 👀 OVERSOLD"
                alerts.append(f"{symbol} oversold (RSI {rsi})")
            lines.append(f"• *{symbol}* `${price}` | RSI: `{rsi}`{rsi_label} | {trend}")
        except Exception as e:
            lines.append(f"• {symbol}: error — {e}")
    if alerts:
        lines.append(f"")
        lines.append(f"⚠️ *ALERTS:* {chr(10).join(alerts)}")
    else:
        lines.append(f"")
        lines.append(f"✅ No extreme RSI readings detected.")
    return "\n".join(lines)

def quick_rsi_check(symbols):
    alerts = []
    for symbol in symbols:
        try:
            df = yf.Ticker(symbol).history(period="1mo")
            if df.empty or len(df) < 15: continue
            rsi = calculate_rsi(df["Close"])
            if rsi >= 70: alerts.append(f"⚠️ {symbol} RSI {rsi} — overbought")
            elif rsi <= 30: alerts.append(f"👀 {symbol} RSI {rsi} — oversold")
        except: continue
    return alerts
