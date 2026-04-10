import telebot
import os
import random
import requests
import threading
import time
import re
import schedule
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import BotCommand
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

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

# --- НАСТРОЙКА МЕНЮ (С ПРОВЕРКОЙ) ---
def setup_bot_commands():
    """Устанавливает команды для кнопки меню"""
    commands = [
        BotCommand("start", "🏠 Главное меню"),
        BotCommand("meme", "🖼 Случайный мем"),
        BotCommand("news", "📰 Последние новости"),
        BotCommand("weather", "🌤 Погода в городе"),
        BotCommand("make_card", "🎨 Создать открытку"),
        BotCommand("vibe_photo", "📸 Вайб-фото дня"),
        BotCommand("astral", "✨ Астральный прогноз"),
        BotCommand("help", "❓ Помощь")
    ]
    
    try:
        # Пробуем установить команды
        result = bot.set_my_commands(commands)
        print(f"✅ Команды установлены: {result}")
        
        # Проверяем, что установилось
        current_commands = bot.get_my_commands()
        print(f"📋 Текущие команды: {[c.command for c in current_commands]}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка установки команд: {e}")
        print("⚠️ Установите команды вручную через @BotFather")
        return False

# --- МЕДИА-ФУНКЦИИ ---

def create_beautiful_card(text, user_name):
    """Создаёт красивую открытку с текстом"""
    try:
        width, height = 800, 600
        image = Image.new('RGB', (width, height), color='#1a1a2e')
        draw = ImageDraw.Draw(image)
        
        try:
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font_title = ImageFont.load_default()
            font_text = ImageFont.load_default()
        
        # Рисуем рамку
        for i in range(5):
            draw.rectangle([i, i, width-i, height-i], outline=f'#{random.randint(100, 200):02x}{random.randint(100, 200):02x}{random.randint(100, 200):02x}', width=2)
        
        draw.text((width//2, 100), f"✨ ДЛЯ {user_name.upper()} ✨", fill='#e94560', anchor='mt', font=font_title)
        
        # Перенос текста
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            if len(' '.join(current_line)) > 30:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        lines.append(' '.join(current_line))
        
        y = 200
        for line in lines:
            draw.text((width//2, y), line, fill='#ffffff', anchor='mt', font=font_text)
            y += 40
        
        draw.text((width//2, height-80), f"🌟 Вайб-бот • {datetime.now().strftime('%d.%m.%Y')}", fill='#888888', anchor='mt', font=font_text)
        
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer
    except Exception as e:
        print(f"Ошибка создания открытки: {e}")
        return None

def get_vibe_photo():
    """Получает красивое фото для вайб-настроения"""
    try:
        url = "https://source.unsplash.com/random/800x600/?nature,peaceful,calm"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return BytesIO(response.content), "🌟 Вайб-фото дня"
    except:
        pass
    
    try:
        img = Image.new('RGB', (800, 600), color=f'#{random.randint(50, 100):02x}{random.randint(50, 100):02x}{random.randint(100, 150):02x}')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer, "🎨 Цифровой вайб"
    except:
        return None, None

def get_astral_forecast():
    """Генерирует астральный прогноз"""
    signs = ["🌟 Звёзды", "🌙 Луна", "☀️ Солнце", "💫 Меркурий", "✨ Венера"]
    energies = ["высокая", "гармоничная", "спокойная", "игривая", "медитативная"]
    advices = [
        "позволь себе отдохнуть", "скажи кому-то тёплые слова", 
        "сделай что-то для себя", "выйди на прогулку", "послушай любимую музыку"
    ]
    
    forecast = f"""
{random.choice(signs)} *Астральный прогноз на сегодня*

✨ Энергия дня: {random.choice(energies)}
💫 Цвет дня: #{random.randint(0, 255):02x}{random.randint(0, 255):02x}{random.randint(0, 255):02x}
🕯️ Камень дня: {random.choice(['Аметист', 'Розовый кварц', 'Лабрадор', 'Лунный камень'])}
🌸 Аромат дня: {random.choice(['Лаванда', 'Сандал', 'Жасмин', 'Мята'])}
🎵 Частота дня: {random.randint(111, 999)} Hz

📜 *Послание:* {random.choice(advices)}

🌙 Хорошего дня в гармонии со вселенной!
    """
    return forecast

def get_weather_with_vibe(city):
    """Погода + вайб-совет"""
    if not WEATHER_API_KEY:
        return "⚠️ Ключ погоды не настроен."
    
    try:
        res = requests.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru", timeout=7)
        if res.status_code == 200:
            d = res.json()
            temp = d['main']['temp']
            feels = d['main']['feels_like']
            condition = d['weather'][0]['description']
            
            if temp < 0:
                vibe_advice = "☕ Время горячего чая и уютного пледа!"
            elif temp < 10:
                vibe_advice = "🧥 Оденься теплее, но не забудь улыбнуться!"
            elif temp < 20:
                vibe_advice = "🌿 Идеальная погода для прогулки!"
            else:
                vibe_advice = "🍦 Мороженое и тень — твои друзья сегодня!"
            
            weather_emoji = {
                'ясно': '☀️', 'солнечно': '😎', 'дождь': '🌧️',
                'облачно': '☁️', 'снег': '❄️', 'туман': '🌫️'
            }.get(condition, '🌈')
            
            return f"""
{weather_emoji} *{city.upper()}* прямо сейчас

🌡️ {temp}°C (ощущается как {feels}°C)
💨 Ветер: {d['wind']['speed']} м/с
💧 Влажность: {d['main']['humidity']}%

{weather_emoji} *Вайб-совет:* {vibe_advice}

✨ Хорошего дня в гармонии с погодой!
            """
        elif res.status_code == 404:
            return f"🌍 Город '{city}' не найден.\nПопробуй: Москва, London, Paris"
    except:
        pass
    return "😅 Не удалось загрузить погоду."

def get_random_meme():
    try:
        res = requests.get("https://meme-api.com/gimme", timeout=5)
        if res.status_code == 200:
            return res.json().get("url"), res.json().get("title", "Мем 🎭")
    except:
        pass
    return "https://http.cat/418.jpg", "Я чайник ☕"

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
                news_list.append(f"{i}. 📰 {title}\n   🔗 [Читать]({link})")
            return "\n\n".join(news_list)
    except:
        pass
    return "😅 Новости временно недоступны."

# --- ОБРАБОТЧИКИ С ОТЛАДКОЙ ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /start")
    
    bot.reply_to(
        message,
        f"✨ *Привет, {message.from_user.first_name}!* ✨\n\n"
        f"🤖 Я *Вайб-бот* — твой цифровой друг.\n\n"
        f"📱 Нажми на кнопку ☰ в левом нижнем углу\n"
        f"   чтобы открыть меню команд!\n\n"
        f"🎨 *Мои возможности:*\n"
        f"   • 🖼 /meme - Случайный мем\n"
        f"   • 📰 /news - Последние новости\n"
        f"   • 🌤 /weather - Погода с вайб-советом\n"
        f"   • 🎨 /make_card - Создать открытку\n"
        f"   • 📸 /vibe_photo - Вайб-фото дня\n"
        f"   • 🔮 /astral - Астральный прогноз\n\n"
        f"🌟 Напиши /help для всех команд\n\n"
        f"📅 Рассылка новостей каждый день в {BROADCAST_TIME} UTC\n\n"
        f"_Твой идеальный день начинается здесь!_",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['meme'])
def cmd_meme(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /meme")
    
    bot.send_chat_action(message.chat.id, 'upload_photo')
    bot.reply_to(message, "🖼 Ищу самый вайбовый мем... 😂")
    
    url, title = get_random_meme()
    bot.send_photo(message.chat.id, url, caption=f"🎭 *{title}*\n\n✨ Смех продлевает жизнь!", parse_mode='Markdown')

@bot.message_handler(commands=['news'])
def cmd_news(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /news")
    
    bot.send_chat_action(message.chat.id, 'typing')
    bot.reply_to(message, "📡 Загружаю свежие новости с любовью... 💫")
    news = get_top_news()
    bot.send_message(message.chat.id, f"📰 *Новости дня*\n\n{news}\n\n✨ Будь в курсе с вайбом!", parse_mode='Markdown')

@bot.message_handler(commands=['weather'])
def cmd_weather_vibe(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /weather")
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message,
            "🌤 *Вайб-погода*\n\n"
            "Напиши: `/weather Москва`\n\n"
            "✨ Получишь не просто температуру, а совет для настроения!",
            parse_mode='Markdown')
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(0.3)
    
    city = parts[1].strip()
    bot.reply_to(message, f"🔮 Смотрю в хрустальный шар для {city}... ✨")
    
    weather_info = get_weather_with_vibe(city)
    bot.send_message(message.chat.id, weather_info, parse_mode='Markdown')

@bot.message_handler(commands=['make_card'])
def cmd_make_card(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /make_card")
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    text = message.text.replace('/make_card', '').strip()
    if not text:
        bot.reply_to(message, 
            "🎨 *Как создать открытку:*\n\n"
            "Напиши: `/make_card Твой текст здесь`\n\n"
            "✨ Например: `/make_card Ты супер!`",
            parse_mode='Markdown')
        return
    
    bot.reply_to(message, "🎨 Создаю твою открытку... Это займёт пару секунд ✨")
    
    card = create_beautiful_card(text, message.from_user.first_name)
    
    if card:
        bot.send_photo(
            message.chat.id,
            card,
            caption=f"🎨 *Открытка для {message.from_user.first_name}*\n\n💫 {text}\n\n✨ Сохрани этот момент!",
            parse_mode='Markdown'
        )
    else:
        bot.reply_to(message, "😅 Не удалось создать открытку, но ты всё равно супер! 💫")

@bot.message_handler(commands=['vibe_photo'])
def cmd_vibe_photo(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /vibe_photo")
    
    bot.send_chat_action(message.chat.id, 'upload_photo')
    bot.reply_to(message, "📸 Ищу вдохновение для тебя... 🌟")
    
    photo, caption = get_vibe_photo()
    
    if photo:
        bot.send_photo(
            message.chat.id,
            photo,
            caption=f"📸 *Вайб-фото дня*\n\n{caption}\n\n✨ Пусть этот день будет прекрасным, {message.from_user.first_name}!",
            parse_mode='Markdown'
        )
    else:
        bot.reply_to(message, 
            f"🌈 *Визуализация настроения*\n\n"
            f"Представь: {random.choice(['закат на море', 'лес в тумане', 'горные вершины', 'тихое утро'])}...\n\n"
            f"✨ Это твоё вайб-фото сегодня!",
            parse_mode='Markdown')

@bot.message_handler(commands=['astral'])
def cmd_astral(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /astral")
    
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(0.5)
    
    forecast = get_astral_forecast()
    bot.reply_to(message, forecast, parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def cmd_help(message):
    active_users.add(message.chat.id)
    print(f"📱 Пользователь {message.from_user.id} вызвал /help")
    
    help_text = """
✨ *КОМАНДЫ ВАЙБ-БОТА* ✨

🎨 *МЕДИА И РАЗВЛЕЧЕНИЯ*
/meme - 🖼 Случайный мем
/make_card - 🎨 Создать красивую открытку
/vibe_photo - 📸 Вдохновляющее фото дня
/astral - 🔮 Астральный прогноз

🌤 *ИНФОРМАЦИЯ*
/weather - 🌤 Погода с вайб-советом
/news - 📰 Последние новости

🌟 *ОСНОВНЫЕ*
/start - 🏠 Главное меню
/help - ❓ Это сообщение

📅 *АВТОМАТИЧЕСКАЯ РАССЫЛКА*
Каждый день в {BROADCAST_TIME} UTC

💫 *Совет:* Нажми на кнопку ☰ в левом нижнем углу!
    """
    bot.reply_to(message, help_text.format(BROADCAST_TIME=BROADCAST_TIME), parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработка текстовых сообщений"""
    active_users.add(message.chat.id)
    text = message.text.lower().strip()
    
    if text.startswith("погода "):
        city = message.text.split(maxsplit=1)[1]
        bot.send_message(message.chat.id, get_weather_with_vibe(city), parse_mode='Markdown')
    elif text in ["привет", "здравствуй", "hi", "hello", "ку"]:
        bot.reply_to(message, f"👋 Привет, {message.from_user.first_name}! Напиши /help чтобы узнать мои команды ✨")
    elif text in ["помощь", "help", "команды"]:
        cmd_help(message)

# --- РАССЫЛКА ---

def job_daily_broadcast():
    if not active_users:
        print("📡 Нет активных пользователей")
        return
    
    print(f"📡 Вайб-рассылка для {len(active_users)} пользователей...")
    
    weather = get_weather_with_vibe(DEFAULT_CITY)
    news = get_top_news()
    
    msg = f"""
🌅 *ДОБРОЕ ВАЙБ-УТРО!* 🌅

📰 *Новость дня:*
{news[:200]}...

🌤 *Погода сегодня:*
{weather}

💫 *Вайб-напоминание:*
Ты уникален. Твой день будет прекрасным.
Сделай что-то доброе для себя сегодня.

✨ Нажми на кнопку ☰ для всех команд!
    """
    
    success_count = 0
    for uid in list(active_users):
        try:
            bot.send_message(uid, msg, parse_mode='Markdown')
            success_count += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"⚠️ Ошибка {uid}: {e}")
            active_users.discard(uid)
    
    print(f"✅ Вайб-рассылка завершена. Отправлено: {success_count}")

# --- СЕРВЕР ---

PORT = int(os.environ.get("PORT", 8080))

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        message = "✨ Vibe Bot is alive and full of positive energy! ✨"
        self.wfile.write(message.encode('utf-8'))
    
    def log_message(self, format, *args): 
        pass

def run_server():
    try:
        server = HTTPServer(('0.0.0.0', PORT), KeepAliveHandler)
        print(f"🌐 HTTP сервер запущен на порту {PORT}")
        server.serve_forever()
    except OSError as e:
        if e.errno == 98:
            print(f"⚠️ Порт {PORT} уже занят, пропускаем HTTP сервер")
        else:
            print(f"❌ Ошибка сервера: {e}")
    except Exception as e:
        print(f"❌ Ошибка сервера: {e}")

def run_scheduler():
    schedule.every().day.at(BROADCAST_TIME).do(job_daily_broadcast)
    print(f"⏰ Планировщик: вайб-рассылка в {BROADCAST_TIME} UTC")
    while True:
        schedule.run_pending()
        time.sleep(10)

# --- ЗАПУСК ---

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════╗
    ║                                           ║
    ║     🎧 VIBE BOT (ОБЛЕГЧЁННАЯ ВЕРСИЯ) 🎧   ║
    ║                                           ║
    ║   ✨ Мемы | Новости | Погода              ║
    ║   🎨 Открытки | Вайб-фото | Астральный    ║
    ║                                           ║
    ╚═══════════════════════════════════════════╝
    """)
    
    # Принудительно удаляем webhook
    print("🔄 Очищаем webhook...")
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ Ошибка удаления webhook: {e}")
    
    time.sleep(1)
    
    # Устанавливаем команды
    setup_bot_commands()
    
    # Запускаем сервер и планировщик
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    print("✅ Бот запущен!")
    print("📱 Откройте чат с ботом и напишите /start")
    print("📋 Проверьте, что команды появились в меню (кнопка ☰)")
    
    # Запускаем бота
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=30)
        except Exception as e:
            print(f"❌ Ошибка polling: {e}")
            print("🔄 Перезапуск через 10 секунд...")
            time.sleep(10)