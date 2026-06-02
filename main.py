import requests
import pandas as pd
import yfinance as yf
import os
import time

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

# =========================
# SAFE DATA CLEANER
# =========================
def clean_data(df):
    if df is None or len(df) == 0:
        return None

    # remove multi-index issue from yfinance
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    df = df.dropna()

    # ensure required columns exist
    required = ["Open", "High", "Low", "Close"]
    for col in required:
        if col not in df.columns:
            return None

    return df

# =========================
# ZONES (1H STRUCTURE)
# =========================
def find_zones(data):
    levels = []

    for i in range(10, len(data) - 10):

        if data["High"].iloc[i] == data["High"].rolling(10).max().iloc[i]:
            levels.append(data["High"].iloc[i])

        if data["Low"].iloc[i] == data["Low"].rolling(10).min().iloc[i]:
            levels.append(data["Low"].iloc[i])

    levels = sorted(levels)

    zones = []
    for l in levels:
        if not zones:
            zones.append(l)
        else:
            if abs(l - zones[-1]) / l < 0.01:
                zones[-1] = (zones[-1] + l) / 2
            else:
                zones.append(l)

    return zones[:3]

# =========================
# TREND DETECTION
# =========================
def detect_trend(data):
    mean = data["Close"].rolling(50).mean().iloc[-1]
    price = data["Close"].iloc[-1]

    if price > mean:
        return "UP"
    elif price < mean:
        return "DOWN"
    return "RANGE"

# =========================
# 30M CANDLE PATTERNS
# =========================
def bullish_engulfing(o, c, po, pc):
    return c > o and c > po and o < pc

def bearish_engulfing(o, c, po, pc):
    return c < o and o > pc and c < po

def hammer(o, c, h, l):
    body = abs(c - o)
    lower = min(o, c) - l
    return lower > 2 * body

def shooting_star(o, c, h, l):
    body = abs(c - o)
    upper = h - max(o, c)
    return upper > 2 * body

# =========================
# CONFIDENCE SCORE
# =========================
def confidence(trend, signal, pattern_score):
    score = 50

    if trend == "UP" and signal == "BUY":
        score += 25
    if trend == "DOWN" and signal == "SELL":
        score += 25

    score += pattern_score

    return min(score, 100)

# =========================
# MAIN BOT LOGIC
# =========================
def run_bot():

    print("Running BTC analysis...")

    # =========================
    # DATA DOWNLOAD
    # =========================
    btc_1h = yf.download("BTC-USD", interval="1h", period="10d")
    btc_30m = yf.download("BTC-USD", interval="30m", period="3d")

    btc_1h = clean_data(btc_1h)
    btc_30m = clean_data(btc_30m)

    if btc_1h is None or btc_30m is None:
        print("Invalid data received")
        return

    if len(btc_1h) < 100 or len(btc_30m) < 50:
        print("Not enough data")
        return

    # =========================
    # ANALYSIS
    # =========================
    zones = find_zones(btc_1h)
    trend = detect_trend(btc_1h)

    price = float(btc_30m["Close"].iloc[-1])

    send_telegram(
        f"📊 *MARKET SCAN*\n\n"
        f"Trend: {trend}\n"
        f"Zones: {zones}\n"
        f"Price: {price}"
    )

    alerted = set()
    confirmed = set()

    # =========================
    # 30M SCAN
    # =========================
    for i in range(2, len(btc_30m)):

        o = btc_30m["Open"].iloc[i]
        c = btc_30m["Close"].iloc[i]
        h = btc_30m["High"].iloc[i]
        l = btc_30m["Low"].iloc[i]

        po = btc_30m["Open"].iloc[i - 1]
        pc = btc_30m["Close"].iloc[i - 1]

        price = c

        for z in zones:

            # =========================
            # ZONE ALERT
            # =========================
            if abs(price - z) / price < 0.002:

                if z not in alerted:
                    send_telegram(
                        f"📍 *ZONE ALERT*\n"
                        f"Price: {price:.2f}\n"
                        f"Zone: {z:.2f}"
                    )
                    alerted.add(z)

                # =========================
                # BUY
                # =========================
                if bullish_engulfing(o, c, po, pc) or hammer(o, c, h, l):

                    score = confidence(trend, "BUY", 35)

                    if z not in confirmed:
                        send_telegram(
                            f"🟢 *BUY SIGNAL*\n\n"
                            f"Price: {price:.2f}\n"
                            f"Zone: {z:.2f}\n"
                            f"Trend: {trend}\n"
                            f"Confidence: {score}%"
                        )
                        confirmed.add(z)

                # =========================
                # SELL
                # =========================
                if bearish_engulfing(o, c, po, pc) or shooting_star(o, c, h, l):

                    score = confidence(trend, "SELL", 35)

                    if z not in confirmed:
                        send_telegram(
                            f"🔴 *SELL SIGNAL*\n\n"
                            f"Price: {price:.2f}\n"
                            f"Zone: {z:.2f}\n"
                            f"Trend: {trend}\n"
                            f"Confidence: {score}%"
                        )
                        confirmed.add(z)

# =========================
# LOOP (SAFE)
# =========================
while True:
    try:
        run_bot()
    except Exception as e:
        print("Error:", e)

    time.sleep(3600)
