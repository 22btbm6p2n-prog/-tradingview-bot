import os
import telebot

# بيانات التوكن والشات آي دي الخاصة بك
TOKEN = "8929649925:AAGl3qoIKKkovo20_8bOdzS6Q5g9dB99ou4"
CHAT_ID = "7917961649"

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
  bot.reply_to(
      message,
      "أهلاً بك! بوت تحليل الرسوم البيانية وتداول الفوركس جاهز.",
  )


@bot.message_handler(content_types=["photo"])
def handle_chart_image(message):
  bot.reply_to(
      message,
      "جاري استلام الصورة وتحليل مؤشر RSI والإشارات الفنية... يرجى الانتظار.",
  )
  # هنا يمكنك لاحقاً إضافة كود معالجة الصورة وتحليلها واستخراج إشارات البيع والشراء


if __name__ == "__main__":
  print("Bot is running...")
  bot.infinity_polling()
