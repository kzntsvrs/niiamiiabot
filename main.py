import telebot
import os
import random
import requests
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.getenv("BOT_TOKEN")
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
    "🎭 В России более 600 театров — больше, чем в любой другой стране.",
    "🐻 В России обитает около 150 000 бурых медведей — это половина всех медведей мира.",
    "🌡️ Самая низкая температура в России: -71,2°C (Оймякон, Якутия).",
    "🏰 В России 29 объектов Всемирного наследия ЮНЕСКО.",
    "🎵 Пётр Ильич Чайковский — один из самых исполняемых композиторов в мире.",
    "🔬 Дмитрий Менделеев создал периодическую систему химических элементов."
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

# --- ОБРАБОТЧИКИ TELEGRAM ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    btn_dice = telebot.types.InlineKeyboardButton("🎲 Кубик", callback_data="roll_dice")
    btn_quote = telebot.types.InlineKeyboardButton("💬 Цитата", callback_data="get_quote")
    btn_meme = telebot.types.InlineKeyboardButton("🖼 Мем", callback_data="send_meme")
    btn_gif = telebot.types.InlineKeyboardButton("🎬 Гифка", callback_data="send_gif")
    btn_fact = telebot.types.InlineKeyboardButton("🧠 Факт", callback_data="send_fact")
    markup.add(btn_dice, btn_quote, btn_meme, btn_gif, btn_fact)
    bot.reply_to(message, "👋 Привет! Я русскоязычный вайб-бот. Выбери действие:", reply_markup=markup)

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

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"🔁 Ты написал: {message.text}")

# --- АНТИ-СОН ДЛЯ БЕСПЛАТНОГО ХОСТИНГА ---
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")
    def log_message(self, format, *args): pass

def run_keepalive():
    server = HTTPServer(('0.0.0.0', 8080), KeepAliveHandler)
    server.serve_forever()

# --- ЗАПУСК ---
if __name__ == "__main__":
    threading.Thread(target=run_keepalive, daemon=True).start()
    print("✅ Бот запущен и работает 24/7...")
    bot.polling(none_stop=True)