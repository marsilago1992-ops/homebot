import os
import re
import json
import random
import logging
import asyncio
import requests
from datetime import datetime, timedelta
from typing import List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
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

# ========= ENV =========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SPOON_KEY = os.getenv("SPOONACULAR_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
if not SPREADSHEET_ID:
    raise RuntimeError("Missing SPREADSHEET_ID")
if not SPOON_KEY:
    raise RuntimeError("Missing SPOONACULAR_KEY")

# ========= LOG =========
logging.basicConfig(level=logging.INFO)

# ========= GOOGLE SHEETS =========
SERVICE_ACCOUNT_FILE = "service_account.json"
sa = os.environ.get("GOOGLE_SA_JSON")
if sa and not os.path.exists(SERVICE_ACCOUNT_FILE):
    with open(SERVICE_ACCOUNT_FILE, "w") as f:
        f.write(sa)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
sheets = build("sheets", "v4", credentials=creds)

SHEETS = {
    "shopping": "Shopping",
    "reminders": "Reminders",
}

def sheet_append(name, values):
    sheets.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{name}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()

def sheet_get(name):
    r = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{name}!A1:Z",
    ).execute()
    return r.get("values", [])

# ========= UTILS =========
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def extract_mentions(text: str):
    return re.findall(r'@\w+', text)

async def reply(update: Update, text: str, **kw):
    await update.effective_message.reply_text(text, **kw)

# ========= SPOONACULAR =========
def get_random_recipe():
    url = "https://api.spoonacular.com/recipes/random"
    params = {"apiKey": SPOON_KEY, "number": 1}
    r = requests.get(url, params=params, timeout=10).json()
    recipe = r["recipes"][0]

    ingredients = "\n".join(
        f"• {i['original']}" for i in recipe["extendedIngredients"]
    )

    return (
        f"🍽 *{recipe['title']}*\n\n"
        f"🧂 Ингредиенты:\n{ingredients}\n\n"
        f"📖 Инструкция:\n{recipe.get('instructions','—')}"
    )

# ========= KEYBOARDS =========
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Покупки", callback_data="shop")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="remind")],
        [InlineKeyboardButton("🎬 Фильм", callback_data="movie")],
        [InlineKeyboardButton("🍳 Что приготовить", callback_data="food")],
        [InlineKeyboardButton("🎲 Досуг", callback_data="fun")],
        [InlineKeyboardButton("🧹 Дом", callback_data="home")],
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="home")]
    ])

# ========= COMMANDS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply(update, "Семейный ассистент готов 👨‍👩‍👧", reply_markup=main_kb())

# ========= SHOPPING =========
async def add_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = " ".join(context.args)
    mentions = " ".join(extract_mentions(item))
    sheet_append(SHEETS["shopping"], [[now_str(), item, "OPEN", mentions]])
    await reply(update, f"🛒 Добавлено: {item}")

# ========= REMINDERS =========
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await reply(update, "Формат: /remind 30m текст")
        return

    delay = int(args[0][:-1])
    text = " ".join(args[1:])
    mentions = " ".join(extract_mentions(text))

    dt = datetime.now() + timedelta(minutes=delay)
    sheet_append(SHEETS["reminders"], [[now_str(), dt.strftime("%Y-%m-%d %H:%M"), text, "OPEN", mentions]])

    chat_id = update.effective_chat.id

    async def job(ctx):
        await ctx.bot.send_message(chat_id, f"⏰ Напоминание: {text}")

    context.job_queue.run_once(job, when=delay * 60)
    await reply(update, f"⏰ Напомню через {delay} мин")

# ========= BUTTONS =========
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "home":
        await q.message.reply_text("Меню:", reply_markup=main_kb())

    elif d == "food":
        recipe = get_random_recipe()
        await q.message.reply_text(recipe, parse_mode="Markdown")

    elif d == "fun":
        ideas = [
            "🚶 Прогулка",
            "🎲 Настольные игры",
            "🎬 Кино",
            "🍕 Заказать еду",
            "🚴 Велопрогулка"
        ]
        await q.message.reply_text(random.choice(ideas))

    elif d == "home":
        tasks = [
            "🧹 Пропылесосить",
            "🪟 Помыть окна",
            "🛁 Уборка ванной",
            "🧺 Стирка"
        ]
        await q.message.reply_text(random.choice(tasks))

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("buy", add_buy))
    app.add_handler(CommandHandler("remind", remind))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
