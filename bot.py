import os, pickle, datetime, time, random, string, json, threading, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = "8820585661:AAHfUzU_y3-p-eezmcd1d_0nCQndtZjWBtw"
ADMIN_ID = 314148464
DATA_FILE = '/tmp/shop_data.pkl'
SUPPORT_LINK = "https://t.me/hesers"
BOT_USERNAME = "ClumsyHeseraBot"
SBP_CARD = "220220671487913"
USD_RATE = 90
API_PORT = 10000
DOWNLOAD_LINK = "https://t.me/+8xHk6E4oLslhMjBk"
GROUP_ID = -1004359350990
CRYPTO_PAY_TOKEN = "551375:AAzRfloY3sYQgypNYytUD4BqHRZ6dcjCSbH"
CRYPTO_PAY_URL = "https://pay.crypt.bot/api"

def generate_key():
    return "Hesera_" + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))

INITIAL_DATA = {
    "users": {}, "pending_receipts": {}, "licenses": {},
    "categories": {"roblox": {"id": "roblox", "name": "🎮 Roblox", "desc": "Приватные читы", "items": [{
        "id": "mm2", "name": "🔪 MM2",
        "desc": "🟢 Приватный скрипт MM2\n🟢 Авто-фарм, Аим, ESP\n🟢 ПК и Android",
        "subscriptions": [
            {"name": "📅 7 дней", "price": 99, "duration_days": 7},
            {"name": "📅 12 дней", "price": 189, "duration_days": 12},
            {"name": "📅 30 дней", "price": 299, "duration_days": 30}
        ]
    }]}},
    "welcome_photo": None, "banned_users": [], "notifications_sent": []
}

class LicenseAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/check/'):
            key = self.path.replace('/check/', '').strip()
            data = load_data()
            lic = data["licenses"].get(key)
            if lic:
                exp = lic.get("expires")
                if isinstance(exp, str): exp = datetime.datetime.fromisoformat(exp)
                if isinstance(exp, datetime.datetime) and exp > datetime.datetime.now():
                    hwid = self.headers.get('HWID', '')
                    if lic.get("activated"):
                        if lic.get("hwid") == hwid: self.send_response(200); response = {"status": "valid"}
                        else: self.send_response(403); response = {"status": "hwid_mismatch"}
                    else:
                        if hwid: lic["hwid"] = hwid; lic["activated"] = True; save_data(data)
                        self.send_response(200); response = {"status": "activated"}
                else: self.send_response(403); response = {"status": "expired"}
            else: self.send_response(404); response = {"status": "invalid"}
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else: self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass

def run_api(): HTTPServer(('0.0.0.0', API_PORT), LicenseAPI).serve_forever()

def load_data():
    if os.path.exists(DATA_FILE):
        try: return pickle.load(open(DATA_FILE, 'rb'))
        except: return INITIAL_DATA
    return INITIAL_DATA

def save_data(data):
    with open(DATA_FILE, 'wb') as f: pickle.dump(data, f)

def is_admin(uid): return int(uid) == ADMIN_ID

def get_user(data, uid):
    uid = str(uid)
    if uid not in data["users"]:
        data["users"][uid] = {"balance_rub": 0, "ref_balance": 0, "purchases": [], "refs": [], "joined": datetime.datetime.now().isoformat()}
    return data["users"][uid]

def has_active_license(data, uid, product_id="mm2"):
    for key, lic in data["licenses"].items():
        if lic.get("user_id") == uid and lic.get("product_id") == product_id:
            exp = lic.get("expires")
            if isinstance(exp, str): exp = datetime.datetime.fromisoformat(exp)
            if isinstance(exp, datetime.datetime) and exp > datetime.datetime.now(): return key, lic
    return None, None

def create_crypto_invoice(amount_usd):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    payload = {"asset": "USDT", "amount": str(amount_usd), "description": "Hesera Shop", "expires_in": 1800}
    try:
        resp = requests.post(f"{CRYPTO_PAY_URL}/createInvoice", json=payload, headers=headers, timeout=15)
        data = resp.json()
        return data["result"] if data.get("ok") else None
    except: return None

def check_crypto_invoice(invoice_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    try:
        resp = requests.get(f"{CRYPTO_PAY_URL}/getInvoices?invoice_ids={invoice_id}", headers=headers, timeout=10)
        data = resp.json()
        return data["result"]["items"][0] if data.get("ok") and data["result"]["items"] else None
    except: return None

async def ban_in_group(context, user_id):
    try: await context.bot.ban_chat_member(GROUP_ID, int(user_id)); return True
    except: return False

async def unban_from_group(context, user_id):
    try:
        await context.bot.unban_chat_member(GROUP_ID, int(user_id))
        invite = await context.bot.create_chat_invite_link(GROUP_ID, member_limit=1)
        return invite.invite_link
    except: return None

async def check_and_ban_expired(context):
    data = load_data(); now = datetime.datetime.now()
    for key, lic in list(data["licenses"].items()):
        exp = lic.get("expires")
        if isinstance(exp, str): exp = datetime.datetime.fromisoformat(exp)
        if isinstance(exp, datetime.datetime) and exp < now and lic.get("in_group"):
            uid = lic.get("user_id")
            if uid and await ban_in_group(context, uid): lic["in_group"] = False
    save_data(data)

async def check_and_notify_expiring(context):
    data = load_data(); now = datetime.datetime.now()
    for key, lic in data["licenses"].items():
        exp = lic.get("expires")
        if isinstance(exp, str): exp = datetime.datetime.fromisoformat(exp)
        if isinstance(exp, datetime.datetime):
            rem = exp - now; dl = rem.days
            if 1 <= dl <= 2 and key not in data.get("notifications_sent", []):
                uid = lic.get("user_id")
                if uid:
                    try:
                        await context.bot.send_message(int(uid), f"⏰ *Подписка истекает!*\n\n📜 {lic.get('product','Hesera')}\n🔑 `{key}`\n⏳ {dl} д. {rem.seconds//3600} ч.\n\n🎮 *Развлекайся пока можешь!*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏰ Принял", callback_data=f"dismiss_{key}")]]))
                        data.setdefault("notifications_sent", []).append(key); save_data(data)
                    except: pass

def main_menu(uid, data):
    u = get_user(data, uid)
    return InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Каталог", callback_data='shop')], [InlineKeyboardButton(f"👤 Профиль · ₽{u.get('balance_rub',0)}", callback_data='profile')]])

def profile_kb(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("💸 Пополнить баланс", callback_data='topup')],
    [InlineKeyboardButton("🗃 Мои покупки", callback_data='purchases'), InlineKeyboardButton("👥 Рефералы", callback_data='referral')],
    [InlineKeyboardButton("🆘 Поддержка", url=SUPPORT_LINK)],
    [InlineKeyboardButton("« Назад", callback_data='main')]
])

def admin_menu(): return InlineKeyboardMarkup([
    [InlineKeyboardButton("👤 Управление пользователем", callback_data='admin_user_manage')],
    [InlineKeyboardButton("👥 Все пользователи", callback_data='admin_users')],
    [InlineKeyboardButton("🔑 Создать лицензию", callback_data='admin_create_key')],
    [InlineKeyboardButton("🗂 Управление категориями", callback_data='admin_cats')],
    [InlineKeyboardButton("🖼 Приветствие", callback_data='admin_welcome')],
    [InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast')],
    [InlineKeyboardButton("🔧 Сброс HWID", callback_data='admin_reset_hwid')],
    [InlineKeyboardButton("👥 Группа", callback_data='admin_group')],
    [InlineKeyboardButton("« Назад", callback_data='main')]
])

def admin_cats_kb(data):
    kb = []
    for cid, cat in data["categories"].items():
        kb.append([InlineKeyboardButton(f"📁 {cat.get('name','?')}", callback_data=f"admin_cat_{cid}")])
        kb.append([InlineKeyboardButton("📦 Товары", callback_data=f"admin_cat_items_{cid}"), InlineKeyboardButton("✏️ Описание", callback_data=f"admin_cat_desc_{cid}")])
    kb.append([InlineKeyboardButton("➕ Создать категорию", callback_data='admin_cat_new')])
    kb.append([InlineKeyboardButton("« Назад", callback_data='admin_menu')]); return InlineKeyboardMarkup(kb)

def admin_items_kb(data, cid):
    kb = [[InlineKeyboardButton(f"📦 {i.get('name','?')}", callback_data=f"admin_item_{cid}_{i['id']}")] for i in data["categories"].get(cid,{}).get("items",[])]
    kb.append([InlineKeyboardButton("➕ Добавить товар", callback_data=f"admin_item_new_{cid}")])
    kb.append([InlineKeyboardButton("« Назад", callback_data=f"admin_cat_{cid}")]); return InlineKeyboardMarkup(kb)

def user_manage_kb(target_uid, data):
    banned = target_uid in data.get("banned_users", [])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Забанить" if not banned else "✅ Разбанить", callback_data=f"um_ban_{target_uid}")],
        [InlineKeyboardButton("🗑 Забрать лицензии", callback_data=f"um_del_lic_{target_uid}")],
        [InlineKeyboardButton("💰 Изменить баланс", callback_data=f"um_bal_{target_uid}")],
        [InlineKeyboardButton("« Назад", callback_data='admin_menu')]
    ])

def shop_cats_kb(data):
    kb = [[InlineKeyboardButton(c["name"], callback_data=f"shop_cat_{cid}")] for cid, c in data["categories"].items()]
    kb.append([InlineKeyboardButton("« Назад", callback_data='main')]); return InlineKeyboardMarkup(kb)

def shop_items_kb(data, cid):
    kb = [[InlineKeyboardButton(i["name"], callback_data=f"product_{cid}_{i['id']}")] for i in data["categories"].get(cid,{}).get("items",[])]
    kb.append([InlineKeyboardButton("« Назад", callback_data='shop')]); return InlineKeyboardMarkup(kb)

def sub_kb(cid, iid, item):
    kb = [[InlineKeyboardButton(f"{s['name']} · {s['price']}₽", callback_data=f"sub_{cid}_{iid}_{i}")] for i, s in enumerate(item.get("subscriptions",[]))]
    kb.append([InlineKeyboardButton("« Назад", callback_data=f"shop_cat_{cid}")]); return InlineKeyboardMarkup(kb)

def topup_menu(): return InlineKeyboardMarkup([[InlineKeyboardButton("💳 СБП", callback_data='sbp'), InlineKeyboardButton("🪙 Крипто", callback_data='crypto')], [InlineKeyboardButton("« Назад", callback_data='profile')]])
def sbp_kb(rid): return InlineKeyboardMarkup([[InlineKeyboardButton("📸 Чек", callback_data=f"send_{rid}"), InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{rid}")]])
def admin_sbp_kb(rid): return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Подтвердить", callback_data=f"ok_{rid}"), InlineKeyboardButton("❌ Отказать", callback_data=f"no_{rid}")]])
def crypto_kb(inv_id, url): return InlineKeyboardMarkup([[InlineKeyboardButton("💳 Оплатить", url=url)], [InlineKeyboardButton("🔎 Проверить", callback_data=f"check_{inv_id}")], [InlineKeyboardButton("« Назад", callback_data='topup')]])
def referral_kb(uid, ref): return InlineKeyboardMarkup([[InlineKeyboardButton("📤 Поделиться", switch_inline_query=ref), InlineKeyboardButton("📋 Копировать", callback_data=f"copyref_{uid}")], [InlineKeyboardButton("« Назад", callback_data='profile')]])

async def start(update, context):
    uid = str(update.effective_user.id); data = load_data()
    user = get_user(data, uid)
    user["first_name"] = update.effective_user.first_name or ""; user["username"] = update.effective_user.username or ""
    save_data(data)
    if is_admin(uid): return await update.message.reply_text("🛠 *Админ-панель*", parse_mode="Markdown", reply_markup=admin_menu())
    await update.message.reply_text("🛍 *Hesera Shop*\n\nДобро пожаловать!", parse_mode="Markdown", reply_markup=main_menu(uid, data))

async def button(update, context):
    q = update.callback_query; await q.answer(); uid = str(q.from_user.id); data = load_data(); cb = q.data
    user = get_user(data, uid)
    if cb.startswith('dismiss_'): await q.message.delete(); return
    if is_admin(uid):
        if cb == 'admin_menu': await q.edit_message_text("🛠 *Админ-панель*", parse_mode="Markdown", reply_markup=admin_menu())
        elif cb == 'admin_user_manage': context.user_data['um'] = True; await q.edit_message_text("👤 Введите ID:")
        elif cb.startswith('um_ban_'):
            t = cb.replace('um_ban_', '')
            if t in data.get("banned_users", []): data["banned_users"].remove(t)
            else: data["banned_users"].append(t)
            save_data(data); await q.edit_message_text("✅ Готово!", reply_markup=admin_menu())
        elif cb.startswith('um_del_lic_'):
            t = cb.replace('um_del_lic_', '')
            for k in list(data["licenses"].keys()):
                if data["licenses"][k].get("user_id") == t: await ban_in_group(context, t); del data["licenses"][k]
            save_data(data); await q.edit_message_text("✅ Лицензии удалены!", reply_markup=admin_menu())
        elif cb.startswith('um_bal_'): context.user_data['um_bal'] = cb.replace('um_bal_', ''); await q.edit_message_text("💰 Введите новый баланс:")
        elif cb == 'admin_users':
            users = data.get("users", {}); msg = f"👥 *Пользователи*\n▸ Всего: {len(users)}\n▸ Лицензий: {len(data.get('licenses',{}))}"
            for u, d in sorted(users.items(), key=lambda x: str(x[1].get("joined","")), reverse=True)[:10]: msg += f"\n▸ `{u}` — {d.get('first_name','?')}"
            await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data='admin_menu')]]))
        elif cb == 'admin_create_key': context.user_data['create_key'] = True; await q.edit_message_text("🔑 Введите: `ID|Продукт|Дни`")
        elif cb == 'admin_cats': await q.edit_message_text("🗂 *Категории:*", parse_mode="Markdown", reply_markup=admin_cats_kb(data))
        elif cb == 'admin_cat_new': context.user_data['acn'] = True; await q.edit_message_text("📝 Введите название:")
        elif cb.startswith('admin_cat_desc_'): context.user_data['acd'] = cb.replace('admin_cat_desc_', ''); await q.edit_message_text("📝 Введите описание:")
        elif cb.startswith('admin_cat_items_'): await q.edit_message_text("📦 *Товары:*", parse_mode="Markdown", reply_markup=admin_items_kb(data, cb.replace('admin_cat_items_', '')))
        elif cb.startswith('admin_cat_'):
            cid = cb.replace('admin_cat_', ''); cat = data["categories"].get(cid, {})
            await q.edit_message_text(f"📁 *{cat.get('name','?')}*\n📝 {cat.get('desc','Нет')}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Товары", callback_data=f"admin_cat_items_{cid}")], [InlineKeyboardButton("✏️ Описание", callback_data=f"admin_cat_desc_{cid}")], [InlineKeyboardButton("« Назад", callback_data='admin_cats')]]))
        elif cb.startswith('admin_item_new_'): context.user_data['ai'] = cb.replace('admin_item_new_', ''); await q.edit_message_text("📝 Введите: `Название|Цена|Описание`")
        elif cb.startswith('admin_item_desc_'): parts = cb.split('_'); context.user_data['aid'] = (parts[3], parts[4]); await q.edit_message_text("📝 Введите новое описание:")
        elif cb.startswith('admin_item_price_'): parts = cb.split('_'); context.user_data['aip'] = (parts[3], parts[4]); await q.edit_message_text("💰 Введите новую цену:")
        elif cb.startswith('admin_item_del_'): parts = cb.split('_'); cid, iid = parts[3], parts[4]; data["categories"][cid]["items"] = [i for i in data["categories"][cid]["items"] if i["id"]!=iid]; save_data(data); await q.edit_message_text("✅ Товар удалён!", reply_markup=admin_items_kb(data, cid))
        elif cb.startswith('admin_item_'):
            parts = cb.split('_'); cid, iid = parts[2], parts[3]
            item = next((i for i in data["categories"].get(cid,{}).get("items",[]) if i["id"]==iid), None)
            if item: await q.edit_message_text(f"📦 *{item.get('name','?')}*\n💰 {item.get('price',0)}₽\n📝 {item.get('desc','')}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Описание", callback_data=f"admin_item_desc_{cid}_{iid}")], [InlineKeyboardButton("✏️ Цена", callback_data=f"admin_item_price_{cid}_{iid}")], [InlineKeyboardButton("❌ Удалить", callback_data=f"admin_item_del_{cid}_{iid}")], [InlineKeyboardButton("« Назад", callback_data=f"admin_cat_items_{cid}")]]))
        elif cb == 'admin_welcome': context.user_data['aw'] = True; await q.edit_message_text("📸 Отправьте фото:")
        elif cb == 'admin_broadcast': context.user_data['br'] = True; await q.edit_message_text("📢 Введите текст:")
        elif cb == 'admin_reset_hwid': context.user_data['rh'] = True; await q.edit_message_text("🔧 Введите ID:")
        elif cb == 'admin_group': await q.edit_message_text(f"👥 *Группа*\n🔗 {DOWNLOAD_LINK}\n• Бан при истечении\n• Разбан при покупке", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Проверить", callback_data='admin_check_ban')], [InlineKeyboardButton("« Назад", callback_data='admin_menu')]]))
        elif cb == 'admin_check_ban': await check_and_ban_expired(context); await q.edit_message_text("✅ Проверка завершена!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data='admin_group')]]))
        elif cb.startswith('ok_'):
            rid = cb.replace('ok_', ''); rec = data["pending_receipts"].get(rid)
            if rec: u = get_user(data, rec["user_id"]); u["balance_rub"] += rec["amount"]; del data["pending_receipts"][rid]; save_data(data)
            await q.edit_message_text("✅ Подтверждено!", reply_markup=admin_menu())
        elif cb.startswith('no_'): context.user_data['rj'] = cb.replace('no_', ''); await q.edit_message_text("📝 Причина отказа:")
        return
    if cb == 'main': await q.edit_message_text("🛍 *Меню*", parse_mode="Markdown", reply_markup=main_menu(uid, data))
    elif cb == 'profile':
        bal = user.get("balance_rub",0); ref_bal = user.get("ref_balance",0); active = sum(1 for l in data["licenses"].values() if l.get("user_id")==uid)
        await q.edit_message_text(f"👤 *Профиль*\n\n💰 Баланс: ₽{bal}\n💎 Реф. баланс: ₽{ref_bal}\n🔑 Лицензий: {active}", parse_mode="Markdown", reply_markup=profile_kb())
    elif cb == 'purchases':
        my = {k:l for k,l in data["licenses"].items() if l.get("user_id")==uid}
        if my:
            for key, lic in my.items():
                exp = lic.get("expires")
                if isinstance(exp, str): exp = datetime.datetime.fromisoformat(exp)
                st = "✅ Активна" if isinstance(exp, datetime.datetime) and exp > datetime.datetime.now() else "❌ Истекла"
                rem = (exp - datetime.datetime.now()) if isinstance(exp, datetime.datetime) and exp > datetime.datetime.now() else datetime.timedelta(0)
                rs = f"{rem.days} д. {rem.seconds//3600} ч." if rem.days > 0 else "0 ч."
                hw = "✅ привязано" if lic.get("activated") else "⚠️ не привязано"
                msg = f"📜 *Лицензия {lic.get('product','Hesera External')}*\n\n🔑 *Ключ:* `{key}`\n📊 *Статус:* {st}\n📺 *Устройство:* {hw}\n⏳ *Осталось времени:* {rs}"
                await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 Скачать", url=DOWNLOAD_LINK)], [InlineKeyboardButton("♻️ Сбросить HWID", url=SUPPORT_LINK)], [InlineKeyboardButton("« Назад", callback_data='profile')]]))
        else: await q.edit_message_text("📭 Нет лицензий.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 В каталог", callback_data='shop')], [InlineKeyboardButton("« Назад", callback_data='profile')]]))
    elif cb == 'referral':
        ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"
        await q.edit_message_text(f"👥 *Рефералы*\n\n▸ Приглашено: {len(user.get('refs',[]))}\n💰 Реф. баланс: ₽{user.get('ref_balance',0)}\n🔗 `{ref_link}`", parse_mode="Markdown", reply_markup=referral_kb(uid, ref_link))
    elif cb.startswith('copyref_'): await q.edit_message_text(f"🔗 `https://t.me/{BOT_USERNAME}?start=ref_{uid}`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Поделиться", switch_inline_query=f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"), InlineKeyboardButton("« Назад", callback_data='referral')]]))
    elif cb == 'topup': await q.edit_message_text("💎 *Пополнение*\n\nВыберите способ:", parse_mode="Markdown", reply_markup=topup_menu())
    elif cb == 'shop': await q.edit_message_text("🛒 *Каталог:*", parse_mode="Markdown", reply_markup=shop_cats_kb(data))
    elif cb.startswith('shop_cat_'): await q.edit_message_text("📦 *Товары:*", parse_mode="Markdown", reply_markup=shop_items_kb(data, cb.replace('shop_cat_', '')))
    elif cb.startswith('product_'):
        _, cid, iid = cb.split('_')
        item = next((i for i in data["categories"].get(cid,{}).get("items",[]) if i["id"]==iid), None)
        if item:
            ak, al = has_active_license(data, uid, item["id"])
            if ak:
                exp = al.get("expires")
                if isinstance(exp, str): exp = datetime.datetime.fromisoformat(exp)
                rs = f"{(exp - datetime.datetime.now()).days} д." if isinstance(exp, datetime.datetime) else "?"
                await q.edit_message_text(f"⚠️ *Активная лицензия!*\n\n🔑 `{ak}`\n⏳ Осталось: {rs}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"shop_cat_{cid}")]]))
            else: await q.edit_message_text(f"🛒 *{item['name']}*\n\n{item['desc']}\n\nВыберите:", parse_mode="Markdown", reply_markup=sub_kb(cid, iid, item))
    elif cb.startswith('sub_'):
        _, cid, iid, idx = cb.split('_')
        item = next((i for i in data["categories"].get(cid,{}).get("items",[]) if i["id"]==iid), None)
        if item and not has_active_license(data, uid, item["id"])[0]:
            sub = item["subscriptions"][int(idx)]; bal = user.get("balance_rub",0)+user.get("ref_balance",0)
            can = bal >= sub["price"]; lack = sub["price"]-bal
            kb = [[InlineKeyboardButton(f"💳 Оплатить ₽{sub['price']}" if can else "💎 Пополнить", callback_data=f"pay_{cid}_{iid}_{idx}" if can else 'topup')], [InlineKeyboardButton("❌ Отказ", callback_data=f"product_{cid}_{iid}")]]
            await q.edit_message_text(f"🛒 *{item['name']} · {sub['name']}*\n\n💰 ₽{sub['price']}\n💳 Баланс: ₽{bal}\n\n{'✅ Хватает!' if can else f'❌ Не хватает ₽{lack}'}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif cb.startswith('pay_'):
        _, cid, iid, idx = cb.split('_')
        item = next((i for i in data["categories"].get(cid,{}).get("items",[]) if i["id"]==iid), None)
        if item and not has_active_license(data, uid, item["id"])[0]:
            sub = item["subscriptions"][int(idx)]; bal = user.get("balance_rub",0)+user.get("ref_balance",0)
            if bal >= sub["price"]:
                rem = sub["price"]
                if user.get("balance_rub",0) >= rem: user["balance_rub"] -= rem
                else: rem -= user["balance_rub"]; user["balance_rub"] = 0; user["ref_balance"] -= rem
                key = generate_key()
                while key in data["licenses"]: key = generate_key()
                gl = await unban_from_group(context, uid)
                data["licenses"][key] = {"user_id":uid,"product":f"{item['name']} ({sub['name']})","product_id":item["id"],"expires":datetime.datetime.now()+datetime.timedelta(days=sub["duration_days"]),"hwid":None,"activated":False,"in_group":True}
                user["purchases"].append({"name":f"{item['name']} ({sub['name']})","price":sub["price"]})
                save_data(data)
                extra = f"\n\n🔗 Группа: {gl}" if gl else ""
                await q.edit_message_text(f"✅ *Куплено!*\n\n🔑 `{key}`\n💰 -₽{sub['price']}{extra}\n\n⚠️ Вставьте ключ в скрипт", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Меню", callback_data='main')]]))
            else: await q.edit_message_text("❌ Мало средств.", reply_markup=topup_menu())
    elif cb == 'sbp': context.user_data['sa'] = True; await q.edit_message_text(f"💳 *СБП*\n\n💰 Введите сумму:\n📋 `{SBP_CARD}`", parse_mode="Markdown")
    elif cb.startswith('send_'): context.user_data['ap'] = cb.replace('send_', ''); await q.edit_message_text("📸 Отправьте скриншот чека:")
    elif cb.startswith('cancel_'): rid = cb.replace('cancel_', ''); data["pending_receipts"].pop(rid, None); save_data(data); await q.edit_message_text("❌ Отменено.", reply_markup=main_menu(uid, data))
    elif cb == 'crypto': context.user_data['cm'] = True; await q.edit_message_text("🪙 *Крипто*\n\n💰 Введите сумму в USDT:", parse_mode="Markdown")
    elif cb.startswith('check_'):
        inv = check_crypto_invoice(cb.replace('check_', ''))
        if inv and inv.get("status") == "paid": rub = int(float(inv["amount"]) * USD_RATE); user["balance_rub"] += rub; save_data(data); await q.edit_message_text(f"✅ Оплачено!\n💰 +₽{rub}", reply_markup=main_menu(uid, data))
        else: await q.answer("⏳ Не оплачен")

async def handle_text(update, context):
    uid = str(update.effective_user.id); data = load_data(); txt = update.message.text.strip()
    user = get_user(data, uid)
    if context.user_data.get('sa'):
        context.user_data.pop('sa')
        try:
            amt = int(txt); rid = f"sbp_{int(time.time())}"
            data["pending_receipts"][rid] = {"user_id":uid,"amount":amt,"first_name":user.get("first_name",""),"username":user.get("username",""),"time":datetime.datetime.now().isoformat()}
            save_data(data)
            await update.message.reply_text(f"💳 *СБП*\n\n💰 {amt}₽\n📋 `{SBP_CARD}`\n\n📸 Отправьте скриншот чека:", parse_mode="Markdown", reply_markup=sbp_kb(rid))
        except: pass
        return
    if context.user_data.get('cm'):
        context.user_data.pop('cm')
        try:
            amt = float(txt); inv = create_crypto_invoice(amt)
            if inv: await update.message.reply_text(f"🪙 *Крипто*\n\n💰 ${amt}\n💡 1 USDT ≈ {USD_RATE}₽", parse_mode="Markdown", reply_markup=crypto_kb(str(inv["invoice_id"]), inv["pay_url"]))
        except: pass
        return
    if not is_admin(uid): return
    if context.user_data.get('um'):
        context.user_data.pop('um'); t = txt.strip()
        if t in data["users"]: u = data["users"][t]; await update.message.reply_text(f"👤 *{u.get('first_name','?')}*\n🆔 `{t}`\n💰 ₽{u.get('balance_rub',0)}", parse_mode="Markdown", reply_markup=user_manage_kb(t, data))
        else: await update.message.reply_text("❌ Не найден!")
        return
    if context.user_data.get('um_bal'):
        t = context.user_data.pop('um_bal')
        try: data["users"][t]["balance_rub"] = int(txt); save_data(data); await update.message.reply_text("✅ Баланс изменён!", reply_markup=admin_menu())
        except: await update.message.reply_text("❌ Число!")
        return
    if context.user_data.get('create_key'):
        context.user_data.pop('create_key'); parts = txt.split('|')
        if len(parts)==3:
            try:
                days = int(parts[2].strip()); key = generate_key()
                while key in data["licenses"]: key = generate_key()
                data["licenses"][key] = {"user_id":parts[0].strip(),"product":parts[1].strip(),"product_id":"custom","expires":datetime.datetime.now()+datetime.timedelta(days=days),"hwid":None,"activated":False}
                save_data(data)
                try: await context.bot.send_message(int(parts[0]), f"🔑 *Ключ!*\n\n🔑 `{key}`\n📦 {parts[1]}\n📅 {days} д.", parse_mode="Markdown")
                except: pass
                await update.message.reply_text(f"✅ Ключ создан!\n🔑 `{key}`\n👤 {parts[0]}", reply_markup=admin_menu())
            except: await update.message.reply_text("❌ Ошибка!")
        else: await update.message.reply_text("❌ Формат: `ID|Продукт|Дни`")
        return
    if context.user_data.get('acn'): context.user_data.pop('acn'); cid = f"cat_{int(time.time())}"; data["categories"][cid] = {"id":cid,"name":txt,"desc":"","items":[]}; save_data(data); await update.message.reply_text(f"✅ «{txt}» создана!", reply_markup=admin_cats_kb(data)); return
    if context.user_data.get('acd'): cid = context.user_data.pop('acd'); data["categories"][cid]["desc"] = txt; save_data(data); await update.message.reply_text("✅ Описание обновлено!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"admin_cat_{cid}")]])); return
    if context.user_data.get('ai'):
        cid = context.user_data.pop('ai'); parts = txt.split('|')
        if len(parts) >= 3:
            try:
                price = int(parts[1].strip()); iid = f"item_{int(time.time())}"
                data["categories"][cid]["items"].append({"id":iid,"name":parts[0].strip(),"price":price,"desc":parts[2].strip(),"subscriptions":[{"name":"30 дней","price":price,"duration_days":30}]})
                save_data(data); await update.message.reply_text(f"✅ Товар «{parts[0]}» добавлен!", reply_markup=admin_items_kb(data, cid))
            except: await update.message.reply_text("❌ Ошибка в цене!")
        return
    if context.user_data.get('aid'):
        cid, iid = context.user_data.pop('aid')
        for item in data["categories"][cid]["items"]:
            if item["id"] == iid: item["desc"] = txt; break
        save_data(data); await update.message.reply_text("✅ Описание обновлено!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"admin_item_{cid}_{iid}")]])); return
    if context.user_data.get('aip'):
        cid, iid = context.user_data.pop('aip')
        try:
            price = int(txt)
            for item in data["categories"][cid]["items"]:
                if item["id"] == iid: item["price"] = price; item["subscriptions"][0]["price"] = price; break
            save_data(data); await update.message.reply_text("✅ Цена обновлена!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Назад", callback_data=f"admin_item_{cid}_{iid}")]]))
        except: await update.message.reply_text("❌ Число!")
        return
    if context.user_data.get('br'): context.user_data.pop('br'); c = 0
    for u in data["users"]:
        try: await context.bot.send_message(int(u), f"📢 {txt}"); c+=1
        except: pass
    await update.message.reply_text(f"✅ {c} чел.", reply_markup=admin_menu())
    elif context.user_data.get('rh'): context.user_data.pop('rh'); c = 0
    for k,l in data["licenses"].items():
        if l.get("user_id")==txt and l.get("activated"): l["hwid"]=None; l["activated"]=False; c+=1
    save_data(data); await update.message.reply_text(f"✅ Сброшено: {c}", reply_markup=admin_menu())
    elif context.user_data.get('rj'): rid = context.user_data.pop('rj'); rec = data["pending_receipts"].get(rid)
    if rec: del data["pending_receipts"][rid]; save_data(data)
    try: await context.bot.send_message(int(rec["user_id"]), f"❌ Отказано.\n📝 {txt}")
    except: pass
    await update.message.reply_text("❌ Отклонено.", reply_markup=admin_menu())

async def handle_photo(update, context):
    uid = str(update.effective_user.id); data = load_data(); photo = update.message.photo[-1].file_id
    if is_admin(uid) and context.user_data.get('aw'): context.user_data.pop('aw'); data["welcome_photo"]=photo; save_data(data); await update.message.reply_text("✅ Фото установлено!", reply_markup=admin_menu()); return
    if context.user_data.get('ap'):
        rid = context.user_data.pop('ap'); rec = data["pending_receipts"].get(rid)
        if rec:
            rec["photo"]=photo; save_data(data)
            await update.message.reply_text("✅ Чек отправлен!", reply_markup=main_menu(uid, data))
            try: await context.bot.send_photo(ADMIN_ID, photo, caption=f"📎 *Чек #{rid}*\n\n🆔 `{rec['user_id']}`\n👤 {rec.get('first_name','?')}\n💰 {rec.get('amount','?')}₽\n📅 {rec.get('time','?')}", parse_mode="Markdown", reply_markup=admin_sbp_kb(rid))
            except: pass

def main():
    threading.Thread(target=run_api, daemon=True).start()
    app = ApplicationBuilder().token(TOKEN).connect_timeout(60).read_timeout(60).write_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.job_queue.run_repeating(check_and_ban_expired, interval=3600, first=10)
    app.job_queue.run_repeating(check_and_notify_expiring, interval=21600, first=30)
    print("✅ Hesera Bot + API запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
