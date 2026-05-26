import requests
import pandas as pd
import yfinance as yf
import os
import time

from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

# =========================
# CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

LAST_SIGNAL_FILE = "last_signal.txt"


# =========================
# SAVE SIGNAL
# =========================
def save_last_signal(signal):
    with open(LAST_SIGNAL_FILE, "w") as file:
        file.write(signal)


# =========================
# LOAD SIGNAL
# =========================
def load_last_signal():
    if not os.path.exists(LAST_SIGNAL_FILE):
        return None

    with open(LAST_SIGNAL_FILE, "r") as file:
        return file.read().strip()


# =========================
# SEND TELEGRAM MESSAGE
# =========================
def send_telegram(message):

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message
        }
    )


# =========================
# MAIN BOT
# =========================
def run_bot():

    print("Running BTC analysis...")

    # =========================
    # 1. GET DATA
    # =========================
    btc = yf.download(
        tickers="BTC-USD",
        interval="1h",
        period="10d"
    )

    # Safety check
    if btc.empty:
        print("No data received")
        return

    btc = btc.dropna()

    btc["Close"] = btc["Close"].astype(float)
    btc["High"] = btc["High"].astype(float)
    btc["Low"] = btc["Low"].astype(float)

    close_prices = btc["Close"].squeeze()

    # =========================
    # 2. INDICATORS
    # =========================
    rsi = RSIIndicator(close_prices, window=14).rsi()
    current_rsi = float(rsi.iloc[-1])

    ema = EMAIndicator(close_prices, window=200).ema_indicator()
    current_ema = float(ema.iloc[-1])

    atr = AverageTrueRange(
        high=btc["High"].squeeze(),
        low=btc["Low"].squeeze(),
        close=btc["Close"].squeeze(),
        window=14
    ).average_true_range()

    current_atr = float(atr.iloc[-1])

    current_price = float(close_prices.iloc[-1])

    # =========================
    # FIX NAN
    # =========================
    if pd.isna(current_ema):
        current_ema = current_price

    if pd.isna(current_atr):
        current_atr = current_price * 0.01

    # =========================
    # TREND
    # =========================
    if current_price > current_ema:
        trend = "Bullish 📈"
    else:
        trend = "Bearish 📉"

    # =========================
    # SIGNAL LOGIC
    # =========================
    if current_rsi < 30 and current_price > current_ema:
        signal = "BUY 📈"
        reason = "Oversold RSI + Bullish Trend"

    elif current_rsi > 70 and current_price < current_ema:
        signal = "SELL 📉"
        reason = "Overbought RSI + Bearish Trend"

    else:
        signal = "HOLD ⏸"
        reason = "No strong confirmation"

    # =========================
    # SKIP HOLD SIGNALS
    # =========================
    if signal == "HOLD ⏸":
        print("No trade setup")
        return

    # =========================
    # SL & TP
    # =========================
    if signal == "BUY 📈":
        stop_loss = current_price - current_atr
        take_profit = current_price + (current_atr * 2)

    else:
        stop_loss = current_price + current_atr
        take_profit = current_price - (current_atr * 2)

    # =========================
    # CONFIDENCE SCORE
    # =========================
    confidence = 60

    if current_price > current_ema and signal == "BUY 📈":
        confidence += 15

    if current_price < current_ema and signal == "SELL 📉":
        confidence += 15

    if current_atr > (current_price * 0.003):
        confidence += 10

    if confidence > 100:
        confidence = 100

    # =========================
    # RISK LEVEL
    # =========================
    if confidence >= 80:
        risk_level = "HIGH CONFIDENCE TRADE 🔥"

    else:
        risk_level = "MODERATE CONFIDENCE TRADE ⚠️ (REDUCE RISK)"

    # =========================
    # ACTIVE TRADE MEMORY
    # =========================
    last_signal = load_last_signal()

    # =========================
    # SAME SIGNAL STILL ACTIVE
    # =========================
    if last_signal == signal:

        message = f"""
📌 BTC TRADE UPDATE

Previous {signal} signal still active.

Maintain previous position.

BTC Price: ${current_price:.2f}

Trend: {trend}

Confidence: {confidence}%

⚠️ No new entry recommended.
"""

        send_telegram(message)

        print("Maintaining previous signal")

        return

    # =========================
    # NEW SIGNAL DETECTED
    # =========================
    message = f"""
🚨 BTC SMART SIGNAL BOT

Timeframe: 1H

BTC Price: ${current_price:.2f}

RSI: {current_rsi:.2f}
EMA 200: ${current_ema:.2f}
ATR: ${current_atr:.2f}

Trend: {trend}

Signal: {signal}
Confidence: {confidence}%

Risk Level: {risk_level}

SL: ${stop_loss:.2f}
TP: ${take_profit:.2f}

Reason:
{reason}

⚠️ NOTE:
60–79% trades require reduced risk.
80%+ are high probability setups.
"""

    send_telegram(message)

    # SAVE SIGNAL
    save_last_signal(signal)

    print("New BTC signal sent!")


# =========================
# RUN FOREVER
# =========================
while True:

    try:
        run_bot()

    except Exception as e:
        print("Error:", e)

    time.sleep(3600)
