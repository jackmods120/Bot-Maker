#  ╭───𓆩🛡️𓆪───╮
#  👨‍💻 𝘿𝙚𝙫: @j4ck_721s  
#  👤 𝙉𝙖𝙢𝙚: ﮼جــاڪ ,.⏳🤎:)
#   📢 𝘾𝙝: @j4ck_721s
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
import requests
from flask import Flask, request, jsonify

# --- Configuration ---
TOKEN = os.getenv('BOT_TOKEN', 'YOUR_TOKEN_HERE')
OWNER_ID = 5977475208
YOUR_USERNAME = 'j4ck_721s'
UPDATE_CHANNEL = 'https://t.me/j4ck_721s'

# Vercel only allows writing to /tmp folder
BASE_DIR = '/tmp'
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')
MAIN_BOT_LOG_PATH = os.path.join(IROTECH_DIR, 'main_bot_log.log')

# Create necessary directories
os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- Data Structures ---
bot_scripts = {} 
user_files = {} 
user_pagination_state = {} 
admin_pagination_state = {} 
bot_usernames_cache = {}
current_file_context = {}  # Track current file for each user

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(MAIN_BOT_LOG_PATH, encoding='utf-8'),
        StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- ReplyKeyboardMarkup Layouts ---
MAIN_MENU_BUTTONS_LAYOUT = [["ℹ️ دەربارە"],
    ["📤 ناردنی فایل", "📂 فایلەکانم"],["⚙️ دانانی چەناڵ", "📢 کەناڵەکەم"]
]
ADMIN_MENU_BUTTONS_LAYOUT = [
    ["ℹ️ دەربارە"],["📤 ناردنی فایل", "📂 فایلەکانم"],["⚙️ دانانی چەناڵ", "📢 کەناڵەکەم"],
    ["👑 پانێڵی گەشەپێدەر"]
]

# --- Database Setup ---
DB_LOCK = threading.Lock()

def init_db():
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        
        c.execute("PRAGMA table_info(user_files)")
        columns = [column[1] for column in c.fetchall()]
        
        if 'bot_username' not in columns:
            try:
                c.execute('ALTER TABLE user_files ADD COLUMN bot_username TEXT')
            except:
                pass
        
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
        c.execute('INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)',
                  ('bot_locked', 'false'))
        c.execute('INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)',
                  ('free_mode', 'false'))
        conn.commit()
        conn.close()

def load_data():
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
            user_files.setdefault(user_id,[]).append((file_name, file_type, status, bot_token_id, bot_username))
        conn.close()

def add_user_to_db(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()

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

def get_all_user_files_from_db():
    all_files =[]
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
            all_files.append({
                'user_id': row[0],
                'file_name': row[1],
                'file_type': row[2],
                'status': row[3],
                'bot_token_id': row[4],
                'bot_username': row[5] if has_username and len(row) > 5 else None
            })
        conn.close()
    return all_files

def add_purchase(user_id, days_count, price):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        purchase_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        expiry_date = (datetime.now() + timedelta(days=days_count)).strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT INTO purchases (user_id, purchase_date, days_count, price, expiry_date) VALUES (?, ?, ?, ?, ?)',
                  (user_id, purchase_date, days_count, price, expiry_date))
        conn.commit()
        conn.close()

def get_all_purchases():
    purchases =[]
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT id, user_id, purchase_date, days_count, price, expiry_date FROM purchases ORDER BY id DESC')
        for row in c.fetchall():
            purchases.append({
                'id': row[0],
                'user_id': row[1],
                'purchase_date': row[2],
                'days_count': row[3],
                'price': row[4],
                'expiry_date': row[5]
            })
        conn.close()
    return purchases

def get_user_active_subscription(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('SELECT expiry_date FROM purchases WHERE user_id = ? AND expiry_date > ? ORDER BY expiry_date DESC LIMIT 1',
                  (user_id, now))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

def is_admin(user_id):
    if user_id == OWNER_ID:
        return True
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result is not None

def add_admin(user_id, added_by):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        added_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('INSERT OR REPLACE INTO admins (user_id, added_by, added_date) VALUES (?, ?, ?)',
                  (user_id, added_by, added_date))
        conn.commit()
        conn.close()

def remove_admin(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()

def get_all_admins():
    admins =[]
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT user_id, added_by, added_date FROM admins')
        for row in c.fetchall():
            admins.append({
                'user_id': row[0],
                'added_by': row[1],
                'added_date': row[2]
            })
        conn.close()
    return admins

def get_bot_setting(key):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT setting_value FROM bot_settings WHERE setting_key = ?', (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

def set_bot_setting(key, value):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO bot_settings (setting_key, setting_value) VALUES (?, ?)',
                  (key, value))
        conn.commit()
        conn.close()

def is_bot_locked():
    return get_bot_setting('bot_locked') == 'true'

def is_free_mode():
    return get_bot_setting('free_mode') == 'true'

def count_user_hosted_bots(user_id):
    files = user_files.get(user_id,[])
    return len(files)

def save_user_channels(user_id, channels):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_channels (user_id, channels) VALUES (?, ?)',
                  (user_id, channels))
        conn.commit()
        conn.close()

def get_user_channels(user_id):
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT channels FROM user_channels WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None

def get_bot_username_from_token(token):
    if token in bot_usernames_cache:
        return bot_usernames_cache[token]
    
    try:
        temp_bot = telebot.TeleBot(token)
        me = temp_bot.get_me()
        username = f"@{me.username}" if me.username else "N/A"
        bot_usernames_cache[token] = username
        return username
    except Exception as e:
        logger.error(f"Error getting bot username: {e}")
        return "N/A"

def get_bot_start_count(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key, {})
    return script_info.get('start_count', 0)

def increment_bot_start_count(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    if script_key in bot_scripts:
        bot_scripts[script_key]['start_count'] = bot_scripts[script_key].get('start_count', 0) + 1
    else:
        bot_scripts[script_key] = {'start_count': 1}

def get_bot_uptime(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and 'start_time' in script_info:
        uptime_seconds = int(time.time() - script_info['start_time'])
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        return f"{hours}h {minutes}m {seconds}s"
    return "N/A"

# Initialize DB
init_db()
load_data()

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def is_bot_running(script_owner_id, file_name):
    script_key = f"{script_owner_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if not script_info or not script_info.get('process'):
        return False
    
    try:
        proc = psutil.Process(script_info['process'].pid)
        is_running = proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        if not is_running:
            _cleanup_stale_script_entry(script_key, script_info)
        return is_running
    except psutil.NoSuchProcess:
        _cleanup_stale_script_entry(script_key, script_info)
        return False
    except Exception as e:
        logger.error(f"Error checking process status: {e}")
        return False

def _cleanup_stale_script_entry(script_key, script_info):
    if 'log_file' in script_info and hasattr(script_info['log_file'], 'close') and not script_info['log_file'].closed:
        try: script_info['log_file'].close()
        except Exception as log_e: pass
    if script_key in bot_scripts: del bot_scripts[script_key]

def kill_process_tree(process_info):
    pid = None
    if 'log_file' in process_info and hasattr(process_info['log_file'], 'close') and not process_info['log_file'].closed:
        try: process_info['log_file'].close()
        except Exception: pass

    process = process_info.get('process')
    if not process or not hasattr(process, 'pid'):
        return

    pid = process.pid
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try: child.terminate()
            except: 
                try: child.kill()
                except: pass
        try:
            parent.terminate()
            parent.wait(timeout=5)
        except psutil.TimeoutExpired:
            try: parent.kill()
            except: pass
    except psutil.NoSuchProcess:
        pass

def start_script(user_id, file_name):
    user_folder = get_user_folder(user_id)
    script_path = os.path.join(user_folder, file_name)
    
    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script file {file_name} not found.")

    script_key = f"{user_id}_{file_name}"
    if is_bot_running(user_id, file_name):
        raise RuntimeError(f"Script {file_name} is already running.")

    log_filename = f"{script_key}_log.log"
    log_path = os.path.join(user_folder, log_filename)
    
    try:
        log_file = open(log_path, 'w', encoding='utf-8')
        process = subprocess.Popen(
            ['python3', script_path],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            cwd=user_folder,
            start_new_session=True
        )
        
        if script_key not in bot_scripts:
            bot_scripts[script_key] = {'start_count': 0}
        
        bot_scripts[script_key].update({
            'process': process,
            'log_file': log_file,
            'log_path': log_path,
            'script_key': script_key,
            'user_id': user_id,
            'file_name': file_name,
            'start_time': time.time()
        })
        
        increment_bot_start_count(user_id, file_name)
        return True
    except Exception as e:
        logger.error(f"Failed to start script {script_key}: {e}")
        raise

def stop_script(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if not script_info:
        raise KeyError("Script is not tracked or not running.")
    kill_process_tree(script_info)
    start_count = script_info.get('start_count', 0)
    if script_key in bot_scripts: del bot_scripts[script_key]
    bot_scripts[script_key] = {'start_count': start_count}
    return True

def send_main_menu(chat_id, user_id):
    if user_id == OWNER_ID or is_admin(user_id):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for row in ADMIN_MENU_BUTTONS_LAYOUT: markup.add(*row)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for row in MAIN_MENU_BUTTONS_LAYOUT: markup.add(*row)
    bot.send_message(chat_id, "🏠 مینیوی سەرەکی:", reply_markup=markup)

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.\n\nتکایە دواتر هەوڵبدەوە.")
        return
    add_user_to_db(user_id)
    welcome_text = (
        f"✨ <b>بەخێربێیت بۆ بۆتی Hosting!</b> ✨\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 👤 <b>ناو:</b> {message.from_user.first_name}\n"
        f"┃ 🆔 <b>ئایدی:</b> <code>{user_id}</code>\n"
        f"┃ 📢 <b>کەناڵ:</b> @{YOUR_USERNAME}\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"🚀 <b>ئەم بۆتە تایبەتە بە:</b>\n"
        f"   • Host کردنی بۆتەکانت بە خێرایی\n"
        f"   • کۆنترۆڵی تەواو بەسەر بۆتەکانتدا\n"
        f"   • سیستەمی پێشکەوتوو و ئاسان\n\n"
        f"💡 <i>بۆ دەستپێکردن دوگمەیەک هەڵبژێرە...</i>"
    )
    send_main_menu(message.chat.id, user_id)
    bot.send_message(message.chat.id, welcome_text, parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "ℹ️ دەربارە")
def about_button(message):
    about_text = (
        f"🌟 <b>دەربارەی بۆتی Hosting</b> 🌟\n\n"
        f"┏━━━━━━━━━━━━━━━━━━━━┓\n"
        f"┃ 🤖 <b>ناوی بۆت:</b> Hosting Bot\n"
        f"┃ 👨‍💻 <b>گەشەپێدەر:</b> @{YOUR_USERNAME}\n"
        f"┃ 📢 <b>کەناڵ:</b> @{YOUR_USERNAME}\n"
        f"┃ 🔖 <b>وەشان:</b> 2.0 Pro\n"
        f"┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"✨ <b>تایبەتمەندییەکان:</b>\n"
        f"   ✅ Host کردنی بۆت بە خێرایی\n"
        f"   ✅ کۆنترۆڵی تەواو (Start/Stop/Restart)\n"
        f"   ✅ پشتیوانی لە .py و .zip\n"
        f"💬 بۆ هەر پرسیارێک: @{YOUR_USERNAME}"
    )
    bot.send_message(message.chat.id, about_text, parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "📢 کەناڵەکەم")
def channel_button(message):
    user_id = message.from_user.id
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 کەناڵەکەم", url=UPDATE_CHANNEL))
    bot.send_message(message.chat.id, "لێرە کەناڵەکەمە:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "⚙️ دانانی چەناڵ")
def set_channel_button(message):
    user_id = message.from_user.id
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id):
        return bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
    current_channels = get_user_channels(user_id)
    msg_text = (
        "⚙️ <b>دانانی چەناڵەکانت</b>\n\n📝 یوزەرنەیمی چەناڵەکانت بنێرە (بە @ دەست پێبکات)\n"
    )
    if current_channels: msg_text += f"✅ چەناڵەکانی ئێستا:\n<code>{current_channels}</code>"
    msg = bot.send_message(message.chat.id, msg_text, parse_mode='HTML')
    bot.register_next_step_handler(msg, process_set_channels)

def process_set_channels(message):
    user_id = message.from_user.id
    channels = message.text.strip()
    if not channels: return bot.send_message(message.chat.id, "❌ هیچ چەناڵێک نەنووسرا!")
    save_user_channels(user_id, channels)
    bot.send_message(message.chat.id, f"✅ <b>چەناڵەکان دانران!</b>\n<code>{channels}</code>", parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "📤 ناردنی فایل")
def upload_file_button(message):
    user_id = message.from_user.id
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id): return bot.send_message(user_id, "🔒 بۆت لە ئێستادا داخراوە.")
    if not is_free_mode() and not get_user_active_subscription(user_id) and user_id != OWNER_ID and not is_admin(user_id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💰 کڕین", callback_data="buy_subscription"))
        return bot.send_message(user_id, "⚠️ بۆ بەکارهێنانی بۆت پێویستە بەشداریکردن بکەیت.", reply_markup=markup)
    
    bot.send_message(message.chat.id, "📤 <b>ناردنی فایل</b>\n\n📂 تکایە فایلی بۆتەکەت بنێرە (.py یان .zip)", parse_mode='HTML')

@bot.message_handler(func=lambda message: message.text == "📂 فایلەکانم")
def my_files_button(message):
    list_user_files(message)

@bot.message_handler(func=lambda message: message.text == "👑 پانێڵی گەشەپێدەر")
def admin_panel_button(message):
    if message.from_user.id != OWNER_ID and not is_admin(message.from_user.id): return
    show_owner_panel(message)

def show_owner_panel(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("💰 لیستی کڕیارەکان", callback_data="owner_purchases_list"),
               types.InlineKeyboardButton("🗂️ فایلەکانی بەکارهێنەران", callback_data="owner_view_all_users"))
    lock_status = "🔓 کردنەوە" if is_bot_locked() else "🔒 قفڵکردن"
    free_status = "💵 بەپارە" if is_free_mode() else "🆓 بێ بەرامبەر"
    markup.add(types.InlineKeyboardButton(f"{lock_status} بۆت", callback_data="owner_toggle_lock"),
               types.InlineKeyboardButton(f"{free_status} کردن", callback_data="owner_toggle_free"))
    if message.from_user.id == OWNER_ID:
        markup.add(types.InlineKeyboardButton("➕ زیادکردنی ئەدمین", callback_data="owner_add_admin"),
                   types.InlineKeyboardButton("➖ سڕینەوەی ئەدمین", callback_data="owner_remove_admin"))
        markup.add(types.InlineKeyboardButton("📋 لیستی ئەدمینەکان", callback_data="owner_list_admins"))
    markup.add(types.InlineKeyboardButton("📊 ئاماری بۆت", callback_data="owner_statistics"))
    bot.send_message(message.chat.id, "👑 <b>پانێڵی کۆنتڕۆڵی گەشەپێدەر</b>", parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "owner_toggle_lock")
def toggle_bot_lock(call):
    if call.from_user.id != OWNER_ID: return
    new_status = 'false' if is_bot_locked() else 'true'
    set_bot_setting('bot_locked', new_status)
    bot.answer_callback_query(call.id, "✅ گۆڕانکاری کرا")
    show_owner_panel(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "owner_toggle_free")
def toggle_free_mode(call):
    if call.from_user.id != OWNER_ID: return
    new_status = 'false' if is_free_mode() else 'true'
    set_bot_setting('free_mode', new_status)
    bot.answer_callback_query(call.id, "✅ گۆڕانکاری کرا")
    show_owner_panel(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "owner_statistics")
def show_statistics(call):
    if call.from_user.id != OWNER_ID and not is_admin(call.from_user.id): return
    with DB_LOCK:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM active_users')
        total_users = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM user_files')
        total_files = c.fetchone()[0]
        conn.close()
    response = f"📊 <b>ئاماری بۆت:</b>\n\n👥 بەکارهێنەران: <code>{total_users}</code>\n📂 کۆی فایلەکان: <code>{total_files}</code>"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 گەڕانەوە", callback_data="back_to_owner_panel"))
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_owner_panel")
def back_to_owner_panel(call):
    show_owner_panel(call.message)

@bot.message_handler(content_types=['document'])
def handle_file_upload(message):
    user_id = message.from_user.id
    if is_bot_locked() and user_id != OWNER_ID and not is_admin(user_id): return
    file = message.document
    file_name = file.file_name
    if not (file_name.endswith('.py') or file_name.endswith('.zip')):
        return bot.send_message(message.chat.id, "❌ تەنیا `.py` یان `.zip` قبووڵە.")

    user_folder = get_user_folder(user_id)
    progress_msg = bot.send_message(message.chat.id, "⏳ بارکردنی فایل...")
    try:
        file_info = bot.get_file(file.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_path = os.path.join(user_folder, file_name)
        with open(file_path, 'wb') as new_file: new_file.write(downloaded_file)
        
        if file_name.endswith('.zip'):
            with zipfile.ZipFile(file_path, 'r') as zip_ref: zip_ref.extractall(user_folder)
            os.remove(file_path)
            extracted_files = [f for f in os.listdir(user_folder) if f.endswith('.py')]
            for ext_file in extracted_files:
                user_files.setdefault(user_id,[]).append((ext_file, 'py', 'approved', None, "N/A"))
                update_user_file_db(user_id, ext_file, 'py', 'approved', None, "N/A")
                try: start_script(user_id, ext_file)
                except: pass
        else:
            user_files.setdefault(user_id,[]).append((file_name, 'py', 'approved', None, "N/A"))
            update_user_file_db(user_id, file_name, 'py', 'approved', None, "N/A")
            try: start_script(user_id, file_name)
            except: pass
        bot.edit_message_text("✅ فایلەکەت بە سەرکەوتوویی بارکرا!", message.chat.id, progress_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ هەڵە: {e}", message.chat.id, progress_msg.message_id)

def extract_bot_token(file_path):
    token_pattern = re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            match = token_pattern.search(f.read())
            return match.group(0) if match else None
    except: return None

def list_user_files(message):
    user_id = message.from_user.id
    files = user_files.get(user_id,[])
    if not files: return bot.send_message(message.chat.id, "❌ هیچ فایلێکت نییە.")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for file_name, file_type, status, bot_token_id, bot_username in files:
        status_emoji = "🟢" if is_bot_running(user_id, file_name) else "🔴"
        markup.add(types.KeyboardButton(f"{status_emoji} {file_name}"))
    markup.add("🔙 گەڕانەوە بۆ مینیو")
    bot.send_message(message.chat.id, "دوگمەیەک هەڵبژێرە:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text and (message.text.startswith("🟢 ") or message.text.startswith("🔴 ")))
def handle_file_button(message):
    user_id = message.from_user.id
    file_name = message.text[2:]
    files = user_files.get(user_id, [])
    file_info = next((f for f in files if f[0] == file_name), None)
    if not file_info: return bot.send_message(message.chat.id, "❌ فایلەکە نەدۆزرایەوە!")
    current_file_context[user_id] = file_name
    show_bot_control(message.chat.id, user_id, file_info)

def show_bot_control(chat_id, user_id, file_info):
    file_name, file_type, status, bot_token_id, bot_username = file_info
    is_running = is_bot_running(user_id, file_name)
    status_emoji = "🟢 Running" if is_running else "🔴 Stopped"
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_running: markup.add("⏸ وەستاندن", "🔄 نوێکردنەوە")
    else: markup.add("▶️ دەستپێکردن", "🔄 نوێکردنەوە")
    markup.add("📥 دابەزاندن", "🗑 سڕینەوە")
    markup.add("🔙 گەڕانەوە بۆ مینیو")
    bot.send_message(chat_id, f"📂 فایل: <code>{file_name}</code>\n📊 دۆخ: {status_emoji}", parse_mode='HTML', reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in["▶️ دەستپێکردن", "⏸ وەستاندن", "🔄 نوێکردنەوە", "📥 دابەزاندن", "🗑 سڕینەوە", "🔙 گەڕانەوە بۆ مینیو"])
def handle_control_buttons(message):
    user_id = message.from_user.id
    action = message.text
    if action == "🔙 گەڕانەوە بۆ مینیو": return send_main_menu(message.chat.id, user_id)
    file_name = current_file_context.get(user_id)
    if not file_name: return bot.send_message(message.chat.id, "❌ هیچ فایلێکت نییە!")
    
    if action == "▶️ دەستپێکردن":
        start_script(user_id, file_name)
        bot.send_message(message.chat.id, "▶️ بۆت دەستی پێکرد!")
    elif action == "⏸ وەستاندن":
        stop_script(user_id, file_name)
        bot.send_message(message.chat.id, "⏸ بۆت وەستاندرا!")
    elif action == "🔄 نوێکردنەوە":
        if is_bot_running(user_id, file_name): stop_script(user_id, file_name)
        start_script(user_id, file_name)
        bot.send_message(message.chat.id, "🔄 بۆت نوێکرایەوە!")
    elif action == "🗑 سڕینەوە":
        if is_bot_running(user_id, file_name): stop_script(user_id, file_name)
        file_path = os.path.join(get_user_folder(user_id), file_name)
        if os.path.exists(file_path): os.remove(file_path)
        remove_user_file_db(user_id, file_name)
        bot.send_message(message.chat.id, "🗑 فایل سڕایەوە!")
        send_main_menu(message.chat.id, user_id)

# --- Flask Webhook Routes ---
@app.route('/api/main', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    else:
        return jsonify({"error": "unsupported content-type"}), 403

@app.route('/api/main', methods=['GET'])
def index():
    return "🚀 Hosting Bot is active on Vercel!"
