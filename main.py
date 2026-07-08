from telegram import Bot
import asyncio
import os

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

async def main():
    bot = Bot(token=TOKEN)
    await bot.send_message(
        chat_id=CHAT_ID,
        text="✅ Forex Telegram Bot is running!"
    )

if __name__ == "__main__":
    asyncio.run(main())
