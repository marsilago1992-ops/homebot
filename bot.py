import os
import calendar
import logging
import random
import requests
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ================= ENV =================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
OMDB_KEY = os.getenv("OMDB_API_KEY")

if not TOKEN or not SPREADSHEET_ID:
    raise RuntimeError("Missing env vars")

# ================= GOOGLE =================
if os.getenv("GOOGLE_SA_JSON"):
    with open("service_account.json", "w") as f:
        f.write(os.getenv("GOOGLE_SA_JSON"))

creds = Credentials.from_service_account_file(
    "service_account.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)
sheets = build("sheets", "v4", credentials=creds)

# ================= UTILS =================
MODE = "mode"

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def sheet_append(sheet, values):
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

async def reply(update: Update, text: str, **kw):
    if update.effective_message:
        await update.effective_message.reply_text(text, **kw)

# ================= KEYBOARDS =================
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Покупки", callback_data="shop")],
        [InlineKeyboardButton("🎬 Фильм из интернета", callback_data="movie")],
        [InlineKeyboardButton("⏰ Напоминание", callback_data="remind")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="home")]])

# ================= CALENDAR =================
def calendar_kb(year, month):
    kb = []
    kb.append([InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore")])
    kb.append([InlineKeyboardButton(d, callback_data="ignore") for d in ["Mo","Tu","We","Th","Fr","Sa","Su"]])

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date = f"{year}-{month:02d}-{day:02d}"
                row.append(InlineKeyboardButton(str(day), callback_data=f"cal:{date}"))
        kb.append(row)

    return InlineKeyboardMarkup(kb)

# ================= OMDB =================
def get_movie():
    words = ["love","war","life","night","world","game","future"]
    q = random.choice(words)

    url = f"http://www.omdbapi.com/?apikey={OMDB_KEY}&s={q}&type=movie"
    r = requests.get(url, timeout=10).json()

    if "Search" not in r:
        return None

    m = random.choice(r["Search"])
    imdb = m["imdbID"]

    d = requests.get(
        f"http://www.omdbapi.com/?apikey={OMDB_KEY}&i={imdb}&plot=full"
    ).json()

    return {
        "title": d.get("Title"),
        "year": d.get("Year"),
        "genre": d.get("Genre"),
        "rating": d.get("imdbRating"),
        "plot": d.get("Plot"),
        "poster": d.get("Poster"),
    }

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, "🏠 Главное меню", reply_markup=main_kb())

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # ===== HOME =====
    if data == "home":
        context.user_data.clear()
        await q.message.reply_text("🏠 Главное меню", reply_markup=main_kb())
        return

    # ===== MOVIE =====
    if data == "movie":
        await q.message.reply_text("🎬 Ищу фильм...")
        m = get_movie()
        if not m:
            await q.message.reply_text("Не нашёл фильм 😢")
            return

        txt = (
            f"🎬 *{m['title']}* ({m['year']})\n"
            f"⭐ IMDb: {m['rating']}\n"
            f"🎭 {m['genre']}\n\n"
            f"{m['plot']}"
        )

        if m["poster"] and m["poster"] != "N/A":
            await q.message.reply_photo(m["poster"], caption=txt, parse_mode="Markdown")
        else:
            await q.message.reply_text(txt, parse_mode="Markdown")
        return

    # ===== REMINDER =====
    if data == "remind":
        now = datetime.now()
        await q.message.reply_text(
            "📅 Выбери дату:",
            reply_markup=calendar_kb(now.year, now.month)
        )
        return

    # ===== DATE PICK =====
    if data.startswith("cal:"):
        date = data.split(":")[1]
        context.user_data["date"] = date
        context.user_data[MODE] = "TIME"
        await q.message.reply_text(
            "🕒 Введи время ЧЧ:ММ\nПример: 19:30",
            reply_markup=back_kb()
        )
        return

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get(MODE)
    text = update.message.text.strip()

    # ===== TIME INPUT =====
    if mode == "TIME":
        try:
            datetime.strptime(text, "%H:%M")
        except:
            await reply(update, "Неверный формат времени. Пример 18:30")
            return

        date = context.user_data.get("date")
        dt = datetime.strptime(f"{date} {text}", "%Y-%m-%d %H:%M")

        if dt <= datetime.now():
            await reply(update, "Это время уже прошло")
            return

        context.user_data["dt"] = dt
        context.user_data[MODE] = "TEXT"

        await reply(update, "✏️ Введи текст напоминания")
        return

    # ===== REMINDER TEXT =====
    if mode == "TEXT":
        dt = context.user_data.get("dt")
        user = update.effective_user.full_name

        sheet_append("Reminders", [[now_str(), dt.strftime("%Y-%m-%d %H:%M"), text, "OPEN", user]])

        delay = max(1, int((dt - datetime.now()).total_seconds()))
        chat_id = update.effective_chat.id

        async def job(ctx):
            await ctx.bot.send_message(chat_id, f"⏰ Напоминание: {text}")

        context.job_queue.run_once(job, delay)

        context.user_data.clear()
        await reply(update, f"✅ Напоминание установлено на {dt.strftime('%d.%m %H:%M')}")
        return

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("BOT RUNNING")
    app.run_polling()

if __name__ == "__main__":
    main()
