import os
import logging
import threading
import concurrent.futures
import telebot
import yfinance as yf
import pandas as pd

# =====================================
# TELEGRAM CONFIGURATION
# =====================================
# ضع التوكن الخاص بك هنا بين علامتي التنصيص
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7718919427:AAH0d...ضع_التوكن_هنا")
# ضع الـ Chat ID الخاص بك هنا
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7917961649")

bot = telebot.TeleBot(TOKEN)
logging.basicConfig(level=logging.INFO)

# =====================================
# MARKETS
# =====================================

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
    "GC=F": "GOLD"
}

ENTRY_TIMEFRAME = "15m"
CONFIRM_TIMEFRAME = "1h"

MIN_SCORE = 6
MIN_RR = 2.5

is_scanning = False
scan_lock = threading.Lock()

# =====================================
# INDICATORS
# =====================================

def calculate_indicators(df):
    df = df.copy()
    close = df["Close"]

    df["EMA20"] = close.ewm(span=20, adjust=False).mean()
    df["EMA50"] = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["RSI"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()

    # ATR
    previous_close = close.shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - previous_close).abs(),
        (df["Low"] - previous_close).abs()
    ], axis=1).max(axis=1)

    df["ATR"] = tr.ewm(alpha=1/14, adjust=False).mean()
    return df


def get_data(symbol, interval, period="60d"):
    try:
        data = yf.Ticker(symbol).history(
            period=period,
            interval=interval,
            auto_adjust=False
        )
        if data is None or data.empty:
            return None

        required = ["Open", "High", "Low", "Close"]
        data = data.dropna(subset=required).copy()

        if len(data) < 80:
            return None

        return calculate_indicators(data)
    except Exception:
        return None


# =====================================
# ICT: FAIR VALUE GAP
# =====================================

def detect_fvg(df, direction):
    if len(df) < 4:
        return False
    last = df.iloc[-1]
    two_back = df.iloc[-3]

    if direction == "BUY":
        return last["Low"] > two_back["High"]
    if direction == "SELL":
        return last["High"] < two_back["Low"]
    return False


# =====================================
# ICT: LIQUIDITY SWEEP
# =====================================

def detect_liquidity_sweep(df, direction):
    if len(df) < 15:
        return False
    last = df.iloc[-1]
    previous = df.iloc[-11:-1]

    old_low = previous["Low"].min()
    old_high = previous["High"].max()

    if direction == "BUY":
        return last["Low"] < old_low and last["Close"] > old_low
    if direction == "SELL":
        return last["High"] > old_high and last["Close"] < old_high
    return False


# =====================================
# ICT: ORDER BLOCK APPROXIMATION
# =====================================

def detect_order_block(df, direction):
    if len(df) < 15:
        return False

    current = df.iloc[-1]
    recent = df.iloc[-12:-1]
    price = float(current["Close"])
    atr = float(current["ATR"])

    if atr <= 0:
        return False

    for i in range(len(recent) - 1, -1, -1):
        candle = recent.iloc[i]
        following = recent.iloc[i+1:]

        if direction == "BUY":
            opposite = candle["Close"] < candle["Open"]
            displacement = (
                (following["Close"] > candle["High"])
                & ((following["Close"] - following["Open"]) > 0.8 * atr)
            ).any()
            near_zone = candle["Low"] - 0.25 * atr <= price <= candle["High"] + 0.25 * atr

            if opposite and displacement and near_zone:
                return True

        if direction == "SELL":
            opposite = candle["Close"] > candle["Open"]
            displacement = (
                (following["Close"] < candle["Low"])
                & ((following["Open"] - following["Close"]) > 0.8 * atr)
            ).any()
            near_zone = candle["Low"] - 0.25 * atr <= price <= candle["High"] + 0.25 * atr

            if opposite and displacement and near_zone:
                return True

    return False


# =====================================
# SMART MONEY: BOS / CHoCH
# =====================================

def detect_structure(df, direction):
    if len(df) < 20:
        return False
    last = df.iloc[-1]
    previous = df.iloc[-11:-1]

    old_high = previous["High"].max()
    old_low = previous["Low"].min()

    if direction == "BUY":
        return last["Close"] > old_high
    if direction == "SELL":
        return last["Close"] < old_low
    return False


# =====================================
# SUPPORT AND RESISTANCE
# =====================================

def calculate_levels(df):
    previous = df.iloc[-21:-1]
    support = float(previous["Low"].min())
    resistance = float(previous["High"].max())
    return support, resistance


# =====================================
# HIGHER TIMEFRAME CONFIRMATION
# =====================================

def timeframe_direction(df):
    if df is None or len(df) < 60:
        return None
    candle = df.iloc[-2]
    if candle["EMA20"] > candle["EMA50"]:
        return "BUY"
    if candle["EMA20"] < candle["EMA50"]:
        return "SELL"
    return None


def get_h4_data(h1_data):
    if h1_data is None:
        return None
    h4 = h1_data.resample("4h").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum"
    }).dropna()
    return calculate_indicators(h4)


# =====================================
# MAIN MARKET ANALYSIS
# =====================================

def analyze_market(symbol, name):
    try:
        # جلب بيانات المتاجر المحددة
        data = get_data(symbol, ENTRY_TIMEFRAME)
        if data is None or len(data) < 80:
            return None

        h1 = get_data(symbol, CONFIRM_TIMEFRAME)
        if h1 is None:
            return None
            
        h4 = get_h4_data(h1)
        if h4 is None or len(h4) < 60:
            return None

        # استبعاد الشموع غير المكتملة
        data = data.iloc[:-1]
        h1 = h1.iloc[:-1]
        h4 = h4.iloc[:-1]

        if len(data) < 30 or len(h1) < 60 or len(h4) < 60:
            return None

        last = data.iloc[-1]
        price = float(last["Close"])
        ema20 = float(last["EMA20"])
        ema50 = float(last["EMA50"])
        rsi = float(last["RSI"])
        macd = float(last["MACD"])
        macd_signal = float(last["MACD_SIGNAL"])
        atr = float(last["ATR"])

        values = [price, ema20, ema50, rsi, macd, macd_signal, atr]
        if not all(pd.notna(x) for x in values) or price <= 0 or atr <= 0:
            return None

        support, resistance = calculate_levels(data)
        h1_direction = timeframe_direction(h1)
        h4_direction = timeframe_direction(h4)

        results = []

        for direction in ["BUY", "SELL"]:
            score = 0
            reasons = []

            # 1. M15 EMA trend
            if direction == "BUY":
                ema_condition = (ema20 > ema50 and price > ema20)
            else:
                ema_condition = (ema20 < ema50 and price < ema20)

            if ema_condition:
                score += 1
                reasons.append("EMA trend confirmed")

            # 2. H1 + H4 trend confirmation
            if h1_direction == direction and h4_direction == direction:
                score += 1
                reasons.append("H1 and H4 aligned")

            # 3. RSI
            if direction == "BUY"
