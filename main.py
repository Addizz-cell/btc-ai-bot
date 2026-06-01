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

LAST_SIGNAL_FILE = "last_signal.txt"

# =========================
# MEMORY
# =========================
def save_last_signal(signal):
    with open(LAST_SIGNAL_FILE, "w") as f:
        f.write(signal)

def load_last_signal():
    if not os.path.exists(LAST_SIGNAL_FILE):
        return None
    with open(LAST_SIGNAL_FILE, "r") as f:
        return f.read().strip()

# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
    )

# =========================
# ZONE DETECTION (1H)
# =========================
def find_zones(data):
    levels = []

    for i in range(10, len(data)-10):
        if data["High"].iloc[i] == data["High"].rolling(10).max().iloc[i]:
            levels.append(data["High"].iloc[i])

        if data["Low"].iloc[i] == data["Low"].rolling(10).min().iloc[i]:
            levels.append(data["Low"].iloc[i])

    levels = sorted(levels)

    zones = []
    for l in levels:
        if not zones:
            zones.append(l)
        elif abs(l - zones[-1]) / l < 0.01:
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
def bullish_engulfing(o, c, prev_o, prev_c):
    return c > o and c > prev_o and o < prev_c

def bearish_engulfing(o, c, prev_o, prev_c):
    return c < o and o > prev_c and c < prev_o

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
def confidence(trend, signal, pattern_strength):
    score = 50

    if trend == "UP" and signal == "BUY":
        score += 25
    if trend == "DOWN" and signal == "SELL":
        score += 25

    score += pattern_strength

    return min(score, 100)

# =========================
# MAIN BOT
# =========================
def run_bot():

    print("Running BTC analysis...")

    # =========================
    # DATA
    # =========================
    btc_1h = yf.download("BTC-USD", interval="1h", period="10d")
    btc_30m = yf.download("BTC-USD", interval="30m", period="3d")

    if btc_1h.empty or btc_30m.empty:
        print("No data")
        return

    btc_1h = btc_1h.dropna()
    btc_30m = btc_30m.dropna()

    zones = find_zones(btc_1h)
    trend = detect_trend(btc_1h)

    price = float(btc_30m["Close"].iloc[-1])

    # =========================
    # TELEGRAM: MARKET INFO
    # =========================
    send_telegram(f"""
📊 *DAILY MARKET SCAN*

Trend: {trend}
Zones: {zones}
Current Price: {price}
""")

    alerted = set()
    confirmed = set()

    # =========================
    # SCAN 30M
    # =========================
    for i in range(2, len(btc_30m)):

        o = btc_30m["Open"].iloc[i]
        c = btc_30m["Close"].iloc[i]
        h = btc_30m["High"].iloc[i]
        l = btc_30m["Low"].iloc[i]

        prev_o = btc_30m["Open"].iloc[i-1]
        prev_c = btc_30m["Close"].iloc[i-1]

        price = c

        for z in zones:

            # =========================
            # ZONE ALERT
            # =========================
            if abs(price - z) / price < 0.002:

                if z not in alerted:
                    send_telegram(f"📍 *ZONE ALERT*\nPrice: {price:.2f}\nZone: {z:.2f}")
                    alerted.add(z)

                # =========================
                # BUY CONFIRMATION
                # =========================
                if bullish_engulfing(o, c, prev_o, prev_c) or hammer(o, c, h, l):

                    score = confidence(trend, "BUY", 35)

                    if z not in confirmed:
                        send_telegram(f"""
🟢 *BUY SIGNAL*

Price: {price:.2f}
Zone: {z:.2f}
Trend: {trend}
Confidence: {score}%
""")
                        confirmed.add(z)

                # =========================
                # SELL CONFIRMATION
                # =========================
                if bearish_engulfing(o, c, prev_o, prev_c) or shooting_star(o, c, h, l):

                    score = confidence(trend, "SELL", 35)

                    if z not in confirmed:
                        send_telegram(f"""
🔴 *SELL SIGNAL*

Price: {price:.2f}
Zone: {z:.2f}
Trend: {trend}
Confidence: {score}%
""")
                        confirmed.add(z)

# =========================
# LOOP
# =========================
while True:
    try:
        run_bot()
    except Exception as e:
        print("Error:", e)

    time.sleep(3600)
