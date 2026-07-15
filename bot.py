import telebot
from telebot import types
from telebot import apihelper
import sqlite3
import datetime
import urllib.parse
import requests
import ssl
import time
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

# --- ОБХОД SSL ДЛЯ TERMUX ---
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

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = "8974171870:AAHaaECMgLrO1PRXEXxfMkfNrKqrpdXmjSE"
CRYPTO_TOKEN = "551375:AAKMHUgqI7K5BVcFQA0ujATRAZgT6XpVRQ4"
ADMIN_ID = 314148464
ADMIN_USERNAME = "hesers"
BOT_USERNAME = "Clumsysell_bot"
FIXED_USDT_RUB = 77.20
GOLDA_RATE = 0.54
COMMISSION = 0.20

bot = telebot.TeleBot(BOT_TOKEN)
admin_product_draft = {}
admin_mailing_draft = {}
user_menu_messages = {}

# ================= ПЕРЕВОД =================
def get_user_lang(user_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 'ru'

def set_user_lang(user_id, lang):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def tr_text(user_id, text):
    if not text: return text
    lang = get_user_lang(user_id)
    if lang == 'ru': return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={lang}&dt=t&q={urllib.parse.quote(text)}"
        resp = requests.get(url, timeout=5)
        result = resp.json()
        translated = result[0][0][0]
        return translated if translated and translated != text else text
    except: return text

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
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    new_cols = {
        'lang': "TEXT DEFAULT 'ru'",
        'gold_balance': "REAL DEFAULT 0.00",
        'usd_balance': "REAL DEFAULT 0.00",
        'ref_gold': "REAL DEFAULT 0.00",
        'ref_usd': "REAL DEFAULT 0.00"
    }
    for col, col_type in new_cols.items():
        if col not in columns:
            try: cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            except: pass
    
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
    cursor.execute("UPDATE products SET content_type = ?, content = ? WHERE id = ?", (content_type, content, prod_id))
    conn.commit(); conn.close()

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
        cursor.execute("INSERT INTO users (user_id, username, reg_date, balance, referrer_id) VALUES (?, ?, ?, 0.0, ?)", (user_id, username, date_str, referrer_id))
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
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    count = cursor.fetchone()[0] or 0
    cursor.execute("SELECT ref_balance, ref_usd, ref_gold FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row: return count, row[0] or 0, row[1] or 0, row[2] or 0
    return count, 0, 0, 0

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
    today = datetime.datetime.now().strftime("%Y-%m-%d"); week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d"); month_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    cursor.execute("SELECT COUNT(*), SUM(price) FROM purchases_stats"); total_count, total_sum = cursor.fetchone()
    cursor.execute("SELECT COUNT(*), SUM(price) FROM purchases_stats WHERE date LIKE ?", (today + '%',)); today_count, today_sum = cursor.fetchone()
    cursor.execute("SELECT COUNT(*), SUM(price) FROM purchases_stats WHERE date >= ?", (week_ago,)); week_count, week_sum = cursor.fetchone()
    cursor.execute("SELECT COUNT(*), SUM(price) FROM purchases_stats WHERE date >= ?", (month_ago,)); month_count, month_sum = cursor.fetchone()
    conn.close()
    return {"total_count": total_count or 0, "total_sum": total_sum or 0, "today_count": today_count or 0, "today_sum": today_sum or 0, "week_count": week_count or 0, "week_sum": week_sum or 0, "month_count": month_count or 0, "month_sum": month_sum or 0}

def create_balance_request(user_id, amount, method):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("INSERT INTO balance_requests (user_id, amount, status, method) VALUES (?, ?, 'pending', ?)", (user_id, amount, method)); req_id = cursor.lastrowid; conn.commit(); conn.close(); return req_id

def get_balance_request(req_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, status, invoice_id, method FROM balance_requests WHERE id = ?", (req_id,)); row = cursor.fetchone(); conn.close(); return row

def approve_balance_request(req_id):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT user_id, amount, method FROM balance_requests WHERE id = ?", (req_id,))
    row = cursor.fetchone()
    if not row: conn.close(); return None, None
    user_id, amount, method = row
    currency = method.split('_')[1] if '_' in method else 'rub'
    if currency == 'rub': cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    elif currency == 'usd': cursor.execute("UPDATE users SET usd_balance = usd_balance + ? WHERE user_id = ?", (amount, user_id))
    elif currency == 'gold': cursor.execute("UPDATE users SET gold_balance = gold_balance + ? WHERE user_id = ?", (amount, user_id))
    cursor.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    ref = cursor.fetchone()
    if ref and ref[0]:
        bonus = round(amount * 0.20)
        if currency == 'rub': cursor.execute("UPDATE users SET ref_balance = ref_balance + ? WHERE user_id = ?", (bonus, ref[0]))
        elif currency == 'usd': cursor.execute("UPDATE users SET ref_usd = ref_usd + ? WHERE user_id = ?", (bonus, ref[0]))
        elif currency == 'gold': cursor.execute("UPDATE users SET ref_gold = ref_gold + ? WHERE user_id = ?", (bonus, ref[0]))
        try: bot.send_message(ref[0], f"🎉 +{bonus} {currency.upper()}!", parse_mode="HTML")
        except: pass
    cursor.execute("UPDATE balance_requests SET status = 'approved' WHERE id = ?", (req_id,)); conn.commit(); conn.close()
    return user_id, amount

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
def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(types.KeyboardButton("▶️ Перейти в магазин"))
    markup.row(types.KeyboardButton("👤 Личный кабинет"), types.KeyboardButton("💰 Реферальная система"))
    markup.row(types.KeyboardButton("👨‍💻 Поддержка"))
    if user_id == ADMIN_ID: markup.row(types.KeyboardButton("⚙️ Админ панель"))
    return markup

def admin_main_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("➕ Категория", callback_data="adm_new_main_cat"), types.InlineKeyboardButton("🖼️ Фото меню", callback_data="adm_menu_photo"))
    markup.add(types.InlineKeyboardButton("🖼️ Фото оплаты", callback_data="adm_payment_photo"), types.InlineKeyboardButton("🖼️ Упр. фото", callback_data="adm_manage_photos"))
    markup.add(types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_mailing"), types.InlineKeyboardButton("🔄 Переместить", callback_data="adm_move_menu"))
    markup.add(types.InlineKeyboardButton("✏️ Ред. товар", callback_data="adm_edit_prod_start"), types.InlineKeyboardButton("🎟️ Промокоды", callback_data="adm_promo"))
    markup.add(types.InlineKeyboardButton("💰 Баланс", callback_data="adm_balance"), types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats"))
    markup.add(types.InlineKeyboardButton("💳 Заявки", callback_data="adm_balance_reqs"))
    return markup

def send_with_photo(chat_id, text, markup, photo_id=None, parse_mode="HTML"):
    if photo_id:
        try: bot.send_photo(chat_id, photo_id, caption=text, parse_mode=parse_mode, reply_markup=markup); return
        except: pass
    bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=markup)

def send_menu_with_photo(chat_id, text, markup):
    send_with_photo(chat_id, text, markup, get_setting("menu_photo"))

def send_menu_with_photo_return(chat_id, text, markup):
    photo_id = get_setting("menu_photo")
    if photo_id:
        try: return bot.send_photo(chat_id, photo_id, caption=text, parse_mode="HTML", reply_markup=markup)
        except: pass
    return bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

# ================= ФАЙЛЫ =================
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio', 'voice'])
def handle_all_files(message):
    user_id = message.from_user.id; d = admin_product_draft.get(user_id, {})
    if d.get('waiting_content_type') and (message.document or message.photo or message.video or message.audio):
        admin_product_draft[user_id]['content_type'] = 'file'
        admin_product_draft[user_id]['waiting_content_type'] = False
        admin_product_draft[user_id]['waiting_product_photo'] = True
        bot.send_message(message.chat.id, "✅ Тип: файл\n📸 Теперь отправь фото для товара (или /skip_photo):")
        return
    if d.get('waiting_cat_photo') and message.photo:
        fid = message.photo[-1].file_id; tgt = d
        if tgt['target_type'] == 'category': update_category_photo(tgt['target_id'], fid)
        elif tgt['target_type'] == 'subcategory': update_subcategory_photo(tgt['target_id'], fid)
        elif tgt['target_type'] == 'product': update_product_photo(tgt['target_id'], fid)
        bot.send_message(message.chat.id, "✅ Фото сохранено!"); del admin_product_draft[user_id]; return
    if d.get('waiting_menu_photo') and message.photo:
        set_setting("menu_photo", message.photo[-1].file_id); bot.send_message(message.chat.id, "✅ Фото меню сохранено!"); del admin_product_draft[user_id]; return
    if d.get('waiting_payment_photo') and message.photo:
        set_setting("payment_photo", message.photo[-1].file_id); bot.send_message(message.chat.id, "✅ Фото оплаты сохранено!"); del admin_product_draft[user_id]; return
    if d.get('waiting_file'):
        fid, ftype = None, None
        if message.document: fid, ftype = message.document.file_id, 'document'
        elif message.photo: fid, ftype = message.photo[-1].file_id, 'photo'
        elif message.video: fid, ftype = message.video.file_id, 'video'
        elif message.audio: fid, ftype = message.audio.file_id, 'audio'
        if fid:
            if d.get('action') == 'replace_file': update_product_content(d['prod_id'], ftype, fid); bot.send_message(message.chat.id, "✅ Файл обновлён!")
            else: add_product(d['parent_type'], d['parent_id'], d['name'], d['desc'], d['price'], d.get('photo_id'), ftype, fid, d['stock']); bot.send_message(message.chat.id, f"✅ Товар «{d['name']}» создан!\n💳 Цена: {d['price']} руб\n📦 Остаток: {d['stock']} шт.")
            del admin_product_draft[user_id]
        else: bot.send_message(message.chat.id, "❌ Отправьте файл!"); return
    if d.get('waiting_content') and message.text:
        content = message.text; ctype = 'text'
        if d.get('action') == 'replace_content': update_product_content(d['prod_id'], ctype, content); bot.send_message(message.chat.id, "✅ Контент обновлён!")
        else: add_product(d['parent_type'], d['parent_id'], d['name'], d['desc'], d['price'], d.get('photo_id'), ctype, content, d['stock']); bot.send_message(message.chat.id, f"✅ Товар «{d['name']}» создан!\n💳 Цена: {d['price']} руб\n📦 Остаток: {d['stock']} шт.")
        del admin_product_draft[user_id]; return
    if d.get('waiting_product_photo') and message.photo:
        admin_product_draft[user_id]['photo_id'] = message.photo[-1].file_id
        admin_product_draft[user_id]['waiting_product_photo'] = False
        if d.get('content_type') == 'text': admin_product_draft[user_id]['waiting_content'] = True; bot.send_message(message.chat.id, "📝 Отправьте текст/ссылку для товара:")
        else: admin_product_draft[user_id]['waiting_file'] = True; bot.send_message(message.chat.id, "📎 Отправьте файл для товара:")
        return

# ================= КОМАНДЫ =================
@bot.message_handler(commands=['start'])
def cmd_start(message):
    args = message.text.split(); ref = args[1] if len(args) > 1 and args[1].isdigit() else None
    add_user(message.from_user.id, message.from_user.username, ref)
    text = "Наша команда рада приветствовать вас!\n\nЗдесь вы можете приобрести конфиги для Netwing.\n\nЗаходя в бота, вы соглашаетесь с <a href='https://netwing.space'>Политикой конфиденциальности</a>."
    markup = get_main_menu(message.from_user.id)
    sent = send_menu_with_photo_return(message.chat.id, text, markup)
    if sent: user_menu_messages[message.from_user.id] = sent.message_id

@bot.message_handler(commands=['language'])
def cmd_language(message):
    user_id = message.from_user.id; current = get_user_lang(user_id); new_lang = 'en' if current == 'ru' else 'ru'
    set_user_lang(user_id, new_lang); cmd_start(message)

@bot.message_handler(commands=['skip_photo'])
def skip_product_photo(message):
    if message.from_user.id in admin_product_draft:
        d = admin_product_draft[message.from_user.id]
        if d.get('waiting_product_photo'): d['photo_id'] = None; d['waiting_product_photo'] = False; d['waiting_content'] = True; bot.send_message(message.chat.id, "📝 Отправьте текст/ссылку:")

@bot.message_handler(commands=['cancel_mailing'])
def cancel_mailing(message):
    if message.from_user.id in admin_mailing_draft: del admin_mailing_draft[message.from_user.id]; bot.send_message(message.chat.id, "❌ Рассылка отменена")

# ================= ТЕКСТОВЫЕ КНОПКИ =================
@bot.message_handler(content_types=['text'])
def handle_text_buttons(message):
    user_id = message.from_user.id; d = admin_product_draft.get(user_id, {})
    if d.get('waiting_content_type'):
        ct = message.text.strip().lower() if message.text else ''
        if ct in ['text', 'file']:
            admin_product_draft[user_id]['content_type'] = ct
            admin_product_draft[user_id]['waiting_content_type'] = False
            admin_product_draft[user_id]['waiting_product_photo'] = True
            bot.send_message(message.chat.id, f"✅ Тип: {ct}\n📸 Отправь фото (или /skip_photo):")
        else:
            msg = bot.send_message(message.chat.id, "❌ Отправь 'text' или 'file'\nИли просто отправь файл:")
            bot.register_next_step_handler(msg, handle_text_buttons)
        return
    if d.get('waiting_content'):
        content = message.text
        if d.get('action') == 'replace_content': update_product_content(d['prod_id'], 'text', content); bot.send_message(message.chat.id, "✅ Контент обновлён!")
        else: add_product(d['parent_type'], d['parent_id'], d['name'], d['desc'], d['price'], d.get('photo_id'), 'text', content, d['stock']); bot.send_message(message.chat.id, f"✅ Товар «{d['name']}» создан!\n💳 {d['price']} руб\n📦 {d['stock']} шт.")
        del admin_product_draft[user_id]; return
    if d.get('waiting_file'): bot.send_message(message.chat.id, "⚠️ Отправьте файл как вложение"); return
    
    txt = message.text
    if txt in ["▶️ Перейти в магазин", "▶️ Go to shop"]:
        cats = get_categories(); markup = types.InlineKeyboardMarkup(row_width=1)
        for c_id, c_name, _ in cats: markup.add(types.InlineKeyboardButton(tr_text(user_id, c_name), callback_data=f"view_cat_{c_id}"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="to_main_menu_nav"))
        bot.send_message(message.chat.id, "🛍 Покупки", reply_markup=markup)
    
    elif txt in ["👤 Личный кабинет", "👤 Profile"]:
        user = get_user(user_id)
        _, ref_rub, ref_usd, ref_gold = get_ref_stats(user_id)
        text = f"👤 <b>Личный кабинет</b>\n\n🆔 <code>{user_id}</code>\n💰 RUB: {user['balance']} ₽ (Ref: {ref_rub} ₽)\n💵 USD: {user['usd_balance']} $ (Ref: {ref_usd} $)\n🪙 GOLD: {user['gold_balance']} (Ref: {ref_gold})\n🛒 Покупок: {user['purchases_count']}"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📦 Мои покупки", callback_data="my_purchases_view"))
        markup.add(types.InlineKeyboardButton("💳 Пополнить", callback_data="balance_topup"))
        markup.add(types.InlineKeyboardButton("🎟️ Промокод", callback_data="promo_enter"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="to_main_menu_nav"))
        send_menu_with_photo(message.chat.id, text, markup)
    
    elif txt in ["💰 Реферальная система", "💰 Referral system"]:
        count, ref_rub, ref_usd, ref_gold = get_ref_stats(user_id)
        link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
        text = f"🤝 <b>Реферальная система</b>\n\n👥 Рефералов: {count}\n\n💰 RUB: {ref_rub} ₽\n💵 USD: {ref_usd} $\n🪙 GOLD: {ref_gold}\n\n🔗 <code>{link}</code>"
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📤 Поделиться", url=f"https://t.me/share/url?url={urllib.parse.quote(link)}"))
        markup.add(types.InlineKeyboardButton("📋 Скопировать", callback_data=f"ref_copy_{user_id}"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="to_main_menu_nav"))
        send_menu_with_photo(message.chat.id, text, markup)
    
    elif txt in ["👨‍💻 Поддержка", "👨‍💻 Support"]:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💬 Написать", url=f"https://t.me/{ADMIN_USERNAME}"))
        bot.send_message(message.chat.id, "👨‍💻 <b>Служба поддержки</b>", reply_markup=markup, parse_mode="HTML")
    
    elif txt in ["⚙️ Админ панель", "⚙️ Admin panel"] and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "🛠 <b>Панель администратора:</b>", reply_markup=admin_main_keyboard(), parse_mode="HTML")

# ================= МАГАЗИН =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_cat_'))
def view_category(call):
    cat_id = int(call.data.split('_')[2]); cat = get_category(cat_id)
    if not cat: return
    user_id = call.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    for s_id, s_name, _ in get_subcategories(cat_id): markup.add(types.InlineKeyboardButton(f"📁 {tr_text(user_id, s_name)}", callback_data=f"view_sub_{s_id}"))
    for p_id, p_name, p_price, _, stock in get_products('category', cat_id): markup.add(types.InlineKeyboardButton(f"📦 {tr_text(user_id, p_name)} — {p_price}₽ (${round(p_price/get_usdt_rub_rate(),2)})", callback_data=f"select_pay_{p_id}"))
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("➕ Подкатегория", callback_data=f"adm_new_sub_in_{cat_id}"))
        markup.add(types.InlineKeyboardButton("➕ Товар", callback_data=f"adm_new_prod_cat_{cat_id}"))
    markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="to_main_menu_nav"))
    send_with_photo(call.message.chat.id, f"📁 {tr_text(user_id, cat[1])}", markup, cat[2])

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_sub_'))
def view_subcategory(call):
    sub_id = int(call.data.split('_')[2]); sub = get_subcategory(sub_id)
    if not sub: return
    user_id = call.from_user.id
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p_id, p_name, p_price, _, stock in get_products('subcategory', sub_id): markup.add(types.InlineKeyboardButton(f"📦 {tr_text(user_id, p_name)} — {p_price}₽ (${round(p_price/get_usdt_rub_rate(),2)})", callback_data=f"select_pay_{p_id}"))
    if user_id == ADMIN_ID: markup.add(types.InlineKeyboardButton("➕ Товар", callback_data=f"adm_new_prod_sub_{sub_id}"))
    markup.add(types.InlineKeyboardButton("‹ Назад", callback_data=f"view_cat_{sub[3]}"))
    send_with_photo(call.message.chat.id, f"📁 {tr_text(user_id, sub[1])}", markup, sub[2])

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_pay_'))
def select_payment(call):
    prod_id = int(call.data.split('_')[2]); prod = get_product(prod_id)
    if not prod: return
    name, desc, price, photo, _, _, ptype, pid, stock = prod
    user = get_user(call.from_user.id); user_id = call.from_user.id
    _, ref_rub, _, ref_gold = get_ref_stats(user_id)
    total_rub = user['balance'] + ref_rub
    total_gold = user['gold_balance'] + ref_gold
    usd_price = round(price / get_usdt_rub_rate(), 2)
    gold_price = round(price / GOLDA_RATE)
    
    text = f"📦 {tr_text(user_id, name)}\n\n{tr_text(user_id, desc)}\n\n💰 Цена: {price} ₽ | ${usd_price}\n📦 Остаток: {stock}\n💼 Баланс: {total_rub} ₽ | {total_gold} голды"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 Оплатить картой", callback_data=f"pay_balance_{prod_id}"))
    markup.add(types.InlineKeyboardButton(f"🪙 Оплатить голдой ({gold_price} голды)", callback_data=f"pay_gold_{prod_id}"))
    markup.add(types.InlineKeyboardButton("💸 Оплатить CRYPTO", callback_data=f"pay_crypto_{prod_id}"))
    markup.add(types.InlineKeyboardButton("‹ Назад", callback_data=f"view_back_{ptype}_{pid}"))
    send_with_photo(call.message.chat.id, text, markup, photo)

@bot.callback_query_handler(func=lambda call: call.data.startswith('view_back_'))
def view_back(call):
    parts = call.data.split('_')
    if len(parts) >= 4:
        call.data = f"view_{'cat' if parts[2] == 'category' else 'sub'}_{parts[3]}"
        if parts[2] == 'category': view_category(call)
        else: view_subcategory(call)

# ================= ПОКУПКИ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_balance_'))
def purchase(call):
    prod_id = int(call.data.split('_')[2]); prod = get_product(prod_id)
    if not prod: return
    name, _, price, _, content_type, content, _, _, stock = prod
    user = get_user(call.from_user.id); user_id = call.from_user.id
    _, ref_rub, _, _ = get_ref_stats(user_id)
    total = user['balance'] + ref_rub
    if total < price:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("💳 Пополнить баланс", callback_data="balance_topup"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data=f"select_pay_{prod_id}"))
        bot.send_message(call.message.chat.id, f"❌ Недостаточно средств!\n\n💰 Нужно: {price} ₽\n💼 У вас: {total} ₽\n\nПополните баланс:", reply_markup=markup)
        bot.answer_callback_query(call.id)
        return
    if stock <= 0: bot.answer_callback_query(call.id, "❌ Товар закончился!"); return
    remaining = price
    if user['balance'] >= remaining: update_balance(user_id, -remaining)
    else:
        update_balance(user_id, -user['balance']); remaining -= user['balance']
        conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE users SET ref_balance = ref_balance - ? WHERE user_id = ?", (remaining, user_id)); conn.commit(); conn.close()
    decrease_stock(prod_id); record_purchase(user_id, prod_id, price, name, content, content_type)
    bot.send_message(user_id, f"✅ {tr_text(user_id, name)} — {price} ₽!")
    send_content(user_id, content_type, content, f"🎉 {tr_text(user_id, name)}")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_gold_'))
def purchase_gold(call):
    prod_id = int(call.data.split('_')[2]); prod = get_product(prod_id)
    if not prod: return
    name, _, price, _, content_type, content, _, _, stock = prod
    user = get_user(call.from_user.id); user_id = call.from_user.id
    _, _, _, ref_gold = get_ref_stats(user_id)
    gold_needed = round(price / GOLDA_RATE)
    total_gold = user['gold_balance'] + ref_gold
    if total_gold < gold_needed:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🪙 Пополнить голду", callback_data="balance_topup"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data=f"select_pay_{prod_id}"))
        bot.send_message(call.message.chat.id, f"❌ Недостаточно голды!\n\n🪙 Нужно: {gold_needed} голды\n💼 У вас: {total_gold} голды\n\nПополните баланс:", reply_markup=markup)
        bot.answer_callback_query(call.id)
        return
    if stock <= 0: bot.answer_callback_query(call.id, "❌ Товар закончился!"); return
    remaining = gold_needed
    if user['gold_balance'] >= remaining: update_gold_balance(user_id, -remaining)
    else:
        update_gold_balance(user_id, -user['gold_balance']); remaining -= user['gold_balance']
        conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE users SET ref_gold = ref_gold - ? WHERE user_id = ?", (remaining, user_id)); conn.commit(); conn.close()
    decrease_stock(prod_id); record_purchase(user_id, prod_id, price, name, content, content_type)
    bot.send_message(user_id, f"✅ {tr_text(user_id, name)} — {gold_needed} голды!")
    send_content(user_id, content_type, content, f"🎉 {tr_text(user_id, name)}")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('pay_crypto_'))
def purchase_crypto(call):
    prod_id = int(call.data.split('_')[2]); prod = get_product(prod_id)
    if not prod: return
    name, _, price, _, content_type, content, _, _, stock = prod
    invoice_url, invoice_id = create_crypto_invoice(price, f"Purchase: {name}")
    if invoice_url:
        conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("INSERT INTO balance_requests (user_id, amount, invoice_id, status, method) VALUES (?, ?, ?, 'pending', 'crypto_purchase')", (call.from_user.id, price, invoice_id)); req_id = conn.cursor().lastrowid; conn.commit(); conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔗 Оплатить", url=invoice_url))
        markup.add(types.InlineKeyboardButton("🔄 Проверить", callback_data=f"check_purchase_{req_id}_{prod_id}"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data=f"select_pay_{prod_id}"))
        bot.send_message(call.message.chat.id, f"💸 CRYPTO\n\n📦 {name}\n💰 {price} ₽\n💵 {round(price/get_usdt_rub_rate(),2)} USD", parse_mode="HTML", reply_markup=markup)
    else: bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_purchase_'))
def check_crypto_purchase(call):
    parts = call.data.split('_'); req_id, prod_id = int(parts[2]), int(parts[3])
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor(); cursor.execute("SELECT invoice_id FROM balance_requests WHERE id = ?", (req_id,)); row = cursor.fetchone(); conn.close()
    if row and check_crypto_invoice(row[0]):
        prod = get_product(prod_id)
        if prod and prod[8] > 0:
            name, _, price, _, content_type, content, _, _, _ = prod
            conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status = 'approved' WHERE id = ?", (req_id,)); conn.commit(); conn.close()
            decrease_stock(prod_id); record_purchase(call.from_user.id, prod_id, price, name, content, content_type)
            bot.edit_message_text(f"✅ Оплачено!\n🎉 {name}", call.message.chat.id, call.message.message_id)
            send_content(call.from_user.id, content_type, content, f"🎉 {name}")
            bot.send_message(ADMIN_ID, f"✅ Крипто продажа!\n👤 {call.from_user.id}\n📦 {name}\n💰 {price} ₽")
        else: bot.answer_callback_query(call.id, "❌ Закончился!", show_alert=True)
    else: bot.answer_callback_query(call.id, "❌ Не оплачено", show_alert=True)

def send_content(chat_id, content_type, content, caption):
    try:
        if content_type == 'text': bot.send_message(chat_id, f"{caption}\n\n{content}")
        elif content_type == 'photo': bot.send_photo(chat_id, content, caption=caption)
        elif content_type == 'video': bot.send_video(chat_id, content, caption=caption)
        elif content_type == 'document': bot.send_document(chat_id, content, caption=caption)
        elif content_type == 'audio': bot.send_audio(chat_id, content, caption=caption)
        else: bot.send_message(chat_id, f"{caption}\n{content}")
    except: bot.send_message(chat_id, "❌ Ошибка выдачи.")

# ================= ПОПОЛНЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data == "balance_topup")
def topup_start(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 RUB", callback_data="topup_currency_rub"), types.InlineKeyboardButton("💸 USD", callback_data="topup_currency_usd"), types.InlineKeyboardButton("🪙 GOLD", callback_data="topup_currency_gold"))
    markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="back_to_profile"))
    bot.edit_message_text("💱 <b>Выберите валюту:</b>", call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('topup_currency_'))
def topup_currency(call):
    currency = call.data.split('_')[2]
    if currency == 'rub': msg = bot.send_message(call.message.chat.id, "💳 Введите сумму в рублях:"); bot.register_next_step_handler(msg, topup_amount_rub)
    elif currency == 'usd': msg = bot.send_message(call.message.chat.id, "💸 Введите сумму в долларах:"); bot.register_next_step_handler(msg, topup_amount_usd)
    elif currency == 'gold': msg = bot.send_message(call.message.chat.id, "🪙 Введите сумму в голде:"); bot.register_next_step_handler(msg, topup_amount_gold)

def topup_amount_rub(message):
    try:
        amount = int(message.text)
        if amount < 1: raise ValueError
        show_payment_methods(message, amount, 'rub')
    except: msg = bot.send_message(message.chat.id, "❌ Введите число > 0"); bot.register_next_step_handler(msg, topup_amount_rub)

def topup_amount_usd(message):
    try:
        usd = int(message.text)
        if usd < 1: raise ValueError
        amount = round(usd * get_usdt_rub_rate())
        show_payment_methods(message, amount, 'usd')
    except: msg = bot.send_message(message.chat.id, "❌ Введите число > 0"); bot.register_next_step_handler(msg, topup_amount_usd)

def topup_amount_gold(message):
    try:
        gold = int(message.text)
        if gold < 1: raise ValueError
        gold_to_buy = round(gold / (1 - COMMISSION))
        req_id = create_balance_request(message.from_user.id, gold, 'gold_direct')
        text = f"🪙 <b>Пополнение ГОЛДЫ</b>\n\n🪙 Вы хотите: <b>{gold} голды</b>\n📌 Комиссия: 20%\n🛒 Купить скин за: <b>{gold_to_buy} голды</b>\n💰 Получите: <b>{gold} голды</b>\n\n📝 Напишите админу."
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📝 Написать админу", url=f"https://t.me/{ADMIN_USERNAME}"))
        markup.add(types.InlineKeyboardButton("✅ Я купил", callback_data=f"bal_gold_direct_done_{req_id}"))
        bot.send_message(message.chat.id, text, parse_mode="HTML", reply_markup=markup)
    except: msg = bot.send_message(message.chat.id, "❌ Введите число > 0"); bot.register_next_step_handler(msg, topup_amount_gold)

def show_payment_methods(message, amount, currency):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💳 СБП карта", callback_data=f"bal_sbp_{amount}_{currency}"))
    markup.add(types.InlineKeyboardButton("💸 CRYPTO", callback_data=f"bal_crypto_{amount}_{currency}"))
    bot.send_message(message.chat.id, f"💳 Сумма: {amount} ₽\n\nВыберите способ:", reply_markup=markup)

# ================= СБП =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('bal_sbp_') and 'done' not in call.data)
def topup_sbp(call):
    parts = call.data.split('_'); amount, currency = int(parts[2]), parts[3] if len(parts) > 3 else 'rub'
    req_id = create_balance_request(call.from_user.id, amount, f'sbp_{currency}')
    text = f"💳 <b>СБП</b>\n\n💰 {amount} ₽\n🏦 Сбербанк\n💳 2202206714879132\n👤 Илья\n\n📸 Отправьте скриншот"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("✅ Я оплатил", callback_data=f"bal_sbp_done_{req_id}"))
    markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="to_main_menu_nav"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('bal_sbp_done_'))
def topup_sbp_done(call):
    req_id = int(call.data.split('_')[3])
    msg = bot.send_message(call.message.chat.id, "📷 Отправьте чек:")
    bot.register_next_step_handler(msg, lambda m: topup_sbp_receipt(m, req_id))

def topup_sbp_receipt(message, req_id):
    if not (message.photo or message.document):
        msg = bot.send_message(message.chat.id, "❌ Отправьте скриншот!"); bot.register_next_step_handler(msg, lambda m: topup_sbp_receipt(m, req_id)); return
    bot.send_message(message.chat.id, "⏳ Отправлено админу")
    row = get_balance_request(req_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_bal_apr_{req_id}"), types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_bal_dec_{req_id}"))
    cap = f"💳 Пополнение\n👤 {message.from_user.id}\n💰 {row[1]} ₽"
    if message.photo: bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=cap, reply_markup=markup)
    else: bot.send_document(ADMIN_ID, message.document.file_id, caption=cap, reply_markup=markup)

# ================= КРИПТО ПОПОЛНЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('bal_crypto_'))
def topup_crypto(call):
    parts = call.data.split('_'); amount, currency = int(parts[2]), parts[3] if len(parts) > 3 else 'rub'
    req_id = create_balance_request(call.from_user.id, amount, f'crypto_{currency}')
    url, inv_id = create_crypto_invoice(amount, f"Top-up {amount} ₽")
    if url:
        conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET invoice_id = ? WHERE id = ?", (inv_id, req_id)); conn.commit(); conn.close()
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("🔗 Оплатить", url=url), types.InlineKeyboardButton("🔄 Проверить", callback_data=f"check_bal_cry_{req_id}"))
        bot.edit_message_text(f"🧾 {round(amount/get_usdt_rub_rate(),2)} USDT", call.message.chat.id, call.message.message_id, reply_markup=markup)
    else: bot.answer_callback_query(call.id, "❌ Ошибка", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_bal_cry_'))
def check_crypto(call):
    req_id = int(call.data.split('_')[3]); row = get_balance_request(req_id)
    if not row: return
    if row[2] == 'approved': bot.answer_callback_query(call.id, "✅ Уже пополнено!"); return
    if check_crypto_invoice(row[3]):
        uid, amt = approve_balance_request(req_id)
        bot.edit_message_text(f"✅ +{amt} ₽!", call.message.chat.id, call.message.message_id)
        bot.send_message(uid, f"✅ +{amt} ₽!")
    else: bot.answer_callback_query(call.id, "❌ Не оплачено", show_alert=True)

# ================= ГОЛДА =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('bal_gold_direct_done_'))
def topup_gold_direct_done(call):
    req_id = int(call.data.split('_')[4])
    bot.edit_message_text("⏳ Отправлено админу.", call.message.chat.id, call.message.message_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_gold_direct_apr_{req_id}"), types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_gold_direct_dec_{req_id}"))
    bot.send_message(ADMIN_ID, f"🪙 GOLD пополнение!\n👤 {call.from_user.id}\n🪙 {get_balance_request(req_id)[1]} gold", reply_markup=markup)

# ================= АДМИН ПОДТВЕРЖДЕНИЕ =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_bal_apr_'))
def admin_approve_balance(call):
    req_id = int(call.data.split('_')[3])
    uid, amt = approve_balance_request(req_id)
    if uid: bot.edit_message_caption("✅ Подтверждено", call.message.chat.id, call.message.message_id); bot.send_message(uid, f"✅ Заявка №{req_id} одобрена!\n💰 +{amt} ₽")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_bal_dec_'))
def admin_decline_balance(call):
    req_id = int(call.data.split('_')[3])
    conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status='declined' WHERE id=?", (req_id,)); conn.commit(); conn.close()
    bot.edit_message_caption("❌ Отклонено", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_gold_direct_apr_'))
def admin_approve_gold_direct(call):
    req_id = int(call.data.split('_')[4]); row = get_balance_request(req_id)
    if row: update_gold_balance(row[0], row[1]); conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status='approved' WHERE id=?", (req_id,)); conn.commit(); conn.close(); bot.edit_message_text(f"✅ +{row[1]} gold!", call.message.chat.id, call.message.message_id); bot.send_message(row[0], f"✅ +{row[1]} gold!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_gold_direct_dec_'))
def admin_decline_gold_direct(call):
    req_id = int(call.data.split('_')[4])
    conn = sqlite3.connect("bot_database.db"); conn.cursor().execute("UPDATE balance_requests SET status='declined' WHERE id=?", (req_id,)); conn.commit(); conn.close()
    bot.edit_message_text("❌ Отклонено", call.message.chat.id, call.message.message_id)

# ================= ПОКУПКИ =================
@bot.callback_query_handler(func=lambda call: call.data == "my_purchases_view")
def my_purchases(call):
    uid = call.from_user.id
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT id, product_name, price, date, content, content_type FROM user_purchases WHERE user_id=? ORDER BY id DESC LIMIT 20", (uid,)); rows = cursor.fetchall(); conn.close()
    if not rows: bot.edit_message_text("📦 Нет покупок", call.message.chat.id, call.message.message_id); return
    text = "📦 <b>Покупки:</b>\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    for pid, name, price, date, content, ctype in rows:
        text += f"• {name} — {price} ₽\n  📅 {date}\n\n"
        if content: markup.add(types.InlineKeyboardButton(f"📦 {name}", callback_data=f"repurchase_{pid}"))
    markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="back_to_profile"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('repurchase_'))
def resend_file(call):
    pid = int(call.data.split('_')[1])
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
    cursor.execute("SELECT content, content_type, product_name FROM user_purchases WHERE id=? AND user_id=?", (pid, call.from_user.id)); row = cursor.fetchone(); conn.close()
    if row and row[0]: send_content(call.message.chat.id, row[1], row[0], f"🎁 {row[2]}"); bot.answer_callback_query(call.id, "✅ Отправлено!")
    else: bot.answer_callback_query(call.id, "❌ Не найдено", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "back_to_profile")
def back_profile(call): cmd_start(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "to_main_menu_nav")
def back_menu(call):
    bot.answer_callback_query(call.id); user_id = call.from_user.id
    text = "Наша команда рада приветствовать вас!\n\nЗдесь вы можете приобрести конфиги для Netwing."
    markup = get_main_menu(user_id); photo_id = get_setting("menu_photo")
    try:
        if photo_id: media = types.InputMediaPhoto(media=photo_id, caption=text, parse_mode="HTML"); bot.edit_message_media(media, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else: bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    except:
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        send_menu_with_photo_return(call.message.chat.id, text, markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ref_copy_'))
def copy_ref(call):
    user_id = call.data.split('_')[2]; link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    bot.answer_callback_query(call.id, text=f"🔗 {link}", show_alert=True)
    bot.send_message(call.message.chat.id, f"📋 <code>{link}</code>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith('promo_enter'))
def promo_enter(call):
    msg = bot.send_message(call.message.chat.id, "🎟️ Введите промокод:")
    bot.register_next_step_handler(msg, process_promo)

def process_promo(message):
    code = message.text.strip().upper(); promo = get_promocode(code)
    if promo:
        user = get_user(message.from_user.id); bonus = user['purchases_count'] * promo[0] / 100; update_balance(message.from_user.id, bonus)
        bot.send_message(message.chat.id, f"✅ +{bonus:.2f} ₽!")
    else: bot.send_message(message.chat.id, "❌ Недействительный")

# ================= АДМИНКА =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_new_sub_in_'))
def add_sub_start(call):
    if call.from_user.id != ADMIN_ID: return
    cat_id = int(call.data.split('_')[4])
    msg = bot.send_message(call.message.chat.id, "📝 Название подкатегории:")
    bot.register_next_step_handler(msg, lambda m: save_sub(m, cat_id))

def save_sub(message, cat_id):
    add_subcategory(cat_id, message.text)
    bot.send_message(ADMIN_ID, "✅ Добавлено!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_new_prod_cat_'))
def add_prod_cat(call):
    if call.from_user.id != ADMIN_ID: return
    cat_id = int(call.data.split('_')[4])
    admin_product_draft[call.from_user.id] = {'parent_type': 'category', 'parent_id': cat_id}
    msg = bot.send_message(call.message.chat.id, "1️⃣ Название товара:")
    bot.register_next_step_handler(msg, prod_step_name)

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_new_prod_sub_'))
def add_prod_sub(call):
    if call.from_user.id != ADMIN_ID: return
    sub_id = int(call.data.split('_')[4])
    admin_product_draft[call.from_user.id] = {'parent_type': 'subcategory', 'parent_id': sub_id}
    msg = bot.send_message(call.message.chat.id, "1️⃣ Название товара:")
    bot.register_next_step_handler(msg, prod_step_name)

def prod_step_name(message):
    if message.from_user.id not in admin_product_draft: return
    admin_product_draft[message.from_user.id]['name'] = message.text
    msg = bot.send_message(message.chat.id, "2️⃣ Описание:"); bot.register_next_step_handler(msg, prod_step_desc)

def prod_step_desc(message):
    if message.from_user.id not in admin_product_draft: return
    admin_product_draft[message.from_user.id]['desc'] = message.text
    msg = bot.send_message(message.chat.id, "3️⃣ Цена (₽):"); bot.register_next_step_handler(msg, prod_step_price)

def prod_step_price(message):
    if message.from_user.id not in admin_product_draft: return
    if not message.text.isdigit(): msg = bot.send_message(message.chat.id, "❌ Число!"); bot.register_next_step_handler(msg, prod_step_price); return
    admin_product_draft[message.from_user.id]['price'] = int(message.text)
    msg = bot.send_message(message.chat.id, "4️⃣ Остаток:"); bot.register_next_step_handler(msg, prod_step_stock)

def prod_step_stock(message):
    if message.from_user.id not in admin_product_draft: return
    if not message.text.isdigit(): msg = bot.send_message(message.chat.id, "❌ Число!"); bot.register_next_step_handler(msg, prod_step_stock); return
    admin_product_draft[message.from_user.id]['stock'] = int(message.text)
    admin_product_draft[message.from_user.id]['waiting_content_type'] = True
    bot.send_message(message.chat.id, "5️⃣ Отправь 'text' для текста или 'file' для файла\nИли просто отправь файл:")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_edit_content_'))
def edit_content_start(call):
    if call.from_user.id != ADMIN_ID: return
    prod_id = int(call.data.split('_')[3])
    admin_product_draft[call.from_user.id] = {'prod_id': prod_id, 'action': 'replace_content', 'waiting_content': True}
    bot.send_message(call.message.chat.id, "📝 Отправь новый текст/ссылку:")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_edit_file_'))
def edit_file_start(call):
    if call.from_user.id != ADMIN_ID: return
    prod_id = int(call.data.split('_')[3])
    admin_product_draft[call.from_user.id] = {'prod_id': prod_id, 'action': 'replace_file', 'waiting_file': True}
    bot.send_message(call.message.chat.id, "📎 Отправь новый файл:")

@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def admin_actions(call):
    if call.from_user.id != ADMIN_ID: return
    data = call.data
    if data == "adm_new_main_cat":
        msg = bot.send_message(call.message.chat.id, "📝 Название категории:"); bot.register_next_step_handler(msg, lambda m: (add_category(m.text), bot.send_message(ADMIN_ID, "✅ Создана!")))
    elif data == "adm_menu_photo": admin_product_draft[call.from_user.id] = {'waiting_menu_photo': True}; bot.send_message(call.message.chat.id, "🖼️ Отправь фото меню:")
    elif data == "adm_payment_photo": admin_product_draft[call.from_user.id] = {'waiting_payment_photo': True}; bot.send_message(call.message.chat.id, "🖼️ Отправь фото оплаты:")
    elif data == "adm_stats":
        stats = get_stats()
        text = f"📊 Статистика\n\n📅 Сегодня: {stats['today_count']}/{stats['today_sum']} ₽\n🗓 Неделя: {stats['week_count']}/{stats['week_sum']} ₽\n📆 Месяц: {stats['month_count']}/{stats['month_sum']} ₽\n📦 Всего: {stats['total_count']}/{stats['total_sum']} ₽"
        markup = types.InlineKeyboardMarkup(row_width=1); markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="admin_back")); bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    elif data == "adm_balance": msg = bot.send_message(call.message.chat.id, "💰 ID СУММА"); bot.register_next_step_handler(msg, lambda m: (update_balance(int(m.text.split()[0]), float(m.text.split()[1])), bot.send_message(m.chat.id, "✅ Обновлён!")) if len(m.text.split())==2 else None)
    elif data == "adm_promo":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("➕ Создать", callback_data="adm_promo_add"), types.InlineKeyboardButton("🗑️ Удалить", callback_data="adm_promo_del"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="admin_back")); bot.edit_message_text("🎟️ Промокоды", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif data == "adm_promo_add": msg = bot.send_message(call.message.chat.id, "🎟️ КОД СКИДКА\nПример: SALE50 50"); bot.register_next_step_handler(msg, lambda m: (add_promocode(m.text.split()[0].upper(), int(m.text.split()[1])), bot.send_message(m.chat.id, "✅ Создан!")) if len(m.text.split())==2 and m.text.split()[1].isdigit() else bot.send_message(m.chat.id, "❌ Формат: КОД ЧИСЛО"))
    elif data == "adm_promo_del": msg = bot.send_message(call.message.chat.id, "🗑️ Код:"); bot.register_next_step_handler(msg, lambda m: (delete_promocode(m.text.strip().upper()), bot.send_message(m.chat.id, "✅ Удалён!")))
    elif data == "adm_mailing":
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📝 Текст", callback_data="mail_text"), types.InlineKeyboardButton("🖼️ Текст+Фото", callback_data="mail_photo"))
        markup.add(types.InlineKeyboardButton("🖼️ Фото+Кнопки", callback_data="mail_photo_btn"), types.InlineKeyboardButton("📝 Текст+Кнопки", callback_data="mail_text_btn"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="admin_back")); bot.edit_message_text("📢 Рассылка", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif data == "adm_balance_reqs":
        conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, amount, method FROM balance_requests WHERE status='pending'"); reqs = cursor.fetchall(); conn.close()
        if not reqs: bot.edit_message_text("📭 Нет заявок", call.message.chat.id, call.message.message_id); return
        markup = types.InlineKeyboardMarkup(row_width=1)
        for r_id, u_id, amt, mt in reqs: markup.add(types.InlineKeyboardButton(f"{'💳' if 'sbp' in mt else '💸' if 'crypto' in mt else '🪙'} {u_id} — {amt} ₽", callback_data=f"adm_balance_req_{r_id}"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="admin_back")); bot.edit_message_text("💳 Заявки", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif data.startswith("adm_balance_req_"):
        req_id = int(data.split('_')[3]); row = get_balance_request(req_id)
        if not row: return
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"adm_bal_apr_{req_id}"), types.InlineKeyboardButton("❌ Отклонить", callback_data=f"adm_bal_dec_{req_id}"))
        markup.add(types.InlineKeyboardButton("‹ Назад", callback_data="adm_balance_reqs")); bot.edit_message_text(f"#{req_id}\n👤 {row[0]}\n💰 {row[1]} ₽", call.message.chat.id, call.message.message_id, reply_markup=markup)
    elif data == "admin_back": cmd_start(call.message)

def edit_field(message, prod_id, field):
    try: val = int(message.text) if field in ('price', 'stock') else message.text
    except: bot.send_message(message.chat.id, "❌ Ошибка!"); return
    conn = sqlite3.connect("bot_database.db"); conn.cursor().execute(f"UPDATE products SET {field}=? WHERE id=?", (val, prod_id)); conn.commit(); conn.close()
    bot.send_message(message.chat.id, "✅ Обновлено!")

# ================= РАССЫЛКА =================
@bot.callback_query_handler(func=lambda call: call.data.startswith('mail_'))
def handle_mailing(call):
    if call.from_user.id != ADMIN_ID: return
    data = call.data
    if data == "mail_text": admin_mailing_draft[call.from_user.id] = {'type': 'text'}; msg = bot.send_message(call.message.chat.id, "📝 Текст:\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_text)
    elif data == "mail_photo": admin_mailing_draft[call.from_user.id] = {'type': 'photo'}; msg = bot.send_message(call.message.chat.id, "🖼️ Фото:\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_photo)
    elif data == "mail_photo_btn": admin_mailing_draft[call.from_user.id] = {'type': 'photo_btn'}; msg = bot.send_message(call.message.chat.id, "🖼️ Фото:\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_photo_btn_photo)
    elif data == "mail_text_btn": admin_mailing_draft[call.from_user.id] = {'type': 'text_btn'}; msg = bot.send_message(call.message.chat.id, "📝 Текст:\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_text_btn_text)

def process_mailing_text(message):
    if message.from_user.id not in admin_mailing_draft: return
    if message.text == "/cancel_mailing": cancel_mailing(message); return
    admin_mailing_draft[message.from_user.id]['text'] = message.text; start_mailing(message.from_user.id, message.text)

def process_mailing_photo(message):
    if message.from_user.id not in admin_mailing_draft: return
    if not message.photo: msg = bot.send_message(message.chat.id, "❌ Фото!"); bot.register_next_step_handler(msg, process_mailing_photo); return
    admin_mailing_draft[message.from_user.id]['photo'] = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "📝 Текст:\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_photo_text)

def process_mailing_photo_text(message):
    if message.from_user.id not in admin_mailing_draft: return
    if message.text == "/cancel_mailing": cancel_mailing(message); return
    admin_mailing_draft[message.from_user.id]['text'] = message.text; draft = admin_mailing_draft[message.from_user.id]; start_mailing(message.from_user.id, draft['text'], draft['photo'])

def process_mailing_photo_btn_photo(message):
    if message.from_user.id not in admin_mailing_draft: return
    if not message.photo: msg = bot.send_message(message.chat.id, "❌ Фото!"); bot.register_next_step_handler(msg, process_mailing_photo_btn_photo); return
    admin_mailing_draft[message.from_user.id]['photo'] = message.photo[-1].file_id
    msg = bot.send_message(message.chat.id, "📝 Текст:\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_photo_btn_text)

def process_mailing_photo_btn_text(message):
    if message.from_user.id not in admin_mailing_draft: return
    if message.text == "/cancel_mailing": cancel_mailing(message); return
    admin_mailing_draft[message.from_user.id]['text'] = message.text
    msg = bot.send_message(message.chat.id, "🔘 Кнопки:\nТекст|url\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_photo_btn_btns)

def process_mailing_photo_btn_btns(message):
    if message.from_user.id not in admin_mailing_draft: return
    if message.text == "/cancel_mailing": cancel_mailing(message); return
    admin_mailing_draft[message.from_user.id]['btns'] = message.text; draft = admin_mailing_draft[message.from_user.id]; start_mailing(message.from_user.id, draft['text'], draft['photo'], draft['btns'])

def process_mailing_text_btn_text(message):
    if message.from_user.id not in admin_mailing_draft: return
    if message.text == "/cancel_mailing": cancel_mailing(message); return
    admin_mailing_draft[message.from_user.id]['text'] = message.text
    msg = bot.send_message(message.chat.id, "🔘 Кнопки:\nТекст|url\n/cancel_mailing"); bot.register_next_step_handler(msg, process_mailing_text_btn_btns)

def process_mailing_text_btn_btns(message):
    if message.from_user.id not in admin_mailing_draft: return
    if message.text == "/cancel_mailing": cancel_mailing(message); return
    admin_mailing_draft[message.from_user.id]['btns'] = message.text; draft = admin_mailing_draft[message.from_user.id]; start_mailing(message.from_user.id, draft['text'], None, draft['btns'])

def start_mailing(admin_id, text, photo=None, btns_raw=None):
    conn = sqlite3.connect("bot_database.db"); cursor = conn.cursor(); cursor.execute("SELECT user_id FROM users"); users = cursor.fetchall(); conn.close()
    total = len(users); sent = 0; failed = 0
    bot.send_message(admin_id, f"📢 Рассылка... Всего: {total}")
    markup = None
    if btns_raw:
        markup = types.InlineKeyboardMarkup(row_width=1)
        for line in btns_raw.strip().split('\n'):
            try: btn_text, url = line.split('|'); markup.add(types.InlineKeyboardButton(btn_text.strip(), url=url.strip()))
            except: pass
    for user in users:
        try:
            if photo and markup: bot.send_photo(user[0], photo, caption=text, parse_mode="HTML", reply_markup=markup)
            elif photo: bot.send_photo(user[0], photo, caption=text, parse_mode="HTML")
            elif markup: bot.send_message(user[0], text, parse_mode="HTML", reply_markup=markup)
            else: bot.send_message(user[0], text, parse_mode="HTML")
            sent += 1
        except: failed += 1
    bot.send_message(admin_id, f"✅ Готово!\nОтправлено: {sent}\nНе доставлено: {failed}")
    if admin_id in admin_mailing_draft: del admin_mailing_draft[admin_id]

# ================= ЗАПУСК =================
if __name__ == "__main__":
    print("🤖 Бот запущен!")
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            print("🔄 Перезапуск через 5 сек...")
            time.sleep(5)
