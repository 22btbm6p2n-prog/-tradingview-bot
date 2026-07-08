import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("8608742930:AAHucSgQBSDjMRHKjE50FXXYzbx7vtRbwBM")
CHAT_ID = os.getenv("7917961649")

SYMBOLS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "AUD/USD",
    "USD/CAD",
    "USD/CHF",
    "NZD/USD"
]

TIMEFRAMES = [
    "5min",
    "15min",
    "1h"
]

EMA_FAST = 20
EMA_SLOW = 50

RSI_PERIOD = 14

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

RISK_REWARD = 2
ATR_PERIOD = 14
