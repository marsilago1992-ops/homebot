# ================== IMPORTS ==================
import os
import logging
import random
from datetime import datetime, timedelta
from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

# ================== UI STATE ==================
MODE = "mode"

# ================== KEYBOARDS ==================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👨‍👩‍👧 Семья", callback_data="menu:family")],
        [InlineKeyboardButton("🎯 Досуг", callback_data="menu:fun")],
        [InlineKeyboardButton("🍽 Питание", callback_data="menu:food")],
        [InlineKeyboardButton("🧰 Дом", callback_data="menu:homecare")],
        [InlineKeyboardButton("🛒 Покупки", callback_data="menu:shop")],
        [InlineKeyboardButton("⏰ Напоминания", callback_data="menu:remind")],
    ])

def back_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")]
    ])

# ===== Семья =====
def family_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить задачу", callback_data="family:add")],
        [InlineKeyboardButton("📋 Список задач", callback_data="family:list")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")]
    ])

# ===== Досуг =====
def fun_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Чем заняться дома", callback_data="fun:home")],
        [InlineKeyboardButton("🚶 Куда сходить", callback_data="fun:go")],
        [InlineKeyboardButton("🎬 Случайный фильм", callback_data="fun:movie")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")]
    ])

# ===== Питание =====
def food_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить блюдо", callback_data="food:add")],
        [InlineKeyboardButton("📅 Меню на неделю", callback_data="food:list")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")]
    ])

# ===== Дом =====
def homecare_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Добавить задачу", callback_data="homecare:add")],
        [InlineKeyboardButton("📋 Список", callback_data="homecare:list")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:home")]
    ])

# ================== DATA ==================
family_tasks = []
food_plan = []
home_tasks = []

fun_home = [
    "🎲 Настольные игры",
    "🎬 Семейный фильм",
    "🍕 Приготовить пиццу",
    "🎮 Поиграть в видеоигры",
    "📚 Почитать книгу",
]

fun_go = [
    "☕ Сходить в кофейню",
    "🌳 Прогулка в парке",
    "🎥 Кинотеатр",
    "🛍 Торговый центр",
    "🏞 Выезд на природу",
]

movies_online = [
    "🎬 Интерстеллар",
    "🎬 Начало",
    "🎬 Достать ножи",
    "🎬 Марсианин",
    "🎬 Ford против Ferrari",
]

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏠 Семейный ассистент готов!",
        reply_markup=main_menu()
    )

# ================== BUTTONS ==================
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # Главное меню
    if data == "menu:home":
        await q.message.reply_text("Главное меню:", reply_markup=main_menu())
        return

    # ===== СЕМЬЯ =====
    if data == "menu:family":
        await q.message.reply_text("👨‍👩‍👧 Семейные задачи:", reply_markup=family_kb())
        return

    if data == "family:add":
        context.user_data[MODE] = "FAMILY_ADD"
        await q.message.reply_text("Напиши задачу для семьи:", reply_markup=back_btn())
        return

    if data == "family:list":
        if not family_tasks:
            await q.message.reply_text("Задач нет ✅", reply_markup=family_kb())
            return
        text = "📋 Семейные задачи:\n" + "\n".join(f"• {t}" for t in family_tasks)
        await q.message.reply_text(text, reply_markup=family_kb())
        return

    # ===== ДОСУГ =====
    if data == "menu:fun":
        await q.message.reply_text("🎯 Досуг:", reply_markup=fun_kb())
        return

    if data == "fun:home":
        await q.message.reply_text(random.choice(fun_home), reply_markup=fun_kb())
        return

    if data == "fun:go":
        await q.message.reply_text(random.choice(fun_go), reply_markup=fun_kb())
        return

    if data == "fun:movie":
        await q.message.reply_text(random.choice(movies_online), reply_markup=fun_kb())
        return

    # ===== ПИТАНИЕ =====
    if data == "menu:food":
        await q.message.reply_text("🍽 План питания:", reply_markup=food_kb())
        return

    if data == "food:add":
        context.user_data[MODE] = "FOOD_ADD"
        await q.message.reply_text("Напиши блюдо:", reply_markup=back_btn())
        return

    if data == "food:list":
        if not food_plan:
            await q.message.reply_text("Меню пусто", reply_markup=food_kb())
            return
        text = "📅 Меню:\n" + "\n".join(f"• {m}" for m in food_plan)
        await q.message.reply_text(text, reply_markup=food_kb())
        return

    # ===== ДОМ =====
    if data == "menu:homecare":
        await q.message.reply_text("🧰 Обслуживание дома:", reply_markup=homecare_kb())
        return

    if data == "homecare:add":
        context.user_data[MODE] = "HOME_ADD"
        await q.message.reply_text("Напиши задачу по дому:", reply_markup=back_btn())
        return

    if data == "homecare:list":
        if not home_tasks:
            await q.message.reply_text("Задач нет", reply_markup=homecare_kb())
            return
        text = "🧰 Задачи по дому:\n" + "\n".join(f"• {t}" for t in home_tasks)
        await q.message.reply_text(text, reply_markup=homecare_kb())
        return

# ================== TEXT ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    mode = context.user_data.get(MODE)

    if mode == "FAMILY_ADD":
        family_tasks.append(text)
        context.user_data.clear()
        await update.message.reply_text("✅ Задача добавлена", reply_markup=family_kb())
        return

    if mode == "FOOD_ADD":
        food_plan.append(text)
        context.user_data.clear()
        await update.message.reply_text("✅ Блюдо добавлено", reply_markup=food_kb())
        return

    if mode == "HOME_ADD":
        home_tasks.append(text)
        context.user_data.clear()
        await update.message.reply_text("✅ Задача добавлена", reply_markup=homecare_kb())
        return

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
