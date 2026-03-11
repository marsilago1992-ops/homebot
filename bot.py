import os
import logging
import asyncio
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

logging.basicConfig(level=logging.INFO)

# ===== ENV =====
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OMDB_KEY = os.getenv("OMDB_API_KEY")
SPOON_KEY = os.getenv("SPOONACULAR_KEY")

if not TOKEN:
    raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")

# ===== SIMPLE STORAGE =====
PRODUCTS = []
REMINDERS = []
HOME_PLANS = []

# ===== UI =====
def menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Продукты", callback_data="prod")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="rem")],
        [InlineKeyboardButton("🎬 Фильмы", callback_data="film")],
        [InlineKeyboardButton("🍳 Что приготовить", callback_data="cook")],
        [InlineKeyboardButton("🏠 Дом", callback_data="home")],
    ])

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Семейный ассистент готов 👇", reply_markup=menu_kb())

# ===== PRODUCTS =====
def prod_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить", callback_data="prod_add")],
        [InlineKeyboardButton("📋 Список", callback_data="prod_list")],
        [InlineKeyboardButton("✅ Куплено", callback_data="prod_done")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

# ===== REMINDERS =====
def rem_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать", callback_data="rem_add")],
        [InlineKeyboardButton("📋 Список", callback_data="rem_list")],
        [InlineKeyboardButton("❌ Удалить", callback_data="rem_del")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

# ===== MOVIES =====
def film_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Рекомендовать фильм", callback_data="film_pick")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

# ===== COOK =====
def cook_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Случайное блюдо", callback_data="cook_pick")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

# ===== HOME =====
def home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить план", callback_data="home_add")],
        [InlineKeyboardButton("📋 Планы", callback_data="home_list")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="home_edit")],
        [InlineKeyboardButton("❌ Удалить", callback_data="home_del")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

# ===== BUTTONS =====
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    if data == "back":
        await q.message.reply_text("Меню:", reply_markup=menu_kb())

    elif data == "prod":
        await q.message.reply_text("Продукты:", reply_markup=prod_kb())

    elif data == "rem":
        await q.message.reply_text("Напоминания:", reply_markup=rem_kb())

    elif data == "film":
        await q.message.reply_text("Фильмы:", reply_markup=film_kb())

    elif data == "cook":
        await q.message.reply_text("Рецепты:", reply_markup=cook_kb())

    elif data == "home":
        await q.message.reply_text("Дом:", reply_markup=home_kb())

    # ===== MOVIE PICK =====
    elif data == "film_pick":
        await send_movie(q)

    # ===== COOK PICK =====
    elif data == "cook_pick":
        await send_recipe(q)

    # ===== PRODUCT LIST =====
    elif data == "prod_list":
        if not PRODUCTS:
            await q.message.reply_text("Список пуст")
        else:
            txt = "\n".join([f"• {p}" for p in PRODUCTS])
            await q.message.reply_text(f"🛒 Продукты:\n{txt}")

# ===== MOVIE =====
async def send_movie(q):
    try:
        year = random.randint(1990, 2024)
        url = f"http://www.omdbapi.com/?apikey={OMDB_KEY}&s=movie&y={year}"
        data = requests.get(url).json()
        movies = data.get("Search", [])
        if not movies:
            await q.message.reply_text("Фильм не найден")
            return
        m = random.choice(movies)
        detail = requests.get(
            f"http://www.omdbapi.com/?apikey={OMDB_KEY}&i={m['imdbID']}&plot=full"
        ).json()
        text = f"🎬 {detail.get('Title')} ({detail.get('Year')})\n⭐ {detail.get('imdbRating')}\n\n{detail.get('Plot')}"
        poster = detail.get("Poster")
        if poster and poster != "N/A":
            await q.message.reply_photo(poster, caption=text)
        else:
            await q.message.reply_text(text)
    except:
        await q.message.reply_text("Ошибка фильма")

# ===== RECIPE =====
async def send_recipe(q):
    try:
        url = f"https://api.spoonacular.com/recipes/random?apiKey={SPOON_KEY}&number=1"
        data = requests.get(url).json()
        r = data["recipes"][0]
        title = r["title"]
        img = r["image"]
        ingredients = "\n".join([f"• {i['original']}" for i in r["extendedIngredients"]])
        text = f"🍳 {title}\n\n🧾 Ингредиенты:\n{ingredients}"
        await q.message.reply_photo(img, caption=text)
    except:
        await q.message.reply_text("Ошибка рецепта")

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
