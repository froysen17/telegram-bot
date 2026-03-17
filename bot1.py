import logging
import asyncio
import os
import csv
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
import ssl
import aiohttp

# ---------- НАСТРОЙКИ ----------
TOKEN = "8525229498:AAHCQ_uQALiHkLJRA-Grq0OeQDzfREkgDNE"  # Твой токен
ADMIN_IDS = [1222259915]  # 👈 Твой ID
# --------------------------------

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Создаем переменные
bot = None
dp = None
storage = None

# Класс для хранения состояния анкеты
class Quiz(StatesGroup):
    waiting_for_age = State()
    waiting_for_interest = State()
    waiting_for_income = State()
    waiting_for_username = State()
    waiting_for_call = State()

# Функция для сохранения ответов в CSV для Excel 2010
def save_to_csv(user_id, first_name, last_name, username, data):
    filename = "responses.csv"
    file_exists = os.path.isfile(filename)
    
    try:
        # Для Excel 2010 используем кодировку cp1251
        with open(filename, 'a', newline='', encoding='cp1251', errors='ignore') as f:
            writer = csv.writer(f, delimiter=';')  # Точка с запятой для Excel
            
            # Если файл новый - пишем заголовки
            if not file_exists:
                writer.writerow(['Дата', 'ID', 'Имя', 'Фамилия', 'Username TG', 
                               'Возраст', 'Занятость', 'Доход', 'Telegram юзер', 'Созвон'])
            
            # Пишем данные
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                user_id,
                first_name,
                last_name,
                username,
                data.get('age', ''),
                data.get('interest', ''),
                data.get('income', ''),
                data.get('username', ''),
                data.get('call', '')
            ])
        
        print(f"✅ Данные сохранены в {filename}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при сохранении в CSV: {e}")
        return False

# Функция для создания сообщения админу
def create_admin_message(user_id, full_name, username, data):
    name_parts = full_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else "Не указано"
    
    user_link = f"tg://user?id={user_id}"
    
    message = (
        f"📋 Новая анкета заполнена!\n\n"
        f"🆔 ID: {user_id}\n"
        f"👤 Имя: {first_name}\n"
        f"📛 Фамилия: {last_name}\n"
        f"🧑‍💻 Юзернейм: @{username}\n"
        f"🔗 Ссылка: {user_link}\n\n"
        f"📊 Ответы:\n"
        f"1. Возраст: {data.get('age', 'Не указано')}\n"
        f"2. Занятость: {data.get('interest', 'Не указано')}\n"
        f"3. Месячный доход: {data.get('income', 'Не указано')}\n"
        f"4. Telegram юзер: {data.get('username', 'Не указано')}\n"
        f"5. Готовность к созвону: {data.get('call', 'Не указано')}"
    )
    
    return message

# Функция для отправки сообщения админу
async def notify_admin(message_text):
    try:
        await bot.send_message(ADMIN_IDS[0], message_text)
        print(f"✅ Сообщение отправлено админу")
    except Exception as e:
        print(f"❌ Ошибка отправки админу: {e}")

# ---------- INLINE КНОПКИ ----------
def get_age_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="14-16 лет", callback_data="age_14-16")],
        [InlineKeyboardButton(text="16-17 лет", callback_data="age_16-17")],
        [InlineKeyboardButton(text="18-19 лет", callback_data="age_18-19")],
        [InlineKeyboardButton(text="20+ лет", callback_data="age_20+")]
    ])

def get_interest_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Работаю в найме", callback_data="interest_job")],
        [InlineKeyboardButton(text="Учусь в школе / Унике", callback_data="interest_study")],
        [InlineKeyboardButton(text="Работаю на себя / фриланс", callback_data="interest_freelance")],
        [InlineKeyboardButton(text="Не работаю", callback_data="interest_unemployed")]
    ])

def get_income_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0 - 5.000", callback_data="income_0_5000")],
        [InlineKeyboardButton(text="5.000 - 10.000", callback_data="income_5000_10000")],
        [InlineKeyboardButton(text="10.000 - 20.000", callback_data="income_10000_20000")],
        [InlineKeyboardButton(text="20.000 - 30.000", callback_data="income_20000_30000")],
        [InlineKeyboardButton(text="30.000 - 50.000", callback_data="income_30000_50000")],
        [InlineKeyboardButton(text="50.000+", callback_data="income_50000+")]
    ])

def get_call_inline_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, газ", callback_data="call_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="call_no")]
    ])

# Функция для создания бота
async def create_bot():
    global bot
    
    # Пробуем разные способы подключения
    ways = [
        ("Обычное", lambda: Bot(token=TOKEN)),
        ("SSL отключен", lambda: Bot(
            token=TOKEN, 
            session=AiohttpSession(
                connector=aiohttp.TCPConnector(ssl=False)
            )
        )),
        ("Альтернативный API", lambda: Bot(
            token=TOKEN,
            session=AiohttpSession(
                api=TelegramAPIServer.from_base('https://api.telegram.org')
            )
        ))
    ]
    
    for name, creator in ways:
        try:
            print(f"🔄 Пробуем способ: {name}")
            bot = creator()
            me = await bot.get_me()
            print(f"✅ Успешно! Бот: @{me.username}")
            return bot
        except Exception as e:
            print(f"❌ {name} не сработал: {e}")
            continue
    
    print("❌ Все способы не сработали. Попробуй включить VPN")
    return None

# ---------- ОБРАБОТЧИКИ ----------
async def start_command(message: types.Message, state: FSMContext):
    user_name = message.from_user.first_name
    
    await message.answer(
        f"{user_name}, привет!⚡️\n\n"
        "На связи Антон!\n\n"
        "🎁Чтобы зайти на бесплатную диагностику нужно пройти небольшую анкету - буквально 2 минуты твоего времени\n\n"
        "Полетели к вопросам👇"
    )
    
    await message.answer(
        "1/5 Сколько тебе сейчас лет?",
        reply_markup=get_age_inline_keyboard()
    )
    await state.set_state(Quiz.waiting_for_age)

async def process_age(callback: types.CallbackQuery, state: FSMContext):
    age_map = {
        'age_14-16': '14-16 лет',
        'age_16-17': '16-17 лет',
        'age_18-19': '18-19 лет',
        'age_20+': '20+ лет'
    }
    
    await state.update_data(age=age_map.get(callback.data, 'Не указано'))
    await callback.message.delete()
    await callback.message.answer(
        "2/5 Чем ты сейчас интересуешься/занимаешься из направлений заработка?🔥",
        reply_markup=get_interest_inline_keyboard()
    )
    await state.set_state(Quiz.waiting_for_interest)
    await callback.answer()

async def process_interest(callback: types.CallbackQuery, state: FSMContext):
    interest_map = {
        'interest_job': 'Работаю в найме',
        'interest_study': 'Учусь в школе / Унике',
        'interest_freelance': 'Работаю на себя / фриланс',
        'interest_unemployed': 'Не работаю'
    }
    
    await state.update_data(interest=interest_map.get(callback.data, 'Не указано'))
    await callback.message.delete()
    await callback.message.answer(
        "3/5 Какой у тебя примерный месячный доход?",
        reply_markup=get_income_inline_keyboard()
    )
    await state.set_state(Quiz.waiting_for_income)
    await callback.answer()

async def process_income(callback: types.CallbackQuery, state: FSMContext):
    income_map = {
        'income_0_5000': '0 - 5.000',
        'income_5000_10000': '5.000 - 10.000',
        'income_10000_20000': '10.000 - 20.000',
        'income_20000_30000': '20.000 - 30.000',
        'income_30000_50000': '30.000 - 50.000',
        'income_50000+': '50.000+'
    }
    
    await state.update_data(income=income_map.get(callback.data, 'Не указано'))
    await callback.message.delete()
    await callback.message.answer(
        "4/5 Напиши свой юз в тг\n\nВ формате: @antoniobrando"
    )
    await state.set_state(Quiz.waiting_for_username)
    await callback.answer()

async def process_username(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text)
    await message.answer(
        "5/5 Готов ли ты выйти на созвон со мной или моей командой, чтобы мы провели тебя из твоей точки А в точку Б?",
        reply_markup=get_call_inline_keyboard()
    )
    await state.set_state(Quiz.waiting_for_call)

async def process_call(callback: types.CallbackQuery, state: FSMContext):
    call_map = {
        'call_yes': 'Да, газ',
        'call_no': 'Нет'
    }
    
    await state.update_data(call=call_map.get(callback.data, 'Не указано'))
    await callback.message.delete()
    
    # Получаем все данные
    user_data = await state.get_data()
    user_id = callback.from_user.id
    full_name = callback.from_user.full_name
    username = callback.from_user.username or "нет_юзернейма"
    
    # Разделяем имя и фамилию
    name_parts = full_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    # Сохраняем в CSV
    save_to_csv(user_id, first_name, last_name, username, user_data)
    
    # Отправляем админу
    admin_message = create_admin_message(user_id, full_name, username, user_data)
    await notify_admin(admin_message)
    
    # Подтверждение пользователю
    await callback.message.answer("Спасибо за ответы! Скоро свяжемся.")
    await state.clear()
    await callback.answer()

# ---------- ЗАПУСК ----------
async def main():
    global bot, dp, storage
    
    # Создаем бота
    bot = await create_bot()
    if not bot:
        return
    
    # Создаем диспетчер
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрируем обработчики
    dp.message.register(start_command, Command("start"))
    dp.message.register(process_username, Quiz.waiting_for_username)
    dp.callback_query.register(process_age, lambda c: c.data and c.data.startswith('age_'))
    dp.callback_query.register(process_interest, lambda c: c.data and c.data.startswith('interest_'))
    dp.callback_query.register(process_income, lambda c: c.data and c.data.startswith('income_'))
    dp.callback_query.register(process_call, lambda c: c.data and c.data.startswith('call_'))
    
    print("🚀 Бот запущен!")
    print(f"👤 Админ: {ADMIN_IDS[0]}")
    print(f"📁 Файл с ответами: responses.csv")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(main())
