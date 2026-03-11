import os
import calendar
import random
import logging
from datetime import datetime, timedelta

import requests
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

# ========= ENV =========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
OMDB_KEY = os.getenv("OMDB_API_KEY")
SPOON_KEY = os.getenv("SPOONACULAR_KEY")

if not TOKEN or not SPREADSHEET_ID:
    raise RuntimeError("ENV VARS MISSING")

# ========= GOOGLE SHEETS =========
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

sa_json = os.getenv("GOOGLE_SA_JSON")
if sa_json and not os.path.exists("service_account.json"):
    with open("service_account.json", "w") as f:
        f.write(sa_json)

creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
sheets = build("sheets", "v4", credentials=creds)

def sheet_append(sheet, values):
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

def sheet_get(sheet):
    r = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{sheet}!A1:Z"
    ).execute()
    return r.get("values", [])

# ========= UI =========
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Продукты", callback_data="shop")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="remind")],
        [InlineKeyboardButton("🎬 Фильм", callback_data="movie")],
        [InlineKeyboardButton("🍳 Что приготовить", callback_data="cook")],
        [InlineKeyboardButton("🏠 Дом", callback_data="home")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="home")]])

# ========= CALENDAR =========
def calendar_kb(year, month):
    kb = []
    kb.append([InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="ignore")])
    days = ["Mo","Tu","We","Th","Fr","Sa","Su"]
    kb.append([InlineKeyboardButton(d, callback_data="ignore") for d in days])

    for week in calendar.monthcalendar(year, month):
        row=[]
        for d in week:
            if d==0:
                row.append(InlineKeyboardButton(" ", callback_data="ignore"))
            else:
                date=f"{year}-{month:02d}-{d:02d}"
                row.append(InlineKeyboardButton(str(d), callback_data=f"date:{date}"))
        kb.append(row)

    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="home")])
    return InlineKeyboardMarkup(kb)

def time_kb():
    kb=[]
    hours=[9,12,15,18,21]
    for h in hours:
        kb.append([InlineKeyboardButton(f"{h:02d}:00", callback_data=f"time:{h:02d}:00")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="home")])
    return InlineKeyboardMarkup(kb)

# ========= APIs =========
def random_movie():
    try:
        year=random.randint(1990,2024)
        r=requests.get("http://www.omdbapi.com/",params={
            "apikey":OMDB_KEY,
            "type":"movie",
            "y":year,
            "s":"love"
        }).json()
        if "Search" not in r:
            return "❌ Фильм не найден"
        m=random.choice(r["Search"])
        d=requests.get("http://www.omdbapi.com/",params={
            "apikey":OMDB_KEY,"i":m["imdbID"]
        }).json()
        return f"🎬 {d['Title']} ({d['Year']})\n⭐ {d.get('imdbRating','?')}\n{d.get('Plot','')}"
    except:
        return "❌ Ошибка сервиса фильмов"

def random_recipe():
    try:
        r=requests.get("https://api.spoonacular.com/recipes/random",
            params={"apiKey":SPOON_KEY}).json()
        rec=r["recipes"][0]
        ings="\n".join("• "+i["original"] for i in rec["extendedIngredients"][:8])
        return f"🍳 {rec['title']}\n⏱ {rec['readyInMinutes']} мин\n\n{ings}\n\n{rec['sourceUrl']}"
    except:
        return "❌ Ошибка рецептов"

# ========= HANDLERS =========
async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Семейный ассистент готов ✅",reply_markup=main_kb())

async def buttons(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    d=q.data
    await q.answer()

    if d=="home":
        await q.message.reply_text("Главное меню:",reply_markup=main_kb())

    elif d=="shop":
        rows=sheet_get("Shopping")
        if len(rows)<=1:
            txt="Список пуст"
        else:
            txt="\n".join("• "+r[1] for r in rows[1:])
        await q.message.reply_text("🛒 Продукты:\n"+txt,reply_markup=back_kb())

    elif d=="remind":
        now=datetime.now()
        await q.message.reply_text("📅 Выбери дату:",reply_markup=calendar_kb(now.year,now.month))

    elif d.startswith("date:"):
        context.user_data["date"]=d.split(":")[1]
        await q.message.reply_text("🕒 Выбери время:",reply_markup=time_kb())

    elif d.startswith("time:"):
        context.user_data["time"]=d.split(":")[1]
        context.user_data["mode"]="rem_text"
        await q.message.reply_text("✍️ Напиши текст напоминания")

    elif d=="movie":
        await q.message.reply_text(random_movie(),reply_markup=back_kb())

    elif d=="cook":
        await q.message.reply_text(random_recipe(),reply_markup=back_kb())

    elif d=="home":
        rows=sheet_get("Home")
        if len(rows)<=1:
            txt="Планов нет"
        else:
            txt="\n".join("• "+r[1] for r in rows[1:])
        await q.message.reply_text("🏠 Планы по дому:\n"+txt,reply_markup=back_kb())

async def text_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.strip()
    mode=context.user_data.get("mode")

    # напоминание текст
    if mode=="rem_text":
        date=context.user_data.get("date")
        time=context.user_data.get("time")
        dt=datetime.strptime(f"{date} {time}","%Y-%m-%d %H:%M")
        user=update.effective_user.full_name

        sheet_append("Reminders",[[datetime.now().strftime("%Y-%m-%d %H:%M"),dt.strftime("%Y-%m-%d %H:%M"),txt,"OPEN",user]])

        delay=max(1,int((dt-datetime.now()).total_seconds()))
        chat_id=update.effective_chat.id

        async def job(ctx):
            await ctx.bot.send_message(chat_id=chat_id,text=f"⏰ Напоминание: {txt}")

        context.job_queue.run_once(job,delay)
        context.user_data.clear()
        await update.message.reply_text("✅ Напоминание создано",reply_markup=main_kb())
        return

    # продукты
    if txt.lower().startswith("купить "):
        item=txt[7:]
        user=update.effective_user.full_name
        sheet_append("Shopping",[[datetime.now().strftime("%Y-%m-%d %H:%M"),item,"OPEN",user]])
        await update.message.reply_text("Добавлено в покупки",reply_markup=main_kb())
        return

    # планы дома
    if txt.lower().startswith("дом "):
        plan=txt[4:]
        user=update.effective_user.full_name
        sheet_append("Home",[[datetime.now().strftime("%Y-%m-%d %H:%M"),plan,user]])
        await update.message.reply_text("План добавлен",reply_markup=main_kb())
        return

# ========= MAIN =========
def main():
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    print("Bot running...")
    app.run_polling()

if __name__=="__main__":
    main()
