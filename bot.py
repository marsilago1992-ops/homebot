import os
import logging
import asyncio
import random
import requests
import calendar
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

# ===== КАЛЕНДАРЬ ДЛЯ НАПОМИНАНИЙ =====
def create_calendar_kb(year=None, month=None):
    """Создает клавиатуру-календарь для выбора даты"""
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    
    # Заголовок с месяцем и годом
    keyboard = []
    
    # Кнопки навигации по месяцам
    nav_row = []
    nav_row.append(InlineKeyboardButton("◀️", callback_data=f"cal_prev:{year}:{month}"))
    nav_row.append(InlineKeyboardButton(f"{calendar.month_name[month]} {year}", callback_data="cal_ignore"))
    nav_row.append(InlineKeyboardButton("▶️", callback_data=f"cal_next:{year}:{month}"))
    keyboard.append(nav_row)
    
    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    keyboard.append([InlineKeyboardButton(day, callback_data="cal_ignore") for day in week_days])
    
    # Календарь
    month_calendar = calendar.monthcalendar(year, month)
    for week in month_calendar:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_ignore"))
            else:
                # Проверяем, что дата не в прошлом
                date = datetime(year, month, day)
                if date.date() < now.date():
                    row.append(InlineKeyboardButton(f"{day}", callback_data="cal_ignore"))
                else:
                    row.append(InlineKeyboardButton(f"{day}", callback_data=f"cal_date:{year}:{month}:{day}"))
        keyboard.append(row)
    
    # Кнопка "Сегодня" и "Отмена"
    keyboard.append([
        InlineKeyboardButton("📅 Сегодня", callback_data=f"cal_today"),
        InlineKeyboardButton("❌ Отмена", callback_data="back")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_time_kb():
    """Создает клавиатуру для выбора времени с шагом 1 час"""
    keyboard = []
    
    # Часы с шагом 1 час (0-23)
    hours_row1 = []
    hours_row2 = []
    hours_row3 = []
    
    for h in range(0, 24):
        btn = InlineKeyboardButton(f"{h:02d}:00", callback_data=f"time_hour:{h}")
        if h < 8:
            hours_row1.append(btn)
        elif h < 16:
            hours_row2.append(btn)
        else:
            hours_row3.append(btn)
    
    keyboard.append(hours_row1)
    keyboard.append(hours_row2)
    keyboard.append(hours_row3)
    
    # Кнопка "Текущее время"
    now = datetime.now()
    keyboard.append([
        InlineKeyboardButton(f"🕐 Сейчас ({now.hour:02d}:{now.minute:02d})", callback_data=f"time_now")
    ])
    
    # Навигация
    keyboard.append([
        InlineKeyboardButton("⬅️ Назад к дате", callback_data="rem_create"),
        InlineKeyboardButton("❌ Отмена", callback_data="back")
    ])
    
    return InlineKeyboardMarkup(keyboard)

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
        [InlineKeyboardButton("🍳 На завтрак", callback_data="cook_breakfast")],
        [InlineKeyboardButton("🍲 На обед", callback_data="cook_lunch"),
         InlineKeyboardButton("🍽️ На ужин", callback_data="cook_dinner")],
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

# ===== ФУНКЦИИ ДЛЯ ПЕРЕВОДА =====
def translate_to_russian(text):
    """Переводит текст с английского на русский используя Google Translate"""
    if not text or text == "N/A":
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "ru",
            "dt": "t",
            "q": text
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            result = response.json()
            translated = ""
            for sentence in result[0]:
                if sentence[0]:
                    translated += sentence[0]
            return translated
        return text
    except:
        return text

def translate_recipe_data(recipe_data):
    """Переводит основные поля рецепта на русский"""
    translated = {}
    
    # Название блюда
    if recipe_data.get('title'):
        translated['title'] = translate_to_russian(recipe_data['title'])
    else:
        translated['title'] = "Неизвестное блюдо"
    
    # Ингредиенты
    translated['ingredients'] = []
    for ingredient in recipe_data.get('extendedIngredients', []):
        if ingredient.get('original'):
            # Переводим название ингредиента
            translated_name = translate_to_russian(ingredient.get('name', ''))
            # Сохраняем оригинальное количество и единицы измерения
            original = ingredient.get('original', '')
            # Пытаемся перевести меру, если есть
            translated['ingredients'].append(f"• {original}")
    
    # Инструкции
    if recipe_data.get('instructions'):
        instructions = recipe_data['instructions']
        # Очищаем от HTML тегов
        import re
        instructions = re.sub('<[^<]+?>', '', instructions)
        translated['instructions'] = translate_to_russian(instructions)
    else:
        translated['instructions'] = None
    
    # Время приготовления
    if recipe_data.get('readyInMinutes'):
        translated['readyInMinutes'] = recipe_data['readyInMinutes']
    
    # Количество порций
    if recipe_data.get('servings'):
        translated['servings'] = recipe_data['servings']
    
    # Кухня (если есть)
    if recipe_data.get('cuisines') and recipe_data['cuisines']:
        cuisines = [translate_to_russian(cuisine) for cuisine in recipe_data['cuisines']]
        translated['cuisines'] = cuisines
    
    # Тип блюда (завтрак/обед/ужин)
    if recipe_data.get('dishTypes'):
        translated['dishTypes'] = recipe_data['dishTypes']
    
    # Изображение
    if recipe_data.get('image'):
        translated['image'] = recipe_data['image']
    
    return translated

def get_meal_type_description(meal_type):
    """Возвращает описание типа приема пищи"""
    descriptions = {
        "breakfast": "🍳 ЗАВТРАК",
        "lunch": "🍲 ОБЕД",
        "dinner": "🍽️ УЖИН"
    }
    return descriptions.get(meal_type, "🍳 БЛЮДО")

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
        await q.message.reply_text("🍳 Что приготовить?", reply_markup=cook_kb())
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
        context.user_data["mode"] = "REM_DATE"
        await q.message.reply_text(
            "Выберите дату для напоминания:",
            reply_markup=create_calendar_kb()
        )
        return
    
    # Обработка календаря
    elif data.startswith("cal_"):
        await handle_calendar(q, context, data)
        return
    
    # Обработка времени
    elif data.startswith("time_"):
        await handle_time(q, context, data)
        return

    elif data == "rem_list":
        if not REMINDERS:
            await q.message.reply_text("Напоминаний нет")
        else:
            # Сортируем напоминания по дате
            sorted_reminders = sorted(REMINDERS, key=lambda x: datetime.strptime(x.split(" — ")[0], "%Y-%m-%d %H:%M"))
            txt = "\n".join([f"• {r}" for r in sorted_reminders])
            await q.message.reply_text(f"⏰ Напоминания:\n{txt}")
        return

    elif data == "rem_del":
        REMINDERS.clear()
        await q.message.reply_text("Все напоминания удалены")
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
        await send_recipe(q, context, meal_type=None)
    elif data == "cook_breakfast":
        await send_recipe(q, context, meal_type="breakfast")
    elif data == "cook_lunch":
        await send_recipe(q, context, meal_type="lunch")
    elif data == "cook_dinner":
        await send_recipe(q, context, meal_type="dinner")

async def handle_calendar(q, context, data):
    """Обработка нажатий на календарь"""
    parts = data.split(":")
    
    if data.startswith("cal_prev"):
        year, month = int(parts[1]), int(parts[2])
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
        await q.message.edit_text(
            "Выберите дату для напоминания:",
            reply_markup=create_calendar_kb(year, month)
        )
    
    elif data.startswith("cal_next"):
        year, month = int(parts[1]), int(parts[2])
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
        await q.message.edit_text(
            "Выберите дату для напоминания:",
            reply_markup=create_calendar_kb(year, month)
        )
    
    elif data.startswith("cal_today"):
        now = datetime.now()
        context.user_data["reminder_date"] = now.date()
        await q.message.edit_text(
            f"Выбрана дата: {now.strftime('%Y-%m-%d')}\nТеперь выберите время:",
            reply_markup=create_time_kb()
        )
    
    elif data.startswith("cal_date"):
        year, month, day = int(parts[1]), int(parts[2]), int(parts[3])
        selected_date = datetime(year, month, day).date()
        context.user_data["reminder_date"] = selected_date
        await q.message.edit_text(
            f"Выбрана дата: {selected_date.strftime('%Y-%m-%d')}\nТеперь выберите время:",
            reply_markup=create_time_kb()
        )
    
    elif data == "cal_ignore":
        # Игнорируем нажатия на пустые кнопки
        pass

async def handle_time(q, context, data):
    """Обработка выбора времени"""
    parts = data.split(":")
    
    if data.startswith("time_hour"):
        hour = int(parts[1])
        date = context.user_data["reminder_date"]
        
        # Создаем datetime с выбранным часом и текущими минутами (00)
        reminder_datetime = datetime.combine(date, datetime.min.time().replace(hour=hour, minute=0))
        
        # Проверяем, что время не в прошлом
        now = datetime.now()
        if reminder_datetime < now:
            # Если выбран сегодняшний день и время уже прошло, предлагаем следующий час
            if reminder_datetime.date() == now.date():
                await q.message.edit_text(
                    f"❌ Выбранное время {hour:02d}:00 уже прошло.\n"
                    f"Пожалуйста, выберите другое время:",
                    reply_markup=create_time_kb()
                )
                return
        
        context.user_data["reminder_datetime"] = reminder_datetime
        
        # Показываем подтверждение и запрашиваем текст
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="time_confirm")],
            [InlineKeyboardButton("⬅️ Назад к дате", callback_data="rem_create")],
            [InlineKeyboardButton("❌ Отмена", callback_data="back")]
        ])
        
        await q.message.edit_text(
            f"✅ Выбрано:\n"
            f"📅 {reminder_datetime.strftime('%Y-%m-%d')}\n"
            f"⏰ {reminder_datetime.strftime('%H:%M')}\n\n"
            f"Теперь напишите текст напоминания:",
            reply_markup=keyboard
        )
        
        context.user_data["mode"] = "REM_TEXT"
    
    elif data.startswith("time_now"):
        now = datetime.now()
        date = context.user_data["reminder_date"]
        
        # Используем текущее время, но округляем минуты до ближайших 5 минут вперед
        current_hour = now.hour
        current_minute = now.minute
        
        # Если выбрана сегодняшняя дата и текущее время, добавляем 5 минут
        if date == now.date():
            reminder_datetime = now + timedelta(minutes=5)
        else:
            reminder_datetime = datetime.combine(date, datetime.min.time().replace(hour=current_hour, minute=current_minute))
        
        context.user_data["reminder_datetime"] = reminder_datetime
        
        # Показываем подтверждение и запрашиваем текст
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data="time_confirm")],
            [InlineKeyboardButton("⬅️ Назад к дате", callback_data="rem_create")],
            [InlineKeyboardButton("❌ Отмена", callback_data="back")]
        ])
        
        await q.message.edit_text(
            f"✅ Выбрано:\n"
            f"📅 {reminder_datetime.strftime('%Y-%m-%d')}\n"
            f"⏰ {reminder_datetime.strftime('%H:%M')}\n\n"
            f"Теперь напишите текст напоминания:",
            reply_markup=keyboard
        )
        
        context.user_data["mode"] = "REM_TEXT"

# ===== MOVIE =====
async def send_movie(q, context, mood=None, genre=None):
    if not OMDB_KEY:
        await q.message.reply_text("OMDB API ключ не настроен")
        return
    
    try:
        # Пробуем разные годы для поиска
        for attempt in range(3):
            year = random.randint(1990, 2024)
            
            # Формируем поисковый запрос
            search_params = {
                "apikey": OMDB_KEY,
                "s": "movie",
                "y": year,
                "type": "movie"
            }
            
            # Добавляем жанр если указан
            if genre:
                # Используем английское название жанра для поиска
                search_params["s"] = f"movie {genre}"
            
            response = requests.get("http://www.omdbapi.com/", params=search_params, timeout=10)
            data = response.json()
            
            if data.get("Response") == "True" and data.get("Search"):
                movies = data.get("Search", [])
                m = random.choice(movies)
                
                # Получаем детальную информацию
                detail_params = {
                    "apikey": OMDB_KEY,
                    "i": m['imdbID'],
                    "plot": "full"
                }
                detail_response = requests.get("http://www.omdbapi.com/", params=detail_params, timeout=10)
                detail = detail_response.json()
                
                if detail.get("Response") == "True":
                    # Переводим данные на русский
                    translated = translate_movie_data(detail)
                    
                    # Формируем текст на русском
                    title = translated.get('Title', 'Неизвестно')
                    year = translated.get('Year', 'Неизвестно')
                    rating = translated.get('imdbRating', 'N/A')
                    
                    # Переводим рейтинг
                    if rating != 'N/A':
                        rating_text = f"⭐ Рейтинг IMDb: {rating}"
                    else:
                        rating_text = "⭐ Рейтинг: Н/Д"
                    
                    # Формируем основную информацию
                    text_parts = [f"🎬 *{title}* ({year})", rating_text]
                    
                    # Добавляем жанр на русском
                    if detail.get('Genre') and detail['Genre'] != "N/A":
                        genres = detail['Genre'].split(', ')
                        russian_genres = [get_russian_genre(g) for g in genres]
                        text_parts.append(f"📺 Жанр: {', '.join(russian_genres)}")
                    
                    # Добавляем сюжет
                    if translated.get('Plot') and translated['Plot'] != "N/A":
                        plot = translated['Plot']
                        if len(plot) > 300:
                            plot = plot[:300] + "..."
                        text_parts.append(f"\n📝 {plot}")
                    
                    # Добавляем режиссера
                    if translated.get('Director') and translated['Director'] != "N/A":
                        text_parts.append(f"🎬 Режиссер: {translated['Director']}")
                    
                    # Добавляем актеров (первые 3)
                    if translated.get('Actors') and translated['Actors'] != "N/A":
                        actors = translated['Actors'].split(', ')[:3]
                        text_parts.append(f"👥 В ролях: {', '.join(actors)}")
                    
                    # Добавляем страну
                    if translated.get('Country') and translated['Country'] != "N/A":
                        text_parts.append(f"🌍 Страна: {translated['Country']}")
                    
                    # Добавляем продолжительность
                    if detail.get('Runtime') and detail['Runtime'] != "N/A":
                        text_parts.append(f"⏱️ {detail['Runtime']}")
                    
                    final_text = "\n".join(text_parts)
                    
                    poster = detail.get("Poster")
                    if poster and poster != "N/A":
                        await q.message.reply_photo(poster, caption=final_text, parse_mode='Markdown')
                    else:
                        await q.message.reply_text(final_text, parse_mode='Markdown')
                    return
        
        # Если не нашли фильмы
        await q.message.reply_text("Не удалось найти подходящий фильм. Попробуйте еще раз.")
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при запросе к OMDB API: {e}")
        await q.message.reply_text("Ошибка при получении информации о фильме. Проверьте подключение к интернету.")
    except Exception as e:
        logging.error(f"Неожиданная ошибка в send_movie: {e}")
        await q.message.reply_text("Произошла ошибка при поиске фильма")

def translate_movie_data(movie_data):
    """Переводит основные поля фильма на русский"""
    translated = movie_data.copy()
    
    # Поля для перевода
    fields_to_translate = {
        'Title': 'Название',
        'Plot': 'Сюжет',
        'Genre': 'Жанр',
        'Director': 'Режиссер',
        'Writer': 'Сценарист',
        'Actors': 'Актеры',
        'Country': 'Страна',
        'Language': 'Язык',
        'Awards': 'Награды',
        'Production': 'Производство',
        'Type': 'Тип'
    }
    
    # Переводим значения
    for eng_field, ru_field in fields_to_translate.items():
        if movie_data.get(eng_field) and movie_data[eng_field] != "N/A":
            translated[eng_field] = translate_to_russian(movie_data[eng_field])
    
    # Рейтинг не переводим, но добавляем русскую метку
    if movie_data.get('imdbRating') and movie_data['imdbRating'] != "N/A":
        translated['imdbRating'] = movie_data['imdbRating']
    
    # Год выпуска не переводим
    if movie_data.get('Year'):
        translated['Year'] = movie_data['Year']
    
    # Постер не переводим
    if movie_data.get('Poster'):
        translated['Poster'] = movie_data['Poster']
    
    return translated

def get_russian_genre(english_genre):
    """Переводит жанры фильмов на русский"""
    genres = {
        "Action": "Боевик",
        "Adventure": "Приключения",
        "Animation": "Мультфильм",
        "Biography": "Биография",
        "Comedy": "Комедия",
        "Crime": "Криминал",
        "Documentary": "Документальный",
        "Drama": "Драма",
        "Family": "Семейный",
        "Fantasy": "Фэнтези",
        "Film-Noir": "Нуар",
        "History": "История",
        "Horror": "Ужасы",
        "Music": "Музыка",
        "Musical": "Мюзикл",
        "Mystery": "Мистика",
        "Romance": "Мелодрама",
        "Sci-Fi": "Фантастика",
        "Sport": "Спорт",
        "Thriller": "Триллер",
        "War": "Военный",
        "Western": "Вестерн"
    }
    return genres.get(english_genre, english_genre)

# ===== RECIPE =====
async def send_recipe(q, context, meal_type=None):
    if not SPOON_KEY:
        await q.message.reply_text("Spoonacular API ключ не настроен")
        return
    
    try:
        # Формируем URL в зависимости от типа приема пищи
        url = f"https://api.spoonacular.com/recipes/random?apiKey={SPOON_KEY}&number=1"
        
        # Добавляем теги для типа приема пищи
        if meal_type:
            meal_tags = {
                "breakfast": "breakfast",
                "lunch": "lunch",
                "dinner": "dinner"
            }
            tag = meal_tags.get(meal_type)
            if tag:
                url += f"&tags={tag}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            await q.message.reply_text("Ошибка при получении рецепта. Проверьте API ключ.")
            return
            
        data = response.json()
        if not data.get("recipes"):
            await q.message.reply_text("Не удалось найти рецепт")
            return
            
        recipe = data["recipes"][0]
        
        # Переводим данные рецепта
        translated = translate_recipe_data(recipe)
        
        # Формируем текст на русском
        title = translated.get('title', 'Неизвестное блюдо')
        
        # Заголовок с типом приема пищи
        if meal_type:
            meal_header = get_meal_type_description(meal_type)
            text_parts = [f"{meal_header}\n🍳 *{title}*"]
        else:
            text_parts = [f"🍳 *{title}*"]
        
        # Время приготовления
        if translated.get('readyInMinutes'):
            text_parts.append(f"⏱️ Время приготовления: {translated['readyInMinutes']} минут")
        
        # Количество порций
        if translated.get('servings'):
            text_parts.append(f"👥 Порций: {translated['servings']}")
        
        # Кухня
        if translated.get('cuisines') and translated['cuisines']:
            cuisines_text = ", ".join(translated['cuisines'])
            text_parts.append(f"🍜 Кухня: {cuisines_text}")
        
        # Ингредиенты
        if translated.get('ingredients'):
            text_parts.append("\n🧾 *Ингредиенты:*")
            # Берем первые 10 ингредиентов, если их много
            ingredients = translated['ingredients'][:10]
            text_parts.extend(ingredients)
            if len(translated['ingredients']) > 10:
                text_parts.append(f"... и еще {len(translated['ingredients']) - 10} ингредиентов")
        
        # Инструкции
        if translated.get('instructions'):
            instructions = translated['instructions']
            # Ограничиваем длину
            if len(instructions) > 500:
                instructions = instructions[:500] + "..."
            text_parts.append(f"\n📝 *Приготовление:*\n{instructions}")
        
        final_text = "\n".join(text_parts)
        
        # Отправляем фото если есть
        if translated.get('image'):
            await q.message.reply_photo(translated['image'], caption=final_text, parse_mode='Markdown')
        else:
            await q.message.reply_text(final_text, parse_mode='Markdown')
            
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

    elif mode == "REM_TEXT":
        if "reminder_datetime" in context.user_data:
            dt = context.user_data["reminder_datetime"]
            
            # Проверяем, что дата не в прошлом
            if dt < datetime.now():
                await update.message.reply_text(
                    "❌ Нельзя создать напоминание на прошедшую дату.\n"
                    "Попробуйте снова через меню Напоминания."
                )
                context.user_data.clear()
                return

            reminder_text = f"{dt.strftime('%Y-%m-%d %H:%M')} — {txt}"
            REMINDERS.append(reminder_text)
            
            # Сортируем напоминания
            REMINDERS.sort(key=lambda x: datetime.strptime(x.split(" — ")[0], "%Y-%m-%d %H:%M"))

            await update.message.reply_text(
                f"✅ Напоминание создано:\n"
                f"📅 {dt.strftime('%Y-%m-%d %H:%M')}\n"
                f"📝 {txt}"
            )
        else:
            await update.message.reply_text("❌ Ошибка: не выбрана дата и время")
        
        context.user_data.clear()

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
