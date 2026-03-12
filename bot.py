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
        [InlineKeyboardButton("➕ Создать", callback_data="rem_create")],
        [InlineKeyboardButton("📋 Список", callback_data="rem_list")],
        [InlineKeyboardButton("❌ Удалить", callback_data="rem_del")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")],
    ])

# ===== MOVIES =====
def film_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Случайный фильм", callback_data="film_pick")],
        [InlineKeyboardButton("😊 Легкое настроение", callback_data="film_mood:light"),
         InlineKeyboardButton("🤯 Думать", callback_data="film_mood:smart")],
        [InlineKeyboardButton("😂 Комедия", callback_data="film_genre:Comedy"),
         InlineKeyboardButton("🚀 Фантастика", callback_data="film_genre:Sci-Fi")],
        [InlineKeyboardButton("🔙 Назад", callback_data="menu")]
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
        return

    elif data == "prod":
        await q.message.reply_text("Продукты:", reply_markup=prod_kb())
        return

    elif data == "rem":
        await q.message.reply_text("Напоминания:", reply_markup=rem_kb())
        return

    elif data == "film":
        await q.message.reply_text("Фильмы:", reply_markup=film_kb())
        return

    elif data == "cook":
        await q.message.reply_text("Рецепты:", reply_markup=cook_kb())
        return

    elif data == "home":
        await q.message.reply_text("Дом:", reply_markup=home_kb())
        return

    
    # ===== PRODUCT ADD =====
    elif data == "prod_add":
        context.user_data["mode"] = "PROD_ADD"
        await q.message.reply_text("Напиши продукт одним сообщением")
        return

    elif data == "prod_done":
        if not PRODUCTS:
            await q.message.reply_text("Список пуст")
        else:
            PRODUCTS.clear()
            await q.message.reply_text("Список очищен")
        return

    # ===== PRODUCT LIST =====
    elif data == "prod_list":
        if not PRODUCTS:
            await q.message.reply_text("Список пуст")
        else:
            txt = "\n".join([f"• {p}" for p in PRODUCTS])
            await q.message.reply_text(f"🛒 Продукты:\n{txt}")
        return

    # ===== REMINDERS =====
    elif data == "rem_create":
        context.user_data["mode"] = "REM_CREATE"
        await q.message.reply_text("Напиши напоминание в формате: YYYY-MM-DD HH:MM текст")
        return

    elif data == "rem_list":
        if not REMINDERS:
            await q.message.reply_text("Напоминаний нет")
        else:
            txt = "\n".join([f"• {r}" for r in REMINDERS])
            await q.message.reply_text(f"⏰ Напоминания:\n{txt}")
        return

    elif data == "rem_del":
        REMINDERS.clear()
        await q.message.reply_text("Напоминания удалены")
        return

    # ===== HOME =====
    elif data == "home_add":
        context.user_data["mode"] = "HOME_ADD"
        await q.message.reply_text("Напиши план по дому")
        return

    elif data == "home_list":
        if not HOME_PLANS:
            await q.message.reply_text("Планов нет")
        else:
            txt = "\n".join([f"• {h}" for h in HOME_PLANS])
            await q.message.reply_text(f"🏠 Планы:\n{txt}")
        return

    elif data == "home_edit":
        await q.message.reply_text("Функция редактирования пока не реализована")
        return

    elif data == "home_del":
        HOME_PLANS.clear()
        await q.message.reply_text("Все планы удалены")
        return

    # ===== MOVIE PICK =====
    elif data == "film_pick":
        await send_movie(q, context)
    elif data.startswith("film_mood:"):
        mood = data.split(":")[1]
        await send_movie(q, context, mood=mood)
    elif data.startswith("film_genre:"):
        genre = data.split(":")[1]
        await send_movie(q, context, genre=genre)
    elif data == "menu":
        await q.message.reply_text("Меню:", reply_markup=menu_kb())

    # ===== COOK PICK =====
    elif data == "cook_pick":
        await send_recipe(q, context)


# ===== MOVIE =====
async def send_movie(q, context, mood=None, genre=None):
    if not OMDB_KEY:
        await q.message.reply_text("OMDB API ключ не настроен")
        return
    
    try:
        # Пробуем разные годы для поиска
        for _ in range(3):  # Делаем до 3 попыток найти фильм
            year = random.randint(1990, 2024)
            search_url = f"http://www.omdbapi.com/?apikey={OMDB_KEY}&s=movie&y={year}&type=movie"
            
            # Добавляем жанр если указан
            if genre:
                search_url += f"&genre={genre}"
            
            response = requests.get(search_url, timeout=10)
            data = response.json()
            
            if data.get("Response") == "True" and data.get("Search"):
                movies = data.get("Search", [])
                m = random.choice(movies)
                
                # Получаем детальную информацию
                detail_url = f"http://www.omdbapi.com/?apikey={OMDB_KEY}&i={m['imdbID']}&plot=full"
                detail_response = requests.get(detail_url, timeout=10)
                detail = detail_response.json()
                
                if detail.get("Response") == "True":
                    title = detail.get('Title', 'Неизвестно')
                    year = detail.get('Year', 'Неизвестно')
                    rating = detail.get('imdbRating', 'N/A')
                    plot = detail.get('Plot', 'Описание отсутствует')
                    
                    text = f"🎬 {title} ({year})\n⭐ {rating}\n\n{plot}"
                    
                    # Добавляем информацию о жанре если есть
                    if detail.get('Genre'):
                        text = f"🎬 {title} ({year})\n📺 {detail.get('Genre')}\n⭐ {rating}\n\n{plot}"
                    
                    poster = detail.get("Poster")
                    if poster and poster != "N/A":
                        await q.message.reply_photo(poster, caption=text)
                    else:
                        await q.message.reply_text(text)
                    return
        
        # Если не нашли фильмы
        await q.message.reply_text("Не удалось найти подходящий фильм. Попробуйте еще раз.")
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к OMDB API: {e}")
        await q.message.reply_text("Ошибка при получении информации о фильме. Проверьте подключение к интернету.")
    except Exception as e:
        logging.error(f"Неожиданная ошибка в send_movie: {e}")
        await q.message.reply_text("Произошла ошибка при поиске фильма")

# ===== RECIPE =====
async def send_recipe(q, context):
    if not SPOON_KEY:
        await q.message.reply_text("Spoonacular API ключ не настроен")
        return
    
    try:
        url = f"https://api.spoonacular.com/recipes/random?apiKey={SPOON_KEY}&number=1"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            await q.message.reply_text("Ошибка при получении рецепта. Проверьте API ключ.")
            return
            
        data = response.json()
        if not data.get("recipes"):
            await q.message.reply_text("Не удалось найти рецепт")
            return
            
        r = data["recipes"][0]
        title = r.get("title", "Неизвестное блюдо")
        img = r.get("image")
        
        # Форматируем ингредиенты
        ingredients = []
        for i in r.get("extendedIngredients", []):
            original = i.get("original", "")
            if original:
                ingredients.append(f"• {original}")
        
        if ingredients:
            ingredients_text = "\n".join(ingredients)
            text = f"🍳 {title}\n\n🧾 Ингредиенты:\n{ingredients_text}"
        else:
            text = f"🍳 {title}"
        
        # Добавляем инструкцию если есть
        if r.get("instructions"):
            # Ограничиваем длину инструкции
            instructions = r.get("instructions")[:500] + "..." if len(r.get("instructions", "")) > 500 else r.get("instructions")
            text += f"\n\n📝 Приготовление:\n{instructions}"
        
        if img:
            await q.message.reply_photo(img, caption=text)
        else:
            await q.message.reply_text(text)
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к Spoonacular API: {e}")
        await q.message.reply_text("Ошибка при получении рецепта. Проверьте подключение к интернету.")
    except Exception as e:
        logging.error(f"Неожиданная ошибка в send_recipe: {e}")
        await q.message.reply_text("Произошла ошибка при поиске рецепта")


# ===== TEXT HANDLER =====
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    txt = update.message.text.strip()

    if mode == "PROD_ADD":
        if txt:
            PRODUCTS.append(txt)
            context.user_data.clear()
            await update.message.reply_text(f"✅ Продукт '{txt}' добавлен в список")
        else:
            await update.message.reply_text("❌ Нельзя добавить пустой продукт")

    elif mode == "REM_CREATE":
        try:
            # Проверяем формат даты и времени
            if len(txt) < 16:
                await update.message.reply_text(
                    "❌ Слишком короткое сообщение.\n"
                    "Используй формат: YYYY-MM-DD HH:MM текст\n"
                    "Пример: 2024-12-31 18:00 Купить подарки"
                )
                return
                
            date_part = txt[:16]
            text_part = txt[16:].strip()
            
            if not text_part:
                await update.message.reply_text(
                    "❌ Добавьте текст напоминания после даты и времени"
                )
                return

            dt = datetime.strptime(date_part, "%Y-%m-%d %H:%M")
            
            # Проверяем, что дата не в прошлом
            if dt < datetime.now():
                await update.message.reply_text(
                    "❌ Нельзя создать напоминание на прошедшую дату"
                )
                return

            REMINDERS.append(f"{dt.strftime('%Y-%m-%d %H:%M')} — {text_part}")
            context.user_data.clear()

            await update.message.reply_text(
                f"✅ Напоминание создано:\n"
                f"📅 {dt.strftime('%Y-%m-%d %H:%M')}\n"
                f"📝 {text_part}"
            )

        except ValueError as e:
            await update.message.reply_text(
                "❌ Неверный формат даты и времени.\n"
                "Используй: YYYY-MM-DD HH:MM текст\n"
                "Пример: 2024-12-31 18:00 Купить подарки"
            )
        except Exception as e:
            logging.error(f"Ошибка при создании напоминания: {e}")
            await update.message.reply_text("❌ Произошла ошибка при создании напоминания")

    elif mode == "HOME_ADD":
        if txt:
            HOME_PLANS.append(txt)
            context.user_data.clear()
            await update.message.reply_text(f"✅ План '{txt}' добавлен")
        else:
            await update.message.reply_text("❌ Нельзя добавить пустой план")

    else:
        # Если не в специальном режиме, просто игнорируем или показываем меню
        await update.message.reply_text(
            "Используйте кнопки меню для навигации",
            reply_markup=menu_kb()
        )


# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    
    print("🤖 Бот запущен...")
    print(f"Токен: {TOKEN[:10]}...")
    print(f"OMDB ключ: {'✅' if OMDB_KEY else '❌'}")
    print(f"Spoonacular ключ: {'✅' if SPOON_KEY else '❌'}")
    
    app.run_polling()

if __name__ == "__main__":
    main()
