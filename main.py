import telebot
import os
import random
import requests
import threading
import re
import xml.etree.ElementTree as ET
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

if not TOKEN:
    print("❌ ОШИБКА: Переменная BOT_TOKEN не найдена. Проверь Render Environment.")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# --- КОНТЕНТ ---
QUOTES = [
    "💡 «Главное — не переставать задавать вопросы.» — Эйнштейн",
    "🚀 «Успех — это способность идти от неудачи к неудаче, не теряя энтузиазма.» — Черчилль",
    "🌟 «Не бойся двигаться медленно, бойся стоять на месте.» — Китайская мудрость",
    "🔥 «Код — это поэзия для машин.» — Неизвестный разработчик",
    "🛠 «Любая достаточно развитая технология неотличима от магии.» — Артур Кларк"
]

RUSSIAN_FACTS = [
    "🇷🇺 Россия — самая большая страна в мире, её площадь составляет 17,1 млн км².",
    "🏔️ В России находится самое глубокое озеро в мире — Байкал (1642 метра).",
    "🚀 Россия первой отправила человека в космос — Юрия Гагарина 12 апреля 1961 года.",
    "👩🚀 Первая в мире женщина-космонавт — Валентина Терешкова (СССР, 1963).",
    "🎭 В России более 600 театров — больше, чем в любой другой стране."
]

# --- ФУНКЦИИ КОНТЕНТА ---
def get_random_meme():
    try:
        res = requests.get("https://meme-api.com/gimme", timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data.get("url"), data.get("title", "Случайный мем 🎭")
    except: pass
    return "https://http.cat/418.jpg", "Я чайник, а не сервер ☕"

def get_random_gif():
    apis = ["https://random.dog/woof.json", "https://aws.random.cat/meow"]
    try:
        res = requests.get(random.choice(apis), timeout=5)
        if res.status_code == 200:
            data = res.json()
            url = data.get("file") or data.get("url")
            if url: return url, "Случайное животное 🐾"
    except: pass
    return "https://media.giphy.com/media/Ju7l5y9osyymQ/giphy.gif", "Танцующий котик 💃"

def get_weather(city):
    if not WEATHER_API_KEY:
        return "⚠️ Ключ погоды не настроен. Попроси админа добавить WEATHER_API_KEY."
    
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
    try:
        res = requests.get(url, timeout=7)
        if res.status_code == 200:
            d = res.json()
            return (f"🌤 Погода в {d['name']}, {d['sys']['country']}\n"
                    f"🌡 Температура: {d['main']['temp']}°C (ощущается как {d['main']['feels_like']}°C)\n"
                    f"💨 Ветер: {d['wind']['speed']} м/с\n"
                    f"☁️ {d['weather'][0]['description'].capitalize()}")
        elif res.status_code == 404:
            return f"🌍 Город '{city}' не найден. Попробуй написать на английском."
        else:
            return f"❌ Ошибка сервера погоды: {res.status_code}"
    except Exception:
        return "😅 Не удалось загрузить погоду. Попробуй позже."

def get_top_news():
    """Парсит топ-3 новости из RSS-ленты Ленты.ру"""
    rss_url = "https://lenta.ru/rss/news/main/"
    try:
        res = requests.get(rss_url, timeout=10)
        res.raise_for_status()
        
        root = ET.fromstring(res.content)
        items = root.findall('.//item')[:3]  # Берём первые 3 новости
        
        news_list = []
        for i, item in enumerate(items, 1):
            title = item.find('title').text or "Без заголовка"
            link = item.find('link').text
            desc = item.find('description').text or ""
            
            # Убираем HTML-теги из описания
            clean_desc = re.sub(r'<[^>]+>', '', desc).strip()[:150] + "..."
            
            news_list.append(f"{i}. 📰 {title}\n   {clean_desc}\n   🔗 {link}")
            
        return "📡 **ТОП-3 НОВОСТИ:**\n\n" + "\n\n".join(news_list)
    except Exception as e:
        return f"😅 Не удалось загрузить новости. Попробуй позже.\n(Тех. причина: {str(e)[:40]})"

# --- ОБРАБОТЧИКИ TELEGRAM ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    btn_dice = telebot.types.InlineKeyboardButton("🎲 Кубик", callback_data="roll_dice")
    btn_quote = telebot.types.InlineKeyboardButton("💬 Цитата", callback_data="get_quote")
    btn_meme = telebot.types.InlineKeyboardButton("🖼 Мем", callback_data="send_meme")
    btn_gif = telebot.types.InlineKeyboardButton("🎬 Гифка", callback_data="send_gif")
    btn_fact = telebot.types.InlineKeyboardButton("🧠 Факт", callback_data="send_fact")
    btn_news = telebot.types.InlineKeyboardButton("📰 Новости", callback_data="get_news")
    btn_weather = telebot.types.InlineKeyboardButton("🌤 Погода", callback_data="ask_weather")
    markup.add(btn_dice, btn_quote, btn_meme, btn_gif, btn_fact, btn_news, btn_weather)
    
    bot.reply_to(message, "👋 Привет! Я русскоязычный вайб-бот. Выбери действие или используй `/weather Город` / `/news`:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "roll_dice":
        res = random.randint(1, 6)
        bot.answer_callback_query(call.id, text=f"🎲 Выпало: {res}")
        bot.send_message(call.message.chat.id, f"🎲 Ты нажал кнопку! Выпало: {res}")
    elif call.data == "get_quote":
        bot.answer_callback_query(call.id, text="📖 Цитата загружена!")
        bot.send_message(call.message.chat.id, random.choice(QUOTES))
    elif call.data == "send_meme":
        bot.answer_callback_query(call.id, text="🖼 Загружаю мем...")
        try:
            url, title = get_random_meme()
            bot.send_photo(call.message.chat.id, url, caption=title)
        except: bot.send_message(call.message.chat.id, "😅 Не удалось загрузить мем.")
    elif call.data == "send_gif":
        bot.answer_callback_query(call.id, text="🎬 Загружаю гифку...")
        try:
            url, title = get_random_gif()
            bot.send_animation(call.message.chat.id, url, caption=title)
        except: bot.send_message(call.message.chat.id, "😅 Не удалось загрузить гифку.")
    elif call.data == "send_fact":
        bot.answer_callback_query(call.id, text="🧠 Загружаю факт...")
        bot.send_message(call.message.chat.id, random.choice(RUSSIAN_FACTS))
    elif call.data == "get_news":
        bot.answer_callback_query(call.id, text="📡 Загружаю новости...")
        bot.send_message(call.message.chat.id, get_top_news(), parse_mode="Markdown")
    elif call.data == "ask_weather":
        bot.answer_callback_query(call.id, text="🌤 Введи город текстом!")
        bot.send_message(call.message.chat.id, "💬 Просто напиши мне название города, например: `Москва` или `Лондон`.")

@bot.message_handler(commands=['weather'])
def cmd_weather(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "🌤 Введи город после команды.\nПример: `/weather Москва`")
        return
    city = parts[1].strip()
    bot.reply_to(message, f"🔍 Ищу погоду для {city}...")
    bot.send_message(message.chat.id, get_weather(city))

@bot.message_handler(commands=['news'])
def cmd_news(message):
    bot.reply_to(message, "📡 Загружаю свежие новости...")
    bot.send_message(message.chat.id, get_top_news(), parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"🔁 Ты написал: {message.text}")

# --- АНТИ-СОН ДЛЯ RENDER ---
PORT = int(os.environ.get("PORT", 8080))

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is alive and polling!")
    def log_message(self, format, *args): pass

def run_server():
    try:
        server = HTTPServer(('0.0.0.0', PORT), KeepAliveHandler)
        print(f"✅ Веб-сервер запущен на порту {PORT}")
        server.serve_forever()
    except Exception as e:
        print(f"❌ Сервер не запустился: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("✅ Бот запущен. Ожидание сообщений...")
    bot.polling(none_stop=True)