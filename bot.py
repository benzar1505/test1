import os
import json
import time
from typing import Dict, Any
from dotenv import load_dotenv
import telebot
from telebot import types

# === ENV ===
load_dotenv()  # поддержка локального запуска из .env
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
                # Примеры лотов "из коробки"
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
            "pending_bids": {}  # user_id -> lot_id (ожидание ввода суммы)
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

def lot_open_inline_kb(lot_id: str):
    ikb = types.InlineKeyboardMarkup()
    ikb.add(types.InlineKeyboardButton("🔎 Открыть лот", callback_data=f"view:{lot_id}"))
    return ikb

# === HELPERS ===
def mask_user(user: telebot.types.User) -> str:
    # Маскировка юзера для публичных сообщений
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
    # На всякий случай перечитать файл, если проект запускается в среде с внешними изменениями
    global DATA
    DATA = load_data()

# === COMMANDS ===
@bot.message_handler(commands=["start", "menu"])
def start(message: types.Message):
    text = (
        "Привет! Это бот аукциона авто 🚗\n\n"
        "Выберите действие:\n"
        "• 📋 Список лотов — посмотреть доступные авто\n"
        "• ℹ️ Информация / Правила — как участвовать\n"
        "• 🆘 Поддержка — сообщить об ошибке"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu_kb())

@bot.message_handler(func=lambda m: m.text and m.text.strip().lower() in ["📋 список лотов", "список лотов", "лоты"])
def show_lots(message: types.Message):
    ensure_data()
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
            # На всякий случай, если картинка не отдалась
            bot.send_message(message.chat.id, caption, reply_markup=lot_inline_kb(lot_id))

@bot.message_handler(func=lambda m: m.text and m.text.strip().lower().startswith("ℹ️ информация"))
def info(message: types.Message):
    rules = (
        "<b>Правила аукциона</b>\n\n"
        f"• Минимальная ставка: <b>${MIN_BID_USD}</b>.\n"
        "• Следующая ставка должна быть больше текущей минимум на $1.\n"
        "• Ставки окончательные и отмене не подлежат.\n"
        "• Организатор может снять лот до окончания торгов.\n"
        "• Любые спорные ситуации решаются администрацией."
    )
    bot.send_message(message.chat.id, rules, reply_markup=main_menu_kb())

@bot.message_handler(func=lambda m: m.text and m.text.strip().lower().startswith("🆘 поддержка"))
def support(message: types.Message):
    text = (
        "Если вы столкнулись с ошибкой, опишите проблему одним сообщением — мы поможем.\n\n"
        "Сообщение будет отправлено администратору."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu_kb())
    bot.register_next_step_handler(message, collect_support)

def collect_support(message: types.Message):
    report = message.text or "<без текста>"
    bot.reply_to(message, "Спасибо! Ваше сообщение отправлено в поддержку.")
    if ADMIN_CHAT_ID:
        try:
            bot.send_message(int(ADMIN_CHAT_ID),
                             f"🆘 <b>Обращение в поддержку</b>\nОт: {mask_user(message.from_user)}\n\n{report}")
        except Exception:
            pass

# === CALLBACKS ===
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

@bot.callback_query_handler(func=lambda c: c.data.startswith("bid:"))
def on_bid(call: types.CallbackQuery):
    lot_id = call.data.split(":", 1)[1]
    ensure_data()
    lot = DATA["lots"].get(lot_id)
    if not lot:
        bot.answer_callback_query(call.id, "Лот не найден.")
        return

    bot.answer_callback_query(call.id)
    msg = bot.send_message(
        call.message.chat.id,
        f"Введите сумму ставки в $ для лота:\n<b>{lot['title']}</b>\n"
        f"(минимум ${MAX(MIN_BID_USD, lot.get('current_bid', 0)+1) if lot.get('current_bid', 0) else MIN_BID_USD})"
    )
    # Запоминаем, что ждём ввод суммы для этого лота
    ensure_data()
    DATA["pending_bids"][str(call.from_user.id)] = lot_id
    save_data(DATA)
    bot.register_next_step_handler(msg, handle_bid_amount)

def handle_bid_amount(message: types.Message):
    user_id = str(message.from_user.id)
    ensure_data()
    lot_id = DATA["pending_bids"].get(user_id)
    if not lot_id:
        bot.reply_to(message, "Похоже, запрос ставки устарел. Нажмите «Сделать ставку» ещё раз.")
        return
    lot = DATA["lots"].get(lot_id)
    if not lot:
        bot.reply_to(message, "Лот не найден.")
        DATA["pending_bids"].pop(user_id, None)
        save_data(DATA)
        return

    # Парсим число
    text = (message.text or "").strip().replace(",", ".").replace("$", "")
    try:
        amount = float(text)
    except ValueError:
        bot.reply_to(message, "Введите число, например 150 или 150.5")
        bot.register_next_step_handler(message, handle_bid_amount)
        return

    # Валидация ставки
    cur = float(lot.get("current_bid", 0) or 0)
    min_required = MIN_BID_USD if cur < MIN_BID_USD else (cur + 1)
    if amount < min_required:
        bot.reply_to(
            message,
            f"Ставка слишком маленькая. Требуется минимум <b>${min_required:.2f}</b>."
        )
        bot.register_next_step_handler(message, handle_bid_amount)
        return

    # Принятие ставки
    lot["current_bid"] = round(amount, 2)
    lot["current_bidder_id"] = message.from_user.id
    DATA["lots"][lot_id] = lot
    # очищаем ожидание
    DATA["pending_bids"].pop(user_id, None)
    save_data(DATA)

    bot.reply_to(
        message,
        f"✅ Ставка принята: <b>${lot['current_bid']:.2f}</b> на лот <b>{lot['title']}</b>.\n"
        f"Участник: {mask_user(message.from_user)}"
    )

    # уведомление админу
    if ADMIN_CHAT_ID:
        try:
            bot.send_message(
                int(ADMIN_CHAT_ID),
                f"🧾 Новая ставка\nЛот: {lot['title']}\nСумма: ${lot['current_bid']:.2f}\nОт: {mask_user(message.from_user)}"
            )
        except Exception:
            pass

# === FALLBACKS ===
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

    bot.send_message(
        message.chat.id,
        "Не понял команду. Нажмите /menu или используйте кнопки ниже.",
        reply_markup=main_menu_kb()
    )

# === RUN ===
if __name__ == "__main__":
    print("Bot is running...")
    # long polling
    bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
