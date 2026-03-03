import telebot
import subprocess
import os
import zipfile
import shutil
import re
from telebot import types
import time
from datetime import datetime, timedelta
import psutil
import sqlite3
import logging
from logging import StreamHandler
import threading
import sys
import atexit
from flask import Flask, request, jsonify

# --- Configuration for Vercel ---
# وەرگرتنی تۆکن لە Environment Variables
TOKEN = os.getenv('BOT_TOKEN')

# Vercel only allows writing to /tmp
BASE_DIR = '/tmp'
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
MAIN_BOT_LOG_PATH = os.path.join(IROTECH_DIR, 'main_bot_log.log')

# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

# خاوەن و چەناڵ (دەتوانیت لێرە بیانسڕیتەوە ئەگەر دەتەوێت)
OWNER_ID = 5977475208
YOUR_USERNAME = 'j4ck_721s'
UPDATE_CHANNEL = 'https://t.me/j4ck_721s'

# Initialize Bot and Flask
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# --- Data Structures ---
bot_scripts = {} 
user_files = {} 
bot_usernames_cache = {}
current_file_context = {}

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Menus ---
MAIN_MENU_BUTTONS_LAYOUT = [
    ["ℹ️ دەربارە"],
    ["📤 ناردنی فایل", "📂 فایلەکانم"],
    ["⚙️ دانانی چەناڵ", "📢 کەناڵەکەم"]
]
ADMIN_MENU_BUTTONS_LAYOUT = [
    ["ℹ️ دەربارە"],
    ["📤 ناردنی فایل", "📂 فایلەکانم"],
    ["⚙️ دانانی چەناڵ", "📢 کەناڵەکەم"],
    ["👑 پانێڵی گەشەپێدەر"]
]

# --- Database Functions ---
DB_LOCK = threading.Lock()

def init_db():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        # Check columns
        c.execute("PRAGMA table_info(user_files)")
        columns = [column[1] for column in c.fetchall()]
        if 'bot_username' not in columns:
            try: c.execute('ALTER TABLE user_files ADD COLUMN bot_username TEXT')
            except: pass
        
        c.execute('''CREATE TABLE IF NOT EXISTS user_files
                     (user_id INTEGER, file_name TEXT, file_type TEXT, status TEXT, bot_token_id TEXT, bot_username TEXT,
                      PRIMARY KEY (user_id, file_name))''')
        c.execute('''CREATE TABLE IF NOT EXISTS active_users
                     (user_id INTEGER PRIMARY KEY)''')
        c.execute('''CREATE TABLE IF NOT EXISTS purchases
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      purchase_date TEXT,
                      days_count INTEGER,
                      price REAL,
                      expiry_date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (user_id INTEGER PRIMARY KEY,
                      added_by INTEGER,
                      added_date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS bot_settings
                     (setting_key TEXT PRIMARY KEY,
                      setting_value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS user_channels
                     (user_id INTEGER PRIMARY KEY,
                      channels TEXT)''')
        c.execute('INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)', ('bot_locked', 'false'))
        c.execute('INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)', ('free_mode', 'false'))
        conn.commit()
        conn.close()

def load_data():
    # Load data from DB into memory
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute("PRAGMA table_info(user_files)")
        columns = [column[1] for column in c.fetchall()]
        has_username = 'bot_username' in columns
        
        if has_username:
            c.execute('SELECT user_id, file_name, file_type, status, bot_token_id, bot_username FROM user_files')
        else:
            c.execute('SELECT user_id, file_name, file_type, status, bot_token_id FROM user_files')
        
        for row in c.fetchall():
            user_id = row[0]
            file_name = row[1]
            file_type = row[2]
            status = row[3]
            bot_token_id = row[4]
            bot_username = row[5] if has_username and len(row) > 5 else None
            user_files.setdefault(user_id, []).append((file_name, file_type, status, bot_token_id, bot_username))
        conn.close()

# --- Helper Functions (DB) ---
def update_user_file_db(user_id, file_name, file_type, status, bot_token_id, bot_username=None):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type, status, bot_token_id, bot_username) VALUES (?, ?, ?, ?, ?, ?)',
                  (user_id, file_name, file_type, status, bot_token_id, bot_username))
        conn.commit()
        conn.close()

def remove_user_file_db(user_id, file_name):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM user_files WHERE user_id = ? AND file_name = ?', (user_id, file_name))
        conn.commit()
        conn.close()

def get_bot_setting(key):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT setting_value FROM bot_settings WHERE setting_key = ?', (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

def is_bot_locked(): return get_bot_setting('bot_locked') == 'true'
def is_free_mode(): return get_bot_setting('free_mode') == 'true'
def is_admin(user_id): return user_id == OWNER_ID # Simplified for Vercel

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

# --- Process Management (Vercel Limitation Warning) ---
# تێبینی: لەسەر Vercel پرۆسەکان بۆ ماوەی درێژ نامێننەوە
def is_bot_running(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    return script_key in bot_scripts

def start_script(user_id, file_name):
    user_folder = get_user_folder(user_id)
    script_path = os.path.join(user_folder, file_name)
    script_key = f"{user_id}_{file_name}"
    
    if not os.path.isfile(script_path):
        raise FileNotFoundError("File not found")

    try:
        # Start process (Will be killed when Vercel sleeps)
        process = subprocess.Popen(['python3', script_path], cwd=user_folder)
        bot_scripts[script_key] = {'process': process, 'start_time': time.time()}
        return True
    except Exception as e:
        logger.error(f"Error starting script: {e}")
        return False

def stop_script(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    if script_key in bot_scripts:
        try:
            bot_scripts[script_key]['process'].kill()
        except: pass
        del bot_scripts[script_key]
    return True

# --- Telegram Handlers ---

@bot.message_handler(commands=['start'])
def start_command(message):
    init_db() # Ensure DB exists
    user_id = message.from_user.id
    
    if is_bot_locked() and user_id != OWNER_ID:
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ADMIN_MENU_BUTTONS_LAYOUT if (user_id == OWNER_ID) else MAIN_MENU_BUTTONS_LAYOUT
    for row in buttons:
        markup.add(*row)
        
    welcome = f"👋 بەخێربێیت {message.from_user.first_name}!\n\n🤖 بۆتی هۆستینگ ئامادەیە."
    bot.send_message(message.chat.id, welcome, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📤 ناردنی فایل")
def upload_file_button(message):
    bot.send_message(message.chat.id, "📂 تکایە فایلی بۆتەکەت بنێرە (.py یان .zip)")

@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    user_id = message.from_user.id
    file_name = message.document.file_name
    
    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        bot.send_message(message.chat.id, "❌ تەنیا .py و .zip قبوڵ دەکرێت.")
        return

    user_folder = get_user_folder(user_id)
    file_path = os.path.join(user_folder, file_name)
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with open(file_path, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        if file_name.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(user_folder)
            os.remove(file_path) # Remove zip after extraction
            bot.send_message(message.chat.id, "✅ فایلەکان دەرھێنران (.zip extracted).")
            # Register extracted py files
            for f in os.listdir(user_folder):
                if f.endswith('.py'):
                    update_user_file_db(user_id, f, 'py', 'approved', 'N/A', 'N/A')
                    user_files.setdefault(user_id, []).append((f, 'py', 'approved', 'N/A', 'N/A'))
        else:
            update_user_file_db(user_id, file_name, 'py', 'approved', 'N/A', 'N/A')
            user_files.setdefault(user_id, []).append((file_name, 'py', 'approved', 'N/A', 'N/A'))
            bot.send_message(message.chat.id, f"✅ فایلی {file_name} وەرگیرا.")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ هەڵە: {e}")

@bot.message_handler(func=lambda message: message.text == "📂 فایلەکانم")
def my_files_button(message):
    load_data() # Refresh data
    user_id = message.from_user.id
    files = user_files.get(user_id, [])
    
    if not files:
        bot.send_message(message.chat.id, "❌ هیچ فایلێکت نییە.")
        return
        
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for f in files:
        fname = f[0]
        status = "🟢" if is_bot_running(user_id, fname) else "🔴"
        markup.add(f"{status} {fname}")
    markup.add("🔙 گەڕانەوە")
    
    bot.send_message(message.chat.id, "فایلێک هەڵبژێرە:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and (message.text.startswith("🟢") or message.text.startswith("🔴")))
def file_control(message):
    user_id = message.from_user.id
    file_name = message.text[2:].strip()
    current_file_context[user_id] = file_name
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("▶️ دەستپێکردن", "⏸ وەستاندن", "🗑 سڕینەوە", "🔙 گەڕانەوە")
    
    bot.send_message(message.chat.id, f"کۆنترۆڵی فایل: {file_name}", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["▶️ دەستپێکردن", "⏸ وەستاندن", "🗑 سڕینەوە"])
def action_handler(message):
    user_id = message.from_user.id
    file_name = current_file_context.get(user_id)
    if not file_name:
        return bot.send_message(message.chat.id, "سەرەتا فایلێک هەڵبژێرە.")
        
    if message.text == "▶️ دەستپێکردن":
        start_script(user_id, file_name)
        bot.send_message(message.chat.id, "✅ بۆت دەستی پێکرد (تێبینی: لە Vercel تەنها کاتییە).")
    elif message.text == "⏸ وەستاندن":
        stop_script(user_id, file_name)
        bot.send_message(message.chat.id, "🛑 بۆت وەستێنرا.")
    elif message.text == "🗑 سڕینەوە":
        path = os.path.join(get_user_folder(user_id), file_name)
        if os.path.exists(path): os.remove(path)
        remove_user_file_db(user_id, file_name)
        bot.send_message(message.chat.id, "🗑 فایل سڕایەوە.")

@bot.message_handler(func=lambda m: m.text == "🔙 گەڕانەوە")
def back(m):
    start_command(m)

# --- Flask Webhook Route ---
@app.route('/api/main', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return jsonify({"error": "Forbidden"}), 403

@app.route('/')
def index():
    return "Bot is running on Vercel!"

if __name__ == "__main__":
    init_db()
