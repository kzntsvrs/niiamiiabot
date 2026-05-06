import telebot
import os
import random
import requests
import sqlite3
import time
from datetime import datetime, timedelta
from telebot.types import BotCommand
from io import BytesIO
import threading
import sys
import fcntl
import os

# Защита от множественного запуска
def lock_instance():
    try:
        with open('/tmp/bot.lock', 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("✅ Блокировка получена, бот запущен")
    except:
        print("❌ Бот уже запущен! Выход...")
        sys.exit(0)

lock_instance()
# ========== FLASK ДЛЯ RENDER (ОБЯЗАТЕЛЬНО) ==========
try:
    from flask import Flask
    from threading import Thread
    
    web_app = Flask(__name__)
    
    @web_app.route('/')
    @web_app.route('/health')
    def health_check():
        return "🤖 Vibe Bot is running!", 200
    
    def run_web_server():
        port = int(os.environ.get("PORT", 8080))
        web_app.run(host='0.0.0.0', port=port, debug=False)
    
    # Запускаем Flask в отдельном потоке
    Thread(target=run_web_server, daemon=True).start()
    print("✅ Flask сервер запущен на порту", os.environ.get("PORT", 8080))
except ImportError:
    print("⚠️ Flask не установлен, веб-сервер не запущен")

# ========== КОНФИГ ==========
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден")
    print("📝 Добавьте переменную окружения BOT_TOKEN в Render")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# ========== SQLite БАЗА ДАННЫХ ==========
DB_PATH = "/tmp/vibe_bot.db"  # Render использует /tmp для временных файлов

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Пользователи
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_active TEXT
        )
    ''')
    
    # Статистика
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            user_id INTEGER PRIMARY KEY,
            memes_viewed INTEGER DEFAULT 0
        )
    ''')
    
    # Списки покупок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shopping_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            created_at TEXT
        )
    ''')
    
    # Товары в списках
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shopping_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id INTEGER,
            item_name TEXT,
            is_checked BOOLEAN DEFAULT 0,
            created_at TEXT
        )
    ''')
    
    # Заметки
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            content TEXT,
            category TEXT DEFAULT 'Общее',
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована в", DB_PATH)

def add_or_update_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    current_time = datetime.now().isoformat()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_active)
        VALUES (?, ?, ?, ?)
    ''', (user_id, username, first_name, current_time))
    
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

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========

import vk_api
import random
import requests
import os

# ========== НАСТРОЙКА VK ==========
VK_TOKEN = os.getenv("VK_TOKEN")  # Сервисный ключ

def get_random_meme_from_vk():
    """
    Получает случайный мем из VK-паблика через сервисный ключ
    """
    if not VK_TOKEN:
        print("⚠️ VK_TOKEN не настроен, использую резервный источник")
        return get_random_meme_fallback()
    
    try:
        print("🔄 Запрос к VK API...")
        vk_session = vk_api.VkApi(token=VK_TOKEN)
        vk = vk_session.get_api()
        
        # ID групп, которые точно работают с сервисным ключом
        meme_groups = [-102532714, -104564583, -162888774]  # популярные паблики
        
        group_id = random.choice(meme_groups)
        print(f"📢 Выбрана группа: {group_id}")
        
        wall_posts = vk.wall.get(
            owner_id=group_id,
            count=50,
            filter='owner',
            extended=0
        )
        
        memes = []
        for post in wall_posts['items']:
            if 'attachments' in post:
                for attachment in post['attachments']:
                    if attachment['type'] == 'photo':
                        sizes = attachment['photo']['sizes']
                        max_size = max(sizes, key=lambda x: x['width'] * x['height'])
                        caption = post.get('text', '')[:200]
                        if not caption:
                            caption = "🎭 Мем из VK"
                        else:
                            caption = caption.replace('\n', ' ').strip()
                        
                        memes.append({
                            'url': max_size['url'],
                            'caption': caption
                        })
        
        if memes:
            meme = random.choice(memes)
            print(f"✅ Мем найден: {meme['url'][:50]}...")
            return meme['url'], meme['caption']
        else:
            print("⚠️ Мемы не найдены в постах, использую резерв")
            return get_random_meme_fallback()
            
    except Exception as e:
        print(f"❌ Ошибка VK API: {e}")
        return get_random_meme_fallback()

def get_random_meme_fallback():
    """Резервный источник мемов (без VK)"""
    fallback_memes = [
        ("https://i.imgflip.com/1bij.jpg", "🤣 Это хорошо?"),
        ("https://i.imgflip.com/26am.jpg", "😄 Всегда было"),
        ("https://i.imgflip.com/22bd.jpg", "🎭 Здесь могла быть ваша реклама"),
        ("https://http.cat/418.jpg", "🫖 Я чайник (мем не загрузился)"),
    ]
    return random.choice(fallback_memes)

def get_vibe_photo():
    try:
        response = requests.get("https://picsum.photos/800/600", timeout=10)
        if response.status_code == 200:
            return BytesIO(response.content), "🌟 Вайб-фото дня"
    except:
        pass
    return None, None

def get_top_news():
    # Упрощённая версия без RSS, чтобы не падало
    quotes = [
        "✨ Хорошие новости: сегодня ты молодец!",
        "💫 Лучшая новость: ты существуешь и это прекрасно!",
        "🌟 Новость дня: жизнь прекрасна прямо сейчас!"
    ]
    return f"📡 **НОВОСТИ ДНЯ:**\n\n{random.choice(quotes)}"

def get_weather(city):
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "570b5fda9c1c64963ec8e36a2795e2d1")
    if not WEATHER_API_KEY:
        return "⚠️ Ключ погоды не настроен. Добавьте переменную WEATHER_API_KEY в Render"
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        r = requests.get(url, timeout=7)
        if r.status_code == 200:
            d = r.json()
            temp = d['main']['temp']
            feels_like = d['main']['feels_like']
            humidity = d['main']['humidity']
            wind = d['wind']['speed']
            weather_desc = d['weather'][0]['description']
            return f"🌡 *{city}*:\n{weather_desc}\n🌡 {temp}°C (ощущается как {feels_like}°C)\n💧 Влажность: {humidity}%\n💨 Ветер: {wind} м/с"
    except:
        pass
    return f"😅 Не удалось загрузить погоду для {city}"

# ========== ЗАМЕТКИ ==========

def create_note(user_id, title, content, category="Общее"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO notes (user_id, title, content, category, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, title, content, category, now, now))
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id

def get_notes(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, content, category, created_at FROM notes WHERE user_id = ? ORDER BY updated_at DESC', (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def search_notes(user_id, query):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, content, category 
        FROM notes 
        WHERE user_id = ? AND (title LIKE ? OR content LIKE ?)
        ORDER BY updated_at DESC
    ''', (user_id, f'%{query}%', f'%{query}%'))
    results = cursor.fetchall()
    conn.close()
    return results

def delete_note(note_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
    conn.commit()
    conn.close()

# ========== СПИСКИ ПОКУПОК ==========

def create_shopping_list(user_id, name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO shopping_lists (user_id, name, created_at)
        VALUES (?, ?, ?)
    ''', (user_id, name, datetime.now().isoformat()))
    list_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return list_id

def get_shopping_lists(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name FROM shopping_lists WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def add_item_to_list(list_id, item_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO shopping_items (list_id, item_name, created_at)
        VALUES (?, ?, ?)
    ''', (list_id, item_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_list_items(list_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, item_name, is_checked FROM shopping_items WHERE list_id = ? ORDER BY is_checked, created_at', (list_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def toggle_item(item_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE shopping_items SET is_checked = NOT is_checked WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()

def delete_list(list_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM shopping_items WHERE list_id = ?', (list_id,))
    cursor.execute('DELETE FROM shopping_lists WHERE id = ?', (list_id,))
    conn.commit()
    conn.close()

# ========== НАСТРОЙКА МЕНЮ ==========
def setup_bot_commands():
    commands = [
        BotCommand("start", "🏠 Главное меню"),
        BotCommand("meme", "🖼 Случайный мем"),
        BotCommand("vibe_photo", "📸 Вайб-фото"),
        BotCommand("weather", "🌤 Погода"),
        BotCommand("news", "📰 Новости"),
        BotCommand("shopping", "🛒 Список покупок"),
        BotCommand("notes", "📝 Мои заметки"),
        BotCommand("search", "🔍 Поиск по заметкам"),
        BotCommand("help", "❓ Помощь"),
    ]
    try:
        bot.set_my_commands(commands)
        print("✅ Меню команд установлено")
    except Exception as e:
        print(f"⚠️ Ошибка установки команд: {e}")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========

@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    add_or_update_user(user.id, user.username, user.first_name)
    
    bot.reply_to(
        message,
        f"✨ *Привет, {user.first_name}!* ✨\n\n"
        f"🤖 Я *Вайб-бот* — твой цифровой помощник.\n\n"
        f"📱 *Мои возможности:*\n"
        f"• 🖼 Мемы для поднятия настроения\n"
        f"• 📸 Вдохновляющие фото\n"
        f"• 🌤 Погода в любом городе\n"
        f"• 📰 Свежие новости\n"
        f"• 🛒 Списки покупок\n"
        f"• 📝 Заметки и идеи\n\n"
        f"🔍 Напиши /help для всех команд",
        parse_mode='Markdown'
    )

@bot.message_handler(commands=['meme'])
def meme(message):
    user = message.from_user
    update_stat(user.id, 'memes_viewed')
    url, title = get_random_meme()
    bot.send_photo(message.chat.id, url, caption=title)

@bot.message_handler(commands=['vibe_photo'])
def vibe_photo(message):
    photo, cap = get_vibe_photo()
    if photo:
        bot.send_photo(message.chat.id, photo, caption=cap)
    else:
        bot.reply_to(message, "🌟 Представь красивый закат... Это твоё вайб-фото!")

@bot.message_handler(commands=['weather'])
def weather(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "🌤 *Пример:* `/weather Москва`", parse_mode='Markdown')
        return
    bot.reply_to(message, get_weather(parts[1]), parse_mode='Markdown')

@bot.message_handler(commands=['news'])
def news(message):
    bot.reply_to(message, get_top_news(), parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_cmd(message):
    help_text = """
✨ *КОМАНДЫ ВАЙБ-БОТА* ✨

**🎉 Развлечения:**
/meme - 🖼 Случайный мем
/vibe_photo - 📸 Вайб-фото

**🌍 Информация:**
/weather - 🌤 Погода в городе
/news - 📰 Последние новости

**📝 Организация:**
/shopping - 🛒 Списки покупок
/notes - 📝 Все заметки
/search - 🔍 Поиск по заметкам

**ℹ️ Прочее:**
/start - 🏠 Главное меню
/help - ❓ Эта справка

📌 *Быстрые заметки:*
/note Название | Текст
    """
    bot.reply_to(message, help_text, parse_mode='Markdown')

# ========== ЗАМЕТКИ - КОМАНДЫ ==========

@bot.message_handler(commands=['note'])
def create_note_command(message):
    text = message.text.replace('/note', '').strip()
    
    if '|' not in text:
        bot.reply_to(message, "📝 *Формат:* `/note Название | Текст заметки`\n\n"
                     "Пример: `/note Идея | Добавить в бот напоминалку`", parse_mode='Markdown')
        return
    
    title, content = text.split('|', 1)
    title = title.strip()
    content = content.strip()
    
    create_note(message.from_user.id, title, content)
    bot.reply_to(message, f"✅ Заметка *{title}* сохранена!", parse_mode='Markdown')

@bot.message_handler(commands=['notes'])
def show_notes(message):
    user_id = message.from_user.id
    notes = get_notes(user_id)
    
    if not notes:
        bot.reply_to(message, "📝 *У вас пока нет заметок*\n\nСоздайте первую: `/note Название | Текст`", 
                     parse_mode='Markdown')
        return
    
    text = f"📝 *Ваши заметки* (всего: {len(notes)})\n\n"
    for note_id, title, content, category, _ in notes[:15]:
        text += f"📄 **{title}** [{category}]\n"
        text += f"   _{content[:100]}{'...' if len(content) > 100 else ''}_\n\n"
    
    text += "🔍 Для поиска используй `/search слово`"
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['search'])
def search_notes_command(message):
    query = message.text.replace('/search', '').strip()
    
    if not query:
        bot.reply_to(message, "🔍 *Что ищем?*\n\nПример: `/search проект`", parse_mode='Markdown')
        return
    
    results = search_notes(message.from_user.id, query)
    
    if not results:
        bot.reply_to(message, f"🔍 Ничего не найдено по запросу *{query}*", parse_mode='Markdown')
        return
    
    text = f"🔍 *Результаты поиска:* «{query}»\n\n"
    for note_id, title, content, category in results[:10]:
        text += f"📄 **{title}** [{category}]\n_{content[:150]}..._\n\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

# ========== СПИСКИ ПОКУПОК - КОМАНДЫ ==========

user_temp_list = {}

@bot.message_handler(commands=['shopping'])
def shopping_lists(message):
    user_id = message.from_user.id
    lists = get_shopping_lists(user_id)
    
    markup = telebot.types.InlineKeyboardMarkup()
    
    if lists:
        for list_id, name in lists:
            markup.add(telebot.types.InlineKeyboardButton(f"🛒 {name}", callback_data=f"shop_list_{list_id}"))
        markup.add(telebot.types.InlineKeyboardButton("➕ Новый список", callback_data="shop_new_list"))
        markup.add(telebot.types.InlineKeyboardButton("❌ Удалить список", callback_data="shop_delete_list"))
    else:
        markup.add(telebot.types.InlineKeyboardButton("➕ Создать первый список", callback_data="shop_new_list"))
    
    bot.reply_to(message, "🛒 *Мои списки покупок*\n\nВыберите список или создайте новый:", 
                 parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('shop_'))
def shopping_callback(call):
    user_id = call.from_user.id
    action = call.data.split('_')[1]
    
    if action == "list":
        list_id = int(call.data.split('_')[2])
        items = get_list_items(list_id)
        
        if items:
            text = f"🛒 *Список покупок:*\n\n"
            for item_id, name, checked in items:
                status = "✅" if checked else "⬜"
                text += f"{status} {name}\n"
            
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар", callback_data=f"shop_add_{list_id}"))
            markup.add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="shop_back"))
            
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, 
                                 parse_mode='Markdown', reply_markup=markup)
        else:
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("➕ Добавить товар", callback_data=f"shop_add_{list_id}"))
            markup.add(telebot.types.InlineKeyboardButton("◀️ Назад", callback_data="shop_back"))
            bot.edit_message_text("🛒 *Список покупок пуст*\n\nДобавьте первый товар!", 
                                 call.message.chat.id, call.message.message_id,
                                 parse_mode='Markdown', reply_markup=markup)
    
    elif action == "add":
        list_id = int(call.data.split('_')[2])
        user_temp_list[user_id] = list_id
        bot.edit_message_text("📝 *Введите название товара:*\n\nПросто напишите сообщение с названием товара",
                             call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.register_next_step_handler(call.message, add_item_step)
    
    elif action == "new_list":
        bot.edit_message_text("📝 *Введите название нового списка:*",
                             call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        bot.register_next_step_handler(call.message, create_list_step)
    
    elif action == "delete_list":
        lists = get_shopping_lists(user_id)
        markup = telebot.types.InlineKeyboardMarkup()
        for list_id, name in lists:
            markup.add(telebot.types.InlineKeyboardButton(f"❌ {name}", callback_data=f"shop_del_{list_id}"))
        markup.add(telebot.types.InlineKeyboardButton("◀️ Отмена", callback_data="shop_back"))
        bot.edit_message_text("🗑️ *Выберите список для удаления:*",
                             call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)
    
    elif action == "del":
        list_id = int(call.data.split('_')[2])
        delete_list(list_id)
        bot.answer_callback_query(call.id, "Список удалён!")
        shopping_lists(call.message)
    
    elif action == "back":
        shopping_lists(call.message)

def add_item_step(message):
    user_id = message.from_user.id
    if user_id not in user_temp_list:
        bot.reply_to(message, "❌ Ошибка. Попробуйте снова /shopping")
        return
    
    list_id = user_temp_list[user_id]
    item_name = message.text.strip()
    add_item_to_list(list_id, item_name)
    bot.reply_to(message, f"✅ *{item_name}* добавлен в список!", parse_mode='Markdown')
    del user_temp_list[user_id]

def create_list_step(message):
    list_name = message.text.strip()
    user_id = message.from_user.id
    create_shopping_list(user_id, list_name)
    bot.reply_to(message, f"✅ Список *{list_name}* создан!", parse_mode='Markdown')
    shopping_lists(message)

# ========== ПРОСТЫЕ ТЕКСТОВЫЕ ОТВЕТЫ ==========

@bot.message_handler(func=lambda message: True)
def simple_reply(message):
    user = message.from_user
    text = message.text.lower().strip()
    
    if text in ["привет", "здравствуй", "ку", "hi", "hello", "здарова"]:
        greetings = [
            f"👋 Привет, {user.first_name}!",
            f"✨ Здравствуй, {user.first_name}!",
            f"💫 О, {user.first_name}! Рад тебя видеть!"
        ]
        bot.reply_to(message, random.choice(greetings))
        return
    
    if text in ["пока", "до свидания", "bye", "удачи"]:
        bot.reply_to(message, f"👋 Пока, {user.first_name}! Заходи ещё!")
        return
    
    if any(word in text for word in ["спасибо", "благодарю", "спс", "thanks"]):
        bot.reply_to(message, f"🙏 Пожалуйста, {user.first_name}! Всегда рад помочь!")
        return
    
    if any(word in text for word in ["кто ты", "что ты умеешь", "как тебя зовут"]):
        bot.reply_to(message, 
            "🤖 Я Вайб-бот — твой дружелюбный помощник!\n\n"
            "📱 Мои команды: /help\n\n"
            "🛒 Веди списки покупок\n"
            "📝 Делай заметки\n"
            "🌤 Узнавай погоду\n"
            "📰 Читай новости\n"
            "🖼 Смотри мемы и фото")

# ========== ЗАПУСК ДЛЯ RENDER ==========
if __name__ == "__main__":
    print("🚀 Запуск Вайб-бота на Render...")
    
    init_database()
    setup_bot_commands()
    
    # Удаляем вебхук (важно для polling режима)
    try:
        bot.remove_webhook()
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ Ошибка удаления webhook: {e}")
    
    print("✅ Бот готов! Напишите /start в Telegram")
    
    # Бесконечный цикл с переподключением для Render
    while True:
        try:
            bot.polling(none_stop=True, interval=3, timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("🔄 Перезапуск через 15 секунд...")
            time.sleep(15)