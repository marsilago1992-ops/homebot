import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing env var TELEGRAM_BOT_TOKEN")
if not SPREADSHEET_ID:
    raise RuntimeError("Missing env var SPREADSHEET_ID")
import re
import logging

print("BOT BUILD MARKER: LOOP_FIX_V1", flush=True)

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from calendar import monthrange

logging.basicConfig(level=logging.INFO)

# ====== НАСТРОЙКИ (ЗАПОЛНИ) ======
SERVICE_ACCOUNT_FILE = "service_account.json"  # C:\Users\ASUS\Desktop\Homebot

SHEETS = {
    "shopping": "Shopping",
    "pickups": "Pickups",
    "movies": "Movies",
    "reminders": "Reminders",
}

# ====== UI STATE (для кнопок) ======
MODE = "mode"          # что сейчас вводим
TMP = "tmp"            # временные данные

# ====== Универсальный reply ======
async def reply(update: Update, text: str, **kwargs):
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, **kwargs)

import os, json

sa = os.environ.get("GOOGLE_SA_JSON")
if sa and not os.path.exists("service_account.json"):
    with open("service_account.json", "w", encoding="utf-8") as f:
        f.write(sa)

# ====== GOOGLE SHEETS CLIENT ======
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
sheets_service = build("sheets", "v4", credentials=creds)

def sheet_append(sheet_name: str, values: List[List[str]]):
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()

def sheet_get_all(sheet_name: str) -> List[List[str]]:
    resp = sheets_service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!A1:Z",
    ).execute()
    return resp.get("values", [])

def sheet_update_cell(sheet_name: str, row: int, col_letter: str, value: str):
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet_name}!{col_letter}{row}",
        valueInputOption="USER_ENTERED",
        body={"values": [[value]]},
    ).execute()

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def ensure_headers():
    def init(sheet_key, headers):
        rows = sheet_get_all(SHEETS[sheet_key])
        if not rows:
            sheet_append(SHEETS[sheet_key], [headers])

    init("shopping", ["Created", "Item", "Status", "By"])
    init("pickups", ["Created", "Marketplace", "Point", "Deadline", "Item", "Status", "By"])
    init("movies", ["Added", "Title", "Status", "By"])
    init("reminders", ["Created", "When", "Text", "Status", "By"])

# ====== КНОПКИ ======
def calendar_kb(year: int, month: int):
    days = monthrange(year, month)[1]
    buttons = []
    row = []

    for day in range(1, days + 1):
        row.append(
            InlineKeyboardButton(
                str(day),
                callback_data=f"cal:day:{year}-{month:02d}-{day:02d}"
            )
        )
        if len(row) == 7:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton("⬅️ Назад", callback_data="menu:remind")
    ])

    return InlineKeyboardMarkup(buttons)
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Покупки", callback_data="menu:shop"),
         InlineKeyboardButton("📦 Посылки", callback_data="menu:pickups")],
        [InlineKeyboardButton("🎬 Кино", callback_data="menu:movies"),
         InlineKeyboardButton("⏰ Напоминания", callback_data="menu:remind")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в меню", callback_data="menu:home")]])

def shop_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="shop:add"),
         InlineKeyboardButton("📋 Список", callback_data="shop:list")],
        [InlineKeyboardButton("✅ Отметить куплено", callback_data="shop:done")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")],
    ])

def pickups_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="pick:add"),
         InlineKeyboardButton("📋 Список", callback_data="pick:list")],
        [InlineKeyboardButton("✅ Забрано", callback_data="pick:done")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")],
    ])

def movies_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="mov:add"),
         InlineKeyboardButton("📋 Список", callback_data="mov:list")],
        [InlineKeyboardButton("🎲 Выбрать случайно", callback_data="mov:choose")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")],
    ])

def remind_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Поставить напоминание", callback_data="rem:add")],
        [InlineKeyboardButton("📋 Активные напоминания", callback_data="rem:list")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")],
    ])

def remind_time_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("10 мин", callback_data="rem:time:10m"),
         InlineKeyboardButton("30 мин", callback_data="rem:time:30m")],
        [InlineKeyboardButton("1 час", callback_data="rem:time:1h"),
         InlineKeyboardButton("2 часа", callback_data="rem:time:2h")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:remind")],
        [InlineKeyboardButton("📅 Ввести дату и время", callback_data="rem:time:custom")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:remind")],
    ])

# ====== PARSERS ======
def parse_delay(s: str) -> Optional[timedelta]:
    s = s.strip().lower()
    m = re.fullmatch(r"(\d+)\s*(m|min|h|d)", s)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit in ("m", "min"):
        return timedelta(minutes=n)
    if unit == "h":
        return timedelta(hours=n)
    if unit == "d":
        return timedelta(days=n)
    return None

def parse_datetime_or_delay(args: List[str]) -> Tuple[Optional[datetime], int]:
    if not args:
        return None, 0

    td = parse_delay(args[0])
    if td:
        return datetime.now() + td, 1

    if len(args) >= 2:
        try:
            dt = datetime.strptime(args[0] + " " + args[1], "%Y-%m-%d %H:%M")
            return dt, 2
        except ValueError:
            pass

    try:
        dt = datetime.strptime(args[0], "%Y-%m-%d")
        dt = dt.replace(hour=9, minute=0)
        return dt, 1
    except ValueError:
        return None, 0

# ====== BOT HANDLERS ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    await update.message.reply_text(
        "Домашний бот готов ✅\n\n"
        "Можно командами, можно кнопками.\n"
        "Нажми меню ниже 👇"
    )
    await update.message.reply_text("Выбери раздел:", reply_markup=main_menu_kb())

# --- Shopping ---
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    item = " ".join(context.args).strip()
    if not item:
        await update.message.reply_text("Формат: /buy молоко 2л")
        return
    by = update.effective_user.full_name
    sheet_append(SHEETS["shopping"], [[now_str(), item, "OPEN", by]])
    await update.message.reply_text(f"Добавил в покупки: {item}")

async def list_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    rows = sheet_get_all(SHEETS["shopping"])
    if len(rows) <= 1:
        await reply(update, "Список покупок пуст.", reply_markup=shop_kb())
        return
    data = rows[1:]
    open_items = [(i+2, r) for i, r in enumerate(data) if len(r) >= 3 and r[2] == "OPEN"]
    if not open_items:
        await reply(update, "Открытых покупок нет ✅", reply_markup=shop_kb())
        return
    lines = ["🛒 Покупки:"]
    for _, r in open_items[:30]:
        lines.append(f"• {r[1]}")
    await reply(update, "\n".join(lines), reply_markup=shop_kb())

async def done_shopping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    if not context.args:
        await update.message.reply_text("Формат: /done 1")
        return
    n = int(context.args[0])
    rows = sheet_get_all(SHEETS["shopping"])
    data = rows[1:]
    open_rows = [(i+2, r) for i, r in enumerate(data) if len(r) >= 3 and r[2] == "OPEN"]
    if n < 1 or n > len(open_rows):
        await update.message.reply_text("Неверный номер. Смотри /list")
        return
    sheet_row, r = open_rows[n-1]
    sheet_update_cell(SHEETS["shopping"], sheet_row, "C", "DONE")
    await update.message.reply_text(f"✅ Куплено: {r[1]}")

def clear_open_shopping():
    rows = sheet_get_all(SHEETS["shopping"])
    data = rows[1:] if len(rows) > 1 else []
    # В таблице: C = Status
    for i, r in enumerate(data, start=2):  # start=2 потому что 1-я строка — заголовки
        if len(r) >= 3 and r[2] == "OPEN":
            sheet_update_cell(SHEETS["shopping"], i, "C", "DONE")

# --- Pickups ---
async def pickup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    if len(context.args) < 4:
        await update.message.reply_text("Формат: /pickup ozon <пвз> <до YYYY-MM-DD> <что>")
        return
    marketplace = context.args[0]
    point = context.args[1]
    deadline = context.args[2]
    item = " ".join(context.args[3:])
    by = update.effective_user.full_name
    sheet_append(SHEETS["pickups"], [[now_str(), marketplace, point, deadline, item, "OPEN", by]])
    await update.message.reply_text(f"📦 Добавил: {marketplace}, {point}, до {deadline}: {item}")

async def pickups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    rows = sheet_get_all(SHEETS["pickups"])
    if len(rows) <= 1:
        await reply(update, "Список посылок пуст.", reply_markup=pickups_kb())
        return
    data = rows[1:]
    open_items = [(i+2, r) for i, r in enumerate(data) if len(r) >= 6 and r[5] == "OPEN"]
    if not open_items:
        await reply(update, "Открытых посылок нет ✅", reply_markup=pickups_kb())
        return
    lines = ["📦 Забрать:"]
    for _, r in open_items[:30]:
        lines.append(f"• {r[1]} / {r[2]} / до {r[3]} — {r[4]}")
    await reply(update, "\n".join(lines), reply_markup=pickups_kb())

async def picked(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    if not context.args:
        await update.message.reply_text("Формат: /picked 1")
        return
    n = int(context.args[0])
    rows = sheet_get_all(SHEETS["pickups"])
    data = rows[1:]
    open_rows = [(i+2, r) for i, r in enumerate(data) if len(r) >= 6 and r[5] == "OPEN"]
    if n < 1 or n > len(open_rows):
        await update.message.reply_text("Неверный номер. Смотри /pickups")
        return
    sheet_row, r = open_rows[n-1]
    sheet_update_cell(SHEETS["pickups"], sheet_row, "F", "DONE")
    await update.message.reply_text(f"✅ Забрано: {r[4]}")

# --- Movies ---
async def movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    title = " ".join(context.args).strip()
    if not title:
        await update.message.reply_text("Формат: /movie Интерстеллар")
        return
    by = update.effective_user.full_name
    sheet_append(SHEETS["movies"], [[now_str(), title, "OPEN", by]])
    await update.message.reply_text(f"🎬 Добавил в список: {title}")

async def movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    rows = sheet_get_all(SHEETS["movies"])
    if len(rows) <= 1:
        await reply(update, "Список фильмов пуст.", reply_markup=movies_kb())
        return
    data = rows[1:]
    open_items = [r for r in data if len(r) >= 3 and r[2] == "OPEN"]
    if not open_items:
        await reply(update, "Фильмов к просмотру нет ✅", reply_markup=movies_kb())
        return
    lines = ["🎬 Что посмотреть:"]
    for r in open_items[:30]:
        lines.append(f"• {r[1]}")
    await reply(update, "\n".join(lines), reply_markup=movies_kb())

async def choose_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import random
    ensure_headers()
    rows = sheet_get_all(SHEETS["movies"])
    data = rows[1:]
    open_items = [r for r in data if len(r) >= 3 and r[2] == "OPEN"]
    if not open_items:
        await reply(update, "Список пуст.", reply_markup=movies_kb())
        return
    pick = random.choice(open_items)
    await reply(update, f"🎲 Сегодня смотрим: {pick[1]}", reply_markup=movies_kb())

# --- Reminders ---
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    args = context.args
    dt, consumed = parse_datetime_or_delay(args)
    if not dt:
        await update.message.reply_text("Формат: /remind 30m вынести мусор  |  /remind 2026-03-08 19:00 купить кофе")
        return
    text = " ".join(args[consumed:]).strip()
    if not text:
        await update.message.reply_text("Добавь текст напоминания.")
        return

    by = update.effective_user.full_name
    when_str = dt.strftime("%Y-%m-%d %H:%M")
    sheet_append(SHEETS["reminders"], [[now_str(), when_str, text, "OPEN", by]])

    delay_sec = max(1, int((dt - datetime.now()).total_seconds()))
    chat_id = update.effective_chat.id

    async def send_job(ctx: ContextTypes.DEFAULT_TYPE):
        await ctx.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")

    context.job_queue.run_once(send_job, when=delay_sec)
    await update.message.reply_text(f"✅ Ок! Напомню {when_str}: {text}")

# ====== BUTTON HANDLER ======
async def on_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "menu:home":
        context.user_data.pop(MODE, None)
        await q.message.reply_text("Выбери раздел:", reply_markup=main_menu_kb())
        return

    if data == "menu:shop":
        context.user_data.clear()
        await q.message.reply_text("🛒 Покупки:", reply_markup=shop_kb())
        return

    if data == "menu:pickups":
        context.user_data.clear()
        await q.message.reply_text("📦 Посылки:", reply_markup=pickups_kb())
        return

    if data == "menu:movies":
        context.user_data.clear()
        await q.message.reply_text("🎬 Кино:", reply_markup=movies_kb())
        return

    if data == "menu:remind":
        context.user_data.pop(MODE, None)
        await q.message.reply_text("⏰ Напоминания:", reply_markup=remind_kb())
        return

    if data == "shop:add":
        context.user_data[MODE] = "SHOP_ADD"
        await q.message.reply_text("Напиши, что купить (одним сообщением).", reply_markup=back_kb())
        return

    if data == "shop:list":
        await list_shopping(update, context)
        return
    if data == "shop:done":
        clear_open_shopping()
        await q.message.reply_text("✅ Готово! Список покупок очищен.", reply_markup=shop_kb())
        return

    if data == "pick:add":
        context.user_data[MODE] = "PICKUP_ADD"
        await q.message.reply_text(
            "Напиши одной строкой:\nmarketplace; пвз; дедлайн(YYYY-MM-DD); что забрать\n\nПример:\nozon; ПВЗ у дома; 2026-03-10; зарядка",
            reply_markup=back_kb()
        )
        return

    if data == "pick:list":
        await pickups(update, context)
        return

    if data == "mov:add":
        context.user_data[MODE] = "MOVIE_ADD"
        await q.message.reply_text("Напиши название фильма/сериала.", reply_markup=back_kb())
        return

    if data == "mov:list":
        await movies(update, context)
        return

    if data == "mov:choose":
        await choose_movie(update, context)
        return

    if data == "rem:add":
        now = datetime.now()
        await q.message.reply_text(
        "📅 Выбери дату:",
        reply_markup=calendar_kb(now.year, now.month)
    )
    return

    if data.startswith("cal:"):
    date_str = data.split(":")[1]   # 2026-03-15
    context.user_data["remind_date"] = date_str

    await q.message.reply_text(
        "Теперь введи время в формате ЧЧ:ММ\nПример: 19:30",
        reply_markup=back_kb()
    )
    return

    if data == "rem:list":
        rows = sheet_get_all(SHEETS["reminders"])
        data_rows = rows[1:] if len(rows) > 1 else []
        open_items = [r for r in data_rows if len(r) >= 4 and r[3] == "OPEN"]

    if not open_items:
        await q.message.reply_text("Активных напоминаний нет ✅", reply_markup=remind_kb())
        return

    lines = ["⏰ Активные напоминания:"]
    for r in open_items[:30]:
        lines.append(f"• {r[1]} — {r[2]}")

    await q.message.reply_text("\n".join(lines), reply_markup=remind_kb())
    return

    await q.message.reply_text("Не понял кнопку. Нажми /start", reply_markup=main_menu_kb())

# ====== TEXT INPUT AFTER BUTTONS ======
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_headers()
    if not update.message:
        return
    text = (update.message.text or "").strip()
    if not text:
        return

    mode = context.user_data.get(MODE)

    if mode == "SHOP_ADD":
        by = update.effective_user.full_name
        sheet_append(SHEETS["shopping"], [[now_str(), text, "OPEN", by]])
        context.user_data.clear()
        await reply(update, f"Добавил в покупки: {text}", reply_markup=shop_kb())
        return

    if mode == "MOVIE_ADD":
        by = update.effective_user.full_name
        sheet_append(SHEETS["movies"], [[now_str(), text, "OPEN", by]])
        context.user_data.clear()
        await reply(update, f"🎬 Добавил: {text}", reply_markup=movies_kb())
        return

    if mode == "PICKUP_ADD":
        parts = [p.strip() for p in text.split(";")]
        if len(parts) < 4:
            await reply(
                update,
                "Формат неверный. Нужно 4 части через ';'\n"
                "marketplace; пвз; YYYY-MM-DD; что\n\n"
                "Пример:\n"
                "ozon; ПВЗ у дома; 2026-03-10; зарядка",
                reply_markup=back_kb()
            )
            return

        marketplace, point, deadline, item = parts[0], parts[1], parts[2], "; ".join(parts[3:])
        by = update.effective_user.full_name
        sheet_append(SHEETS["pickups"], [[now_str(), marketplace, point, deadline, item, "OPEN", by]])
        context.user_data.clear()
        await reply(update, f"📦 Добавил: {marketplace}, до {deadline}: {item}", reply_markup=pickups_kb())
        return

    if mode == "REMIND_TIME_INPUT":
        time_str = text.strip()

    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await reply(update, "Неверный формат времени. Пример: 18:30")
        return

        date_str = context.user_data.get("remind_date")
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")

        context.user_data["remind_dt"] = dt
        context.user_data[MODE] = "REMIND_TEXT"

    await reply(update, "Теперь напиши текст напоминания.")
    return
       
    if mode == "REMIND_DATETIME":
        try:
            dt = datetime.strptime(text, "%d.%m.%Y %H:%M")
        except ValueError:
            await reply(
                update,
                "Неверный формат.\nИспользуй: ДД.ММ.ГГГГ ЧЧ:ММ\nПример: 08.03.2026 19:30",
                reply_markup=back_kb()
            )
            return

    if dt <= datetime.now():
        await reply(update, "Это время уже прошло.", reply_markup=back_kb())
        return

        context.user_data[MODE] = "REMIND_TEXT"
        context.user_data["remind_dt"] = dt

        await reply(update, "Теперь напиши текст напоминания.", reply_markup=back_kb())
        return

    if mode == "REMIND_TEXT":
        dt = context.user_data.get("remind_dt")

    if not dt:
        context.user_data.clear()
        await reply(update, "Сценарий сбился. Нажми /start", reply_markup=main_menu_kb())
        return

    if dt <= datetime.now():
        await reply(update, "Это время уже прошло.")
        return

        by = update.effective_user.full_name
        when_str = dt.strftime("%Y-%m-%d %H:%M")
        sheet_append(SHEETS["reminders"], [[now_str(), when_str, text, "OPEN", by]])

        delay_sec = max(1, int((dt - datetime.now()).total_seconds()))
        chat_id = update.effective_chat.id

    async def send_job(ctx: ContextTypes.DEFAULT_TYPE):
        await ctx.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")

    context.job_queue.run_once(send_job, when=delay_sec)

    context.user_data.clear()
    await reply(update, f"✅ Напоминание поставлено на {when_str}")
    return

    td = parse_delay(delay_str)
    if not td:
        context.user_data.clear()
        await reply(update, "Не понял время. Нажми /start", reply_markup=main_menu_kb())
        return

    dt = datetime.now() + td

    by = update.effective_user.full_name
    when_str = dt.strftime("%Y-%m-%d %H:%M")
    sheet_append(SHEETS["reminders"], [[now_str(), when_str, text, "OPEN", by]])

    delay_sec = max(1, int((dt - datetime.now()).total_seconds()))
    chat_id = update.effective_chat.id

    async def send_job(ctx: ContextTypes.DEFAULT_TYPE):
        await ctx.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")

    context.job_queue.run_once(send_job, when=delay_sec)

    context.user_data.clear()
    
    await reply(update, f"✅ Ок! Напомню через {delay_str}: {text}", reply_markup=remind_kb())
    return

    await reply(update, "Нажми /start и выбери действие кнопками.", reply_markup=main_menu_kb())

# ====== ERROR HANDLER ======
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.exception("Exception while handling an update:", exc_info=context.error)

def main():
    import asyncio
    import requests

    asyncio.set_event_loop(asyncio.new_event_loop())

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))

    # Кнопки
    app.add_handler(CallbackQueryHandler(on_buttons))

    # Текст после кнопок
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Bot is running. Open Telegram and send /start", flush=True)

    print(
        "DELETE WEBHOOK:",
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
        ).text,
        flush=True,
    )

    app.run_polling()
print("BOOT: bottom reached", flush=True)

if __name__ == "__main__":
    print("BOOT: entering main()", flush=True)
    main()
    print("BOOT: main started", flush=True)














































