import os
import asyncio
import calendar
from datetime import datetime, timedelta
from typing import List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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


# ================== ENV ==================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
if not SPREADSHEET_ID:
    raise RuntimeError("Missing SPREADSHEET_ID")


# ================== GOOGLE ==================
SERVICE_ACCOUNT_FILE = "service_account.json"

sa = os.environ.get("GOOGLE_SA_JSON")
if sa and not os.path.exists(SERVICE_ACCOUNT_FILE):
    with open(SERVICE_ACCOUNT_FILE, "w", encoding="utf-8") as f:
        f.write(sa)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
sheets = build("sheets", "v4", credentials=creds)

SHEETS = {
    "shopping": "Shopping",
    "reminders": "Reminders",
}


def sheet_append(sheet: str, values: List[List[str]]):
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": values},
    ).execute()


def sheet_get(sheet: str):
    resp = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A1:Z",
    ).execute()
    return resp.get("values", [])


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


# ================== STATE ==================
MODE = "mode"


# ================== UI ==================
def menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Покупки", callback_data="menu:shop")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="menu:remind")],
    ])


def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")]
    ])


def shop_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="shop:add")],
        [InlineKeyboardButton("📋 Список", callback_data="shop:list")],
        [InlineKeyboardButton("🧹 Очистить купленные", callback_data="shop:clear")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")],
    ])


def remind_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Поставить напоминание", callback_data="rem:add")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")],
    ])


# ================== CALENDAR ==================
def calendar_kb(year: int, month: int):
    kb = []

    kb.append([InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore")])

    days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    kb.append([InlineKeyboardButton(d, callback_data="ignore") for d in days])

    month_cal = calendar.monthcalendar(year, month)
    for week in month_cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(str(day), callback_data=f"cal:{date_str}"))
        kb.append(row)

    kb.append([
        InlineKeyboardButton("⬅️", callback_data=f"calprev:{year}:{month}"),
        InlineKeyboardButton("➡️", callback_data=f"calnext:{year}:{month}")
    ])

    return InlineKeyboardMarkup(kb)


# ================== HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏠 Домашний бот", reply_markup=menu_kb())


async def on_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "menu:home":
        context.user_data.clear()
        await q.message.reply_text("Главное меню:", reply_markup=menu_kb())
        return

    if data == "menu:shop":
        await q.message.reply_text("🛒 Покупки:", reply_markup=shop_kb())
        return

    if data == "menu:remind":
        await q.message.reply_text("⏰ Напоминания:", reply_markup=remind_kb())
        return

    # ===== SHOP =====
    if data == "shop:add":
        context.user_data[MODE] = "SHOP_ADD"
        await q.message.reply_text("Напиши что купить:", reply_markup=back_kb())
        return

    if data == "shop:list":
        rows = sheet_get(SHEETS["shopping"])
        if len(rows) <= 1:
            await q.message.reply_text("Список пуст")
            return
        lines = ["🛒 Список:"]
        for r in rows[1:]:
            if len(r) >= 3 and r[2] == "OPEN":
                lines.append(f"• {r[1]}")
        await q.message.reply_text("\n".join(lines))
        return

    if data == "shop:clear":
        rows = sheet_get(SHEETS["shopping"])
        for i, r in enumerate(rows[1:], start=2):
            if len(r) >= 3 and r[2] == "OPEN":
                sheets.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{SHEETS['shopping']}!C{i}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [["DONE"]]},
                ).execute()
        await q.message.reply_text("✅ Очищено")
        return

    # ===== REMINDER =====
    if data == "rem:add":
        now = datetime.now()
        await q.message.reply_text("📅 Выбери дату:", reply_markup=calendar_kb(now.year, now.month))
        return

    if data.startswith("cal:"):
        date_str = data.split(":")[1]
        context.user_data["remind_date"] = date_str
        context.user_data[MODE] = "REMIND_TIME"
        await q.message.reply_text("Введи время ЧЧ:ММ\nПример: 19:30", reply_markup=back_kb())
        return

    if data.startswith("calprev:") or data.startswith("calnext:"):
        _, y, m = data.split(":")
        y, m = int(y), int(m)
        if "calprev" in data:
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        else:
            m += 1
            if m == 13:
                m = 1
                y += 1
        await q.message.edit_reply_markup(reply_markup=calendar_kb(y, m))
        return


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    mode = context.user_data.get(MODE)

    # SHOP
    if mode == "SHOP_ADD":
        user = update.effective_user.full_name
        sheet_append(SHEETS["shopping"], [[now_str(), text, "OPEN", user]])
        context.user_data.clear()
        await update.message.reply_text("✅ Добавлено", reply_markup=shop_kb())
        return

    # REMIND TIME
    if mode == "REMIND_TIME":
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError:
            await update.message.reply_text("Неверный формат времени")
            return

        date_str = context.user_data.get("remind_date")
        dt = datetime.strptime(f"{date_str} {text}", "%Y-%m-%d %H:%M")

        context.user_data["remind_dt"] = dt
        context.user_data[MODE] = "REMIND_TEXT"
        await update.message.reply_text("Теперь напиши текст напоминания")
        return

    # REMIND TEXT
    if mode == "REMIND_TEXT":
        dt: datetime = context.user_data.get("remind_dt")
        if not dt:
            await update.message.reply_text("Ошибка сценария")
            return

        user = update.effective_user.full_name
        when_str = dt.strftime("%Y-%m-%d %H:%M")
        sheet_append(SHEETS["reminders"], [[now_str(), when_str, text, "OPEN", user]])

        delay = max(1, int((dt - datetime.now()).total_seconds()))
        chat_id = update.effective_chat.id

        async def job(ctx):
            await ctx.bot.send_message(chat_id=chat_id, text=f"⏰ Напоминание: {text}")

        context.job_queue.run_once(job, when=delay)

        context.user_data.clear()
        await update.message.reply_text(f"✅ Напоминание на {when_str}", reply_markup=remind_kb())
        return


# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
