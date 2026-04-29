import telebot
import os

# ВСТАВЬТЕ ВАШ ТОКЕН СЮДА (в кавычках)
TOKEN = "8684435692:AAG9krc0q0__Boq_fwnf-XRCFoP5CJ1tGik"

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "✨ Привет! Я Вайб-бот работаю!")

@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, f"Ты написал: {message.text}")

print("✅ Бот запущен!")
bot.infinity_polling()