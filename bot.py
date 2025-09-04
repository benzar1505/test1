import os
import json
import time
from typing import Dict, Any
from dotenv import load_dotenv
import telebot
from telebot import types

# === ENV ===
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # необязательно: для пересылки обращений в поддержку

if not BOT_TOKEN:
    raise RuntimeError("Укажите BOT_TOKEN в переменных окружения (например, в .env или Secrets Replit).")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

DATA_FILE = "data.json"
MIN_BID_USD = 50  # минимальная ставка $50

# === STORAGE ===
def load_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        data = {
            "lots": {
                "1": {
                    "id": "1",
                    "title": "BMW M3 (E92), 2012",
                    "photo_url": "https://picsum.photos/seed/bmw_m3/1024/768",
                    "current_bid": 0,
                    "current_bidder_id": None,
                    "created_at": int(time.time())
                },
                "2": {
                    "id": "2",
                    "title": "Audi A6 (C7), 2014",
                    "photo_url": "https://picsum.photos/seed/audi_a6/1024/768",
                    "current_bid": 0,
                    "current_bidder_id": None,
                    "created_at": int(time.time())
                }
            },
            "pending_bids": {},  # user_id -> lot_id
            "registered_users": {}  # user_id -> phone_number
        }
        save_data(data)
        return data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

DATA = load_data()

# === KEYBOARDS ===
def main_menu_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(types.KeyboardButton("📋 Список лотов"))
    kb.row(types.KeyboardButton("ℹ️ Информация / Правила"), types.KeyboardButton("🆘 Поддержка"))
    return kb

def lot_inline_kb(lot_id: str):
    ikb = types.InlineKeyboardMarkup()
    ikb.add(types.InlineKeyboardButton("💸 Сделать ставку", callback_data=f"bid:{lot_id}"))
    return ikb

# === HELPERS ===
def mask_user(user: telebot.types.User) -> str:
    name = user.first_name or "Участник"
    return f"{name} ({user.id})"

def lot_text(lot: Dict[str, Any]) -> str:
    cur = lot.get("current_bid", 0)
    status = f"Текущая ставка: <b>${cur}</b>" if cur and cur >= MIN_BID_USD else "Ставок ещё нет"
    return (
        f"<b>{lot['title']}</b>\n"
        f"{status}\n"
        f"Минимальная ставка: <b>${MIN_BID_USD}</b>"
    )

def ensure_data():
    global DATA
    DATA = load_data()

# === START + REGISTRATION ===
@bot.message_handler(commands=["start", "menu"])
def start(message: types.Message):
    text = (
        "📢 <b>Вітаємо у ХЛР-АУКЦІОНІ!</b> 🎊\n\n"
        "Аукціон ХЛР — це не просто торги, а шанс придбати унікальні товари та послуги 🔥\n\n"
        "🔹 <b>Як все працює?</b>\n"
        "🪄 Сьогодні представлено <b>5 лотів</b>;\n"
        "🪄 Початкова ціна кожного лота — <b>0$</b>;\n"
        f"🪄 Ваша ставка — мінімум <b>${MIN_BID_USD}</b>;\n"
        "🪄 Якщо хтось переб’є Вашу ставку — бот надішле сповіщення;\n"
        "🪄 Аукціон завершується через <b>10 хвилин після останньої ставки</b>;\n\n"
        "🏆 Перемагає той, хто зробив найбільшу ставку!\n\n"
        "👉 Для участі необхідно пройти <b>реєстрацію</b>:\n"
        "📱 Надішліть свій номер телефону за допомогою кнопки нижче."
    )

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    phone_btn = types.KeyboardButton("📲 Надіслати номер телефону", request_contact=True)
    markup.add(phone_btn)

    bot.send_message(message.chat.id, text, reply_markup=markup)

# === HANDLE CONTACT ===
@bot.message_handler(content_types=['contact'])
def handle_contact(message: types.Message):
    if message.contact is not None:
        phone_number = message.contact.phone_number
        user_id = str(message.from_user.id)
        DATA["registered_users"][user_id] = phone_number
        save_data(DATA)

        bot.send_message(
            message.chat.id,
            f"✅ Дякуємо за реєстрацію!\nВаш номер: {phone_number}\n\n"
            "Тепер ви можете переглянути список лотів та робити ставки, натиснувши 📋 Список лотів.",
            reply_markup=main_menu_kb()
        )

# === SHOW LOTS ===
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ["📋 список лотов", "список лотов", "лоты"])
def show_lots(message: types.Message):
    ensure_data()
    user_id = str(message.from_user.id)
    if user_id not in DATA.get("registered_users", {}):
        bot.send_message(message.chat.id, "❌ Спочатку зареєструйтесь, надіславши свій номер телефону.", reply_markup=main_menu_kb())
        return

    lots = DATA.get("lots", {})
    if not lots:
        bot.send_message(message.chat.id, "Пока лотов нет.", reply_markup=main_menu_kb())
        return

    bot.send_message(message.chat.id, "Доступные лоты:", reply_markup=main_menu_kb())
    for lot_id, lot in lots.items():
        caption = lot_text(lot)
        try:
            bot.send_photo(message.chat.id, photo=lot["photo_url"], caption=caption, reply_markup=lot_inline_kb(lot_id))
        except Exception:
            bot.send_message(message.chat.id, caption, reply_markup=lot_inline_kb(lot_id))

# === INFO / RULES ===
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower().startswith("ℹ️ информация"))
def info(message: types.Message):
    rules = (
        "<b>Правила аукціону</b>\n\n"
        f"• Мінімальна ставка: <b>${MIN_BID_USD}</b>.\n"
        "• Наступна ставка повинна бути більшою за поточну мінімум на $1.\n"
        "• Ставки остаточні та відміні не підлягають.\n"
        "• Організатор може зняти лот до закінчення торгів.\n"
        "• Будь-які спірні ситуації вирішуються адміністрацією."
    )
    bot.send_message(message.chat.id, rules, reply_markup=main_menu_kb())

# === SUPPORT ===
@bot.message_handler(func=lambda m: m.text and m.text.strip().lower().startswith("🆘 поддержка"))
def support(message: types.Message):
    text = (
        "Якщо зіткнулися з проблемою, опишіть її одним повідомленням — ми допоможемо.\n\n"
        "Повідомлення буде надіслане адміністратору."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu_kb())
    bot.register_next_step_handler(message, collect_support)

def collect_support(message: types.Message):
    report = message.text or "<без текста>"
    bot.reply_to(message, "Дякуємо! Ваше повідомлення надіслано в підтримку.")
    if ADMIN_CHAT_ID:
        try:
            bot.send_message(int(ADMIN_CHAT_ID),
                             f"🆘 <b>Звернення в підтримку</b>\nВід: {mask_user(message.from_user)}\n\n{report}")
        except Exception:
            pass

# === CALLBACKS: VIEW LOT ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("view:"))
def on_view_lot(call: types.CallbackQuery):
    lot_id = call.data.split(":", 1)[1]
    ensure_data()
    lot = DATA["lots"].get(lot_id)
    if not lot:
        bot.answer_callback_query(call.id, "Лот не найден.")
        return
    caption = lot_text(lot)
    try:
        bot.send_photo(call.message.chat.id, photo=lot["photo_url"], caption=caption, reply_markup=lot_inline_kb(lot_id))
    except Exception:
        bot.send_message(call.message.chat.id, caption, reply_markup=lot_inline_kb(lot_id))
    bot.answer_callback_query(call.id)

# === CALLBACKS: BID ===
@bot.callback_query_handler(func=lambda c: c.data.startswith("bid:"))
def on_bid(call: types.CallbackQuery):
    user_id = str(call.from_user.id)
    ensure_data()
    if user_id not in DATA.get("registered_users", {}):
        bot.answer_callback_query(call.id, "❌ Спочатку зареєструйтесь, надіславши номер телефону.")
        return

    lot_id = call.data.split(":", 1)[1]
    lot = DATA["lots"].get(lot_id)
    if not lot:
        bot.answer_callback_query(call.id, "Лот не найден.")
        return

    bot.answer_callback_query(call.id)
    min_required = MIN_BID_USD if lot.get('current_bid', 0) < MIN_BID_USD else lot.get('current_bid', 0) + 1
    msg = bot.send_message(
        call.message.chat.id,
        f"Введіть суму ставки в $ для лота:\n<b>{lot['title']}</b>\n(мінімум ${min_required:.2f})"
    )
    DATA["pending_bids"][user_id] = lot_id
    save_data(DATA)
    bot.register_next_step_handler(msg, handle_bid_amount)

def handle_bid_amount(message: types.Message):
    user_id = str(message.from_user.id)
    ensure_data()
    lot_id = DATA["pending_bids"].get(user_id)
    if not lot_id:
        bot.reply_to(message, "Похоже, запит ставки устарел. Натисніть «Сделать ставку» ще раз.")
        return
    lot = DATA["lots"].get(lot_id)
    if not lot:
        bot.reply_to(message, "Лот не найден.")
        DATA["pending_bids"].pop(user_id, None)
        save_data(DATA)
        return

    text = (message.text or "").strip().replace(",", ".").replace("$", "")
    try:
        amount = float(text)
    except ValueError:
        bot.reply_to(message, "Введіть число, наприклад 150 або 150.5")
        bot.register_next_step_handler(message, handle_bid_amount)
        return

    cur = float(lot.get("current_bid", 0) or 0)
    min_required = MIN_BID_USD if cur < MIN_BID_USD else cur + 1
    if amount < min_required:
        bot.reply_to(message, f"Ставка занадто мала. Мінімум <b>${min_required:.2f}</b>.")
        bot.register_next_step_handler(message, handle_bid_amount)
        return

    lot["current_bid"] = round(amount, 2)
    lot["current_bidder_id"] = message.from_user.id
    DATA["lots"][lot_id] = lot
    DATA["pending_bids"].pop(user_id, None)
    save_data(DATA)

    bot.reply_to(message,
        f"✅ Ставка прийнята: <b>${lot['current_bid']:.2f}</b> на лот <b>{lot['title']}</b>.\n"
        f"Учасник: {mask_user(message.from_user)}"
    )

    if ADMIN_CHAT_ID:
        try:
            bot.send_message(int(ADMIN_CHAT_ID),
                             f"🧾 Нова ставка\nЛот: {lot['title']}\nСума: ${lot['current_bid']:.2f}\nВід: {mask_user(message.from_user)}")
        except Exception:
            pass

# === FALLBACK TEXT ===
@bot.message_handler(content_types=["text"])
def route_text(message: types.Message):
    txt = (message.text or "").strip().lower()
    if txt in ("/help", "help", "правила", "инфо", "информация", "ℹ️ информация / правила"):
        return info(message)
    if txt in ("поддержка", "🆘 поддержка"):
        return support(message)
    if txt in ("меню", "/start", "/menu"):
        return start(message)
    if txt in ("лоты", "список лотов", "📋 список лотов"):
        return show_lots(message)

    bot.send_message(message.chat.id,
                     "Не понял команду. Нажмите /menu або використайте кнопки нижче.",
                     reply_markup=main_menu_kb())

# === RUN BOT ===
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
