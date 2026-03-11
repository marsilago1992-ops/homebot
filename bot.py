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
    MessageHandler,
    filters,
)

# ========= ENV =========
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OMDB_KEY = os.getenv("OMDB_API_KEY")

if not TOKEN:
    raise RuntimeError("No TELEGRAM_BOT_TOKEN")
if not OMDB_KEY:
    raise RuntimeError("No OMDB_API_KEY")

logging.basicConfig(level=logging.INFO)

# ========= MEMORY =========
shopping_list = []
home_plans = []
reminders = []

# ========= KEYBOARDS =========
def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Продукты", callback_data="shop")],
        [InlineKeyboardButton("⏰ Напоминание", callback_data="remind")],
        [InlineKeyboardButton("🎬 Фильм", callback_data="movie")],
        [InlineKeyboardButton("🏠 Дом", callback_data="home")],
    ])

def back_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
    ])

# ========= MOVIES =========
def get_random_movie():
    try:
        r = requests.get(
            "http://www.omdbapi.com/",
            params={
                "apikey": OMDB_KEY,
                "s": random.choice("abcdefghijklmnopqrstuvwxyz"),
                "type": "movie"
            },
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
    except:
        return "Ошибка при запросе фильма"

# ========= HOME IDEAS =========
def random_home_idea():
    ideas = [
        "🧹 Генеральная уборка",
        "🗂 Разобрать шкафы",
        "🛠 Починить мелкие поломки",
        "💡 Сделать перестановку",
        "🛋 Обновить интерьер",
        "🌿 Уход за растениями",
        "🧺 Разобрать вещи",
        "📦 Организовать хранение",
        "🧼 Глубокая чистка кухни",
        "🚿 Чистка ванной",
        "💡 Улучшить освещение",
        "🖼 Повесить декор",
        "🔌 Проверить технику",
        "🛏 Обновить текстиль"
    ]
    return random.choice(ideas)

# ========= HANDLERS =========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍👩‍👧 Семейный ассистент готов",
        reply_markup=main_kb()
    )

# ========= BUTTONS =========
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d == "menu":
        await q.message.reply_text("Меню:", reply_markup=main_kb())

    # ===== SHOPPING =====
    elif d == "shop":
        text = "🛒 Список покупок:\n"
        if not shopping_list:
            text += "пусто"
        else:
            for i, item in enumerate(shopping_list, 1):
                text += f"{i}. {item}\n"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить", callback_data="shop_add")],
            [InlineKeyboardButton("🗑 Очистить", callback_data="shop_clear")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
        ])
        await q.message.reply_text(text, reply_markup=kb)

    elif d == "shop_add":
        context.user_data["mode"] = "shop_add"
        await q.message.reply_text("Напиши продукт:")

    elif d == "shop_clear":
        shopping_list.clear()
        await q.message.reply_text("Список очищен ✅", reply_markup=back_kb())

    # ===== REMINDERS =====
    elif d == "remind":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить", callback_data="rem_add")],
            [InlineKeyboardButton("📋 Список", callback_data="rem_list")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
        ])
        await q.message.reply_text("⏰ Напоминания:", reply_markup=kb)

    elif d == "rem_add":
        context.user_data["mode"] = "rem_text"
        await q.message.reply_text("Напиши текст напоминания:")

    elif d == "rem_list":
        if not reminders:
            await q.message.reply_text("Нет активных напоминаний", reply_markup=back_kb())
        else:
            text = "⏰ Напоминания:\n"
            for r in reminders:
                text += f"• {r}\n"
            await q.message.reply_text(text, reply_markup=back_kb())

    # ===== MOVIES =====
    elif d == "movie":
        await q.message.reply_text(get_random_movie(), parse_mode="Markdown")

    # ===== HOME =====
    elif d == "home":
        text = "🏠 Дом\n\n"
        if home_plans:
            text += "Твои планы:\n"
            for i, p in enumerate(home_plans, 1):
                text += f"{i}. {p}\n"
            text += "\n"

        text += f"💡 Идея: {random_home_idea()}"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить план", callback_data="home_add")],
            [InlineKeyboardButton("🗑 Очистить планы", callback_data="home_clear")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
        ])
        await q.message.reply_text(text, reply_markup=kb)

    elif d == "home_add":
        context.user_data["mode"] = "home_add"
        await q.message.reply_text("Напиши план по дому:")

    elif d == "home_clear":
        home_plans.clear()
        await q.message.reply_text("Планы очищены ✅", reply_markup=back_kb())

# ========= TEXT INPUT =========
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    text = update.message.text.strip()

    if mode == "shop_add":
        shopping_list.append(text)
        context.user_data.clear()
        await update.message.reply_text("Добавлено ✅", reply_markup=main_kb())

    elif mode == "home_add":
        home_plans.append(text)
        context.user_data.clear()
        await update.message.reply_text("План добавлен ✅", reply_markup=main_kb())

    elif mode == "rem_text":
        reminders.append(text)
        context.user_data.clear()
        await update.message.reply_text("Напоминание сохранено ✅", reply_markup=main_kb())

# ========= MAIN =========
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
