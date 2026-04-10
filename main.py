import telebot
import os
import random
import requests
import threading
import time
import re
import schedule
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import BotCommand

TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
BROADCAST_TIME = os.getenv("BROADCAST_TIME", "09:00")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Москва")
ADMIN_ID = os.getenv("ADMIN_ID")

if not TOKEN:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена.")
    exit(1)

bot = telebot.TeleBot(TOKEN)
active_users = set()

# --- НАСТРОЙКА МЕНЮ (кнопка слева) ---
def setup_bot_commands():
    """Устанавливает команды для кнопки меню"""
    try:
        commands = [
            BotCommand("start", "🏠 Главное меню"),
            BotCommand("dice", "🎲 Бросить кубик"),
            BotCommand("quote", "💬 Случайная цитата"),
            BotCommand("meme", "🖼 Случайный мем"),
            BotCommand("gif", "🎬 Случайная гифка"),
            BotCommand("fact", "🧠 Интересный факт"),
            BotCommand("news", "📰 Последние новости"),
            BotCommand("weather", "🌤 Погода в городе"),
            BotCommand("help", "❓ Помощь")
        ]
        result = bot.set_my_commands(commands)
        print(f"✅ Команды установлены: {result}")
        
        # Дополнительно: устанавливаем кнопку меню через API
        import requests as req
        url = f"https://api.telegram.org/bot{TOKEN}/setChatMenuButton"
        response = req.post(url, json={"menu_button": {"type": "commands"}})
        print(f"✅ Кнопка меню настроена: {response.json()}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка установки команд: {e}")
        return False

# --- КОНТЕНТ ---
QUOTES = ["💡 «Главное — не переставать задавать вопросы.» — Эйнштейн", 
          "🚀 «Успех — это идти от неудачи к неудаче без потери энтузиазма.» — Черчилль",
          "🌟 «Делай, что можешь, с тем, что имеешь, там, где ты есть.» — Рузвельт"]

RUSSIAN_FACTS = ["🇷🇺 Россия — самая большая страна в мире (17,1 млн км²).", 
                 "🏔️ Байкал — самое глубокое озеро в мире (1642 м).", 
                 "🚀 Гагарин полетел в космос 12 апреля 1961 года."]

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_random_meme():
    try:
        res = requests.get("https://meme-api.com/gimme", timeout=5)
        if res.status_code == 200: 
            return res.json().get("url"), res.json().get("title", "Мем 🎭")
    except: 
        pass
    return "https://http.cat/418.jpg", "Я чайник ☕"

def get_random_gif():
    try:
        res = requests.get(random.choice(["https://random.dog/woof.json", "https://aws.random.cat/meow"]), timeout=5)
        if res.status_code == 200:
            url = res.json().get("file") or res.json().get("url")
            if url: 
                return url, "Гифка 🐾"
    except: 
        pass
    return "https://media.giphy.com/media/Ju7l5y9osyymQ/giphy.gif", "Котик 💃"

def get_weather(city):
    if not WEATHER_API_KEY: 
        return "⚠️ Ключ погоды не настроен."
    try:
        res = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru", timeout=7)
        if res.status_code == 200:
            d = res.json()
            return f"🌡 {d['main']['temp']}°C (ощущается {d['main']['feels_like']}°C)\n💨 Ветер: {d['wind']['speed']} м/с\n☁️ {d['weather'][0]['description'].capitalize()}"
        elif res.status_code == 404: 
            return f"🌍 Город '{city}' не найден."
    except: 
        pass
    return "😅 Не удалось загрузить погоду."

def get_top_news():
    try:
        res = requests.get("https://api.rss2json.com/v1/api.json?rss_url=https://lenta.ru/rss/news/main/", timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("status") == "ok" and data.get("items"):
            items = data["items"][:5]
            news_list = []
            for i, item in enumerate(items, 1):
                title = item.get("title", "Без заголовка").strip()
                link = item.get("link", "#")
                news_list.append(f"{i}. 📰 {title}\n   🔗 {link}")
            return "📡 **СВЕЖИЕ НОВОСТИ:**\n\n" + "\n\n".join(news_list)
    except: 
        pass
    return "😅 Новости временно недоступны."

# --- ОБРАБОТЧИКИ КОМАНД ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    active_users.add(message.chat.id)
    bot.reply_to(
        message, 
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"🤖 Я бот-помощник с разными функциями.\n\n"
        f"📱 **Нажми на кнопку ☰ в левом нижнем углу**\n"
        f"   чтобы открыть меню команд!\n\n"
        f"📅 Рассылка новостей каждый день в {BROADCAST_TIME} UTC\n\n"
        f"Или просто напиши /help",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['dice'])
def cmd_dice(message):
    active_users.add(message.chat.id)
    r = random.randint(1, 6)
    bot.reply_to(message, f"🎲 Вам выпало: **{r}**", parse_mode="Markdown")
    bot.send_dice(message.chat.id)

@bot.message_handler(commands=['quote'])
def cmd_quote(message):
    active_users.add(message.chat.id)
    bot.reply_to(message, random.choice(QUOTES))

@bot.message_handler(commands=['meme'])
def cmd_meme(message):
    active_users.add(message.chat.id)
    url, title = get_random_meme()
    bot.reply_to(message, "🖼 Загружаю мем...")
    bot.send_photo(message.chat.id, url, caption=title)

@bot.message_handler(commands=['gif'])
def cmd_gif(message):
    active_users.add(message.chat.id)
    url, title = get_random_gif()
    bot.reply_to(message, "🎬 Загружаю гифку...")
    bot.send_animation(message.chat.id, url, caption=title)

@bot.message_handler(commands=['fact'])
def cmd_fact(message):
    active_users.add(message.chat.id)
    bot.reply_to(message, random.choice(RUSSIAN_FACTS))

@bot.message_handler(commands=['news'])
def cmd_news(message):
    active_users.add(message.chat.id)
    bot.reply_to(message, "📡 Загружаю свежие новости...")
    bot.send_message(message.chat.id, get_top_news(), parse_mode="Markdown")

@bot.message_handler(commands=['weather'])
def cmd_weather(message):
    active_users.add(message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "🌤 **Пример:** `/weather Москва`", parse_mode="Markdown")
        return
    bot.reply_to(message, f"🔍 Ищу погоду для {parts[1].strip()}...")
    bot.send_message(message.chat.id, get_weather(parts[1].strip()))

@bot.message_handler(commands=['help'])
def cmd_help(message):
    active_users.add(message.chat.id)
    help_text = """
🤖 **Доступные команды (через кнопку ☰ внизу слева):**

🎲 **/dice** - Бросить кубик
💬 **/quote** - Случайная цитата
🖼 **/meme** - Случайный мем
🎬 **/gif** - Случайная гифка
🧠 **/fact** - Интересный факт
📰 **/news** - Последние новости
🌤 **/weather** - Погода (пример: /weather Москва)
❓ **/help** - Это сообщение
🏠 **/start** - Главное меню

📅 **Автоматическая рассылка:** Каждый день в {BROADCAST_TIME} UTC

💡 **Совет:** Нажми на кнопку ☰ в левом нижнем углу!
    """
    bot.reply_to(message, help_text.format(BROADCAST_TIME=BROADCAST_TIME), parse_mode="Markdown")

# --- ОБРАБОТЧИК ТЕКСТА ---
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    active_users.add(message.chat.id)
    text = message.text.lower().strip()
    
    if text.startswith("погода "):
        city = message.text.split(maxsplit=1)[1]
        bot.send_message(message.chat.id, get_weather(city))
    elif text in ["привет", "здравствуй", "hi", "hello", "ку"]:
        bot.reply_to(message, f"👋 Привет, {message.from_user.first_name}! Нажми на кнопку ☰ внизу слева для меню команд!")
    elif text in ["помощь", "help", "команды"]:
        cmd_help(message)

# --- РАССЫЛКА ---
def job_daily_broadcast():
    if not active_users:
        print("📡 Нет активных пользователей")
        return
    
    print(f"📡 Рассылка для {len(active_users)} пользователей...")
    
    weather = get_weather(DEFAULT_CITY)
    news_raw = get_top_news()
    
    first_news = "Новости временно недоступны"
    lines = news_raw.split('\n')
    for line in lines:
        if line.startswith("1."):
            first_news = line
            break
    
    msg = f"🌅 **ДОБРОЕ УТРО!**\n\n📰 {first_news}\n\n🌤 **Погода в {DEFAULT_CITY}:**\n{weather}\n\n🤖 Нажми на кнопку ☰ внизу слева для меню!"
    
    success_count = 0
    for uid in list(active_users):
        try:
            bot.send_message(uid, msg, parse_mode="Markdown")
            success_count += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"⚠️ Ошибка {uid}: {e}")
            active_users.discard(uid)
    
    print(f"✅ Рассылка завершена. Отправлено: {success_count}")

# --- СЕРВЕР ---
PORT = int(os.environ.get("PORT", 8080))

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args): pass

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), KeepAliveHandler)
    print(f"🌐 HTTP сервер запущен на порту {PORT}")
    server.serve_forever()

def run_scheduler():
    schedule.every().day.at(BROADCAST_TIME).do(job_daily_broadcast)
    print(f"⏰ Планировщик: рассылка в {BROADCAST_TIME} UTC")
    while True: 
        schedule.run_pending()
        time.sleep(10)

# --- ЗАПУСК ---
if __name__ == "__main__":
    print("🚀 Запуск бота...")
    
    # Устанавливаем меню команд
    setup_bot_commands()
    
    # Удаляем webhook на всякий случай
    bot.remove_webhook()
    
    # Запускаем сервер и планировщик в фоне
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    print("✅ Бот запущен!")
    print("📱 Откройте чат с ботом")
    print("👇 В левом нижнем углу появится кнопка ☰ с меню команд")
    print("⚠️ Если кнопки нет - перезапустите Telegram клиент!")
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=20)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        time.sleep(5)