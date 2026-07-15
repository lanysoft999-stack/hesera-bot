import telebot
from telebot import types
from telebot import apihelper
import sqlite3
import datetime
import urllib.parse
import requests
import ssl
import time
import os
import threading
from flask import Flask
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# --- ОБХОД SSL ---
class NoSSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

session = requests.Session()
session.mount('https://', NoSSLAdapter())
apihelper.SESSION = session

# --- Flask для Web Service ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/ping')
def ping():
    return "OK"

# --- АВТОПИНГ ---
def auto_ping():
    time.sleep(30)
    while True:
        time.sleep(240)
        try:
            requests.get("http://localhost:10000/ping", timeout=10)
            print("🔄 Пинг OK")
        except:
            pass

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8974171870:AAHaaECMgLrO1PRXEXxfMkfNrKqrpdXmjSE')
CRYPTO_TOKEN = os.environ.get('CRYPTO_TOKEN', '551375:AAKMHUgqI7K5BVcFQA0ujATRAZgT6XpVRQ4')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 314148464))
ADMIN_USERNAME = "hesers"
BOT_USERNAME = "Clumsysell_bot"
FIXED_USDT_RUB = 77.20
GOLDA_RATE = 0.54
COMMISSION = 0.20

bot = telebot.TeleBot(BOT_TOKEN)
admin_product_draft = {}
admin_mailing_draft = {}
LANG_CACHE = {}

# ================= КУРС =================
def get_usdt_rub_rate():
    try:
        resp = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB", timeout=5)
        if resp.status_code == 200: return float(resp.json()['price'])
    except: pass
    return FIXED_USDT_RUB

# ================= БАЗА ДАННЫХ =================
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, reg_date TEXT,
        balance REAL DEFAULT 0.00, gold_balance REAL DEFAULT 0.00,
        usd_balance REAL DEFAULT 0.00, ref_balance REAL DEFAULT 0.00,
        ref_gold REAL DEFAULT 0.00, ref_usd REAL DEFAULT 0.00,
        purchases_count INTEGER DEFAULT 0,
        referrer_id INTEGER DEFAULT NULL, lang TEXT DEFAULT 'ru')""")
    cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, photo_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS subcategories (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, photo_id TEXT)")
    cursor.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, parent_type TEXT, parent_id INTEGER,
        name TEXT, description TEXT, price INTEGER, photo_id TEXT,
        content_type TEXT DEFAULT 'file', content TEXT, stock INTEGER DEFAULT 0)""")
    cursor.execute("CREATE TABLE IF NOT EXISTS promocodes (code TEXT PRIMARY KEY, discount INTEGER, active INTEGER DEFAULT 1)")
    cursor.execute("""CREATE TABLE IF NOT EXISTS user_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_name TEXT,
        product_id INTEGER, price INTEGER, content TEXT, content_type TEXT, date TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS purchases_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_id INTEGER, price INTEGER, date TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS balance_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL,
        invoice_id TEXT, status TEXT DEFAULT 'pending', method TEXT)""")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    conn.close()

init_db()

# ================= ЯЗЫКИ =================
def get_user_lang(user_id):
    if user_id in LANG_CACHE:
        return LANG_CACHE[user_id]
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    lang = row[0] if row and row[0] else 'ru'
    LANG_CACHE[user_id] = lang
    return lang

def set_user_lang(user_id, lang):
    LANG_CACHE[user_id] = lang
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def tr(user_id, ru_text, en_text=""):
    if not en_text:
        en_text = ru_text
    return en_text if get_user_lang(user_id) == 'en' else ru_text

# ================= ФУНКЦИИ БД =================
def get_setting(key):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,)); row = cursor.fetchone(); conn.close()
    return row[0] if row else None

def set_setting(key, value):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)); conn.commit(); conn.close()

def get_categories():
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, name, photo_id FROM categories"); rows = cursor.fetchall(); conn.close(); return rows

def get_category(cat_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, name, photo_id FROM categories WHERE id = ?", (cat_id,)); row = cursor.fetchone(); conn.close(); return row

def add_category(name):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,)); conn.commit(); conn.close()

def update_category_photo(cat_id, photo_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE categories SET photo_id = ? WHERE id = ?", (photo_id, cat_id)); conn.commit(); conn.close()

def get_subcategories(cat_id=None):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    if cat_id is None: cursor.execute("SELECT id, name, photo_id, category_id FROM subcategories")
    else: cursor.execute("SELECT id, name, photo_id FROM subcategories WHERE category_id = ?", (cat_id,))
    rows = cursor.fetchall(); conn.close(); return rows

def get_subcategory(sub_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, name, photo_id, category_id FROM subcategories WHERE id = ?", (sub_id,)); row = cursor.fetchone(); conn.close(); return row

def add_subcategory(cat_id, name):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("INSERT INTO subcategories (category_id, name) VALUES (?, ?)", (cat_id, name)); conn.commit(); conn.close()

def update_subcategory_photo(sub_id, photo_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE subcategories SET photo_id = ? WHERE id = ?", (photo_id, sub_id)); conn.commit(); conn.close()

def move_subcategory(sub_id, new_cat_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE subcategories SET category_id = ? WHERE id = ?", (new_cat_id, sub_id)); conn.commit(); conn.close()

def get_products(parent_type, parent_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, photo_id, stock FROM products WHERE parent_type = ? AND parent_id = ? AND stock > 0", (parent_type, parent_id))
    rows = cursor.fetchall(); conn.close(); return rows

def get_product(prod_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT name, description, price, photo_id, content_type, content, parent_type, parent_id, stock FROM products WHERE id = ?", (prod_id,))
    row = cursor.fetchone(); conn.close(); return row

def add_product(parent_type, parent_id, name, desc, price, photo_id, content_type, content, stock):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("INSERT INTO products (parent_type, parent_id, name, description, price, photo_id, content_type, content, stock) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (parent_type, parent_id, name, desc, price, photo_id, content_type, content, stock))
    conn.commit(); conn.close()

def update_product_photo(prod_id, photo_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE products SET photo_id = ? WHERE id = ?", (photo_id, prod_id)); conn.commit(); conn.close()

def update_product_content(prod_id, content_type, content):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE products SET content_type = ?, content = ? WHERE id = ?", (content_type, content, prod_id)); conn.commit(); conn.close()

def move_product(prod_id, new_parent_type, new_parent_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE products SET parent_type = ?, parent_id = ? WHERE id = ?", (new_parent_type, new_parent_id, prod_id)); conn.commit(); conn.close()

def decrease_stock(prod_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE products SET stock = stock - 1 WHERE id = ?", (prod_id,)); conn.commit(); conn.close()

def add_user(user_id, username, referrer_id=None):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        date_str = datetime.datetime.now().strftime("%d.%m.%Y")
        if referrer_id and str(referrer_id).isdigit() and int(referrer_id) == user_id: referrer_id = None
        cursor.execute("INSERT INTO users (user_id, username, reg_date, balance, referrer_id, lang) VALUES (?, ?, ?, 0.0, ?, 'ru')",
                      (user_id, username, date_str, referrer_id))
        conn.commit()
        if referrer_id:
            try: bot.send_message(referrer_id, f"🎉 Новый реферал!\n👤 @{username or user_id}\n📅 {date_str}", parse_mode="HTML")
            except: pass
        bot.send_message(ADMIN_ID, f"🆕 @{username or 'нет'}\n🆔 {user_id}" + (f"\n🔗 Реферал: {referrer_id}" if referrer_id else ""))
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT balance, gold_balance, usd_balance, purchases_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone(); conn.close()
    return {"balance": row[0] or 0, "gold_balance": row[1] or 0, "usd_balance": row[2] or 0, "purchases_count": row[3] or 0} if row else {"balance": 0, "gold_balance": 0, "usd_balance": 0, "purchases_count": 0}

def update_balance(user_id, amount):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id)); conn.commit(); conn.close()

def update_gold_balance(user_id, amount):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE users SET gold_balance = gold_balance + ? WHERE user_id = ?", (amount, user_id)); conn.commit(); conn.close()

def update_usd_balance(user_id, amount):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("UPDATE users SET usd_balance = usd_balance + ? WHERE user_id = ?", (amount, user_id)); conn.commit(); conn.close()

def get_ref_stats(user_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)); count = cursor.fetchone()[0] or 0
    cursor.execute("SELECT ref_balance, ref_usd, ref_gold FROM users WHERE user_id = ?", (user_id,)); row = cursor.fetchone(); conn.close()
    return (count, row[0] or 0, row[1] or 0, row[2] or 0) if row else (count, 0, 0, 0)

def add_promocode(code, discount):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO promocodes (code, discount) VALUES (?, ?)", (code, discount)); conn.commit(); conn.close()

def get_promocode(code):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT discount, active FROM promocodes WHERE code = ? AND active = 1", (code,)); row = cursor.fetchone(); conn.close(); return row

def delete_promocode(code):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("DELETE FROM promocodes WHERE code = ?", (code,)); conn.commit(); conn.close()

def record_purchase(user_id, product_id, price, product_name, content=None, content_type=None):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO purchases_stats (user_id, product_id, price, date) VALUES (?, ?, ?, ?)", (user_id, product_id, price, date_str))
    cursor.execute("INSERT INTO user_purchases (user_id, product_name, product_id, price, content, content_type, date) VALUES (?, ?, ?, ?, ?, ?, ?)", (user_id, product_name, product_id, price, content, content_type, date_str))
    cursor.execute("UPDATE users SET purchases_count = purchases_count + 1 WHERE user_id = ?", (user_id,)); conn.commit(); conn.close()

def get_stats():
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*), SUM(price) FROM purchases_stats"); total = cursor.fetchone()
    cursor.execute("SELECT COUNT(*), SUM(price) FROM purchases_stats WHERE date LIKE ?", (today + '%',)); today_data = cursor.fetchone()
    conn.close()
    return {"total": total[0] or 0, "today": today_data[0] or 0}

def create_balance_request(user_id, amount, method):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("INSERT INTO balance_requests (user_id, amount, status, method) VALUES (?, ?, 'pending', ?)", (user_id, amount, method)); req_id = cursor.lastrowid; conn.commit(); conn.close(); return req_id

def get_balance_request(req_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, status, invoice_id, method FROM balance_requests WHERE id = ?", (req_id,)); row = cursor.fetchone(); conn.close(); return row

def approve_balance_request(req_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, method FROM balance_requests WHERE id = ?", (req_id,)); row = cursor.fetchone()
    if not row: conn.close(); return None, None
    uid, amt, method = row; curr = method.split('_')[1] if '_' in method else 'rub'
    if curr == 'rub': cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amt, uid))
    elif curr == 'usd': cursor.execute("UPDATE users SET usd_balance = usd_balance + ? WHERE user_id = ?", (amt, uid))
    elif curr == 'gold': cursor.execute("UPDATE users SET gold_balance = gold_balance + ? WHERE user_id = ?", (amt, uid))
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (uid,)); ref = cursor.fetchone()
    if ref and ref[0]:
        bonus = round(amt * 0.20)
        if curr == 'rub': cursor.execute("UPDATE users SET ref_balance = ref_balance + ? WHERE user_id = ?", (bonus, ref[0]))
        elif curr == 'usd': cursor.execute("UPDATE users SET ref_usd = ref_usd + ? WHERE user_id = ?", (bonus, ref[0]))
        elif curr == 'gold': cursor.execute("UPDATE users SET ref_gold = ref_gold + ? WHERE user_id = ?", (bonus, ref[0]))
        try: bot.send_message(ref[0], f"🎉 +{bonus} {curr.upper()}!", parse_mode="HTML")
        except: pass
    cursor.execute("UPDATE balance_requests SET status='approved' WHERE id=?", (req_id,)); conn.commit(); conn.close()
    return uid, amt

def create_crypto_invoice(amount_rub, description):
    rate = get_usdt_rub_rate(); amount_usdt = round(amount_rub / rate, 2)
    try:
        resp = requests.post("https://pay.crypt.bot/api/createInvoice", json={"asset": "USDT", "amount": str(amount_usdt), "description": description}, headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if resp.get("ok"): return resp["result"]["bot_invoice_url"], resp["result"]["invoice_id"]
    except: pass
    return None, None

def check_crypto_invoice(invoice_id):
    try:
        resp = requests.post("https://pay.crypt.bot/api/getInvoices", json={"invoice_ids": str(invoice_id)}, headers={"Crypto-Pay-API-Token": CRYPTO_TOKEN}).json()
        if resp.get("ok") and resp["result"]["items"]: return resp["result"]["items"][0]["status"] == "paid"
    except: pass
    return False

# ================= КЛАВИАТУРЫ =================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("🛍 Магазин / Shop"))
    markup.row(types.KeyboardButton("👤 Профиль / Profile"), types.KeyboardButton("💰 Рефералы / Referrals"))
    markup.row(types.KeyboardButton("👨‍💻 Поддержка / Support"))
    return markup

def admin_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ Категория", callback_data="adm_cat"), types.InlineKeyboardButton("🖼️ Фото меню", callback_data="adm_menu_photo"))
    markup.add(types.InlineKeyboardButton("🖼️ Фото оплаты", callback_data="adm_pay_photo"), types.InlineKeyboardButton("✏️ Ред. товар", callback_data="adm_edit"))
    markup.add(types.InlineKeyboardButton("🎟️ Промокоды", callback_data="adm_promo"), types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"))
    markup.add(types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_mail"), types.InlineKeyboardButton("💳 Заявки", callback_data="adm_reqs"))
    markup.add(types.InlineKeyboardButton("💰 Баланс", callback_data="adm_bal"), types.InlineKeyboardButton("🔄 Переместить", callback_data="adm_move"))
    markup.add(types.InlineKeyboardButton("🖼️ Упр. фото", callback_data="adm_photos"))
    return markup

def send_with_photo(chat_id, text, markup, photo_id=None):
    if photo_id:
        try: bot.send_photo(chat_id, photo_id, caption=text, parse_mode="HTML", reply_markup=markup); return
        except: pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

# ================= ОБРАБОТЧИКИ ФАЙЛОВ =================
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    uid = message.from_user.id; d = admin_product_draft.get(uid, {})
    if d.get('waiting_menu_photo'):
        set_setting("menu_photo", message.photo[-1].file_id); bot.send_message(message.chat.id, "✅ Фото меню сохранено!"); del admin_product_draft[uid]; return
    if d.get('waiting_pay_photo'):
        set_setting("payment_photo", message.photo[-1].file_id); bot.send_message(message.chat.id, "✅ Фото оплаты сохранено!"); del admin_product_draft[uid]; return
    if d.get('waiting_cat_photo'):
        fid = message.photo[-1].file_id; tgt = d
        if tgt['target_type'] == 'category': update_category_photo(tgt['target_id'], fid)
        elif tgt['target_type'] == 'subcategory': update_subcategory_photo(tgt['target_id'], fid)
        elif tgt['target_type'] == 'product': update_product_photo(tgt['target_id'], fid)
        bot.send_message(message.chat.id, "✅ Фото сохранено!"); del admin_product_draft[uid]; return
    if d.get('waiting_product_photo'):
        admin_product_draft[uid]['photo_id'] = message.photo[-1].file_id
        admin_product_draft[uid]['waiting_product_photo'] = False
        if d.get('content_type') == 'text': admin_product_draft[uid]['waiting_content'] = True; bot.send_message(message.chat.id, "📝 Отправьте текст/ссылку:")
        else: admin_product_draft[uid]['waiting_file'] = True; bot.send_message(message.chat.id, "📎 Отправьте файл:")
        return
    if d.get('waiting_file') and message.photo:
        fid = message.photo[-1].file_id
        if d.get('action') == 'replace_file': update_product_content(d['prod_id'], 'photo', fid); bot.send_message(message.chat.id, "✅ Файл обновлён!")
        else: add_product(d['parent_type'], d['parent_id'], d['name'], d['desc'], d['price'], d.get('photo_id'), 'photo', fid, d['stock']); bot.send_message(message.chat.id, f"✅ Товар создан!")
        del admin_product_draft[uid]; return

@bot.message_handler(content_types=['document', 'video', 'audio', 'voice'])
def handle_file(message):
    uid = message.from_user.id; d = admin_product_draft.get(uid, {})
    if d.get('waiting_file'):
        fid, ftype = None, None
        if message.document: fid, ftype = message.document.file_id, 'document'
        elif message.video: fid, ftype = message.video.file_id, 'video'
        elif message.audio: fid, ftype = message.audio.file_id, 'audio'
        elif message.voice: fid, ftype = message.voice.file_id, 'audio'
        if fid:
            if d.get('action') == 'replace_file': update_product_content(d['prod_id'], ftype, fid); bot.send_message(message.chat.id, "✅ Файл обновлён!")
            else: add_product(d['parent_type'], d['parent_id'], d['name'], d['desc'], d['price'], d.get('photo_id'), ftype, fid, d['stock']); bot.send_message(message.chat.id, f"✅ Товар создан!")
            del admin_product_draft[uid]
        else: bot.send_message(message.chat.id, "❌ Отправьте файл!")

# ================= КОМАНДЫ =================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    args = message.text.split(); ref = args[1] if len(args) > 1 and args[1].isdigit() else None
    add_user(message.from_user.id, message.from_user.username, ref)
    user_id = message.from_user.id
    text = tr(user_id,
        "👑 Добро пожаловать в магазин NetWing!\n\nЗдесь вы можете приобрести конфиги и приватный канал.\n\nКоманды:\n/language - сменить язык",
        "👑 Welcome to NetWing shop!\n\nHere you can purchase configs and private channel.\n\nCommands:\n/language - change language")
    send_with_photo(message.chat.id, text, main_menu(), get_setting("menu_photo"))

@bot.message_handler(commands=['language'])
def cmd_language(message):
    user_id = message.from_user.id
    current = get_user_lang(user_id)
    new_lang = 'en' if current == 'ru' else 'ru'
    set_user_lang(user_id, new_lang)
    
    if new_lang == 'en':
        text = "🇬🇧 Language changed to English!\n\nUse /start to see the menu."
    else:
        text = "🇷🇺 Язык изменён на Русский!\n\nИспользуйте /start чтобы увидеть меню."
    
    bot.send_message(message.chat.id, text)
    cmd_start(message)

@bot.message_handler(commands=['skip_photo'])
def skip_photo(message):
    if message.from_user.id in admin_product_draft:
        d = admin_product_draft[message.from_user.id]
        if d.get('waiting_product_photo'): d['photo_id'] = None; d['waiting_product_photo'] = False; d['waiting_content'] = True; bot.send_message(message.chat.id, "📝 Отправьте текст/ссылку:")

# ================= ТЕКСТ =================
@bot.message_handler(content_types=['text'])
def handle_text(message):
    uid = message.from_user.id; d = admin_product_draft.get(uid, {}); txt = message.text
    
    if d.get('waiting_content'):
        content = message.text
        if d.get('action') == 'replace_content': update_product_content(d['prod_id'], 'text', content); bot.send_message(message.chat.id, "✅ Контент обновлён!")
        else: add_product(d['parent_type'], d['parent_id'], d['name'], d['desc'], d['price'], d.get('photo_id'), 'text', content, d['stock']); bot.send_message(message.chat.id, f"✅ Товар создан!")
        del admin_product_draft[uid]; return
    
    if txt in ["🛍 Магазин / Shop"]:
        cats = get_categories(); markup = types.InlineKeyboardMarkup(row_width=1)
        for c_id, c_name, _ in cats: markup.add(types.InlineKeyboardButton(c_name, callback_data=f"cat_{c_id}"))
        bot.send_message(message.chat.id, tr(uid, "🛍 Выберите раздел:", "🛍 Choose category:"), reply_markup=markup)
    
    elif txt in ["👤 Профиль / Profile"]:
        user = get_user(uid); _, ref_rub, ref_usd, ref_gold = get_ref_stats(uid)
        text = tr(uid,
            f"👤 Профиль\n\n💰 RUB: {user['balance']} ₽ (Ref: {ref_rub})\n💵 USD: {user['usd_balance']} $ (Ref: {ref_usd})\n🪙 GOLD: {user['gold_balance']} (Ref: {ref_gold})\n🛒 Покупок: {user['purchases_count']}",
            f"👤 Profile\n\n💰 RUB: {user['balance']} ₽ (Ref: {ref_rub})\n💵 USD: {user['usd_balance']} $ (Ref: {ref_usd})\n🪙 GOLD: {user['gold_balance']} (Ref: {ref_gold})\n🛒 Purchases: {user['purchases_count']}")
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(tr(uid, "📦 Мои покупки", "📦 My purchases"), callback_data="my_purch"))
        markup.add(types.InlineKeyboardButton(tr(uid, "💳 Пополнить", "💳 Top up"), callback_data="topup"))
        markup.add(types.InlineKeyboardButton(tr(uid, "🎟️ Промокод", "🎟️ Promo"), callback_data="promo"))
        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")
    
    elif txt in ["💰 Рефералы / Referrals"]:
        count, ref_rub, ref_usd, ref_gold = get_ref_stats(uid)
        link = f"https://t.me/{BOT_USERNAME}?start={uid}"
        bot.send_message(message.chat.id, tr(uid,
            f"🤝 Рефералы: {count}\n💰 RUB: {ref_rub} ₽\n💵 USD: {ref_usd} $\n🪙 GOLD: {ref_gold}\n\n🔗 <code>{link}</code>",
            f"🤝 Referrals: {count}\n💰 RUB: {ref_rub} ₽\n💵 USD: {ref_usd} $\n🪙 GOLD: {ref_gold}\n\n🔗 <code>{link}</code>"), parse_mode="HTML")
    
    elif txt in ["👨‍💻 Поддержка / Support"]:
        bot.send_message(message.chat.id, tr(uid, f"💬 Напишите: @{ADMIN_USERNAME}", f"💬 Contact: @{ADMIN_USERNAME}"))
    
    elif txt == "⚙️ Админ панель" and uid == ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 Админ-панель:", reply_markup=admin_menu())

# ================= МАГАЗИН =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def view_cat(call):
    cat_id = int(call.data.split('_')[1]); cat = get_category(cat_id)
    if not cat: return
    uid = call.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    for s_id, s_name, _ in get_subcategories(cat_id): markup.add(types.InlineKeyboardButton(f"📁 {s_name}", callback_data=f"sub_{s_id}"))
    for p_id, p_name, p_price, _, stock in get_products('category', cat_id):
        usd = round(p_price / get_usdt_rub_rate(), 2)
        markup.add(types.InlineKeyboardButton(f"📦 {p_name} — {p_price}₽ (${usd})", callback_data=f"buy_{p_id}"))
    if uid == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("➕ Подкатегория", callback_data=f"add_sub_{cat_id}"))
        markup.add(types.InlineKeyboardButton("➕ Товар", callback_data=f"add_prod_cat_{cat_id}"))
    markup.add(types.InlineKeyboardButton("‹ Назад / Back", callback_data="back_menu"))
    send_with_photo(call.message.chat.id, f"📁 {cat[1]}", markup, cat[2])

@bot.callback_query_handler(func=lambda call: call.data.startswith('sub_'))
def view_sub(call):
    sub_id = int(call.data.split('_')[1]); sub = get_subcategory(sub_id)
    if not sub: return
    uid = call.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p_id, p_name, p_price, _, stock in get_products('subcategory', sub_id):
        usd = round(p_price / get_usdt_rub_rate(), 2)
        markup.add(types.InlineKeyboardButton(f"📦 {p_name} — {p_price}₽ (${usd})", callback_data=f"buy_{p_id}"))
    if uid == ADMIN_ID: markup.add(types.InlineKeyboardButton("➕ Товар", callback_data=f"add_prod_sub_{sub_id}"))
    markup.add(types.InlineKeyboardButton("‹ Назад / Back", callback_data=f"cat_{sub[3]}"))
    send_with_photo(call.message.chat.id, f"📁 {sub[1]}", markup, sub[2])

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def buy_product(call):
    prod_id = int(call.data.split('_')[1]); prod = get_product(prod_id)
    if not prod: return
    name, _, price, photo, _, _, ptype, pid, stock = prod
    uid = call.from_user.id
    user = get_user(uid); _, ref_rub, _, ref_gold = get_ref_stats(uid)
    usd_price = round(price / get_usdt_rub_rate(), 2); gold_price = round(price / GOLDA_RATE)
    text = tr(uid,
        f"📦 {name}\n\n💰 {price} ₽ | ${usd_price}\n📦 Остаток: {stock}\n💼 Баланс: {user['balance']+ref_rub} ₽ | {user['gold_balance']+ref_gold} голды",
        f"📦 {name}\n\n💰 {price} ₽ | ${usd_price}\n📦 Stock: {stock}\n💼 Balance: {user['balance']+ref_rub} ₽ | {user['gold_balance']+ref_gold} gold")
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 Картой / Card", callback_data=f"pay_balance_{prod_id}"))
    markup.add(types.InlineKeyboardButton(f"🪙 Голдой / Gold ({gold_price})", callback_data=f"pay_gold_{prod_id}"))
    markup.add(types.InlineKeyboardButton("💸 CRYPTO", callback_data=f"pay_crypto_{prod_id}"))
    markup.add(types.InlineKeyboardButton("‹ Назад / Back", callback_data=f"view_back_{ptype}_{pid}"))
    send_with_photo(call.message.chat.id, text, markup, photo)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_back_'))
def view_back(call):
    parts = call.data.split('_')
    if parts[2] == 'category': call.data = f"cat_{parts[3]}"; view_cat(call)
    else: call.data = f"sub_{parts[3]}"; view_sub(call)

# ================= ПОКУПКИ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_balance_'))
def pay_balance(call):
    prod_id = int(call.data.split('_')[2]); prod = get_product(prod_id)
    if not prod: return
    name, _, price, _, content_type, content, _, _, stock = prod
    uid = call.from_user.id; user = get_user(uid); _, ref_rub, _, _ = get_ref_stats(uid); total = user['balance'] + ref_rub
    if total < price:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(tr(uid, "💳 Пополнить", "💳 Top up"), callback_data="topup"))
        markup.add(types.InlineKeyboardButton("‹ Назад / Back", callback_data=f"buy_{prod_id}"))
        bot.send_message(call.message.chat.id, tr(uid, f"❌ Недостаточно!\n💰 {price} ₽\n💼 {total} ₽", f"❌ Not enough!\n💰 {price} ₽\n💼 {total} ₽"), reply_markup=markup)
        bot.answer_callback_query(call.id); return
    if stock <= 0: bot.answer_callback_query(call.id, tr(uid, "❌ Закончился!", "❌ Out of stock!")); return
    rem = price
    if user['balance'] >= rem: update_balance(uid, -rem)
    else: update_balance(uid, -user['balance']); rem -= user['balance']; conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE users SET ref_balance = ref_balance - ? WHERE user_id = ?", (rem, uid)); conn.commit(); conn.close()
    decrease_stock(prod_id); record_purchase(uid, prod_id, price, name, content, content_type)
    bot.send_message(uid, f"✅ {name} — {price} ₽!")
    send_content(uid, content_type, content, f"🎉 {name}")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_gold_'))
def pay_gold(call):
    prod_id = int(call.data.split('_')[2]); prod = get_product(prod_id)
    if not prod: return
    name, _, price, _, content_type, content, _, _, stock = prod
    uid = call.from_user.id; user = get_user(uid); _, _, _, ref_gold = get_ref_stats(uid); needed = round(price / GOLDA_RATE); total = user['gold_balance'] + ref_gold
    if total < needed:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(tr(uid, "🪙 Пополнить", "🪙 Top up"), callback_data="topup"))
        markup.add(types.InlineKeyboardButton("‹ Назад / Back", callback_data=f"buy_{prod_id}"))
        bot.send_message(call.message.chat.id, tr(uid, f"❌ Недостаточно!\n🪙 {needed}\n💼 {total}", f"❌ Not enough!\n🪙 {needed}\n💼 {total}"), reply_markup=markup)
        bot.answer_callback_query(call.id); return
    if stock <= 0: bot.answer_callback_query(call.id, "❌ Out of stock!"); return
    rem = needed
    if user['gold_balance'] >= rem: update_gold_balance(uid, -rem)
    else: update_gold_balance(uid, -user['gold_balance']); rem -= user['gold_balance']; conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE users SET ref_gold = ref_gold - ? WHERE user_id = ?", (rem, uid)); conn.commit(); conn.close()
    decrease_stock(prod_id); record_purchase(uid, prod_id, price, name, content, content_type)
    bot.send_message(uid, f"✅ {name} — {needed} голды!")
    send_content(uid, content_type, content, f"🎉 {name}")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_crypto_'))
def pay_crypto(call):
    prod_id = int(call.data.split('_')[2]); prod = get_product(prod_id)
    if not prod: return
    name, _, price, _, content_type, content, _, _, stock = prod
    url, inv_id = create_crypto_invoice(price, f"Purchase: {name}")
    if url:
        conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("INSERT INTO balance_requests (user_id, amount, invoice_id, status, method) VALUES (?, ?, ?, 'pending', 'crypto_purchase')", (call.from_user.id, price, inv_id)); rid = conn.cursor().lastrowid; conn.commit(); conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔗 Оплатить / Pay", url=url), types.InlineKeyboardButton("🔄 Проверить / Check", callback_data=f"check_p_{rid}_{prod_id}"))
        markup.add(types.InlineKeyboardButton("❌ Отмена / Cancel", callback_data=f"buy_{prod_id}"))
        bot.send_message(call.message.chat.id, f"💸 CRYPTO\n📦 {name}\n💰 {price} ₽\n💵 {round(price/get_usdt_rub_rate(),2)} USD", reply_markup=markup)
    else: bot.answer_callback_query(call.id, "❌ Ошибка / Error", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_p_'))
def check_p(call):
    _, rid, pid = call.data.split('_'); rid, pid = int(rid), int(pid)
    conn = sqlite3.connect("bot_database.db"); c = conn.cursor(); c.execute("SELECT invoice_id FROM balance_requests WHERE id=?", (rid,)); row = c.fetchone(); conn.close()
    if row and check_crypto_invoice(row[0]):
        prod = get_product(pid)
        if prod and prod[8] > 0:
            name, _, price, _, ct, content, _, _, _ = prod
            conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status='approved' WHERE id=?", (rid,)); conn.commit(); conn.close()
            decrease_stock(pid); record_purchase(call.from_user.id, pid, price, name, content, ct)
            bot.edit_message_text(f"✅ {name}", call.message.chat.id, call.message.message_id)
            send_content(call.from_user.id, ct, content, f"🎉 {name}")
            bot.send_message(ADMIN_ID, f"✅ Крипто!\n👤 {call.from_user.id}\n📦 {name}\n💰 {price} ₽")
        else: bot.answer_callback_query(call.id, "❌ Закончился!")
    else: bot.answer_callback_query(call.id, "❌ Не оплачено")

def send_content(chat_id, ct, content, caption):
    try:
        if ct == 'text': bot.send_message(chat_id, f"{caption}\n\n{content}")
        elif ct == 'photo': bot.send_photo(chat_id, content, caption=caption)
        elif ct == 'video': bot.send_video(chat_id, content, caption=caption)
        elif ct == 'document': bot.send_document(chat_id, content, caption=caption)
        elif ct == 'audio': bot.send_audio(chat_id, content, caption=caption)
        else: bot.send_message(chat_id, f"{caption}\n{content}")
    except: bot.send_message(chat_id, "❌ Ошибка выдачи.")

# ================= ПОПОЛНЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data == "topup")
def topup_start(call):
    uid = call.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 RUB", callback_data="t_cur_rub"), types.InlineKeyboardButton("💸 USD", callback_data="t_cur_usd"), types.InlineKeyboardButton("🪙 GOLD", callback_data="t_cur_gold"))
    bot.edit_message_text(tr(uid, "💱 Выберите валюту:", "💱 Choose currency:"), call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('t_cur_'))
def topup_cur(call):
    cur = call.data.split('_')[2]; uid = call.from_user.id
    if cur == 'rub': msg = bot.send_message(call.message.chat.id, tr(uid, "💳 Сумма в рублях:", "💳 Amount in RUB:")); bot.register_next_step_handler(msg, topup_rub)
    elif cur == 'usd': msg = bot.send_message(call.message.chat.id, tr(uid, "💸 Сумма в долларах:", "💸 Amount in USD:")); bot.register_next_step_handler(msg, topup_usd)
    elif cur == 'gold': msg = bot.send_message(call.message.chat.id, tr(uid, "🪙 Сумма в голде:", "🪙 Amount in GOLD:")); bot.register_next_step_handler(msg, topup_gold)

def topup_rub(message):
    try:
        amt = int(message.text)
        if amt < 1: raise ValueError
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💳 СБП", callback_data=f"bal_sbp_{amt}_rub"), types.InlineKeyboardButton("💸 CRYPTO", callback_data=f"bal_cry_{amt}_rub"))
        bot.send_message(message.chat.id, f"💳 {amt} ₽\nВыберите способ:", reply_markup=markup)
    except: msg = bot.send_message(message.chat.id, "❌ Число > 0"); bot.register_next_step_handler(msg, topup_rub)

def topup_usd(message):
    try:
        usd = int(message.text)
        if usd < 1: raise ValueError
        amt = round(usd * get_usdt_rub_rate())
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💳 СБП", callback_data=f"bal_sbp_{amt}_usd"), types.InlineKeyboardButton("💸 CRYPTO", callback_data=f"bal_cry_{amt}_usd"))
        bot.send_message(message.chat.id, f"💸 {usd} USD = {amt} ₽\nВыберите способ:", reply_markup=markup)
    except: msg = bot.send_message(message.chat.id, "❌ Число > 0"); bot.register_next_step_handler(msg, topup_usd)

def topup_gold(message):
    try:
        gold = int(message.text)
        if gold < 1: raise ValueError
        rid = create_balance_request(message.from_user.id, gold, 'gold_direct')
        gold_to_buy = round(gold / (1 - COMMISSION))
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📝 Написать админу", url=f"https://t.me/{ADMIN_USERNAME}"))
        markup.add(types.InlineKeyboardButton("✅ Я купил", callback_data=f"g_done_{rid}"))
        bot.send_message(message.chat.id, f"🪙 GOLD\n\nВы хотите: {gold} голды\nКомиссия 20%: купить за {gold_to_buy}\nПолучите: {gold}", reply_markup=markup)
    except: msg = bot.send_message(message.chat.id, "❌ Число > 0"); bot.register_next_step_handler(msg, topup_gold)

@bot.callback_query_handler(func=lambda call: call.data.startswith('bal_sbp_') and 'done' not in call.data)
def bal_sbp(call):
    parts = call.data.split('_'); amt, cur = int(parts[2]), parts[3]
    rid = create_balance_request(call.from_user.id, amt, f'sbp_{cur}')
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"bal_sbp_done_{rid}"), types.InlineKeyboardButton("❌ Отмена", callback_data="back_menu"))
    bot.edit_message_text(f"💳 СБП\n💰 {amt} ₽\n🏦 Сбербанк\n💳 2202206714879132\n👤 Илья\n\n📸 Отправьте скриншот", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('bal_sbp_done_'))
def bal_sbp_done(call):
    rid = int(call.data.split('_')[3])
    msg = bot.send_message(call.message.chat.id, "📷 Отправьте чек:"); bot.register_next_step_handler(msg, lambda m: sbp_rec(m, rid))

def sbp_rec(message, rid):
    if not (message.photo or message.document):
        msg = bot.send_message(message.chat.id, "❌ Скриншот!"); bot.register_next_step_handler(msg, lambda m: sbp_rec(m, rid)); return
    bot.send_message(message.chat.id, "⏳ Отправлено админу")
    row = get_balance_request(rid)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_apr_{rid}"), types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_dec_{rid}"))
    cap = f"💳 Пополнение\n👤 {message.from_user.id}\n💰 {row[1]} ₽"
    if message.photo: bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=cap, reply_markup=markup)
    else: bot.send_document(ADMIN_ID, message.document.file_id, caption=cap, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('bal_cry_'))
def bal_cry(call):
    parts = call.data.split('_'); amt, cur = int(parts[2]), parts[3]
    rid = create_balance_request(call.from_user.id, amt, f'crypto_{cur}')
    url, inv_id = create_crypto_invoice(amt, f"Top-up {amt} ₽")
    if url:
        conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET invoice_id = ? WHERE id = ?", (inv_id, rid)); conn.commit(); conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔗 Оплатить", url=url), types.InlineKeyboardButton("🔄 Проверить", callback_data=f"chk_cry_{rid}"))
        bot.edit_message_text(f"🧾 {round(amt/get_usdt_rub_rate(),2)} USDT", call.message.chat.id, call.message.message_id, reply_markup=markup)
    else: bot.answer_callback_query(call.id, "❌ Ошибка")

@bot.callback_query_handler(func=lambda call: call.data.startswith('chk_cry_'))
def chk_cry(call):
    rid = int(call.data.split('_')[2]); row = get_balance_request(rid)
    if not row: return
    if row[2] == 'approved': bot.answer_callback_query(call.id, "✅ Уже пополнено!"); return
    if check_crypto_invoice(row[3]):
        uid, amt = approve_balance_request(rid)
        bot.edit_message_text(f"✅ +{amt} ₽!", call.message.chat.id, call.message.message_id)
        bot.send_message(uid, f"✅ +{amt} ₽!")
    else: bot.answer_callback_query(call.id, "❌ Не оплачено")

@bot.callback_query_handler(func=lambda call: call.data.startswith('g_done_'))
def g_done(call):
    rid = int(call.data.split('_')[2])
    bot.edit_message_text("⏳ Отправлено админу.", call.message.chat.id, call.message.message_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_g_apr_{rid}"), types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_g_dec_{rid}"))
    bot.send_message(ADMIN_ID, f"🪙 GOLD\n👤 {call.from_user.id}", reply_markup=markup)

# ================= АДМИН ПОДТВЕРЖДЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_apr_'))
def adm_apr(call):
    rid = int(call.data.split('_')[2]); uid, amt = approve_balance_request(rid)
    if uid: bot.edit_message_caption("✅ Подтверждено", call.message.chat.id, call.message.message_id); bot.send_message(uid, f"✅ Заявка №{rid} одобрена!\n💰 +{amt} ₽")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_dec_'))
def adm_dec(call):
    rid = int(call.data.split('_')[2])
    conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status='declined' WHERE id=?", (rid,)); conn.commit(); conn.close()
    bot.edit_message_caption("❌ Отклонено", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_g_apr_'))
def adm_g_apr(call):
    rid = int(call.data.split('_')[3]); row = get_balance_request(rid)
    if row: update_gold_balance(row[0], row[1]); conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status='approved' WHERE id=?", (rid,)); conn.commit(); conn.close(); bot.edit_message_text(f"✅ +{row[1]} gold!", call.message.chat.id, call.message.message_id); bot.send_message(row[0], f"✅ +{row[1]} gold!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_g_dec_'))
def adm_g_dec(call):
    rid = int(call.data.split('_')[3])
    conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status='declined' WHERE id=?", (rid,)); conn.commit(); conn.close()
    bot.edit_message_text("❌ Отклонено", call.message.chat.id, call.message.message_id)

# ================= ПОКУПКИ =================
@bot.callback_query_handler(func=lambda call: call.data == "my_purch")
def my_purch(call):
    conn = sqlite3.connect("bot_database.db"); c = conn.cursor(); c.execute("SELECT product_name, price, date, content, content_type FROM user_purchases WHERE user_id=? ORDER BY id DESC LIMIT 20", (call.from_user.id,)); rows = c.fetchall(); conn.close()
    uid = call.from_user.id
    if not rows: bot.edit_message_text(tr(uid, "📦 Нет покупок", "📦 No purchases"), call.message.chat.id, call.message.message_id); return
    text = tr(uid, "📦 <b>Покупки:</b>\n\n", "📦 <b>Purchases:</b>\n\n")
    for name, price, date, content, ct in rows: text += f"• {name} — {price} ₽\n  📅 {date}\n\n"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "promo")
def promo_enter(call):
    uid = call.from_user.id
    msg = bot.send_message(call.message.chat.id, tr(uid, "🎟️ Введите промокод:", "🎟️ Enter promo code:"))
    bot.register_next_step_handler(msg, process_promo)

def process_promo(message):
    code = message.text.strip().upper(); promo = get_promocode(code); uid = message.from_user.id
    if promo:
        user = get_user(uid); bonus = user['purchases_count'] * promo[0] / 100; update_balance(uid, bonus)
        bot.send_message(message.chat.id, tr(uid, f"✅ +{bonus:.2f} ₽!", f"✅ +{bonus:.2f} ₽!"))
    else: bot.send_message(message.chat.id, tr(uid, "❌ Недействительный", "❌ Invalid"))

@bot.callback_query_handler(func=lambda call: call.data == "back_menu")
def back_menu(call):
    bot.answer_callback_query(call.id)
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    cmd_start(call.message)

# ================= АДМИНКА =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('add_sub_'))
def add_sub_start(call):
    if call.from_user.id != ADMIN_ID: return
    cat_id = int(call.data.split('_')[2])
    msg = bot.send_message(call.message.chat.id, "📝 Название подкатегории:"); bot.register_next_step_handler(msg, lambda m: (add_subcategory(cat_id, m.text), bot.send_message(ADMIN_ID, "✅ Подкатегория создана!")))

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_prod_cat_'))
def add_prod_cat(call):
    if call.from_user.id != ADMIN_ID: return
    cat_id = int(call.data.split('_')[3])
    admin_product_draft[call.from_user.id] = {'parent_type': 'category', 'parent_id': cat_id}
    msg = bot.send_message(call.message.chat.id, "1️⃣ Название:"); bot.register_next_step_handler(msg, prod_name)

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_prod_sub_'))
def add_prod_sub(call):
    if call.from_user.id != ADMIN_ID: return
    sub_id = int(call.data.split('_')[3])
    admin_product_draft[call.from_user.id] = {'parent_type': 'subcategory', 'parent_id': sub_id}
    msg = bot.send_message(call.message.chat.id, "1️⃣ Название:"); bot.register_next_step_handler(msg, prod_name)

def prod_name(message):
    admin_product_draft[message.from_user.id]['name'] = message.text
    msg = bot.send_message(message.chat.id, "2️⃣ Описание:"); bot.register_next_step_handler(msg, prod_desc)

def prod_desc(message):
    admin_product_draft[message.from_user.id]['desc'] = message.text
    msg = bot.send_message(message.chat.id, "3️⃣ Цена:"); bot.register_next_step_handler(msg, prod_price)

def prod_price(message):
    if not message.text.isdigit(): msg = bot.send_message(message.chat.id, "❌ Число!"); bot.register_next_step_handler(msg, prod_price); return
    admin_product_draft[message.from_user.id]['price'] = int(message.text)
    msg = bot.send_message(message.chat.id, "4️⃣ Остаток:"); bot.register_next_step_handler(msg, prod_stock)

def prod_stock(message):
    if not message.text.isdigit(): msg = bot.send_message(message.chat.id, "❌ Число!"); bot.register_next_step_handler(msg, prod_stock); return
    admin_product_draft[message.from_user.id]['stock'] = int(message.text)
    admin_product_draft[message.from_user.id]['waiting_content_type'] = True
    bot.send_message(message.chat.id, "5️⃣ Отправь 'text' или 'file' (или просто файл):")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_actions(call):
    if call.from_user.id != ADMIN_ID: return
    d = call.data
    if d == "adm_cat":
        msg = bot.send_message(call.message.chat.id, "📝 Название категории:")
        bot.register_next_step_handler(msg, lambda m: (add_category(m.text), bot.send_message(ADMIN_ID, "✅ Категория создана!")))
    elif d == "adm_menu_photo": admin_product_draft[call.from_user.id] = {'waiting_menu_photo': True}; bot.send_message(call.message.chat.id, "🖼️ Отправь фото меню:")
    elif d == "adm_pay_photo": admin_product_draft[call.from_user.id] = {'waiting_pay_photo': True}; bot.send_message(call.message.chat.id, "🖼️ Отправь фото оплаты:")
    elif d == "adm_promo":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Создать", callback_data="adm_promo_add"), types.InlineKeyboardButton("🗑️ Удалить", callback_data="adm_promo_del"))
        bot.edit_message_text("🎟️ Промокоды", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d == "adm_promo_add":
        msg = bot.send_message(call.message.chat.id, "🎟️ КОД СКИДКА\nПример: SALE50 50")
        bot.register_next_step_handler(msg, lambda m: (add_promocode(m.text.split()[0].upper(), int(m.text.split()[1])), bot.send_message(m.chat.id, "✅ Создан!")) if len(m.text.split())==2 and m.text.split()[1].isdigit() else bot.send_message(m.chat.id, "❌ Формат"))
    elif d == "adm_promo_del": msg = bot.send_message(call.message.chat.id, "🗑️ Код:"); bot.register_next_step_handler(msg, lambda m: (delete_promocode(m.text.strip().upper()), bot.send_message(m.chat.id, "✅ Удалён!")))
    elif d == "adm_stats":
        stats = get_stats()
        bot.edit_message_text(f"📊 Статистика\n\n📅 Сегодня: {stats['today']}\n📦 Всего: {stats['total']}", call.message.chat.id, call.message.message_id)
    elif d == "adm_bal": msg = bot.send_message(call.message.chat.id, "💰 ID СУММА"); bot.register_next_step_handler(msg, lambda m: (update_balance(int(m.text.split()[0]), float(m.text.split()[1])), bot.send_message(m.chat.id, "✅ Обновлён!")) if len(m.text.split())==2 else None)
    elif d == "adm_reqs":
        conn = sqlite3.connect("bot_database.db"); c = conn.cursor(); c.execute("SELECT id, user_id, amount, method FROM balance_requests WHERE status='pending'"); reqs = c.fetchall(); conn.close()
        if not reqs: bot.edit_message_text("📭 Нет заявок", call.message.chat.id, call.message.message_id); return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for rid, uid, amt, mt in reqs: markup.add(types.InlineKeyboardButton(f"{'💳' if 'sbp' in mt else '💸'} {uid} — {amt} ₽", callback_data=f"adm_balance_req_{rid}"))
        bot.edit_message_text("💳 Заявки", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("adm_balance_req_"):
        rid = int(d.split('_')[3]); row = get_balance_request(rid)
        if not row: return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_apr_{rid}"), types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_dec_{rid}"))
        bot.edit_message_text(f"#{rid}\n👤 {row[0]}\n💰 {row[1]} ₽", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d == "adm_mail":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📝 Текст", callback_data="mail_t"), types.InlineKeyboardButton("🖼️ Текст+Фото", callback_data="mail_p"))
        bot.edit_message_text("📢 Рассылка", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d == "mail_t": admin_mailing_draft[call.from_user.id] = {'type': 'text'}; msg = bot.send_message(call.message.chat.id, "📝 Текст:"); bot.register_next_step_handler(msg, lambda m: start_mailing(call.from_user.id, m.text))
    elif d == "mail_p":
        admin_mailing_draft[call.from_user.id] = {'type': 'photo'}
        msg = bot.send_message(call.message.chat.id, "🖼️ Отправьте фото:")
        bot.register_next_step_handler(msg, lambda m: (setattr(admin_mailing_draft[call.from_user.id], 'photo', m.photo[-1].file_id) if m.photo else None, bot.send_message(call.message.chat.id, "📝 Теперь текст:"), bot.register_next_step_handler(msg, lambda m2: start_mailing(call.from_user.id, m2.text, admin_mailing_draft[call.from_user.id].get('photo')))))
    elif d == "adm_edit":
        products_list = []
        for cat_id, cat_name, _ in get_categories():
            for p_id, p_name, p_price, _, _ in get_products('category', cat_id): products_list.append((p_id, p_name, p_price))
            for s_id, s_name, _ in get_subcategories(cat_id):
                for p_id, p_name, p_price, _, _ in get_products('subcategory', s_id): products_list.append((p_id, p_name, p_price))
        if not products_list: bot.answer_callback_query(call.id, "Нет товаров"); return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for p_id, p_name, p_price in products_list[:20]: markup.add(types.InlineKeyboardButton(f"✏️ {p_name} ({p_price}₽)", callback_data=f"adm_edit_{p_id}"))
        bot.edit_message_text("✏️ Выберите товар:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("adm_edit_"):
        prod_id = int(d.replace("adm_edit_", "")); prod = get_product(prod_id)
        if not prod: return
        name, desc, price, _, ctype, _, _, _, _ = prod
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(types.InlineKeyboardButton("✏️ Название", callback_data=f"e_name_{prod_id}"), types.InlineKeyboardButton("💳 Цена", callback_data=f"e_price_{prod_id}"))
        markup.add(types.InlineKeyboardButton("📝 Описание", callback_data=f"e_desc_{prod_id}"), types.InlineKeyboardButton("📦 Остаток", callback_data=f"e_stock_{prod_id}"))
        markup.add(types.InlineKeyboardButton("📝 Контент" if ctype == 'text' else "📎 Файл", callback_data=f"e_cont_{prod_id}" if ctype == 'text' else f"e_file_{prod_id}"))
        bot.edit_message_text(f"✏️ {name}\n💰 {price} ₽\n📝 {desc}", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("e_name_"): prod_id = int(d.split('_')[2]); msg = bot.send_message(call.message.chat.id, "✏️ Новое название:"); bot.register_next_step_handler(msg, lambda m: edit_field(m, prod_id, "name"))
    elif d.startswith("e_price_"): prod_id = int(d.split('_')[2]); msg = bot.send_message(call.message.chat.id, "💳 Новая цена:"); bot.register_next_step_handler(msg, lambda m: edit_field(m, prod_id, "price"))
    elif d.startswith("e_desc_"): prod_id = int(d.split('_')[2]); msg = bot.send_message(call.message.chat.id, "📝 Новое описание:"); bot.register_next_step_handler(msg, lambda m: edit_field(m, prod_id, "description"))
    elif d.startswith("e_stock_"): prod_id = int(d.split('_')[2]); msg = bot.send_message(call.message.chat.id, "📦 Новый остаток:"); bot.register_next_step_handler(msg, lambda m: edit_field(m, prod_id, "stock"))
    elif d.startswith("e_cont_"):
        prod_id = int(d.split('_')[2]); admin_product_draft[call.from_user.id] = {'prod_id': prod_id, 'action': 'replace_content', 'waiting_content': True}
        bot.send_message(call.message.chat.id, "📝 Отправь новый текст/ссылку:")
    elif d.startswith("e_file_"):
        prod_id = int(d.split('_')[2]); admin_product_draft[call.from_user.id] = {'prod_id': prod_id, 'action': 'replace_file', 'waiting_file': True}
        bot.send_message(call.message.chat.id, "📎 Отправь новый файл:")
    elif d == "adm_move":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📂 Подкатегорию", callback_data="mv_sub"), types.InlineKeyboardButton("📦 Товар", callback_data="mv_prod"))
        bot.edit_message_text("🔄 Переместить", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d == "mv_sub":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for c_id, c_name, _ in get_categories(): markup.add(types.InlineKeyboardButton(c_name, callback_data=f"mv_sub_cat_{c_id}"))
        bot.edit_message_text("📂 Категория:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("mv_sub_cat_"):
        cat_id = int(d.split('_')[3]); markup = types.InlineKeyboardMarkup(row_width=1)
        for s_id, s_name, _ in get_subcategories(cat_id): markup.add(types.InlineKeyboardButton(s_name, callback_data=f"mv_sub_sel_{s_id}"))
        bot.edit_message_text("📂 Подкатегория:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("mv_sub_sel_"):
        sub_id = int(d.split('_')[3]); markup = types.InlineKeyboardMarkup(row_width=1)
        for c_id, c_name, _ in get_categories(): markup.add(types.InlineKeyboardButton(c_name, callback_data=f"mv_sub_to_{sub_id}_{c_id}"))
        bot.edit_message_text("📂 Новая категория:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("mv_sub_to_"): parts = d.split('_'); move_subcategory(int(parts[3]), int(parts[4])); bot.edit_message_text("✅ Перемещено!", call.message.chat.id, call.message.message_id)
    elif d == "mv_prod":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for s_id, s_name, _ in get_subcategories(): markup.add(types.InlineKeyboardButton(s_name, callback_data=f"mv_prod_sel_{s_id}"))
        bot.edit_message_text("📂 Подкатегория:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("mv_prod_sel_"):
        sub_id = int(d.split('_')[3]); markup = types.InlineKeyboardMarkup(row_width=1)
        for p_id, p_name, _, _, _ in get_products('subcategory', sub_id): markup.add(types.InlineKeyboardButton(p_name, callback_data=f"mv_prod_fin_{p_id}_{sub_id}"))
        bot.edit_message_text("📦 Товар:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("mv_prod_fin_"): parts = d.split('_'); pid, old_sub = int(parts[3]), int(parts[4])
        markup = types.InlineKeyboardMarkup(row_width=1)
        for s_id, s_name, _ in get_subcategories():
            if s_id != old_sub: markup.add(types.InlineKeyboardButton(s_name, callback_data=f"mv_prod_to_{pid}_{s_id}"))
        bot.edit_message_text("📂 Новая:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("mv_prod_to_"): parts = d.split('_'); move_product(int(parts[3]), 'subcategory', int(parts[4])); bot.edit_message_text("✅ Перемещено!", call.message.chat.id, call.message.message_id)
    elif d == "adm_photos":
        markup = types.InlineKeyboardMarkup(row_width=1)
        for c_id, c_name, _ in get_categories(): markup.add(types.InlineKeyboardButton(f"📂 {c_name}", callback_data=f"ph_cat_{c_id}"))
        bot.edit_message_text("🖼️ Выберите категорию:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("ph_cat_"):
        cat_id = int(d.split('_')[2]); cat = get_category(cat_id)
        if not cat: return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📸 Фото категории", callback_data=f"ph_set_cat_{cat_id}"))
        for s_id, s_name, _ in get_subcategories(cat_id): markup.add(types.InlineKeyboardButton(f"📂 {s_name}", callback_data=f"ph_sub_{s_id}"))
        bot.edit_message_text(f"📂 {cat[1]}", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif d.startswith("ph_set_cat_"):
        cat_id = int(d.split('_')[3]); admin_product_draft[call.from_user.id] = {'waiting_cat_photo': True, 'target_id': cat_id, 'target_type': 'category'}
        bot.send_message(call.message.chat.id, "🖼️ Отправьте фото:")
    elif d.startswith("ph_sub_"):
        sub_id = int(d.split('_')[2]); admin_product_draft[call.from_user.id] = {'waiting_cat_photo': True, 'target_id': sub_id, 'target_type': 'subcategory'}
        bot.send_message(call.message.chat.id, "🖼️ Отправьте фото:")

def edit_field(message, prod_id, field):
    try: val = int(message.text) if field in ('price', 'stock') else message.text
    except: bot.send_message(message.chat.id, "❌ Ошибка!"); return
    conn = sqlite3.connect("bot_database.db"); conn.cursor().execute(f"UPDATE products SET {field}=? WHERE id=?", (val, prod_id)); conn.commit(); conn.close()
    bot.send_message(message.chat.id, "✅ Обновлено!")

def start_mailing(admin_id, text, photo=None):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor(); cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall(); conn.close()
    sent = 0
    for user in users:
        try:
            if photo: bot.send_photo(user[0], photo, caption=text, parse_mode="HTML")
            else: bot.send_message(user[0], text, parse_mode="HTML")
            sent += 1
        except: pass
    bot.send_message(admin_id, f"✅ Рассылка!\nОтправлено: {sent}/{len(users)}")
    if admin_id in admin_mailing_draft: del admin_mailing_draft[admin_id]

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("🤖 Запуск бота...")
    
    # Автопинг
    threading.Thread(target=auto_ping, daemon=True).start()
    
    # Flask
    port = int(os.environ.get('PORT', 10000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    print(f"🌐 Web Service на порту {port}")
    
    # Бот
    print("🤖 Бот запущен!")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            time.sleep(5)
