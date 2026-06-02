import requests
import pandas as pd
import yfinance as yf
import os
import time
import json
from datetime import datetime

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "state.json"

ZONE_THRESHOLD = 0.0018  # 0.18%

# =========================
# TELEGRAM
# =========================
def send_telegram(message):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

# =========================
# STATE HANDLING
# =========================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {
            "date": "",
            "zones": [],
            "alerted": [],
            "traded": [],
            "breakout_wait": {}
        }

    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def new_day(state):
    today = datetime.utcnow().strftime("%Y-%m-%d")

    if state["date"] != today:
        state["date"] = today
        state["zones"] = []
        state["alerted"] = []
        state["traded"] = []
        state["breakout_wait"] = {}
        return True

    return False

# =========================
# DATA CLEAN
# =========================
def clean(df):
    if df is None or df.empty:
        return None

    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.dropna()

    return df

# =========================
# ZONE GENERATION (1H)
# =========================
def find_zones(df):
    levels = []

    for i in range(10, len(df) - 10):
        if df["High"].iloc[i] == df["High"].rolling(10).max().iloc[i]:
            levels.append(df["High"].iloc[i])

        if df["Low"].iloc[i] == df["Low"].rolling(10).min().iloc[i]:
            levels.append(df["Low"].iloc[i])

    levels = sorted(levels)

    zones = []
    for l in levels:
        if not zones:
            zones.append(l)
        else:
            if abs(l - zones[-1]) / l < ZONE_THRESHOLD:
                zones[-1] = (zones[-1] + l) / 2
            else:
                zones.append(l)

    return zones[:3]

# =========================
# TREND
# =========================
def trend(df):
    ma = df["Close"].rolling(50).mean().iloc[-1]
    price = df["Close"].iloc[-1]

    if price > ma:
        return "UP"
    elif price < ma:
        return "DOWN"
    return "RANGE"

# =========================
# CANDLE PATTERNS
# =========================
def bullish_engulf(o, c, po, pc):
    return c > o and c > po and o < pc

def bearish_engulf(o, c, po, pc):
    return c < o and o < po and c < pc

def hammer(o, c, h, l):
    body = abs(c - o)
    return (min(o, c) - l) > 2 * body

def shooting_star(o, c, h, l):
    body = abs(c - o)
    return (h - max(o, c)) > 2 * body

# =========================
# CONFIDENCE
# =========================
def score(trend_dir, signal, pattern_bonus):
    base = 50

    if trend_dir == "UP" and signal == "BUY":
        base += 25
    if trend_dir == "DOWN" and signal == "SELL":
        base += 25

    base += pattern_bonus
    return min(base, 100)

# =========================
# DAILY SCAN (11 PM LOGIC)
# =========================
def daily_scan(state, btc_1h):
    state["zones"] = find_zones(btc_1h)
    t = trend(btc_1h)

    zones_clean = [round(float(z), 2) for z in state["zones"]]

    send_telegram(
        f"📊 DAILY MARKET SCAN\n\n"
        f"Trend: {t}\n"
        f"Zones:\n{zones_clean}\n"
        f"\nMonitoring market..."
    )

# =========================
# MAIN BOT
# =========================
def run_bot():
    state = load_state()

    btc_1h = clean(yf.download("BTC-USD", interval="1h", period="10d"))
    btc_30m = clean(yf.download("BTC-USD", interval="30m", period="3d"))

    if btc_1h is None or btc_30m is None:
        return

    if len(btc_1h) < 100 or len(btc_30m) < 50:
        return

    # NEW DAY RESET
    if new_day(state):
        daily_scan(state, btc_1h)
        save_state(state)

    current_price = float(btc_30m["Close"].iloc[-1])

    t = trend(btc_1h)

    latest = btc_30m.iloc[-1]
    prev = btc_30m.iloc[-2]

    o, c, h, l = latest["Open"], latest["Close"], latest["High"], latest["Low"]
    po, pc = prev["Open"], prev["Close"]

    # =========================
    # LOOP ZONES
    # =========================
    for z in state["zones"]:

        z = float(z)

        # =========================
        # ZONE ENTRY CHECK
        # =========================
        if abs(current_price - z) / current_price <= ZONE_THRESHOLD:

            if z not in state["alerted"]:
                send_telegram(
                    f"📍 ZONE ALERT\n\n"
                    f"Price: {current_price:.2f}\n"
                    f"Zone: {z:.2f}\n"
                    f"Waiting for 30m confirmation..."
                )
                state["alerted"].append(z)

            # =========================
            # CONFIRMATION
            # =========================
            if bullish_engulf(o, c, po, pc) or hammer(o, c, h, l):

                if z not in state["traded"]:
                    s = score(t, "BUY", 35)

                    send_telegram(
                        f"🟢 BUY SIGNAL\n\n"
                        f"Zone: {z:.2f}\n"
                        f"Price: {current_price:.2f}\n"
                        f"Confidence: {s}%"
                    )

                    state["traded"].append(z)

            if bearish_engulf(o, c, po, pc) or shooting_star(o, c, h, l):

                if z not in state["traded"]:
                    s = score(t, "SELL", 35)

                    send_telegram(
                        f"🔴 SELL SIGNAL\n\n"
                        f"Zone: {z:.2f}\n"
                        f"Price: {current_price:.2f}\n"
                        f"Confidence: {s}%"
                    )

                    state["traded"].append(z)

    save_state(state)

# =========================
# LOOP
# =========================
while True:
    try:
        run_bot()
    except Exception as e:
        print("Error:", e)

    time.sleep(300)  # 5 minutes