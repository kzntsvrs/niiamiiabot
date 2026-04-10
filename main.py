import telebot
import os
import random
import requests
import threading
import time
import re
import schedule
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
BROADCAST_TIME = os.getenv("BROADCAST_TIME", "09:00")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Москва")

if not TOKEN:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена.")
    exit(1)

bot = telebot.TeleBot(TOKEN)
active_users = set()

# --- КОНТЕНТ ---
QUOTES = ["💡 «Главное — не переставать задавать вопросы.» — Эйнштейн", "🚀 «Успех — это идти от неудачи к неудаче без потери энтузиазма.» — Черчилль"]
RUSSIAN_FACTS = ["🇷🇺 Россия — самая большая страна в мире (17,1 млн км²).", "🏔️ Байкал — самое глубокое озеро в мире (1642 м).", "🚀 Гагарин полетел в космос 12 апреля 1961 года."]

# --- ФУНКЦИИ ---
def get_random_meme():
    try:
        res = requests.get("https://meme-api.com/gimme", timeout=5)
        if res.status_code == 200: return res.json().get("url"), res.json().get("title", "Мем 🎭")
    except: pass
    return "https://http.cat/418.jpg", "Я чайник ☕"

def get_random_gif():
    try:
        res = requests.get(random.choice(["https://random.dog/woof.json", "https://aws.random.cat/meow"]), timeout=5)
        if res.status_code == 200:
            url = res.json().get("file") or res.json().get("url")
            if url: return url, "Гифка 🐾"
    except: pass
    return "https://media.giphy.com/media/Ju7l5y9osyymQ/giphy.gif", "Котик 💃"

def get_weather(city):
    if not WEATHER_API_KEY: return "⚠️ Ключ погоды не настроен."
    try:
        res = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru", timeout=7)
        if res.status_code == 200:
            d = res.json()
            return f"🌡 {d['main']['temp']}°C (ощущается {d['main']['feels_like']}°C)\n💨 Ветер: {d['wind']['speed']} м/с\n☁️ {d['weather'][0]['description'].capitalize()}"
        elif res.status_code == 404: return f"🌍 Город '{city}' не найден."
    except: pass
    return "😅 Не удалось загрузить погоду."

def get_top_news():
    rss_urls = ["https://lenta.ru/rss/news/main/", "https://ria.ru/export/rss2/index.xml"]
    for rss_url in rss_urls:
        try:
            res = requests.get(f"https://api.rss2json.com/v1/api.json?rss_url={rss_url}", timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("status") != "ok" or not data.get("items"): continue
            items = data["items"][:3]
            news_list = []
            for i, item in enumerate(items, 1):
                title = item.get("title", "Без заголовка").strip()
                link = item.get("link", "#")
                desc = re.sub(r'<[^>]+>', '', (item.get("description") or "")).strip()[:120] + "..."
                news_list.append(f"{i}. 📰 {title}\n   {desc}\n   🔗 {link}")
            return "📡 ТОП-3 НОВОСТИ:\n\n" + "\n\n".join(news_list)
        except: continue
    return "😅 Новости временно недоступны."

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    active_users.add(message.chat.id)
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(*[
        telebot.types.InlineKeyboardButton("🎲 Кубик", callback_data="roll_dice"),
        telebot.types.InlineKeyboardButton("💬 Цитата", callback_data="get_quote"),
        telebot.types.InlineKeyboardButton("🖼 Мем", callback_data="send_meme"),
        telebot.types.InlineKeyboardButton("🎬 Гифка", callback_data="send_gif"),
        telebot.types.InlineKeyboardButton("🧠 Факт", callback_data="send_fact"),
        telebot.types.InlineKeyboardButton("📰 Новости", callback_data="get_news"),
        telebot.types.InlineKeyboardButton("🌤 Погода", callback_data="ask_weather")
    ])
    bot.reply_to(message, f"👋 Привет! Рассылка в {BROADCAST_TIME} UTC. Выбери действие или `/weather Город` / `/news` / `/broadcast_now`:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    active_users.add(call.from_user.id)
    handlers = {
        "roll_dice": lambda: (bot.answer_callback_query(call.id, text=f"🎲 Выпало: {(r:=random.randint(1,6))}"), bot.send_message(call.message.chat.id, f"🎲 Выпало: {r}")),
        "get_quote": lambda: (bot.answer_callback_query(call.id, text="📖 Цитата!"), bot.send_message(call.message.chat.id, random.choice(QUOTES))),
        "send_meme": lambda: (bot.answer_callback_query(call.id, text="🖼 Загружаю..."), _try_media(call.message.chat.id, lambda: bot.send_photo(call.message.chat.id, *get_random_meme()))),
        "send_gif": lambda: (bot.answer_callback_query(call.id, text="🎬 Загружаю..."), _try_media(call.message.chat.id, lambda: bot.send_animation(call.message.chat.id, *get_random_gif()))),
        "send_fact": lambda: (bot.answer_callback_query(call.id, text="🧠 Факт!"), bot.send_message(call.message.chat.id, random.choice(RUSSIAN_FACTS))),
        "get_news": lambda: (bot.answer_callback_query(call.id, text="📡 Загружаю..."), bot.send_message(call.message.chat.id, get_top_news())),
        "ask_weather": lambda: (bot.answer_callback_query(call.id, text="🌤 Введи город!"), bot.send_message(call.message.chat.id, "💬 Напиши город, например: `Москва`"))
    }
    if call.data in handlers: handlers[call.data]()

def _try_media(chat_id, func):
    try: func()
    except: bot.send_message(chat_id, "😅 Не удалось загрузить медиа.")

@bot.message_handler(commands=['weather'])
def cmd_weather(message):
    active_users.add(message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2: return bot.reply_to(message, "🌤 Пример: `/weather Москва`")
    bot.reply_to(message, f"🔍 Ищу погоду для {parts[1].strip()}...")
    bot.send_message(message.chat.id, get_weather(parts[1].strip()))

@bot.message_handler(commands=['news'])
def cmd_news(message):
    active_users.add(message.chat.id)
    bot.reply_to(message, "📡 Загружаю свежие новости...")
    bot.send_message(message.chat.id, get_top_news())

@bot.message_handler(commands=['broadcast_now'])
def cmd_broadcast_now(message):
    active_users.add(message.chat.id)
    bot.reply_to(message, "📡 Запуск тестовой рассылки...")
    job_daily_broadcast()
    bot.send_message(message.chat.id, "✅ Рассылка отправлена.")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    active_users.add(message.chat.id)
    bot.reply_to(message, f"🔁 Ты написал: {message.text}")

# --- РАССЫЛКА (ИСПРАВЛЕНО) ---
def job_daily_broadcast():
    if not active_users:
        print("📡 Нет активных пользователей")
        return
    print(f"📡 Рассылка для {len(active_users)} пользователей...")
    
    weather = get_weather(DEFAULT_CITY)
    news_raw = get_top_news()
    
    # ✅ ИСПРАВЛЕНИЕ: пропускаем заголовок, берём первую новость
    if "😅" in news_raw or "не удалось" in news_raw.lower():
        first_news = "😅 Новости временно недоступны."
    else:
        parts = news_raw.split("\n\n")
        first_news = parts[1].strip() if len(parts) > 1 else "Новости загружаются..."
        
    msg = f"🌅 ДОБРОЕ УТРО!\n\n📰 Главная новость:\n{first_news}\n\n🌤 Погода в {DEFAULT_CITY}:\n{weather}\n\n🤖 Ваш вайб-бот"
    
    for uid in list(active_users):
        try:
            bot.send_message(uid, msg)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ Ошибка {uid}: {e}")
            active_users.discard(uid)
    print("✅ Рассылка завершена")

# --- СЕРВЕР + ПЛАНИРОВЩИК ---
PORT = int(os.environ.get("PORT", 8080))
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args): pass

def run_server():
    HTTPServer(('0.0.0.0', PORT), KeepAliveHandler).serve_forever()

def run_scheduler():
    schedule.every().day.at(BROADCAST_TIME).do(job_daily_broadcast)
    print(f"⏰ Планировщик: рассылка в {BROADCAST_TIME} UTC")
    while True: schedule.run_pending(); time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("✅ Бот запущен...")
    bot.polling(none_stop=True)