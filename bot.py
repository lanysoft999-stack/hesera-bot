import os, pickle, datetime, time, random, string, json, threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from flask import Flask

# Flask для Render (обязательно)
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "✅ Hesera Bot API is running!"

TOKEN = "8820585661:AAHfUzU_y3-p-eezmcd1d_0nCQndtZjWBtw"
ADMIN_ID = 314148464
DATA_FILE = '/tmp/shop_data.pkl'
SUPPORT_LINK = "https://t.me/hesers"
BOT_USERNAME = "ClumsyHeseraBot"
SBP_CARD = "220220671487913"
API_PORT = 10000

def generate_key():
    return "Hesera_" + ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(8))

INITIAL_DATA = {
    "users": {}, "pending_receipts": {}, "licenses": {},
    "categories": {"roblox": {"id": "roblox", "name": "🎮 Roblox", "items": [{
        "id": "mm2", "name": "🔪 MM2",
        "desc": "🟢 Приватный скрипт MM2\n🟢 Авто-фарм, Аим, ESP\n🟢 ПК и Android",
        "subscriptions": [
            {"name": "📅 7 дней", "price": 99, "duration_days": 7},
            {"name": "📅 12 дней", "price": 189, "duration_days": 12},
            {"name": "📅 30 дней", "price": 299, "duration_days": 30}
        ]
    }]}},
    "welcome_photo": None, "banned_users": []
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
                        if lic.get("hwid") == hwid:
                            self.send_response(200)
                            response = {"status": "valid", "expires": exp.isoformat()}
                        else:
                            self.send_response(403)
                            response = {"status": "hwid_mismatch"}
                    else:
                        if hwid:
                            lic["hwid"] = hwid; lic["activated"] = True; save_data(data)
                            self.send_response(200)
                            response = {"status": "activated", "expires": exp.isoformat()}
                        else:
                            self.send_response(200)
                            response = {"status": "need_hwid", "expires": exp.isoformat()}
                else:
                    self.send_response(403)
                    response = {"status": "expired"}
            else:
                self.send_response(404)
                response = {"status": "invalid"}
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass

def run_api():
    server = HTTPServer(('0.0.0.0', API_PORT), LicenseAPI)
    print(f"🔑 API на порту {API_PORT}")
    server.serve_forever()

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
        data["users"][uid] = {"balance_rub": 0, "ref_balance": 0, "purchases": [], "joined": datetime.datetime.now().isoformat()}
    return data["users"][uid]

def main_menu(uid, data):
    u = get_user(data, uid)
    return InlineKeyboardMarkup([[InlineKeyboardButton("🛍 Каталог", callback_data='shop'), InlineKeyboardButton(f"👤 Профиль · ₽{u.get('balance_rub',0)}", callback_data='profile')]])

def profile_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("💸 Пополнить", callback_data='topup')], [InlineKeyboardButton("🗃 Покупки", callback_data='purchases')], [InlineKeyboardButton("‹ Назад", callback_data='main')]])

def admin_menu(): return InlineKeyboardMarkup([[InlineKeyboardButton("👥 Пользователи", callback_data='admin_users')], [InlineKeyboardButton("🖼 Приветствие", callback_data='admin_welcome')], [InlineKeyboardButton("📢 Рассылка", callback_data='admin_broadcast')], [InlineKeyboardButton("🔧 Сброс HWID", callback_data='admin_reset_hwid')], [InlineKeyboardButton("‹ Назад", callback_data='main')]])

def shop_cats_kb(data):
    kb = [[InlineKeyboardButton(c["name"], callback_data=f"shop_cat_{cid}")] for cid, c in data["categories"].items()]
    kb.append([InlineKeyboardButton("‹ Назад", callback_data='main')]); return InlineKeyboardMarkup(kb)

def shop_items_kb(data, cid):
    kb = [[InlineKeyboardButton(i["name"], callback_data=f"product_{cid}_{i['id']}")] for i in data["categories"].get(cid,{}).get("items",[])]
    kb.append([InlineKeyboardButton("‹ Назад", callback_data='shop')]); return InlineKeyboardMarkup(kb)

def sub_kb(cid, iid, item):
    kb = [[InlineKeyboardButton(f"{s['name']} · {s['price']}₽", callback_data=f"sub_{cid}_{iid}_{i}")] for i, s in enumerate(item.get("subscriptions",[]))]
    kb.append([InlineKeyboardButton("‹ Назад", callback_data=f"shop_cat_{cid}")]); return InlineKeyboardMarkup(kb)

def topup_menu(): return InlineKeyboardMarkup([[InlineKeyboardButton("💳 СБП", callback_data='sbp')], [InlineKeyboardButton("‹ Назад", callback_data='profile')]])

def sbp_kb(rid): return InlineKeyboardMarkup([[InlineKeyboardButton("📸 Чек", callback_data=f"send_{rid}")], [InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{rid}")]])

def admin_sbp_kb(rid): return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Подтвердить", callback_data=f"ok_{rid}")], [InlineKeyboardButton("❌ Отказать", callback_data=f"no_{rid}")]])

async def start(update, context):
    uid = str(update.effective_user.id); data = load_data()
    user = get_user(data, uid)
    user["first_name"] = update.effective_user.first_name or ""; user["username"] = update.effective_user.username or ""
    save_data(data)
    if is_admin(uid): return await update.message.reply_text("🛠 Админ-панель", reply_markup=admin_menu())
    await update.message.reply_text("🛍 *Hesera Shop*\n\nДобро пожаловать!", parse_mode="Markdown", reply_markup=main_menu(uid, data))

async def button(update, context):
    q = update.callback_query; await q.answer(); uid = str(q.from_user.id); data = load_data(); cb = q.data
    user = get_user(data, uid)
    if is_admin(uid):
        if cb == 'admin_menu': await q.edit_message_text("🛠 Админ", reply_markup=admin_menu())
        elif cb == 'admin_users':
            users = data.get("users", {}); msg = f"👥 Всего: {len(users)}\n🔑 Лицензий: {len(data.get('licenses',{}))}"
            for u, d in sorted(users.items(), key=lambda x: str(x[1].get("joined","")), reverse=True)[:10]:
                msg += f"\n▸ `{u}` — {d.get('first_name','?')}"
            await q.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ Назад", callback_data='admin_menu')]]))
        elif cb == 'admin_welcome': context.user_data['aw'] = True; await q.edit_message_text("📸 Отправьте фото:")
        elif cb == 'admin_broadcast': context.user_data['br'] = True; await q.edit_message_text("📢 Текст:")
        elif cb == 'admin_reset_hwid': context.user_data['rh'] = True; await q.edit_message_text("🔧 ID:")
        elif cb.startswith('ok_'):
            rid = cb.replace('ok_', ''); rec = data["pending_receipts"].get(rid)
            if rec: u = get_user(data, rec["user_id"]); u["balance_rub"] += rec["amount"]; del data["pending_receipts"][rid]; save_data(data)
            await q.edit_message_text("✅", reply_markup=admin_menu())
        elif cb.startswith('no_'): context.user_data['rj'] = cb.replace('no_', ''); await q.edit_message_text("📝 Причина:")
        return
    if cb == 'main': await q.edit_message_text("🛍 Меню", reply_markup=main_menu(uid, data))
    elif cb == 'profile': await q.edit_message_text(f"👤 *Профиль*\n💰 Баланс: ₽{user.get('balance_rub',0)}", parse_mode="Markdown", reply_markup=profile_kb())
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
                await q.edit_message_text(f"📜 *Лицензия {lic.get('product','Hesera')}*\n\n🔑 `{key}`\n📊 {st}\n📺 {hw}\n⏳ {rs}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("♻️ Сбросить HWID", url=SUPPORT_LINK)], [InlineKeyboardButton("‹ Назад", callback_data='profile')]]))
        else: await q.edit_message_text("📭 Нет лицензий.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 В каталог", callback_data='shop')], [InlineKeyboardButton("‹ Назад", callback_data='profile')]]))
    elif cb == 'topup': await q.edit_message_text("💳 Способ:", reply_markup=topup_menu())
    elif cb == 'shop': await q.edit_message_text("🛍 Каталог:", reply_markup=shop_cats_kb(data))
    elif cb.startswith('shop_cat_'): await q.edit_message_text("📦 Товары:", reply_markup=shop_items_kb(data, cb.replace('shop_cat_', '')))
    elif cb.startswith('product_'):
        _, cid, iid = cb.split('_')
        item = next((i for i in data["categories"].get(cid,{}).get("items",[]) if i["id"]==iid), None)
        if item: await q.edit_message_text(f"🛒 *{item['name']}*\n\n{item['desc']}\n\nВыберите:", parse_mode="Markdown", reply_markup=sub_kb(cid, iid, item))
    elif cb.startswith('sub_'):
        _, cid, iid, idx = cb.split('_')
        item = next((i for i in data["categories"].get(cid,{}).get("items",[]) if i["id"]==iid), None)
        if item:
            sub = item["subscriptions"][int(idx)]; bal = user.get("balance_rub",0)
            can = bal >= sub["price"]; lack = sub["price"]-bal
            kb = [[InlineKeyboardButton(f"💳 Оплатить ₽{sub['price']}" if can else "💳 Пополнить", callback_data=f"pay_{cid}_{iid}_{idx}" if can else 'topup')], [InlineKeyboardButton("❌ Отказ", callback_data=f"product_{cid}_{iid}")]]
            await q.edit_message_text(f"🛒 *{item['name']} · {sub['name']}*\n\n💰 ₽{sub['price']}\n💳 Баланс: ₽{bal}\n\n{'✅ Хватает!' if can else f'❌ Не хватает ₽{lack}'}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
    elif cb.startswith('pay_'):
        _, cid, iid, idx = cb.split('_')
        item = next((i for i in data["categories"].get(cid,{}).get("items",[]) if i["id"]==iid), None)
        if item and user.get("balance_rub",0) >= item["subscriptions"][int(idx)]["price"]:
            sub = item["subscriptions"][int(idx)]
            user["balance_rub"] -= sub["price"]
            key = generate_key()
            while key in data["licenses"]: key = generate_key()
            data["licenses"][key] = {"user_id":uid,"product":f"{item['name']} ({sub['name']})","product_id":item["id"],"expires":datetime.datetime.now()+datetime.timedelta(days=sub["duration_days"]),"hwid":None,"activated":False}
            user["purchases"].append({"name":f"{item['name']} ({sub['name']})","price":sub["price"]})
            save_data(data)
            await q.edit_message_text(f"✅ *Куплено!*\n\n🔑 `{key}`\n💰 -₽{sub['price']}\n\n⚠️ Вставьте ключ в скрипт", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ Меню", callback_data='main')]]))
        else: await q.edit_message_text("❌ Мало средств.", reply_markup=topup_menu())
    elif cb == 'sbp': context.user_data['sa'] = True; await q.edit_message_text(f"💰 Сумма:\n📋 `{SBP_CARD}`", parse_mode="Markdown")
    elif cb.startswith('send_'): context.user_data['ap'] = cb.replace('send_', ''); await q.edit_message_text("📸 Чек:")
    elif cb.startswith('cancel_'): rid = cb.replace('cancel_', ''); data["pending_receipts"].pop(rid, None); save_data(data); await q.edit_message_text("❌ Отмена.", reply_markup=main_menu(uid, data))

async def handle_text(update, context):
    uid = str(update.effective_user.id); data = load_data(); txt = update.message.text.strip()
    user = get_user(data, uid)
    if context.user_data.get('sa'):
        context.user_data.pop('sa')
        try:
            amt = int(txt); rid = f"sbp_{int(time.time())}"
            data["pending_receipts"][rid] = {"user_id":uid,"amount":amt,"first_name":user.get("first_name",""),"username":user.get("username",""),"time":datetime.datetime.now().isoformat()}
            save_data(data)
            try: await context.bot.send_message(ADMIN_ID, f"📎 СБП!\n🆔 `{uid}`\n💰 {amt}₽", parse_mode="Markdown")
            except: pass
            await update.message.reply_text(f"💳 *СБП*\n💰 {amt}₽\n📋 `{SBP_CARD}`\n📸 Чек:", parse_mode="Markdown", reply_markup=sbp_kb(rid))
        except: pass
        return
    if not is_admin(uid): return
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
    if is_admin(uid) and context.user_data.get('aw'): context.user_data.pop('aw'); data["welcome_photo"]=photo; save_data(data); await update.message.reply_text("✅", reply_markup=admin_menu()); return
    if context.user_data.get('ap'): rid = context.user_data.pop('ap'); rec = data["pending_receipts"].get(rid)
        if rec: rec["photo"]=photo; save_data(data); await update.message.reply_text("✅ Чек отправлен!", reply_markup=main_menu(uid, data))
            try: await context.bot.send_photo(ADMIN_ID, photo, caption=f"📎 #{rid}\n🆔 `{rec['user_id']}`\n💰 {rec.get('amount','?')}₽", parse_mode="Markdown", reply_markup=admin_sbp_kb(rid))
            except: pass

def run_bot():
    app = ApplicationBuilder().token(TOKEN).connect_timeout(60).read_timeout(60).write_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_api, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    flask_app.run(host='0.0.0.0', port=10000)
