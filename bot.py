import telebot
import sqlite3
import datetime
import time
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ==========================================
# НАСТРОЙКИ БОТА
# ==========================================
BOT_TOKEN = '8974171870:AAHB4rwB2SM5hkflzD3BZC94qm7N6Mj0ccE'
ADMIN_ID = 314148464

bot = telebot.TeleBot(BOT_TOKEN)
user_states = {}

# ==========================================
# ЯЗЫКИ
# ==========================================
LANG = {
    'ru': {
        'welcome': "Наша команда рада приветствовать вас в нашем боте!\n\nЗдесь вы можете приобрести подписку для нашего приложения NetWing.",
        'shop': "🗂 Выберите раздел:",
        'profile_text': "👤 Профиль пользователя\n\n🆔 ID: {0}\n👤 Имя: {1}\n📅 Регистрация: {2}\n💰 Потрачено: {3}₽\n🛒 Покупок: {4}",
        'no_profile': "❗ Профиль не найден. Нажмите /start.",
        'cart_empty': "❗ Магазин пуст.",
        'admin_panel': "⚙️ Панель управления",
        'select_lang': "🌐 Выберите язык / Choose language:",
        'lang_switched': "✅ Язык изменён на Русский.",
        'buy_success': "✅ Оплата прошла! Ваш ключ: `{0}`",
        'back': "⬅️ Назад",
        'back_to_sections': "⬅️ К разделам",
    },
    'en': {
        'welcome': "Our team is glad to welcome you to our bot!\n\nHere you can purchase a subscription for our NetWing app.",
        'shop': "🗂 Choose a section:",
        'profile_text': "👤 User Profile\n\n🆔 ID: {0}\n👤 Name: {1}\n📅 Registered: {2}\n💰 Spent: {3}₽\n🛒 Purchases: {4}",
        'no_profile': "❗ Profile not found. Press /start.",
        'cart_empty': "❗ The store is empty.",
        'admin_panel': "⚙️ Control Panel",
        'select_lang': "🌐 Choose language / Выберите язык:",
        'lang_switched': "✅ Language changed to English.",
        'buy_success': "✅ Payment successful! Your key: `{0}`",
        'back': "⬅️ Back",
        'back_to_sections': "⬅️ Back to sections",
    }
}

# ==========================================
# БАЗА ДАННЫХ (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect('shop_data.db')
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, reg_date TEXT, spent INTEGER DEFAULT 0, purchases INTEGER DEFAULT 0, lang TEXT DEFAULT "ru", banned INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT DEFAULT "Не установлено", photo_id TEXT DEFAULT "", is_hidden INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS subcategories (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT NOT NULL, FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE)')
    cur.execute('CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, subcategory_id INTEGER DEFAULT 0, category_id INTEGER DEFAULT 0, name TEXT NOT NULL, price INTEGER NOT NULL, description TEXT DEFAULT "Описание отсутствует", photo_id TEXT DEFAULT "", file_id TEXT DEFAULT "", is_hidden INTEGER DEFAULT 0)')
    cur.execute('CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, product_name TEXT, amount INTEGER, date TEXT, status TEXT DEFAULT "paid")')
    cur.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
    cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('payment_methods', '💳 СБП по номеру +79991234567')")
    conn.commit()
    conn.close()

# ================= ФУНКЦИИ БАЗЫ =================
def get_lang(user_id):
    conn = sqlite3.connect('shop_data.db')
    cur = conn.cursor()
    cur.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 'ru'

def db_add_user(user_id, first_name, username, lang='ru'):
    conn = sqlite3.connect('shop_data.db')
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
    if not cur.fetchone():
        cur.execute("INSERT INTO users (user_id, first_name, username, reg_date, lang) VALUES (?, ?, ?, ?, ?)", 
                    (user_id, first_name, username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), lang))
    else:
        cur.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))
    conn.commit()
    conn.close()

def get_user_lang(user_id):
    conn = sqlite3.connect('shop_data.db')
    cur = conn.cursor()
    cur.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res[0] if res else 'ru'

def is_banned(user_id):
    conn = sqlite3.connect('shop_data.db')
    cur = conn.cursor()
    cur.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
    res = cur.fetchone()
    conn.close()
    return res and res[0] == 1

def db_get_user_profile(user_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,)); res = cur.fetchone(); conn.close(); return res

def db_get_categories(include_hidden=False):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor()
    if include_hidden: cur.execute("SELECT * FROM categories")
    else: cur.execute("SELECT * FROM categories WHERE is_hidden=0")
    res = cur.fetchall(); conn.close(); return res

def db_get_category(cat_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("SELECT * FROM categories WHERE id=?", (cat_id,)); res = cur.fetchone(); conn.close(); return res

def db_add_category(name, desc, photo_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("INSERT INTO categories (name, description, photo_id) VALUES (?, ?, ?)", (name, desc, photo_id)); conn.commit(); conn.close()

def db_update_category(cat_id, field, value):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute(f"UPDATE categories SET {field} = ? WHERE id = ?", (value, cat_id)); conn.commit(); conn.close()

def db_delete_category(cat_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("DELETE FROM categories WHERE id=?", (cat_id,)); conn.commit(); conn.close()

def db_get_subcategories(cat_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("SELECT * FROM subcategories WHERE category_id=?", (cat_id,)); res = cur.fetchall(); conn.close(); return res

def db_add_subcategory(cat_id, name):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("INSERT INTO subcategories (category_id, name) VALUES (?, ?)", (cat_id, name)); conn.commit(); conn.close()

def db_get_products(subcat_id=None, cat_id=None, include_hidden=False):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor()
    if subcat_id: cur.execute("SELECT * FROM products WHERE subcategory_id=?" + (" AND is_hidden=0" if not include_hidden else ""), (subcat_id,))
    elif cat_id: cur.execute("SELECT * FROM products WHERE category_id=? AND subcategory_id=0" + (" AND is_hidden=0" if not include_hidden else ""), (cat_id,))
    else: cur.execute("SELECT * FROM products")
    res = cur.fetchall(); conn.close(); return res

def db_get_product(prod_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("SELECT * FROM products WHERE id=?", (prod_id,)); res = cur.fetchone(); conn.close(); return res

def db_add_product(cat_id, subcat_id, name, price, description, photo_id, file_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("INSERT INTO products (category_id, subcategory_id, name, price, description, photo_id, file_id) VALUES (?, ?, ?, ?, ?, ?, ?)", (cat_id, subcat_id, name, price, description, photo_id, file_id)); conn.commit(); conn.close()

def db_update_product(prod_id, field, value):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute(f"UPDATE products SET {field} = ? WHERE id = ?", (value, prod_id)); conn.commit(); conn.close()

def db_delete_product(prod_id):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); cur.execute("DELETE FROM products WHERE id=?", (prod_id,)); conn.commit(); conn.close()

def db_add_purchase(user_id, product_name, price):
    conn = sqlite3.connect('shop_data.db'); cur = conn.cursor(); now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("INSERT INTO orders (user_id, product_name, amount, date) VALUES (?, ?, ?, ?)", (user_id, product_name, price, now))
    cur.execute("UPDATE users SET spent = spent + ?, purchases = purchases + 1 WHERE user_id=?", (price, user_id)); conn.commit(); conn.close()

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def welcome_keyboard(user_id):
    lang = get_user_lang(user_id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("▶️ " + ("Перейти в магазин" if lang=='ru' else "Go to store")))
    kb.row(KeyboardButton("👤 " + ("Личный кабинет" if lang=='ru' else "Profile")), KeyboardButton("💰 " + ("Реферальная система" if lang=='ru' else "Referral")))
    kb.add(KeyboardButton("👮 " + ("Поддержка" if lang=='ru' else "Support")))
    if user_id == ADMIN_ID: kb.add(KeyboardButton("⚙️ " + ("Панель управления" if lang=='ru' else "Admin Panel")))
    return kb

def profile_inline_keyboard(user_id):
    lang = get_user_lang(user_id)
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(text="📦 " + ("Мои покупки" if lang=='ru' else "My purchases"), callback_data="my_orders"))
    kb.add(InlineKeyboardButton(text="⬅️ " + ("Главное меню" if lang=='ru' else "Main menu"), callback_data="back_to_main"))
    return kb

def categories_shop_kb(user_id):
    lang = get_user_lang(user_id)
    kb = InlineKeyboardMarkup()
    for cat in db_get_categories(include_hidden=False):
        kb.add(InlineKeyboardButton(text=f"📁 {cat[1]}", callback_data=f"shop_cat_{cat[0]}"))
    return kb

def sub_or_products_kb(cat_id, user_id):
    lang = get_user_lang(user_id)
    subs = db_get_subcategories(cat_id); products = db_get_products(cat_id=cat_id, include_hidden=False)
    kb = InlineKeyboardMarkup()
    for sub in subs: kb.add(InlineKeyboardButton(text=f"📂 {sub[2]}", callback_data=f"shop_sub_{sub[0]}"))
    for prod in products: kb.add(InlineKeyboardButton(text=f"📦 {prod[2]} - {prod[3]}₽", callback_data=f"shop_prod_{prod[0]}"))
    kb.add(InlineKeyboardButton(text=LANG[lang]['back_to_sections'], callback_data="shop_back"))
    return kb

def products_shop_kb(subcat_id):
    kb = InlineKeyboardMarkup(); items = db_get_products(subcat_id=subcat_id, include_hidden=False)
    for prod in items: kb.add(InlineKeyboardButton(text=f"📦 {prod[2]} - {prod[3]}₽", callback_data=f"shop_prod_{prod[0]}"))
    kb.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"shop_back_sub_{subcat_id}")); return kb

def product_buy_kb(prod_id):
    kb = InlineKeyboardMarkup(); kb.add(InlineKeyboardButton(text="💳 Оплатить", callback_data=f"buy_{prod_id}")); kb.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"shop_back_prod_{prod_id}")); return kb

def admin_main_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton(text="📦 Управление товарами", callback_data="adm_products"))
    kb.add(InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats"))
    kb.add(InlineKeyboardButton(text="🔨 Забанить / Разбанить", callback_data="adm_ban"))
    kb.add(InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast"))
    kb.add(InlineKeyboardButton(text="💳 Способы оплаты", callback_data="adm_payments"))
    return kb

def admin_categories_kb():
    kb = InlineKeyboardMarkup()
    for cat in db_get_categories(include_hidden=True):
        eye = "👁️" if cat[4] == 0 else "🚫"
        kb.add(InlineKeyboardButton(text=f"{eye} {cat[1]}", callback_data=f"adm_cat_{cat[0]}"))
    kb.add(InlineKeyboardButton(text="➕ Создать категорию", callback_data="adm_add_cat"))
    kb.add(InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_back_menu"))
    return kb

def admin_cat_edit_kb(cat_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"adm_edit_name_{cat_id}"), InlineKeyboardButton(text="✏️ Описание", callback_data=f"adm_edit_desc_{cat_id}"))
    kb.add(InlineKeyboardButton(text="🖼 Фото", callback_data=f"adm_edit_cat_photo_{cat_id}"))
    cat = db_get_category(cat_id)
    toggle_text = "🔓 Показать" if cat[4] == 1 else "🔒 Скрыть"
    kb.add(InlineKeyboardButton(text=toggle_text, callback_data=f"adm_toggle_{cat_id}"))
    kb.row(InlineKeyboardButton(text="➕ Подкатегорию", callback_data=f"adm_add_sub_{cat_id}"), InlineKeyboardButton(text="➕ Товар", callback_data=f"adm_add_prod_{cat_id}"))
    kb.row(InlineKeyboardButton(text="🗑 Удалить категорию", callback_data=f"adm_del_cat_{cat_id}"), InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back_cats"))
    return kb

def admin_product_edit_kb(prod_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"adm_prod_name_{prod_id}"), InlineKeyboardButton(text="📝 Описание", callback_data=f"adm_prod_desc_{prod_id}"))
    kb.add(InlineKeyboardButton(text="💰 Цена", callback_data=f"adm_prod_price_{prod_id}"), InlineKeyboardButton(text="🖼 Фото", callback_data=f"adm_prod_photo_{prod_id}"))
    kb.add(InlineKeyboardButton(text="📁 Файл", callback_data=f"adm_prod_file_{prod_id}"))
    kb.add(InlineKeyboardButton(text="❌ Скрыть товар", callback_data=f"adm_prod_hide_{prod_id}"))
    kb.add(InlineKeyboardButton(text="🗑 Удалить товар", callback_data=f"adm_prod_del_{prod_id}"))
    kb.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"adm_back_prod_{prod_id}"))
    return kb

# ==========================================
# ОБРАБОТЧИКИ КОМАНД
# ==========================================
@bot.message_handler(commands=['start'])
def start(message):
    if is_banned(message.chat.id): return
    db_add_user(message.chat.id, message.chat.first_name, message.chat.username)
    lang = get_user_lang(message.chat.id)
    bot.send_message(message.chat.id, LANG[lang]['welcome'], disable_web_page_preview=True, reply_markup=welcome_keyboard(message.chat.id))

@bot.message_handler(commands=['language'])
def language_command(message):
    if is_banned(message.chat.id): return
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"), InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en"))
    bot.send_message(message.chat.id, LANG[get_user_lang(message.chat.id)]['select_lang'], reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_lang_"))
def set_lang(call):
    lang = call.data.split("_")[2]
    db_add_user(call.from_user.id, call.from_user.first_name, call.from_user.username, lang)
    bot.answer_callback_query(call.id, LANG[lang]['lang_switched'])
    start(call.message)

# ==========================================
# МАГАЗИН И ПОКУПКИ
# ==========================================
@bot.message_handler(func=lambda message: message.text in ["▶️ Перейти в магазин", "▶️ Go to store"])
def go_to_shop(message):
    if is_banned(message.chat.id): return
    lang = get_user_lang(message.chat.id)
    if not db_get_categories(include_hidden=False):
        bot.send_message(message.chat.id, LANG[lang]['cart_empty'], reply_markup=welcome_keyboard(message.chat.id)); return
    bot.send_message(message.chat.id, LANG[lang]['shop'], reply_markup=categories_shop_kb(message.chat.id))

@bot.message_handler(func=lambda message: message.text in ["👤 Личный кабинет", "👤 Profile"])
def user_profile(message):
    if is_banned(message.chat.id): return
    lang = get_user_lang(message.chat.id)
    user = db_get_user_profile(message.chat.id)
    if user:
        text = LANG[lang]['profile_text'].format(user[0], user[1] or "Не указано", user[3], user[4], user[5])
        bot.send_photo(message.chat.id, photo="https://i.imgur.com/your_banner.png", caption=text, parse_mode="HTML", reply_markup=profile_inline_keyboard(message.chat.id))
    else:
        bot.send_message(message.chat.id, LANG[lang]['no_profile'], reply_markup=welcome_keyboard(message.chat.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_cat_"))
def nav_cat(call):
    if is_banned(call.from_user.id): return
    cat_id = int(call.data.split("_")[2]); cat = db_get_category(cat_id)
    if cat[3]:
        bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media=telebot.types.InputMediaPhoto(cat[3], caption=f"📁 **{cat[1]}**\n\n{cat[2]}"), reply_markup=sub_or_products_kb(cat_id, call.from_user.id))
    else:
        bot.edit_message_text(f"📁 **{cat[1]}**\n\n{cat[2]}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=sub_or_products_kb(cat_id, call.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_sub_"))
def nav_sub(call):
    if is_banned(call.from_user.id): return
    sub_id = int(call.data.split("_")[2])
    bot.edit_message_text("📦 Выберите товар:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=products_shop_kb(subcat_id=sub_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_prod_"))
def nav_prod(call):
    if is_banned(call.from_user.id): return
    prod_id = int(call.data.split("_")[2]); prod = db_get_product(prod_id)
    text = f"📦 **{prod[2]}**\n\n📝 {prod[4]}\n\n💰 Цена: {prod[3]}₽"
    if prod[5]:
        bot.edit_message_media(chat_id=call.message.chat.id, message_id=call.message.message_id, media=telebot.types.InputMediaPhoto(prod[5], caption=text, parse_mode="Markdown"), reply_markup=product_buy_kb(prod_id))
    else:
        bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=product_buy_kb(prod_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_process(call):
    if is_banned(call.from_user.id): return
    prod_id = int(call.data.split("_")[1]); prod = db_get_product(prod_id)
    db_add_purchase(call.from_user.id, prod[2], prod[3])
    lang = get_user_lang(call.from_user.id)
    if prod[6]:
        try: bot.send_document(call.message.chat.id, prod[6], caption=f"✅ Ключ/Файл для **{prod[2]}**")
        except: bot.send_message(call.message.chat.id, LANG[lang]['buy_success'].format(f"HESERA-{prod_id}"), parse_mode="Markdown")
    else:
        bot.send_message(call.message.chat.id, LANG[lang]['buy_success'].format(f"HESERA-{prod_id}"), parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == "shop_back")
def back_main(call):
    if is_banned(call.from_user.id): return
    bot.edit_message_text("🗂 " + ("Выберите раздел:" if get_user_lang(call.from_user.id)=='ru' else "Choose section:"), chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=categories_shop_kb(call.from_user.id))

# ==========================================
# АДМИН: ДОБАВЛЕНИЕ ФУНКЦИЙ
# ==========================================
@bot.message_handler(func=lambda message: message.text in ["⚙️ Панель управления", "⚙️ Admin Panel"])
def admin_panel_btn(message):
    if message.chat.id != ADMIN_ID: return
    bot.send_message(message.chat.id, "⚙️ **Панель управления**", parse_mode="Markdown", reply_markup=admin_main_kb())

@bot.callback_query_handler(func=lambda call: call.data == "adm_products" and call.from_user.id == ADMIN_ID)
def adm_products(call): bot.edit_message_text("📁 Категории:", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=admin_categories_kb())

@bot.callback_query_handler(func=lambda call: call.data == "adm_stats" and call.from_user.id == ADMIN_ID)
def adm_stats(call):
    conn=sqlite3.connect('shop_data.db'); c=conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); u=c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders"); o=c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM orders"); s=c.fetchone()[0] or 0
    conn.close()
    bot.edit_message_text(f"📊 Статистика\n\n👤 Пользователей: {u}\n📦 Заказов: {o}\n💰 Выручка: {s}₽", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=admin_main_kb())

# ----- Управление Категориями -----
@bot.callback_query_handler(func=lambda call: call.data == "adm_add_cat" and call.from_user.id == ADMIN_ID)
def adm_add_cat(call): user_states[call.from_user.id] = 'add_cat_name'; bot.send_message(call.message.chat.id, "📦 Введите название категории:")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id) == 'add_cat_name')
def add_cat_name(m): user_states[m.chat.id]='add_cat_desc'; user_states[f'{m.chat.id}_cn']=m.text; bot.send_message(m.chat.id, "📝 Введите описание:")
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id) == 'add_cat_desc')
def add_cat_desc(m): user_states[m.chat.id]='add_cat_photo'; user_states[f'{m.chat.id}_cd']=m.text; bot.send_message(m.chat.id, "🖼 Отправьте фото (или /skip_photo):")
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id) == 'add_cat_photo')
def add_cat_photo(m): db_add_category(user_states[f'{m.chat.id}_cn'], user_states[f'{m.chat.id}_cd'], m.photo[-1].file_id); bot.send_message(m.chat.id, "✅ Категория создана!"); user_states.pop(m.chat.id, None)
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id) == 'add_cat_photo' and m.text == '/skip_photo')
def add_cat_no_photo(m): db_add_category(user_states[f'{m.chat.id}_cn'], user_states[f'{m.chat.id}_cd'], ""); bot.send_message(m.chat.id, "✅ Категория создана!"); user_states.pop(m.chat.id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_cat_") and call.from_user.id == ADMIN_ID)
def adm_cat_edit(call):
    cat_id = int(call.data.split("_")[2]); cat = db_get_category(cat_id)
    bot.edit_message_text(f"🗂 **{cat[1]}**\n\n{cat[2]}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=admin_cat_edit_kb(cat_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_edit_") and call.from_user.id == ADMIN_ID)
def adm_edit_cat(call):
    parts=call.data.split("_"); action, cat_id = parts[2], int(parts[3])
    if action=="name": user_states[call.from_user.id]=f'edit_cn_{cat_id}'; bot.send_message(call.message.chat.id, "✏️ Новое название:")
    elif action=="desc": user_states[call.from_user.id]=f'edit_cd_{cat_id}'; bot.send_message(call.message.chat.id, "✏️ Новое описание:")
    elif action=="cat_photo": user_states[call.from_user.id]=f'edit_cp_{cat_id}'; bot.send_message(call.message.chat.id, "🖼 Новое фото:")
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("edit_"))
def save_edit_cat(m):
    state=user_states[m.chat.id]; parts=state.split("_"); action, cat_id = parts[1], int(parts[2])
    if action=="cn": db_update_category(cat_id, "name", m.text)
    elif action=="cd": db_update_category(cat_id, "description", m.text)
    elif action=="cp": db_update_category(cat_id, "photo_id", m.photo[-1].file_id)
    bot.send_message(m.chat.id, "✅ Обновлено!"); user_states.pop(m.chat.id, None)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_toggle_") and call.from_user.id == ADMIN_ID)
def adm_toggle(call):
    cat_id = int(call.data.split("_")[2]); cat = db_get_category(cat_id)
    db_update_category(cat_id, "is_hidden", 0 if cat[4] == 1 else 1); bot.answer_callback_query(call.id, "🔄 Статус обновлен!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_del_cat_") and call.from_user.id == ADMIN_ID)
def adm_del_cat(call):
    cat_id = int(call.data.split("_")[3])
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✅ Да, удалить", callback_data=f"adm_del_conf_{cat_id}"), InlineKeyboardButton("❌ Отмена", callback_data="adm_back_cats"))
    bot.edit_message_text("⚠️ Вы уверены, что хотите удалить категорию и все её товары?", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_del_conf_") and call.from_user.id == ADMIN_ID)
def adm_del_conf(call):
    cat_id = int(call.data.split("_")[3]); db_delete_category(cat_id); bot.edit_message_text("🗑 Категория удалена.", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=admin_categories_kb())

# ----- Подкатегории -----
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_add_sub_") and call.from_user.id == ADMIN_ID)
def adm_add_sub(call):
    cat_id = int(call.data.split("_")[3]); user_states[call.from_user.id]=f'add_sub_{cat_id}'; bot.send_message(call.message.chat.id, "📂 Введите название подкатегории:")
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("add_sub_"))
def finish_sub(m):
    cat_id = int(user_states[m.chat.id].split("_")[2]); db_add_subcategory(cat_id, m.text); bot.send_message(m.chat.id, "✅ Подкатегория создана!"); user_states.pop(m.chat.id, None)

# ----- УПРАВЛЕНИЕ ТОВАРАМИ -----
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_add_prod_") and call.from_user.id == ADMIN_ID)
def adm_add_prod(call):
    cat_id = int(call.data.split("_")[3]); user_states[call.from_user.id]=f'prod_np_{cat_id}'; bot.send_message(call.message.chat.id, "📦 Шаг 1: Введите `Название Цена` (через пробел)")
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("prod_np_"))
def prod_step1(m):
    cat_id=int(user_states[m.chat.id].split("_")[2])
    try: n,p=m.text.rsplit(" ",1); user_states[m.chat.id]=f'prod_desc_{cat_id}'; user_states[f'{m.chat.id}_pn']=n; user_states[f'{m.chat.id}_pp']=int(p); bot.send_message(m.chat.id, "📝 Шаг 2: Введите описание:")
    except: bot.send_message(m.chat.id, "❌ Ошибка. Пишите: Название Цена")
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("prod_desc_"))
def prod_step2(m):
    cat_id=int(user_states[m.chat.id].split("_")[2]); user_states[m.chat.id]=f'prod_photo_{cat_id}'; user_states[f'{m.chat.id}_pd']=m.text; bot.send_message(m.chat.id, "🖼 Шаг 3: Отправьте фото (или /skip_photo):")
@bot.message_handler(content_types=['photo'], func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("prod_photo_"))
def prod_step3(m):
    cat_id=int(user_states[m.chat.id].split("_")[2]); user_states[m.chat.id]=f'prod_file_{cat_id}'; user_states[f'{m.chat.id}_pphoto']=m.photo[-1].file_id; bot.send_message(m.chat.id, "📁 Шаг 4: Отправьте файл (или /skip_file):")
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("prod_photo_") and m.text == "/skip_photo")
def prod_step3_skip(m):
    cat_id=int(user_states[m.chat.id].split("_")[2]); user_states[m.chat.id]=f'prod_file_{cat_id}'; user_states[f'{m.chat.id}_pphoto']=""; bot.send_message(m.chat.id, "📁 Шаг 4: Отправьте файл (или /skip_file):")
@bot.message_handler(content_types=['document'], func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("prod_file_"))
def prod_step4(m):
    cat_id=int(user_states[m.chat.id].split("_")[2]); db_add_product(cat_id, 0, user_states[f'{m.chat.id}_pn'], user_states[f'{m.chat.id}_pp'], user_states[f'{m.chat.id}_pd'], user_states[f'{m.chat.id}_pphoto'], m.document.file_id); bot.send_message(m.chat.id, "✅ Товар создан!"); user_states.pop(m.chat.id, None)
@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("prod_file_") and m.text == "/skip_file")
def prod_step4_skip(m):
    cat_id=int(user_states[m.chat.id].split("_")[2]); db_add_product(cat_id, 0, user_states[f'{m.chat.id}_pn'], user_states[f'{m.chat.id}_pp'], user_states[f'{m.chat.id}_pd'], user_states[f'{m.chat.id}_pphoto'], ""); bot.send_message(m.chat.id, "✅ Товар создан!"); user_states.pop(m.chat.id, None)

# ----- РЕДАКТИРОВАНИЕ ТОВАРА -----
@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_prod_") and call.from_user.id == ADMIN_ID)
def adm_edit_product(call):
    parts = call.data.split("_"); action, prod_id = parts[2], int(parts[3])
    if action == "name": user_states[call.from_user.id]=f'edit_pn_{prod_id}'; bot.send_message(call.message.chat.id, "✏️ Новое название:")
    elif action == "desc": user_states[call.from_user.id]=f'edit_pd_{prod_id}'; bot.send_message(call.message.chat.id, "✏️ Новое описание:")
    elif action == "price": user_states[call.from_user.id]=f'edit_pp_{prod_id}'; bot.send_message(call.message.chat.id, "💰 Новая цена (цифрами):")
    elif action == "photo": user_states[call.from_user.id]=f'edit_pphoto_{prod_id}'; bot.send_message(call.message.chat.id, "🖼 Отправьте новое фото:")
    elif action == "file": user_states[call.from_user.id]=f'edit_pfile_{prod_id}'; bot.send_message(call.message.chat.id, "📁 Отправьте новый файл:")
    elif action == "hide": db_update_product(prod_id, "is_hidden", 1); bot.answer_callback_query(call.id, "🚫 Товар скрыт от покупателей!")
    elif action == "del": db_delete_product(prod_id); bot.answer_callback_query(call.id, "🗑 Товар удалён!")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id, "").startswith("edit_"))
def save_edit_product(m):
    state=user_states[m.chat.id]; parts=state.split("_"); action, prod_id = parts[1], int(parts[2])
    if action=="pn": db_update_product(prod_id, "name", m.text)
    elif action=="pd": db_update_product(prod_id, "description", m.text)
    elif action=="pp": 
        if m.text.isdigit(): db_update_product(prod_id, "price", int(m.text))
        else: bot.send_message(m.chat.id, "❌ Введите цифры!"); return
    elif action=="pphoto": db_update_product(prod_id, "photo_id", m.photo[-1].file_id)
    elif action=="pfile": db_update_product(prod_id, "file_id", m.document.file_id)
    bot.send_message(m.chat.id, "✅ Товар обновлен!"); user_states.pop(m.chat.id, None)

# ----- БАН/РАЗБАН -----
@bot.callback_query_handler(func=lambda call: call.data == "adm_ban" and call.from_user.id == ADMIN_ID)
def adm_ban_menu(call):
    user_states[call.from_user.id] = 'wait_ban_id'
    bot.send_message(call.message.chat.id, "🔨 Введите ID пользователя (число), которого нужно забанить или разбанить:")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id) == 'wait_ban_id')
def process_ban(m):
    if not m.text.isdigit(): bot.send_message(m.chat.id, "❌ Введите корректный ID (цифры)."); return
    target_id = int(m.text)
    conn = sqlite3.connect('shop_data.db'); cur=conn.cursor()
    cur.execute("SELECT banned FROM users WHERE user_id=?", (target_id,)); res=cur.fetchone()
    if not res: bot.send_message(m.chat.id, "❌ Пользователь не найден."); user_states.pop(m.chat.id, None); return
    new_status = 0 if res[0] == 1 else 1
    cur.execute("UPDATE users SET banned = ? WHERE user_id = ?", (new_status, target_id)); conn.commit(); conn.close()
    bot.send_message(m.chat.id, f"✅ Статус обновлен! {'Забанен' if new_status == 1 else 'Разбанен'}."); user_states.pop(m.chat.id, None)

# ----- РАССЫЛКА -----
@bot.callback_query_handler(func=lambda call: call.data == "adm_broadcast" and call.from_user.id == ADMIN_ID)
def adm_broadcast(call):
    user_states[call.from_user.id] = 'wait_broadcast'
    bot.send_message(call.message.chat.id, "📢 Напишите текст для рассылки. Можно отправить сообщение с фото.")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id) == 'wait_broadcast')
def broadcast_msg(m):
    conn = sqlite3.connect('shop_data.db'); cur=conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE banned=0"); users=cur.fetchall(); conn.close()
    bot.send_message(m.chat.id, f"📢 Начинаю рассылку {len(users)} пользователям...")
    for u in users:
        try:
            if m.photo: bot.send_photo(u[0], m.photo[-1].file_id, caption=m.caption or m.text)
            else: bot.send_message(u[0], m.text)
            time.sleep(0.1)
        except: pass
    bot.send_message(m.chat.id, "✅ Рассылка завершена!"); user_states.pop(m.chat.id, None)

# ----- СПОСОБЫ ОПЛАТЫ -----
@bot.callback_query_handler(func=lambda call: call.data == "adm_payments" and call.from_user.id == ADMIN_ID)
def adm_payments(call):
    conn = sqlite3.connect('shop_data.db'); cur=conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='payment_methods'"); pm=cur.fetchone()[0]; conn.close()
    kb = InlineKeyboardMarkup().add(InlineKeyboardButton("✏️ Изменить", callback_data="adm_edit_payments"))
    bot.edit_message_text(f"💳 Текущие способы оплаты:\n\n{pm}", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data == "adm_edit_payments" and call.from_user.id == ADMIN_ID)
def adm_edit_payments(call):
    user_states[call.from_user.id] = 'wait_payments'
    bot.send_message(call.message.chat.id, "💳 Напишите новый текст для способов оплаты. Он будет показан покупателю.")

@bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID and user_states.get(m.chat.id) == 'wait_payments')
def save_payments(m):
    conn = sqlite3.connect('shop_data.db'); cur=conn.cursor()
    cur.execute("UPDATE settings SET value = ? WHERE key = 'payment_methods'", (m.text,)); conn.commit(); conn.close()
    bot.send_message(m.chat.id, "✅ Способы оплаты обновлены!"); user_states.pop(m.chat.id, None)

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    init_db()
    print("🤖 Бот (bot.py с языками и супер-админкой) запущен!")
    while True:
        try: bot.polling(none_stop=True)
        except Exception as e: print(f"❗ Перезапуск через 5 сек. Ошибка: {e}"); time.sleep(5)
