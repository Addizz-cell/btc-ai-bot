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

        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": msg
            },
            timeout=10
        )

        print("Telegram Status:", response.status_code)

    except Exception as e:
        print("Telegram Error:", e)


# =========================
# STATE
# =========================
def load():

    try:

        if not os.path.exists(STATE_FILE):
            print("Creating new state")
            return {"seen": []}

        with open(STATE_FILE, "r") as f:
            return json.load(f)

    except Exception as e:

        print("STATE LOAD ERROR:", e)

        return {"seen": []}


def save(state):

    try:

        with open(STATE_FILE, "w") as f:
            json.dump(state, f)

    except Exception as e:

        print("STATE SAVE ERROR:", e)


# =========================
# EVENT WEIGHTS
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

BULLISH = [
    "higher",
    "rise",
    "strong",
    "hawkish",
    "beats",
    "increase"
]

BEARISH = [
    "lower",
    "fall",
    "weak",
    "dovish",
    "miss",
    "cut"
]

# =========================
# TIME DECAY
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
# ANALYZE ARTICLE
# =========================
def analyze(entry):

    text = entry.title.lower()

    weight = 1.0

    for keyword, value in WEIGHTS.items():

        if keyword in text:
            weight += value

    score = 50

    for word in BULLISH:

        if word in text:
            score += (8 * weight)

    for word in BEARISH:

        if word in text:
            score -= (8 * weight)

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

    articles = []

    for url in RSS_FEEDS:

        try:

            print(f"Fetching: {url}")

            feed = feedparser.parse(url)

            print(
                f"Feed returned {len(feed.entries)} articles"
            )

            for entry in feed.entries[:10]:
                articles.append(entry)

        except Exception as e:

            print(
                f"Feed Error {url}: {e}"
            )

    return articles


# =========================
# ASSET IMPACT
# =========================
def asset_bias(usdx_score, asset):

    if asset == "BTC":

        shift = (
            (usdx_score - 50)
            * 0.4
        )

    elif asset == "XAU":

        shift = (
            (usdx_score - 50)
            * 0.8
        )

    elif asset == "EURUSD":

        shift = (
            (usdx_score - 50)
            * 1.2
        )

    else:

        shift = 0

    final = 50 + shift

    if final > 60:
        return "📉 SELL PRESSURE"

    if final < 40:
        return "📈 BUY PRESSURE"

    return "⚪ NEUTRAL"


# =========================
# MAIN ENGINE
# =========================
def run():

    print(
        "\n================================"
    )

    print(
        "SCAN STARTED:",
        datetime.now(timezone.utc)
    )

    state = load()

    seen = set(
        state["seen"]
    )

    print(
        "Previously seen:",
        len(seen)
    )

    news = fetch()

    print(
        "Total articles fetched:",
        len(news)
    )

    usd_scores = []

    for article in news:

        if article.title in seen:
            continue

        bias, score = analyze(article)

        print(
            "\nNEW ARTICLE:"
        )

        print(
            article.title
        )

        print(
            f"Bias={bias}"
        )

        print(
            f"Score={score}"
        )

        usd_scores.append(score)

        seen.add(
            article.title
        )

    print(
        "New articles found:",
        len(usd_scores)
    )

    if not usd_scores:

        print(
            "No new articles."
        )

        return

    usdx = (
        sum(usd_scores)
        / len(usd_scores)
    )

    print(
        f"USD INDEX: {usdx:.2f}"
    )

    btc_bias = asset_bias(
        usdx,
        "BTC"
    )

    xau_bias = asset_bias(
        usdx,
        "XAU"
    )

    eur_bias = asset_bias(
        usdx,
        "EURUSD"
    )

    msg = f"""
📊 MACRO ENGINE UPDATE

USD Strength Index:
{usdx:.2f}/100

Assets:

BTC → {btc_bias}

XAUUSD → {xau_bias}

EURUSD → {eur_bias}

Time:
{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
"""

    if usdx > 60 or usdx < 40:

        print(
            "ALERT SENT"
        )

        send(msg)

    else:

        print(
            "No alert threshold reached."
        )

    state["seen"] = list(seen)[-300:]

    save(state)

    print(
        "State saved."
    )

    print(
        "SCAN COMPLETE"
    )


# =========================
# LOOP
# =========================
while True:

    try:

        run()

    except Exception:

        print(
            "\nMAIN LOOP ERROR"
        )

        print(
            traceback.format_exc()
        )

    print(
        "Sleeping 300 seconds..."
    )

    time.sleep(300)