import requests
import os
import time
import json
import feedparser
from datetime import datetime, timezone

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "macro_state.json"

# =========================
# RSS SOURCES (FREE)
# =========================
RSS_FEEDS = [
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://finance.yahoo.com/news/rssindex",
]

# =========================
# TELEGRAM
# =========================
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print("Telegram error:", e)

# =========================
# STATE
# =========================
def load():
    if not os.path.exists(STATE_FILE):
        return {"seen": []}
    return json.load(open(STATE_FILE))

def save(s):
    json.dump(s, open(STATE_FILE, "w"))

# =========================
# EVENT WEIGHTS (INSTITUTIONAL)
# =========================
WEIGHTS = {
    "cpi": 5.0,
    "inflation": 5.0,
    "interest rate": 5.0,
    "fomc": 5.0,
    "fed": 4.0,
    "nfp": 4.5,
    "jobs": 4.0,
    "gdp": 4.0,
    "unemployment": 3.5,
    "dollar": 3.0,
}

BULLISH = ["higher", "rise", "strong", "hawkish", "beats", "increase"]
BEARISH = ["lower", "fall", "weak", "dovish", "miss", "cut"]

# =========================
# TIME DECAY FUNCTION
# =========================
def decay(hours):
    if hours < 1:
        return 1.0
    if hours < 3:
        return 0.8
    if hours < 6:
        return 0.6
    if hours < 12:
        return 0.4
    return 0.2

# =========================
# USD IMPACT ENGINE
# =========================
def analyze(entry):
    text = entry.title.lower()

    weight = 1.0

    # event weighting
    for k, w in WEIGHTS.items():
        if k in text:
            weight += w

    score = 50

    for w in BULLISH:
        if w in text:
            score += 8 * weight

    for w in BEARISH:
        if w in text:
            score -= 8 * weight

    # normalize
    score = max(0, min(100, score))

    if score >= 65:
        bias = "🟢 USD STRONG"
    elif score <= 35:
        bias = "🔴 USD WEAK"
    else:
        bias = "⚪ USD NEUTRAL"

    return bias, score

# =========================
# FETCH NEWS
# =========================
def fetch():
    items = []
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for e in feed.entries[:10]:
            items.append(e)
    return items

# =========================
# ASSET IMPACT MODEL
# =========================
def asset_bias(usdx_score, asset):
    if asset == "BTC":
        shift = (usdx_score - 50) * 0.4
    elif asset == "XAU":
        shift = (usdx_score - 50) * 0.8
    elif asset == "EURUSD":
        shift = (usdx_score - 50) * 1.2
    else:
        shift = 0

    final = 50 + shift

    if final > 60:
        return "📉 SELL PRESSURE"
    elif final < 40:
        return "📈 BUY PRESSURE"
    return "⚪ NEUTRAL"

# =========================
# MAIN ENGINE
# =========================
def run():
    state = load()
    seen = set(state["seen"])

    news = fetch()

    usd_scores = []

    for n in news:
        if n.title in seen:
            continue

        bias, score = analyze(n)
        usd_scores.append(score)

        seen.add(n.title)

    if not usd_scores:
        return

    # USD Strength Index
    usdx = sum(usd_scores) / len(usd_scores)

    btc_bias = asset_bias(usdx, "BTC")
    xau_bias = asset_bias(usdx, "XAU")
    eur_bias = asset_bias(usdx, "EURUSD")

    msg = f"""
📊 MACRO ENGINE UPDATE

USD Strength Index: {usdx:.2f} / 100

Assets:
BTC → {btc_bias}
XAUUSD → {xau_bias}
EURUSD → {eur_bias}

Time:
{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
"""

    # only send meaningful moves
    if usdx > 60 or usdx < 40:
        send(msg)

    state["seen"] = list(seen)[-300:]
    save(state)

# =========================
# LOOP
# =========================
while True:
    try:
        run()
    except Exception as e:
        print("Error:", e)

    time.sleep(300)