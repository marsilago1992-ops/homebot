import os
import calendar
import random
from datetime import datetime
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ========= ENV =========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
OMDB_KEY = os.getenv("OMDB_API_KEY")
SPOON_KEY = os.getenv("SPOONACULAR_KEY")

# ========= GOOGLE =========
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
sa_json = os.getenv("GOOGLE_SA_JSON")
if sa_json and not os.path.exists("service_account.json"):
    with open("service_account.json","w") as f:
        f.write(sa_json)

creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
sheets = build("sheets","v4",credentials=creds)

def sheet_get(name):
    r=sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{name}!A1:Z"
    ).execute()
    return r.get("values",[])

def sheet_append(name,values):
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{name}!A1",
        valueInputOption="USER_ENTERED",
        body={"values":values}
    ).execute()

def sheet_update(name,row,col,val):
    sheets.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{name}!{col}{row}",
        valueInputOption="USER_ENTERED",
        body={"values":[[val]]}
    ).execute()

# ========= UI =========
def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ Напоминания",callback_data="rem")],
        [InlineKeyboardButton("🎬 Фильмы",callback_data="mov")],
        [InlineKeyboardButton("🍳 Что приготовить",callback_data="cook")],
        [InlineKeyboardButton("🏠 Дом",callback_data="house")]
    ])

def kb_back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад",callback_data="home")]])

# ========= CALENDAR =========
def kb_calendar(y,m):
    kb=[]
    kb.append([InlineKeyboardButton(f"{calendar.month_name[m]} {y}",callback_data="x")])
    kb.append([InlineKeyboardButton(d,callback_data="x") for d in ["Mo","Tu","We","Th","Fr","Sa","Su"]])
    for w in calendar.monthcalendar(y,m):
        row=[]
        for d in w:
            if d==0:
                row.append(InlineKeyboardButton(" ",callback_data="x"))
            else:
                date=f"{y}-{m:02d}-{d:02d}"
                row.append(InlineKeyboardButton(str(d),callback_data=f"date:{date}"))
        kb.append(row)
    return InlineKeyboardMarkup(kb)

def kb_time():
    hrs=[9,12,15,18,21]
    kb=[[InlineKeyboardButton(f"{h:02d}:00",callback_data=f"time:{h:02d}:00")] for h in hrs]
    kb.append([InlineKeyboardButton("⬅️ Назад",callback_data="home")])
    return InlineKeyboardMarkup(kb)

# ========= APIs =========
def get_movie():
    try:
        year=random.randint(1995,2024)
        r=requests.get("http://www.omdbapi.com/",params={
            "apikey":OMDB_KEY,"s":"love","type":"movie","y":year
        }).json()
        m=random.choice(r["Search"])
        d=requests.get("http://www.omdbapi.com/",params={
            "apikey":OMDB_KEY,"i":m["imdbID"],"plot":"short","r":"json"
        }).json()
        title=d.get("Title","")
        rating=d.get("imdbRating","?")
        plot=d.get("Plot","")
        poster=d.get("Poster","")
        text=f"🎬 {title}\n⭐ IMDb: {rating}\n\n{plot}"
        return poster,text
    except:
        return None,"❌ Фильм не найден"

def get_recipe():
    try:
        r=requests.get("https://api.spoonacular.com/recipes/random",
            params={"apiKey":SPOON_KEY}).json()
        rec=r["recipes"][0]
        title=rec["title"]
        img=rec["image"]
        mins=rec["readyInMinutes"]
        ings="\n".join("• "+i["original"] for i in rec["extendedIngredients"][:7])
        text=f"🍳 {title}\n⏱ {mins} мин\n\n{ings}\n\n{rec['sourceUrl']}"
        return img,text
    except:
        return None,"❌ Рецепты недоступны"

# ========= HANDLERS =========
async def start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Семейный ассистент",reply_markup=kb_main())

async def buttons(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    d=q.data
    await q.answer()

    if d=="home":
        await q.message.reply_text("Главное меню",reply_markup=kb_main())

    # ===== REMIND =====
    elif d=="rem":
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Создать",callback_data="rem_add")],
            [InlineKeyboardButton("📋 Список",callback_data="rem_list")],
            [InlineKeyboardButton("❌ Удалить все",callback_data="rem_clear")],
            [InlineKeyboardButton("⬅️ Назад",callback_data="home")]
        ])
        await q.message.reply_text("⏰ Напоминания",reply_markup=kb)

    elif d=="rem_add":
        now=datetime.now()
        await q.message.reply_text("Выбери дату",reply_markup=kb_calendar(now.year,now.month))

    elif d.startswith("date:"):
        ctx.user_data["date"]=d.split(":")[1]
        await q.message.reply_text("Выбери время",reply_markup=kb_time())

    elif d.startswith("time:"):
        ctx.user_data["time"]=d.split(":")[1]
        ctx.user_data["mode"]="rem_text"
        await q.message.reply_text("Напиши текст напоминания")

    elif d=="rem_list":
        rows=sheet_get("Reminders")
        items=[r for r in rows[1:] if len(r)>=4 and r[3]=="OPEN"]
        txt="Нет активных" if not items else "\n".join(f"• {r[1]} — {r[2]}" for r in items)
        await q.message.reply_text(txt)

    elif d=="rem_clear":
        rows=sheet_get("Reminders")
        for i,r in enumerate(rows[1:],start=2):
            if len(r)>=4 and r[3]=="OPEN":
                sheet_update("Reminders",i,"D","DONE")
        await q.message.reply_text("Удалено")

    # ===== MOVIE =====
    elif d=="mov":
        poster,text=get_movie()
        if poster:
            await q.message.reply_photo(poster,caption=text,reply_markup=kb_back())
        else:
            await q.message.reply_text(text,reply_markup=kb_back())

    # ===== COOK =====
    elif d=="cook":
        img,text=get_recipe()
        if img:
            await q.message.reply_photo(img,caption=text,reply_markup=kb_back())
        else:
            await q.message.reply_text(text,reply_markup=kb_back())

    # ===== HOUSE =====
    elif d=="house":
        kb=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить план",callback_data="house_add")],
            [InlineKeyboardButton("📋 Список планов",callback_data="house_list")],
            [InlineKeyboardButton("⬅️ Назад",callback_data="home")]
        ])
        await q.message.reply_text("🏠 Дом",reply_markup=kb)

    elif d=="house_add":
        ctx.user_data["mode"]="house_add"
        await q.message.reply_text("Напиши план")

    elif d=="house_list":
        rows=sheet_get("Home")
        txt="Планов нет" if len(rows)<=1 else "\n".join(f"{i}. {r[1]}" for i,r in enumerate(rows[1:],1))
        await q.message.reply_text(txt)

# ========= TEXT =========
async def text_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    txt=update.message.text.strip()
    mode=ctx.user_data.get("mode")

    if mode=="rem_text":
        date=ctx.user_data.get("date")
        time=ctx.user_data.get("time")
        dt=datetime.strptime(f"{date} {time}","%Y-%m-%d %H:%M")
        user=update.effective_user.full_name

        sheet_append("Reminders",[[datetime.now().strftime("%Y-%m-%d %H:%M"),
                                   dt.strftime("%Y-%m-%d %H:%M"),
                                   txt,"OPEN",user]])

        delay=max(1,int((dt-datetime.now()).total_seconds()))
        chat_id=update.effective_chat.id

        async def job(c):
            await c.bot.send_message(chat_id,text=f"⏰ Напоминание: {txt}")

        ctx.job_queue.run_once(job,delay)
        ctx.user_data.clear()
        await update.message.reply_text("✅ Напоминание создано")
        return

    if mode=="house_add":
        user=update.effective_user.full_name
        sheet_append("Home",[[datetime.now().strftime("%Y-%m-%d %H:%M"),txt,user]])
        ctx.user_data.clear()
        await update.message.reply_text("План добавлен")
        return

# ========= MAIN =========
def main():
    app=ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.run_polling()

if __name__=="__main__":
    main()
