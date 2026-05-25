import requests
import pandas as pd
import yfinance as yf

from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

# =========================
# CONFIG
# =========================
BOT_TOKEN = "8991989842:AAEbNKH6w7WBusTzUN1Eo03bAye3yJVqVgo"
CHAT_ID = "-1003963628576"



def run_bot():

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

    # Fix NaN issues
    if pd.isna(current_ema):
        current_ema = current_price

    if pd.isna(current_atr):
        current_atr = current_price * 0.01

    # =========================
    # 3. TREND
    # =========================
    if current_price > current_ema:
        trend = "Bullish 📈"
    else:
        trend = "Bearish 📉"

    # =========================
    # 4. SIGNAL LOGIC
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
    # 5. SL & TP
    # =========================
    if signal == "BUY 📈":
        stop_loss = current_price - current_atr
        take_profit = current_price + (current_atr * 2)

    elif signal == "SELL 📉":
        stop_loss = current_price + current_atr
        take_profit = current_price - (current_atr * 2)

    else:
        stop_loss = current_price
        take_profit = current_price

    # =========================
    # 6. CONFIDENCE SCORE
    # =========================
    confidence = 50

    if signal != "HOLD ⏸":
        confidence += 20

    if current_price > current_ema and signal == "BUY 📈":
        confidence += 15

    if current_price < current_ema and signal == "SELL 📉":
        confidence += 15

    if current_atr > (current_price * 0.003):
        confidence += 10

    if confidence > 100:
        confidence = 100

    # =========================
    # 7. RISK LEVEL SYSTEM
    # =========================
    if confidence >= 80:
        risk_level = "HIGH CONFIDENCE TRADE 🔥"

    elif confidence >= 60:
        risk_level = "MODERATE CONFIDENCE TRADE ⚠️ (RISK REDUCED)"

    else:
        risk_level = "LOW CONFIDENCE - NO TRADE ❌"

    # Skip very low confidence trades
    if confidence < 60:
        print("Signal skipped (confidence too low)")
        return

    # =========================
    # 8. TELEGRAM MESSAGE
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

⚠️ NOTE:
60–79% trades require reduced risk.
80%+ are high probability setups.
"""

    # =========================
    # 9. SEND TO TELEGRAM
    # =========================
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message
        }
    )

    print("BTC smart signal sent!")


# =========================
# RUN ONCE (FOR CLOUD)
# =========================
# run_bot()
