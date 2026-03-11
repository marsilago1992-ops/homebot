import os
import random
import logging
import requests
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

# ========= ENV =========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OMDB_KEY = os.getenv("OMDB_API_KEY")
SPOON_KEY = os.getenv("SPOONACULAR_KEY")

if not TOKEN:
    raise RuntimeError("No TELEGRAM_BOT_TOKEN")
if not OMDB_KEY:
    raise RuntimeError("No OMDB_API_KEY")
if not SPOON_KEY:
    raise RuntimeError("No SPOONACULAR_KEY")

logging.basicConfig(level=logging.INFO)

# ========= KEYBOARDS =========
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Фильм", callback_data="movie")],
        [InlineKeyboardButton("🍳 Что приготовить", callback_data="cook")],
        [InlineKeyboardButton("🌆 Куда сходить", callback_data="go_out")],
        [InlineKeyboardButton("🏠 Чем заняться дома", callback_data="home_fun")],
        [InlineKeyboardButton("🧹 Дом", callback_data="home_tasks")],
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="home")]
    ])

# ========= MOVIES (OMDB) =========
def get_random_movie():
    letters = "abcdefghijklmnopqrstuvwxyz"
    letter = random.choice(letters)

    r = requests.get(
        "http://www.omdbapi.com/",
        params={"apikey": OMDB_KEY, "s": letter, "type": "movie"},
        timeout=10,
    ).json()

    if "Search" not in r:
        return "Не удалось найти фильм 😢"

    m = random.choice(r["Search"])

    info = requests.get(
        "http://www.omdbapi.com/",
        params={"apikey": OMDB_KEY, "i": m["imdbID"], "plot": "short"},
        timeout=10,
    ).json()

    return (
        f"🎬 *{info.get('Title')}* ({info.get('Year')})\n"
        f"⭐ IMDb: {info.get('imdbRating')}\n"
        f"🎭 Жанр: {info.get('Genre')}\n\n"
        f"📝 {info.get('Plot')}"
    )

# ========= COOKING (SPOONACULAR) =========
def get_recipe():
    r = requests.get(
        "https://api.spoonacular.com/recipes/random",
        params={"apiKey": SPOON_KEY, "number": 1},
        timeout=10,
    ).json()

    recipe = r["recipes"][0]

    ingredients = "\n".join(
        f"• {i['original']}" for i in recipe["extendedIngredients"]
    )

    return (
        f"🍽 *{recipe['title']}*\n\n"
        f"🧂 Ингредиенты:\n{ingredients}\n\n"
        f"📖 Инструкция:\n{recipe.get('instructions','—')}"
    )

# ========= GO OUT =========
def where_to_go():
    ideas = [
        "🌌 Съездить смотреть звёзды за город",
        "🎭 Иммерсивный театр или квест",
        "🍷 Дегустация вина / кофе",
        "🎨 Арт-пространство или выставка",
        "🧘 Йога на природе",
        "🚴 Веломаршрут по новым местам",
        "📸 Фото-прогулка по красивым локациям",
        "🎲 Антикафе с настолками",
        "🎤 Стендап или открытый микрофон",
        "🛶 Сап-борды или лодки",
        "🏎 Картинг",
        "🏹 Стрельба из лука",
        "🍣 Мастер-класс по готовке",
        "🎬 Кино под открытым небом",
        "🧖 Спа-день"
    ]
    return random.choice(ideas)

# ========= HOME FUN =========
def home_fun():
    ideas = [
        "🎬 Устроить тематический киновечер",
        "🍕 Приготовить новое блюдо вместе",
        "🧩 Большой пазл или LEGO",
        "🎮 Турнир по играм",
        "📚 Час саморазвития",
        "🧠 Настольные игры",
        "🎧 Подкасты + уборка",
        "🖼 Разобрать фотоархив",
        "💡 Сделать перестановку",
        "🛋 Обновить интерьер мелочами",
        "📝 Планирование целей",
        "🎨 Творческий вечер",
        "💪 Домашняя тренировка",
        "🧘 Медитация",
        "📖 Совместное чтение"
    ]
    return random.choice(ideas)

# ========= HOME TASKS =========
def home_tasks():
    tasks = [
        "🧹 Генеральная уборка комнаты",
        "🪟 Помыть окна",
        "🛁 Глубокая чистка ванной",
        "🍳 Разобрать кухонные шкафы",
        "🧺 Стирка и сортировка вещей",
        "👕 Разобрать гардероб",
        "🗂 Навести порядок в документах",
        "🔧 Починить мелкие поломки",
        "🌿 Уход за растениями",
        "🛒 Составить список покупок",
        "💡 Проверить лампочки и батарейки",
        "📦 Разобрать кладовку",
        "🧼 Дезинфекция поверхностей",
        "🛏 Смена постельного белья",
        "🧯 Проверить безопасность дома"
    ]
    return random.choice(tasks)

# ========= HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍👩‍👧 Семейный ассистент готов",
        reply_markup=main_kb()
    )

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "home":
        await q.message.reply_text("Меню:", reply_markup=main_kb())

    elif d == "movie":
        await q.message.reply_text(get_random_movie(), parse_mode="Markdown")

    elif d == "cook":
        await q.message.reply_text(get_recipe(), parse_mode="Markdown")

    elif d == "go_out":
        await q.message.reply_text(where_to_go(), reply_markup=back_kb())

    elif d == "home_fun":
        await q.message.reply_text(home_fun(), reply_markup=back_kb())

    elif d == "home_tasks":
        await q.message.reply_text(home_tasks(), reply_markup=back_kb())

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
