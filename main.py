import requests
import os
import time
import json
import feedparser
import traceback
from datetime import datetime, timezone

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

STATE_FILE = "macro_state.json"

# =========================
# RSS SOURCES
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
        print("Telegram Error:", e)

# =========================
# STATE
# =========================
def load():
    if not os.path.exists(STATE_FILE):
        return {"seen": []}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# =========================
# EVENT WEIGHTS (UPGRADED)
# =========================
WEIGHTS = {
    "cpi": 10,
    "inflation": 10,
    "interest rate": 15,
    "fomc": 20,
    "fed": 12,
    "nfp": 18,
    "jobs": 10,
    "gdp": 10,
    "unemployment": 8,
    "dollar": 6,
    "powell": 12
}

BULLISH = ["higher", "rise", "strong", "hawkish", "beats", "increase", "tighten"]
BEARISH = ["lower", "fall", "weak", "dovish", "miss", "cut", "slow"]

# =========================
# EVENT DETECTOR (NEW)
# =========================
def detect_event(text):

    events = []

    for k in WEIGHTS.keys():
        if k in text:
            events.append(k.upper())

    return events

# =========================
# ANALYZE
# =========================
def analyze(entry):

    text = entry.title.lower()

    weight = 1.0
    events = detect_event(text)

    for keyword, value in WEIGHTS.items():
        if keyword in text:
            weight += value

    score = 50

    for w in BULLISH:
        if w in text:
            score += 7 * weight

    for w in BEARISH:
        if w in text:
            score -= 7 * weight

    score = max(0, min(100, score))

    if score >= 65:
        bias = "🟢 USD STRONG"
    elif score <= 35:
        bias = "🔴 USD WEAK"
    else:
        bias = "⚪ USD NEUTRAL"

    return bias, score, events

# =========================
# FETCH
# =========================
def fetch():

    items = []

    for url in RSS_FEEDS:

        try:
            feed = feedparser.parse(url)

            for e in feed.entries[:10]:
                items.append(e)

        except Exception as e:
            print("Feed error:", e)

    return items

# =========================
# ASSET IMPACT
# =========================
def asset_bias(usdx, asset):

    if asset == "BTC":
        shift = (usdx - 50) * 0.4
    elif asset == "XAU":
        shift = (usdx - 50) * 0.8
    elif asset == "EURUSD":
        shift = (usdx - 50) * 1.2
    else:
        shift = 0

    final = 50 + shift

    if final > 60:
        return "📉 SELL PRESSURE"
    elif final < 40:
        return "📈 BUY PRESSURE"
    return "⚪ NEUTRAL"

# =========================
# ENGINE
# =========================
def run():

    state = load()
    seen = set(state["seen"])

    news = fetch()

    usd_scores = []
    event_hits = []

    for n in news:

        if n.title in seen:
            continue

        bias, score, events = analyze(n)

        print("\nTITLE:", n.title)
        print("BIAS:", bias)
        print("SCORE:", score)
        print("EVENTS:", events)

        usd_scores.append(score)

        if events:
            event_hits.append((n.title, events))

        seen.add(n.title)

    if not usd_scores:
        return

    usdx = sum(usd_scores) / len(usd_scores)

    btc = asset_bias(usdx, "BTC")
    xau = asset_bias(usdx, "XAU")
    eur = asset_bias(usdx, "EURUSD")

    # BUILD MESSAGE
    msg = f"""
📊 MACRO ENGINE UPDATE

USD Strength Index: {usdx:.2f}

Assets:
BTC → {btc}
XAUUSD → {xau}
EURUSD → {eur}

Top Event(s):
"""

    for t, ev in event_hits[:3]:
        msg += f"\n- {ev} → {t[:60]}..."

    msg += f"\n\nTime: {datetime.now(timezone.utc)}"

    # SMART ALERT CONDITION (IMPROVED)
    major_event = any(
        any(k in t.lower() for k in ["fomc", "cpi", "nfp", "interest rate"])
        for t, _ in event_hits
    )

    if usdx > 60 or usdx < 40 or major_event:

        send(msg)
        print("ALERT SENT")

    else:
        print("No strong signal")

    state["seen"] = list(seen)[-300:]
    save(state)

# =========================
# LOOP
# =========================
while True:
    try:
        run()
    except Exception:
        print(traceback.format_exc())

    time.sleep(300)