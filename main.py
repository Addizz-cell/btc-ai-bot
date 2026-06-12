import requests
import time
import os
import json
import feedparser
from datetime import datetime

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "news_state.json"

# =========================
# SOURCES (FREE RSS)
# =========================
RSS_FEEDS = [
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://finance.yahoo.com/news/rssindex",
]

# =========================
# TELEGRAM
# =========================
def send_telegram(msg):
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
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"seen": []}

    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# =========================
# USD KEYWORDS ENGINE
# =========================
BULLISH = [
    "inflation rises", "cpi higher", "strong jobs", "nfp beats",
    "interest rate hike", "hawkish", "strong dollar", "fomc raises"
]

BEARISH = [
    "inflation falls", "cpi lower", "weak jobs", "nfp misses",
    "rate cut", "dovish", "recession", "usd weak"
]

HIGH_IMPACT = [
    "cpi", "nfp", "fomc", "interest rate", "fed", "unemployment", "gdp"
]

# =========================
# ANALYZE NEWS
# =========================
def analyze(text):

    t = text.lower()

    score = 50

    # direction
    for w in BULLISH:
        if w in t:
            score += 10

    for w in BEARISH:
        if w in t:
            score -= 10

    # high impact boost
    for w in HIGH_IMPACT:
        if w in t:
            score += 5

    if score >= 65:
        bias = "🟢 BULLISH USD"
    elif score <= 35:
        bias = "🔴 BEARISH USD"
    else:
        bias = "⚪ NEUTRAL USD"

    confidence = min(100, abs(score - 50) * 2 + 50)

    return bias, confidence

# =========================
# FETCH NEWS
# =========================
def fetch_news():
    news_items = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for entry in feed.entries[:10]:
            news_items.append({
                "title": entry.title,
                "link": entry.link
            })

    return news_items

# =========================
# MAIN LOOP
# =========================
def run():

    state = load_state()
    seen = set(state["seen"])

    news = fetch_news()

    for item in news:

        title = item["title"]

        if title in seen:
            continue

        bias, confidence = analyze(title)

        # only send strong signals
        if confidence < 60:
            continue

        msg = f"""
🚨 USD NEWS ALERT

Headline:
{title}

Bias:
{bias}

Confidence:
{confidence}%

Time:
{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
"""

        send_telegram(msg)

        seen.add(title)

    state["seen"] = list(seen)[-200:]
    save_state(state)

# =========================
# LOOP
# =========================
while True:
    try:
        run()
    except Exception as e:
        print("Error:", e)

    time.sleep(300)