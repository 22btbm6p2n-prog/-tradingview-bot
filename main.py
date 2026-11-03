import os
import logging
import threading
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
    "GC=F": "GOLD FUTURES (Gold proxy)"
}

TIMEFRAME = "1h"

# Thread safety state
is_scanning = False
scan_lock = threading.Lock()

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

        # EMA 20 and EMA 50
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
        data["SUPPORT"] = data["Low"].rolling(20).min()
        data["RESISTANCE"] = data["High"].rolling(20).max()

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

        values = [
            price, ema20, ema50, rsi,
            macd, macd_signal, atr,
            support, resistance
        ]

        if not all(pd.notna(x) for x in values):
            return None

        if price <= 0 or atr <= 0:
            return None

        # BUY conditions
        buy_score = sum([
            ema20 > ema50,
            price > ema20,
            50 < rsi < 70,
            macd > macd_signal
        ])

        # SELL conditions
        sell_score = sum([
            ema20 < ema50,
            price < ema20,
            30 < rsi < 50,
            macd < macd_signal
        ])

        if buy_score >= 3 and buy_score > sell_score:
            direction = "BUY"
            stop_loss = price - (1.5 * atr)
            take_profit = price + (3 * atr)
            score = buy_score

        elif sell_score >= 3 and sell_score > buy_score:
            direction = "SELL"
            stop_loss = price + (1.5 * atr)
            take_profit = price - (3 * atr)
            score = sell_score

        else:
            return None

        # Precision formatting
        digits = 3 if "JPY" in name else 2 if "GOLD" in name else 5

        return {
            "name": name,
            "direction": direction,
            "entry": round(price, digits),
            "sl": round(stop_loss, digits),
            "tp": round(take_profit, digits),
            "rsi": round(rsi, 2),
            "support": round(support, digits),
            "resistance": round(resistance, digits),
            "score": score
        }

    except Exception:
        logging.exception("Analysis failed for %s", symbol)
        return None


def scan_markets():
    results = []

    for symbol, name in MARKETS.items():
        result = analyze_market(symbol, name)

        if result:
            results.append(result)

    if not results:
        return None

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[0]


def send_signal(chat_id):
    global is_scanning
    try:
        bot.send_message(
            chat_id,
            "🔎 جاري البحث عن أفضل فرصة في الأسواق..."
        )

        result = scan_markets()

        if result is None:
            bot.send_message(
                chat_id,
                "لا توجد حالياً فرصة واضحة حسب شروط الاستراتيجية.\n"
                "حاول مرة أخرى لاحقاً."
            )
            return

        message = (
            "📊 **TRADING SIGNAL**\n\n"
            f"Market: {result['name']}\n"
            f"Direction: {result['direction']}\n"
            f"Entry: {result['entry']}\n"
            f"Stop Loss: {result['sl']}\n"
            f"Take Profit: {result['tp']}\n\n"
            f"RSI: {result['rsi']}\n"
            f"Support: {result['support']}\n"
            f"Resistance: {result['resistance']}\n"
            f"Score: {result['score']}/4\n\n"
            "Timeframe: 1H\n"
            "Strategy: EMA + RSI + MACD"
        )

        bot.send_message(chat_id, message)

    except Exception:
        logging.exception("Signal sending failed")
        bot.send_message(
            chat_id,
            "حدث خطأ أثناء البحث. حاول مرة أخرى."
        )

    finally:
        with scan_lock:
            is_scanning = False


@bot.message_handler(commands=["start"])
def start_command(message):
    global is_scanning
    
    with scan_lock:
        if is_scanning:
            bot.reply_to(message, "البحث جارٍ بالفعل، انتظر قليلاً.")
            return
        is_scanning = True

    threading.Thread(
        target=send_signal,
        args=(message.chat.id,),
        daemon=True
    ).start()


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.reply_to(
        message,
        "أرسل /start للبحث عن فرصة تداول.\n"
        "البوت مبرمج للرد على أوامرك."
    )


if __name__ == "__main__":
    print("Bot is running...")
    # اختياري: يمكنك إرسال إشعار عند بدء تشغيل البوت مباشرة إلى الـ CHAT_ID الخاص بك
    try:
        bot.send_message(CHAT_ID, "🚀 تم تشغيل بوت التداول بنجاح وجاهز لاستقبال الأوامر!")
    except Exception as e:
        logging.warning(f"Could not send startup message: {e}")

    bot.infinity_polling(skip_pending=True)

    

         