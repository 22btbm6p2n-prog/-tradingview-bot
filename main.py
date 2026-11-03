import os
import time
import logging
import telebot
import yfinance as yf
import pandas as pd

# =========================
# TELEGRAM CONFIGURATION
# =========================

TOKEN = "8929649925:AAGl3qoIKKkovo20_8bOdzS6Q5g9dB99ou4"
CHAT_ID = "7917961649"

bot = telebot.TeleBot(TOKEN)

logging.basicConfig(level=logging.INFO)

# =========================
# MARKETS
# =========================

MARKETS = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCHF=X": "USD/CHF",
    "USDCAD=X": "USD/CAD",
    "AUDUSD=X": "AUD/USD",
    "NZDUSD=X": "NZD/USD",
    "EURGBP=X": "EUR/GBP",
    "EURJPY=X": "EUR/JPY",
    "GBPJPY=X": "GBP/JPY",
    "EURCHF=X": "EUR/CHF",
    "EURAUD=X": "EUR/AUD",
    "EURCAD=X": "EUR/CAD",
    "EURNZD=X": "EUR/NZD",
    "GBPAUD=X": "GBP/AUD",
    "GBPCAD=X": "GBP/CAD",
    "GBPNZD=X": "GBP/NZD",
    "GBPCHF=X": "GBP/CHF",
    "AUDJPY=X": "AUD/JPY",
    "AUDCAD=X": "AUD/CAD",
    "AUDNZD=X": "AUD/NZD",
    "AUDCHF=X": "AUD/CHF",
    "NZDJPY=X": "NZD/JPY",
    "NZDCAD=X": "NZD/CAD",
    "NZDCHF=X": "NZD/CHF",
    "CADJPY=X": "CAD/JPY",
    "CHFJPY=X": "CHF/JPY",
    "XAUUSD=X": "XAUUSD GOLD"
}

TIMEFRAME = "1h"

# =========================
# TECHNICAL ANALYSIS
# =========================

def analyze_market(symbol, name):

    try:
        data = yf.Ticker(symbol).history(
            period="1mo",
            interval=TIMEFRAME,
            auto_adjust=False
        )

        if data is None or len(data) < 60:
            return None

        data = data.dropna(
            subset=["Open", "High", "Low", "Close"]
        ).copy()

        if len(data) < 60:
            return None

        close = data["Close"]

        # EMA 20 / EMA 50
        data["EMA20"] = close.ewm(
            span=20, adjust=False
        ).mean()

        data["EMA50"] = close.ewm(
            span=50, adjust=False
        ).mean()

        # RSI 14
        delta = close.diff()

        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.ewm(
            alpha=1/14, adjust=False
        ).mean()

        avg_loss = loss.ewm(
            alpha=1/14, adjust=False
        ).mean()

        rs = avg_gain / avg_loss.replace(0, float("nan"))

        data["RSI"] = 100 - (100 / (1 + rs))

        # MACD
        ema12 = close.ewm(
            span=12, adjust=False
        ).mean()

        ema26 = close.ewm(
            span=26, adjust=False
        ).mean()

        data["MACD"] = ema12 - ema26

        data["MACD_SIGNAL"] = data["MACD"].ewm(
            span=9, adjust=False
        ).mean()

        # ATR 14
        previous_close = close.shift(1)

        tr = pd.concat([
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs()
        ], axis=1).max(axis=1)

        data["ATR"] = tr.ewm(
            alpha=1/14, adjust=False
        ).mean()

        # Support and resistance
        data["SUPPORT"] = data["Low"].rolling(
            20
        ).min()

        data["RESISTANCE"] = data["High"].rolling(
            20
        ).max()

        last = data.iloc[-1]

        price = float(last["Close"])
        ema20 = float(last["EMA20"])
        ema50 = float(last["EMA50"])
        rsi = float(last["RSI"])
        macd = float(last["MACD"])
        macd_signal = float(last["MACD_SIGNAL"])
        atr = float(last["ATR"])

        support = float(last["SUPPORT"])
        resistance = float(last["RESISTANCE"])

        if not all(pd.notna(x) for x in [
            price, ema20, ema50, rsi,
            macd, macd_signal, atr,
            support, resistance
        ]):
            return None

        if price <= 0 or atr <= 0:
            return None

        # BUY / SELL conditions
        buy_score


