import telebot
import os
import random
import requests
import threading
import time
import schedule
import sqlite3
import re
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import BotCommand
from io import BytesIO
# Добавьте в начало файла с другими импортами
try:
    from flask import Flask
    import threading
    
    web_app = Flask(__name__)
    
    @web_app.route('/')
    @web_app.route('/health')
    def health_check():
        return "🤖 Vibe Bot is running!", 200
    
    def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        web_app.run(host='0.0.0.0', port=port, debug=False)
    
    # Запускаем веб-сервер в фоновом потоке
    threading.Thread(target=run_web_server, daemon=True).start()
    print("✅ Flask сервер запущен")
except ImportError:
    print("⚠️ Flask не установлен, веб-сервер не запущен")
    
# ========== PIL ==========
try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ Pillow не установлен. Установите: pip install pillow")

# ========== КОНФИГ ==========
TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
BROADCAST_TIME = os.getenv("BROADCAST_TIME", "09:00")
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "Москва")

# ========== АДМИНИСТРАТОРЫ ==========
# Как получить свой ID: напишите @userinfobot в Telegram
# Замените 123456789 на ваш реальный ID
ADMIN_IDS = [
    300007969,  # ← ВАШ ID СЮДА (число без кавычек)
]

if not TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден")
    print("📝 Установите: export BOT_TOKEN='ваш_токен'")
    exit(1)

bot = telebot.TeleBot(TOKEN)
active_users = set()

# ========== SQLite БАЗА ДАННЫХ ==========
DB_PATH = "vibe_bot.db"

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            joined_date TEXT,
            last_active TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            thanks_given INTEGER DEFAULT 0,
            thanks_received INTEGER DEFAULT 0,
            compliments_given INTEGER DEFAULT 0,
            compliments_received INTEGER DEFAULT 0,
            memes_viewed INTEGER DEFAULT 0,
            weather_requests INTEGER DEFAULT 0,
            cards_created INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mood_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            mood TEXT,
            date TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_activity (
            user_id INTEGER,
            date TEXT,
            messages_count INTEGER DEFAULT 0,
            commands_used TEXT,
            PRIMARY KEY (user_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных SQLite инициализирована")

def upgrade_database_admin():
    """Добавляет таблицы для админ-панели"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Таблица заблокированных пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            blocked_at TEXT
        )
    ''')
    
    # Таблица логов действий администраторов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            target_user INTEGER,
            details TEXT,
            created_at TEXT
        )
    ''')
    
    # Таблица для хранения глобальных настроек
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Админ-таблицы добавлены")

def add_or_update_user(user_id, username, first_name, last_name=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, last_active)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, current_time))
    
    cursor.execute('''
        INSERT OR IGNORE INTO stats (user_id)
        VALUES (?)
    ''', (user_id,))
    
    conn.commit()
    conn.close()

def update_stat(user_id, stat_name, increment=1):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f'''
        UPDATE stats 
        SET {stat_name} = {stat_name} + ?
        WHERE user_id = ?
    ''', (increment, user_id))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM stats WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'thanks_given': result[1],
            'thanks_received': result[2],
            'compliments_given': result[3],
            'compliments_received': result[4],
            'memes_viewed': result[5],
            'weather_requests': result[6],
            'cards_created': result[7]
        }
    return None

def save_mood(user_id, mood):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = datetime.now().date().isoformat()
    cursor.execute('''
        INSERT INTO mood_history (user_id, mood, date)
        VALUES (?, ?, ?)
    ''', (user_id, mood, today))
    conn.commit()
    conn.close()

def get_mood_streak(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT date FROM mood_history 
        WHERE user_id = ? ORDER BY date DESC
    ''', (user_id,))
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not dates:
        return 0
    
    streak = 1
    yesterday = datetime.now().date() - timedelta(days=1)
    yesterday_str = yesterday.isoformat()
    
    for i, date_str in enumerate(dates):
        if i == 0 and date_str == datetime.now().date().isoformat():
            continue
        if date_str == yesterday_str:
            streak += 1
            yesterday_str = (datetime.fromisoformat(date_str) - timedelta(days=1)).date().isoformat()
        else:
            break
    return streak

def get_top_users(limit=5):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT users.user_id, users.username, users.first_name, 
               stats.thanks_received, stats.compliments_received
        FROM stats
        JOIN users ON users.user_id = stats.user_id
        WHERE stats.thanks_received > 0 OR stats.compliments_received > 0
        ORDER BY stats.thanks_received DESC, stats.compliments_received DESC
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def record_command(user_id, command):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = datetime.now().date().isoformat()
    cursor.execute('''
        INSERT INTO daily_activity (user_id, date, messages_count, commands_used)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
            messages_count = messages_count + 1,
            commands_used = commands_used || ',' || ?
    ''', (user_id, today, command, command))
    conn.commit()
    conn.close()

# ========== АДМИН-ФУНКЦИИ ==========

def is_admin(user_id):
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

def log_admin_action(admin_id, action, target_user=None, details=""):
    """Запись логов действий админов"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO admin_logs (admin_id, action, target_user, details, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (admin_id, action, target_user, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def is_blocked(user_id):
    """Проверка, заблокирован ли пользователь"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM blocked_users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def block_user(user_id, reason="", admin_id=None):
    """Блокировка пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO blocked_users (user_id, reason, blocked_at)
        VALUES (?, ?, ?)
    ''', (user_id, reason, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    if admin_id:
        log_admin_action(admin_id, "block", user_id, reason)

def unblock_user(user_id, admin_id=None):
    """Разблокировка пользователя"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM blocked_users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    if admin_id:
        log_admin_action(admin_id, "unblock", user_id)

def get_bot_stats():
    """Получение общей статистики бота"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    today = datetime.now().date().isoformat()
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM daily_activity WHERE date = ?', (today,))
    active_today = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(messages_count) FROM daily_activity')
    total_messages = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(compliments_given) FROM stats')
    total_compliments = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(memes_viewed) FROM stats')
    total_memes = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM blocked_users')
    total_blocked = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'active_today': active_today,
        'total_messages': total_messages,
        'total_compliments': total_compliments,
        'total_memes': total_memes,
        'total_blocked': total_blocked
    }

def get_active_users(limit=20):
    """Список активных пользователей"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, first_name, username, last_active 
        FROM users 
        ORDER BY last_active DESC 
        LIMIT ?
    ''', (limit,))
    results = cursor.fetchall()
    conn.close()
    return results

def admin_required(func):
    """Декоратор для проверки прав администратора"""
    def wrapper(message):
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "⛔ *Доступ запрещён!*\n\nЭта команда только для администраторов.", parse_mode='Markdown')
            return
        return func(message)
    return wrapper

# ========== AI ФУНКЦИИ ==========

def analyze_sentiment(text):
    positive_words = ['хорошо', 'отлично', 'прекрасно', 'классно', 'супер', 'люблю', 'рад', 'счастье', 'весело', 'круто']
    negative_words = ['плохо', 'грустно', 'печально', 'ужасно', 'проблема', 'больно', 'одиноко', 'тяжело', 'устал']
    
    text_lower = text.lower()
    if any(word in text_lower for word in positive_words):
        return "positive", "😊"
    elif any(word in text_lower for word in negative_words):
        return "negative", "😔"
    else:
        return "neutral", "😐"

def get_ai_advice(sentiment):
    if sentiment == "positive":
        advices = [
            "🌟 Твоя энергия заразительна! Поделись радостью с кем-нибудь.",
            "💫 Отличное настроение — время для новых свершений!",
            "🌈 Ты в потоке! Запиши свои мысли, они могут быть гениальными."
        ]
    elif sentiment == "negative":
        advices = [
            "🫂 Ты не один. Позволь себе отдохнуть сегодня.",
            "🌧️ Даже после дождя выходит солнце. Это временно.",
            "💪 Ты сильнее, чем думаешь. Сделай маленький шаг к себе."
        ]
    else:
        advices = [
            "🧘 Хороший день для саморефлексии. Что ты чувствуешь?",
            "📖 Отличный момент почитать книгу или посмотреть фильм.",
            "🌿 Наслаждайся моментом — сегодня спокойный день."
        ]
    return random.choice(advices)

def generate_vibe_quote():
    quotes = [
        "✨ Ты уже достаточно хорош. Прямо сейчас.",
        "💫 Твоё существование делает мир лучше.",
        "🌟 Счастье — это не цель, а способ путешествия.",
        "🌈 Улыбнись. Это улучшит настроение всем вокруг.",
        "💪 Ты пережил 100% своих плохих дней."
    ]
    return f"*Вайб-цитата:*\n\n{random.choice(quotes)}"

def get_ai_response(message_text, user_name):
    sentiment, emoji = analyze_sentiment(message_text)
    advice = get_ai_advice(sentiment)
    
    if sentiment == "positive":
        return f"{emoji} *{user_name}*, я чувствую твою радость!\n\n{advice}"
    elif sentiment == "negative":
        return f"{emoji} *{user_name}*, слышу тебя.\n\n{advice}\n\n🫂 Я здесь."
    else:
        return f"{emoji} *{user_name}*, спасибо за сообщение.\n\n{advice}"

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========

def get_top_news():
    # Альтернативные источники новостей
    news_sources = [
        "https://ria.ru/export/rss2/index.xml",      # РИА Новости
        "https://www.gazeta.ru/export/rss/first.xml",  # Газета.ру
        "https://news.yandex.ru/index.rss",           # Яндекс.Новости
    ]
    
    for source in news_sources:
        try:
            import xml.etree.ElementTree as ET
            response = requests.get(source, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = root.findall('.//item')[:5]
                news = []
                for i, item in enumerate(items, 1):
                    title = item.find('title')
                    title_text = title.text if title is not None else "Новость"
                    link = item.find('link')
                    link_text = link.text if link is not None else "#"
                    news.append(f"{i}. 📰 {title_text}\n   🔗 [Читать]({link_text})")
                return "📡 **СВЕЖИЕ НОВОСТИ:**\n\n" + "\n\n".join(news)
        except:
            continue
    
    # Если всё сломалось - показываем вдохновляющую цитату
    quotes = [
        "✨ Хорошие новости: сегодня ты молодец!",
        "💫 Лучшая новость: ты существуешь и это прекрасно!",
        "🌟 Новость дня: жизнь прекрасна прямо сейчас!"
    ]
    return f"📡 **НОВОСТИ ДНЯ:**\n\n{random.choice(quotes)}\n\n💫 Попробуй позже, сервер новостей отдыхает :)"

def get_vibe_photo():
    try:
        response = requests.get("https://picsum.photos/800/600", timeout=10)
        if response.status_code == 200:
            return BytesIO(response.content), "🌟 Вайб-фото дня"
    except:
        pass
    
    if PILLOW_AVAILABLE:
        try:
            img = Image.new('RGB', (800, 600), color='#1a1a2e')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
            except:
                font = ImageFont.load_default()
            draw.text((400, 300), "✨ Ты прекрасен", fill='white', anchor='mm', font=font)
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            return buffer, "🎨 Цифровой вайб"
        except:
            pass
    return None, None

def create_beautiful_card(text, user_name):
    if not PILLOW_AVAILABLE:
        return None
    try:
        width, height = 800, 600
        img = Image.new('RGB', (width, height), color='#1a1a2e')
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        except:
            font = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        for i in range(3):
            draw.rectangle([i, i, width-i, height-i], outline='#e94560', width=2)
        
        draw.text((width//2, 80), f"✨ ДЛЯ {user_name.upper()} ✨", fill='#e94560', anchor='mt', font=font)
        
        words = text.split()
        lines = []
        current_line = []
        for word in words:
            current_line.append(word)
            if len(' '.join(current_line)) > 30:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))
        
        y = 180
        for line in lines:
            draw.text((width//2, y), line, fill='#ffffff', anchor='mt', font=font_small)
            y += 50
        
        draw.text((width//2, height-50), f"🌟 Вайб-бот • {datetime.now().strftime('%d.%m.%Y')}", fill='#888888', anchor='mt', font=font_small)
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
    except:
        return None

def get_weather_with_vibe(city):
    if not WEATHER_API_KEY:
        return "⚠️ Ключ погоды не настроен"
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        r = requests.get(url, timeout=7)
        if r.status_code == 200:
            d = r.json()
            temp = d['main']['temp']
            return f"🌡 {temp}°C в {city}\n💨 Ветер: {d['wind']['speed']} м/с"
    except:
        pass
    return "😅 Не удалось загрузить погоду"

def get_astral_forecast():
    signs = ["🌟 Звёзды", "🌙 Луна", "☀️ Солнце"]
    return f"{random.choice(signs)}: Сегодня отличный день! ✨"

def get_random_meme():
    try:
        r = requests.get("https://meme-api.com/gimme", timeout=5)
        if r.status_code == 200:
            return r.json().get("url"), r.json().get("title", "Мем")
    except:
        pass
    return "https://http.cat/418.jpg", "Я чайник"

# ========== НАСТРОЙКА МЕНЮ ==========
def setup_bot_commands():
    commands = [
        BotCommand("start", "🏠 Главное меню"),
        BotCommand("meme", "🖼 Случайный мем"),
        BotCommand("news", "📰 Последние новости"),
        BotCommand("weather", "🌤 Погода"),
        BotCommand("make_card", "🎨 Создать открытку"),
        BotCommand("vibe_photo", "📸 Вайб-фото"),
        BotCommand("astral", "✨ Астральный прогноз"),
        BotCommand("compliment", "💫 Отправить комплимент"),
        BotCommand("advice", "🌟 Персональный совет"),
        BotCommand("stats", "📊 Моя статистика"),
        BotCommand("top", "🏆 Топ пользователей"),
        BotCommand("help", "❓ Помощь"),
        BotCommand("admin_stats", "👑 Статистика бота"),
        BotCommand("admin_users", "👥 Список пользователей"),
        BotCommand("admin_logs", "📋 Логи действий"),
        BotCommand("admin_help", "❓ Помощь админа"),
    ]
    try:
        bot.set_my_commands(commands)
        print("✅ Меню команд установлено")
    except Exception as e:
        print(f"⚠️ Ошибка: {e}")

# ========== ОБРАБОТЧИКИ КОМАНД ==========

@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    active_users.add(message.chat.id)
    
    add_or_update_user(user.id, user.username, user.first_name, user.last_name or "")
    stats = get_user_stats(user.id)
    streak = get_mood_streak(user.id)
    
    bot.reply_to(
        message,
        f"✨ *Привет, {user.first_name}!* ✨\n\n"
        f"🤖 Я *Вайб-бот* — твой цифровой друг.\n\n"
        f"📊 *Твоя статистика:*\n"
        f"   🙏 Благодарностей получено: {stats['thanks_received'] if stats else 0}\n"
        f"   💫 Комплиментов отправлено: {stats['compliments_given'] if stats else 0}\n"
        f"   🔥 Дней в вайбе: {streak}\n\n"
        f"✨ Напиши /help для всех команд",
        parse_mode='Markdown'
    )
    record_command(user.id, 'start')

@bot.message_handler(commands=['meme'])
def meme(message):
    user = message.from_user
    active_users.add(message.chat.id)
    update_stat(user.id, 'memes_viewed')
    record_command(user.id, 'meme')
    url, title = get_random_meme()
    bot.send_photo(message.chat.id, url, caption=title)

@bot.message_handler(commands=['news'])
def news(message):
    active_users.add(message.chat.id)
    record_command(message.from_user.id, 'news')
    bot.reply_to(message, get_top_news(), parse_mode='Markdown')

@bot.message_handler(commands=['weather'])
def weather(message):
    user = message.from_user
    active_users.add(message.chat.id)
    update_stat(user.id, 'weather_requests')
    record_command(user.id, 'weather')
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "🌤 *Пример:* `/weather Москва`", parse_mode='Markdown')
        return
    bot.reply_to(message, get_weather_with_vibe(parts[1]), parse_mode='Markdown')

@bot.message_handler(commands=['make_card'])
def make_card(message):
    user = message.from_user
    active_users.add(message.chat.id)
    
    text = message.text.replace('/make_card', '').strip()
    if not text:
        bot.reply_to(message, "🎨 *Напиши:* `/make_card Твой текст`", parse_mode='Markdown')
        return
    
    if not PILLOW_AVAILABLE:
        bot.reply_to(message, "❌ Pillow не установлен", parse_mode='Markdown')
        return
    
    update_stat(user.id, 'cards_created')
    record_command(user.id, 'make_card')
    
    card = create_beautiful_card(text, user.first_name)
    if card:
        bot.send_photo(message.chat.id, card, caption=f"🎨 *Открытка для {user.first_name}*", parse_mode='Markdown')
    else:
        bot.reply_to(message, "😅 Не удалось создать открытку")

@bot.message_handler(commands=['vibe_photo'])
def vibe_photo(message):
    active_users.add(message.chat.id)
    record_command(message.from_user.id, 'vibe_photo')
    photo, cap = get_vibe_photo()
    if photo:
        bot.send_photo(message.chat.id, photo, caption=cap)
    else:
        bot.reply_to(message, "🌟 Представь красивый закат... Это твоё вайб-фото!")

@bot.message_handler(commands=['astral'])
def astral(message):
    active_users.add(message.chat.id)
    record_command(message.from_user.id, 'astral')
    bot.reply_to(message, get_astral_forecast())

@bot.message_handler(commands=['compliment'])
def compliment(message):
    user = message.from_user
    active_users.add(message.chat.id)
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        compliments = ["🌟 Ты сияешь!", "💫 Ты уникален!", "🌈 Ты делаешь мир лучше!"]
        bot.reply_to(message, f"🎀 *Комплимент:*\n\n{random.choice(compliments)}", parse_mode='Markdown')
        return
    
    text = parts[1].strip()
    username_match = re.search(r'@(\w+)', text)
    
    if not username_match:
        bot.reply_to(message, "🌸 *Формат:* `/compliment @username`", parse_mode='Markdown')
        return
    
    username = username_match.group(1)
    compliments = ["💫 Ты невероятный человек!", "🌟 Твоя улыбка освещает всё вокруг!", "🌈 С тобой легко и радостно!"]
    
    update_stat(user.id, 'compliments_given')
    record_command(user.id, 'compliment')
    
    bot.reply_to(message, f"🎀 *Комплимент для @{username}:*\n\n{random.choice(compliments)}\n\n✨ От {user.first_name} с любовью!", parse_mode='Markdown')

@bot.message_handler(commands=['advice'])
def give_advice(message):
    user = message.from_user
    active_users.add(message.chat.id)
    record_command(user.id, 'advice')
    
    advice = get_ai_advice("neutral")
    quote = generate_vibe_quote()
    bot.reply_to(message, f"💫 *Совет для {user.first_name}*\n\n{advice}\n\n{quote}", parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    user = message.from_user
    active_users.add(message.chat.id)
    
    stats = get_user_stats(user.id)
    streak = get_mood_streak(user.id)
    
    if not stats:
        bot.reply_to(message, "📊 *У вас пока нет статистики*", parse_mode='Markdown')
        return
    
    stats_text = f"""
📊 *ТВОЯ СТАТИСТИКА* 📊

🙏 Благодарностей получено: {stats['thanks_received']}
💫 Комплиментов отправлено: {stats['compliments_given']}
🖼 Просмотрено мемов: {stats['memes_viewed']}
🌤 Запросов погоды: {stats['weather_requests']}
🎨 Создано открыток: {stats['cards_created']}
🔥 Дней в вайбе: {streak}
    """
    bot.reply_to(message, stats_text, parse_mode='Markdown')
    record_command(user.id, 'stats')

@bot.message_handler(commands=['top'])
def top_cmd(message):
    active_users.add(message.chat.id)
    record_command(message.from_user.id, 'top')
    
    top_users = get_top_users(5)
    
    if not top_users:
        bot.reply_to(message, "📊 *Статистика пока пуста*", parse_mode='Markdown')
        return
    
    top_list = []
    for i, user in enumerate(top_users, 1):
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, '📌')
        name = user[2] or user[1] or f"user_{user[0]}"
        top_list.append(f"{medal} {i}. {name} — 🙏 {user[3]} благодарностей")
    
    bot.reply_to(message, "🏆 *ТОП ПОЛЬЗОВАТЕЛЕЙ* 🏆\n\n" + "\n".join(top_list), parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_cmd(message):
    active_users.add(message.chat.id)
    help_text = """
✨ *КОМАНДЫ ВАЙБ-БОТА* ✨

/meme - 🖼 Мем
/make_card - 🎨 Открытка
/vibe_photo - 📸 Вайб-фото
/astral - 🔮 Астральный прогноз
/weather - 🌤 Погода
/news - 📰 Новости
/compliment - 💫 Комплимент
/advice - 🌟 Совет
/stats - 📊 Моя статистика
/top - 🏆 Топ
/start - 🏠 Меню
/help - ❓ Помощь
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

# ========== АДМИН-КОМАНДЫ ==========

@bot.message_handler(commands=['admin_stats'])
@admin_required
def admin_stats(message):
    stats = get_bot_stats()
    stats_text = f"""
📊 *СТАТИСТИКА БОТА* 📊

👥 Всего пользователей: {stats['total_users']}
📱 Активных сегодня: {stats['active_today']}
💬 Всего сообщений: {stats['total_messages']}
💫 Отправлено комплиментов: {stats['total_compliments']}
🖼 Просмотрено мемов: {stats['total_memes']}
🚫 Заблокировано: {stats['total_blocked']}
    """
    bot.reply_to(message, stats_text, parse_mode='Markdown')
    log_admin_action(message.from_user.id, "view_stats")

@bot.message_handler(commands=['admin_users'])
@admin_required
def admin_users(message):
    users = get_active_users(15)
    if not users:
        bot.reply_to(message, "📋 Нет активных пользователей")
        return
    user_list = []
    for i, user in enumerate(users, 1):
        user_id, first_name, username, last_active = user
        name = first_name or username or f"user_{user_id}"
        user_list.append(f"{i}. {name} — `{user_id}`")
    users_text = "📋 *АКТИВНЫЕ ПОЛЬЗОВАТЕЛИ:*\n\n" + "\n".join(user_list)
    bot.reply_to(message, users_text, parse_mode='Markdown')

@bot.message_handler(commands=['broadcast'])
@admin_required
def broadcast_command(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "📢 *Как сделать рассылку:*\n\n`/broadcast Текст сообщения`", parse_mode='Markdown')
        return
    
    broadcast_text = parts[1]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        bot.reply_to(message, "❌ Нет пользователей для рассылки")
        return
    
    msg = bot.reply_to(message, f"📡 Начинаю рассылку для {len(users)} пользователей...")
    
    success = 0
    fail = 0
    
    for user in users:
        user_id = user[0]
        try:
            bot.send_message(user_id, f"📢 *Сообщение от администратора:*\n\n{broadcast_text}", parse_mode='Markdown')
            success += 1
        except:
            fail += 1
        time.sleep(0.05)
    
    bot.edit_message_text(f"✅ *Рассылка завершена!*\n\n📨 Отправлено: {success}\n❌ Не доставлено: {fail}", message.chat.id, msg.message_id, parse_mode='Markdown')
    log_admin_action(message.from_user.id, "broadcast", details=f"sent to {success} users")

@bot.message_handler(commands=['block'])
@admin_required
def block_command(message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        bot.reply_to(message, "🚫 *Как заблокировать:*\n`/block 123456789 причина`", parse_mode='Markdown')
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя")
        return
    reason = parts[2] if len(parts) > 2 else "Не указана"
    block_user(user_id, reason, message.from_user.id)
    bot.reply_to(message, f"✅ *Пользователь заблокирован!*\n\nID: `{user_id}`", parse_mode='Markdown')

@bot.message_handler(commands=['unblock'])
@admin_required
def unblock_command(message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "🔓 *Как разблокировать:*\n`/unblock 123456789`", parse_mode='Markdown')
        return
    try:
        user_id = int(parts[1])
    except ValueError:
        bot.reply_to(message, "❌ Неверный ID пользователя")
        return
    unblock_user(user_id, message.from_user.id)
    bot.reply_to(message, f"✅ *Пользователь разблокирован!*\n\nID: `{user_id}`", parse_mode='Markdown')

@bot.message_handler(commands=['admin_logs'])
@admin_required
def admin_logs(message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT admin_id, action, target_user, details, created_at FROM admin_logs ORDER BY created_at DESC LIMIT 10')
    logs = cursor.fetchall()
    conn.close()
    if not logs:
        bot.reply_to(message, "📋 Логов пока нет")
        return
    log_text = "📋 *ПОСЛЕДНИЕ ДЕЙСТВИЯ:*\n\n"
    for log in logs:
        admin_id, action, target, details, created_at = log
        target_text = f" на `{target}`" if target else ""
        log_text += f"• `{admin_id}` → {action}{target_text}\n  _{created_at[:19]}_\n\n"
    bot.reply_to(message, log_text, parse_mode='Markdown')

# ========== УМНЫЙ ОБРАБОТЧИК ТЕКСТА С AI ==========

@bot.message_handler(func=lambda message: True)
def smart_handle_text(message):
    """Умная обработка текстовых сообщений с AI-анализом настроения"""
    user = message.from_user
    text = message.text.lower().strip()
    active_users.add(message.chat.id)
    record_command(user.id, 'chat')
    
    # Погода через текст
    if text.startswith("погода "):
        city = message.text.split(maxsplit=1)[1]
        bot.send_message(message.chat.id, get_weather_with_vibe(city), parse_mode='Markdown')
        return
    
    # Приветствия
    if text in ["привет", "здравствуй", "ку", "hi", "hello", "здарова", "доброе утро", "добрый день", "добрый вечер"]:
        greetings = [
            f"👋 Привет, {user.first_name}! Как твоё настроение сегодня? 😊",
            f"✨ Здравствуй, {user.first_name}! Рад(а) тебя видеть! 💫",
            f"🌟 {user.first_name}, привет! Чем могу помочь? Напиши /help",
            f"💫 О, {user.first_name}! Рассказывай, как дела?"
        ]
        bot.reply_to(message, random.choice(greetings))
        return
    
    # Вопросы о боте
    if any(q in text for q in ["кто ты", "что ты умеешь", "твои команды", "расскажи о себе", "как тебя зовут"]):
        bot.reply_to(message, 
            "🤖 *Я Вайб-бот* — твой цифровой друг с душой!\n\n"
            "📱 Мои команды: /help\n\n"
            "💫 *Я умею:*\n"
            "• 🧠 Понимать твоё настроение по тексту\n"
            "• 💡 Давать персональные советы\n"
            "• 🖼 Отправлять мемы и открытки\n"
            "• 📸 Показывать вдохновляющие фото\n"
            "• 🔮 Делать астральные прогнозы\n"
            "• 💫 Отправлять комплименты\n\n"
            "✨ *Просто напиши мне что-нибудь!* Я пойму твоё настроение.",
            parse_mode='Markdown')
        return
    
    # Благодарности
    if any(t in text for t in ["спасибо", "thanks", "благодарю", "спс"]):
        thanks_responses = [
            f"🙏 Пожалуйста, {user.first_name}! Мне приятно быть полезным. 💫",
            f"💖 Обращайся, {user.first_name}! Всегда рад помочь.",
            f"✨ Спасибо тебе за добрые слова, {user.first_name}!"
        ]
        bot.reply_to(message, random.choice(thanks_responses))
        update_stat(user.id, 'thanks_received')
        return
    
    # Вопросы о настроении
    if any(q in text for q in ["как дела", "как настроение", "что нового", "как ты", "как сам"]):
        mood_responses = [
            f"😊 У меня отлично, {user.first_name}! Особенно когда ты рядом в чате.\n\nА как твои дела? Расскажи, я пойму твоё настроение! 💫",
            f"✨ Я в полном вайбе, {user.first_name}! Спасибо, что спросил(а).\n\nА у тебя как настроение?",
            f"🌈 Прекрасно, {user.first_name}! Живу в моменте и радуюсь общению с тобой.\n\nРасскажи что-нибудь о себе!"
        ]
        bot.reply_to(message, random.choice(mood_responses))
        return
    
    # ========== ОСНОВНОЙ AI АНАЛИЗ ==========
    # Для всех остальных сообщений — анализ настроения и умный ответ
    
    bot.send_chat_action(message.chat.id, 'typing')
    time.sleep(0.5)  # Создаём эффект "думающего" бота
    
    # Получаем AI ответ на основе анализа настроения
    sentiment, emoji = analyze_sentiment(message.text)
    advice = get_ai_advice(sentiment)
    quote = generate_vibe_quote()
    
    # Формируем ответ в зависимости от настроения
    if sentiment == "positive":
        response = (
            f"{emoji} *{user.first_name}*, я чувствую твою радость! 🎉\n\n"
            f"{advice}\n\n"
            f"{quote}\n\n"
            f"✨ Хочешь отправить /compliment кому-то или посмотреть /meme?"
        )
    elif sentiment == "negative":
        response = (
            f"{emoji} *{user.first_name}*, спасибо, что делишься. Я слышу тебя. 🫂\n\n"
            f"{advice}\n\n"
            f"{quote}\n\n"
            f"🫂 Напиши /vibe_photo для вдохновения или /advice для совета.\n\n"
            f"🌟 Помни: это временно, и ты не один."
        )
    else:
        response = (
            f"{emoji} *{user.first_name}*, спасибо за сообщение! 💫\n\n"
            f"{advice}\n\n"
            f"{quote}\n\n"
            f"💫 Может, посмотришь /meme, /astral или создашь /make_card?"
        )
    
    bot.reply_to(message, response, parse_mode='Markdown')
    
    # Сохраняем настроение в историю (если определили)
    if sentiment != "neutral":
        save_mood(user.id, sentiment)

# ========== РАССЫЛКА ==========
def job_daily_broadcast():
    if not active_users:
        return
    weather = get_weather_with_vibe(DEFAULT_CITY)
    for uid in list(active_users):
        try:
            bot.send_message(uid, f"🌅 Доброе утро!\n\n{weather}", parse_mode='Markdown')
            time.sleep(0.3)
        except:
            active_users.discard(uid)

def run_scheduler():
    schedule.every().day.at(BROADCAST_TIME).do(job_daily_broadcast)
    print(f"⏰ Планировщик: рассылка в {BROADCAST_TIME} UTC")
    while True:
        schedule.run_pending()
        time.sleep(10)

# ========== СЕРВЕР ==========
PORT = int(os.environ.get("PORT", 8080))

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write("✨ Vibe Bot is alive! ✨".encode('utf-8'))
    def log_message(self, format, *args): pass

def run_server():
    try:
        server = HTTPServer(('0.0.0.0', PORT), KeepAliveHandler)
        print(f"🌐 Сервер на порту {PORT}")
        server.serve_forever()
    except:
        print(f"⚠️ Порт {PORT} занят")

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🚀 Запуск Вайб-бота...")
    
    init_database()
    upgrade_database_admin()
    
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ {e}")
    
    time.sleep(1)
    setup_bot_commands()
    
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    print("✅ Бот готов! Напишите /start в Telegram")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=30)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            time.sleep(10)
