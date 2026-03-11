import os
import logging
import asyncio
import random
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
REMINDERS = []  # dict: {"text": str, "dt": datetime}
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
        [InlineKeyboardButton("✅ Куплено всё", callback_data="prod_done")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

# ===== REMINDERS =====
def rem_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Создать", callback_data="rem_create")],
        [InlineKeyboardButton("📋 Список", callback_data="rem_list")],
        [InlineKeyboardButton("❌ Удалить все", callback_data="rem_del")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

def days_kb():
    rows = []
    today = datetime.now().date()
    btns = []
    for i in range(7):
        d = today + timedelta(days=i)
        btns.append(InlineKeyboardButton(d.strftime("%d.%m"), callback_data=f"rem_day:{d.isoformat()}"))
        if len(btns) == 4:
            rows.append(btns)
            btns = []
    if btns:
        rows.append(btns)
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="rem")])
    return InlineKeyboardMarkup(rows)

def hours_kb():
    rows = []
    for h in [9, 12, 15, 18, 21]:
        rows.append([InlineKeyboardButton(f"{h:02d}:00", callback_data=f"rem_hour:{h:02d}:00")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="rem")])
    return InlineKeyboardMarkup(rows)

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
        [InlineKeyboardButton("❌ Удалить все", callback_data="home_del")],
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

    # ===== PRODUCTS =====
    elif data == "prod_add":
        context.user_data["mode"] = "PROD_ADD"
        await q.message.reply_text("Напиши продукт одним сообщением (можно тегать @человека)")

    elif data == "prod_list":
        if not PRODUCTS:
            await q.message.reply_text("Список пуст")
        else:
            txt = "\n".join([f"• {p}" for p in PRODUCTS])
            await q.message.reply_text(f"🛒 Список продуктов:\n{txt}")

    elif data == "prod_done":
        PRODUCTS.clear()
        await q.message.reply_text("Список очищен")

    # ===== REMINDERS =====
    elif data == "rem_create":
        context.user_data.clear()
        await q.message.reply_text("📅 Выбери дату:", reply_markup=days_kb())

    elif data.startswith("rem_day:"):
        day = data.split(":")[1]
        context.user_data["rem_day"] = day
        await q.message.reply_text("🕒 Выбери время:", reply_markup=hours_kb())

    elif data.startswith("rem_hour:"):
        hour = data.split(":")[1]
        day = context.user_data.get("rem_day")
        if not day:
            await q.message.reply_text("Ошибка даты")
            return
        dt = datetime.strptime(f"{day} {hour}", "%Y-%m-%d %H:%M")
        context.user_data["rem_dt"] = dt
        context.user_data["mode"] = "REM_TEXT"
        await q.message.reply_text("✏️ Напиши текст напоминания (можно тегать @человека)")

    elif data == "rem_list":
        if not REMINDERS:
            await q.message.reply_text("Напоминаний нет")
        else:
            lines = []
            for r in REMINDERS:
                lines.append(f"• {r['dt'].strftime('%d.%m %H:%M')} — {r['text']}")
            await q.message.reply_text("⏰ Напоминания:\n" + "\n".join(lines))

    elif data == "rem_del":
        REMINDERS.clear()
        await q.message.reply_text("Напоминания удалены")

    # ===== HOME =====
    elif data == "home_add":
        context.user_data["mode"] = "HOME_ADD"
        await q.message.reply_text("Напиши план по дому (можно тегать @человека)")

    elif data == "home_list":
        if not HOME_PLANS:
            await q.message.reply_text("Планов нет")
        else:
            txt = "\n".join([f"• {h}" for h in HOME_PLANS])
            await q.message.reply_text(f"🏠 Планы:\n{txt}")

    elif data == "home_del":
        HOME_PLANS.clear()
        await q.message.reply_text("Планы удалены")

    # ===== MOVIES =====
    elif data == "film_pick":
        await send_movie(q)

    # ===== COOK =====
    elif data == "cook_pick":
        await send_recipe(q)

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
    except Exception as e:
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

# ===== TEXT HANDLER =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    txt = update.message.text.strip()

    if mode == "PROD_ADD":
        PRODUCTS.append(txt)
        context.user_data.clear()
        await update.message.reply_text("Добавлено")

    elif mode == "REM_TEXT":
        dt = context.user_data.get("rem_dt")
        if not dt:
            await update.message.reply_text("Ошибка времени")
            return
        REMINDERS.append({"text": txt, "dt": dt})
        context.user_data.clear()
        await update.message.reply_text("Напоминание создано")

    elif mode == "HOME_ADD":
        HOME_PLANS.append(txt)
        context.user_data.clear()
        await update.message.reply_text("План добавлен")

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
