import os
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, ContextTypes
import time

# Замените на свой Telegram Bot токен
TELEGRAM_TOKEN = '8043862059:AAEPhlASBOas956j3D0-ldloyIU3X8Ow4Uk'

# URL для получения курсов криптовалют (CoinGecko API)
COINGECKO_API_URL = 'https://api.coingecko.com/api/v3/simple/price'

# Установите пороги для оповещений
ALERT_THRESHOLDS = {
    'bitcoin': {'up': 0.15, 'down': 0.15},  # Порог 5% для BTC вверх/вниз
    'ethereum': {'up': 0.15, 'down': 0.15}  # Порог 7% для ETH вверх/вниз
}

# Путь к файлу для хранения данных о криптовалютах
CRYPTO_DATA_FILE = 'crypto_data.json'

# Глобальная переменная для хранения цен
initial_prices = {}

# Получаем текущую цену криптовалют с повторными попытками
def get_crypto_price(crypto_id, retries=3, delay=2):
    for _ in range(retries):
        try:
            response = requests.get(COINGECKO_API_URL, params={'ids': crypto_id, 'vs_currencies': 'usd'})
            data = response.json()
            if crypto_id in data and 'usd' in data[crypto_id]:
                return data[crypto_id]['usd']
            else:
                return None
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе к API: {e}. Попытка повторения.")
            time.sleep(delay)
    return None

# Загружаем данные о криптовалютах из файла
def load_crypto_data():
    if os.path.exists(CRYPTO_DATA_FILE):
        with open(CRYPTO_DATA_FILE, 'r') as file:
            return json.load(file)
    return {}

# Сохраняем данные о криптовалютах в файл
def save_crypto_data(data):
    with open(CRYPTO_DATA_FILE, 'w') as file:
        json.dump(data, file)

# Устанавливаем начальные цены из файла или с помощью API
async def set_initial_prices():
    global initial_prices
    initial_prices = load_crypto_data()
    for crypto_id in ALERT_THRESHOLDS.keys():
        if crypto_id not in initial_prices:
            price = get_crypto_price(crypto_id)
            if price is not None:
                initial_prices[crypto_id] = price
    save_crypto_data(initial_prices)

# Проверка изменений курса и отправка уведомлений
async def check_price_change(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    for crypto_id, thresholds in ALERT_THRESHOLDS.items():
        current_price = get_crypto_price(crypto_id)

        # Если не удалось получить цену, используем старую
        if current_price is None:
            current_price = initial_prices.get(crypto_id)
            if current_price is None:
                continue  # Если и старой цены нет, пропускаем криптовалюту

        initial_price = initial_prices.get(crypto_id)
        if initial_price is None:
            initial_price = current_price  # Если начальной цены нет, установим текущую как начальную

        price_change_percent = ((current_price - initial_price) / initial_price) * 100

        # Отправляем уведомление при достижении порога
        if price_change_percent >= thresholds['up']:
            await context.bot.send_message(job.chat_id, text=f'{crypto_id.capitalize()} вырос на {price_change_percent:.2f}%!')
            initial_prices[crypto_id] = current_price  # обновляем цену после уведомления
        elif price_change_percent <= -thresholds['down']:
            await context.bot.send_message(job.chat_id, text=f'{crypto_id.capitalize()} упал на {abs(price_change_percent):.2f}%!')
            initial_prices[crypto_id] = current_price  # обновляем цену после уведомления

    # Сохраняем обновленные данные в файл
    save_crypto_data(initial_prices)

# Команда /start для приветствия пользователя и отображения текущих курсов
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # Получаем текущие курсы
    prices_message = "Текущие курсы криптовалют:\n"
    for crypto_id in ALERT_THRESHOLDS.keys():
        price = initial_prices.get(crypto_id)
        
        # Если не удалось получить цену, используем старую
        if price is None:
            price = get_crypto_price(crypto_id)
        
        # Если нет данных (и старых данных нет), пропускаем криптовалюту
        if price is None:
            continue
        
        prices_message += f"{crypto_id.capitalize()}: ${price}\n"

    # Приветственное сообщение
    welcome_message = "Привет! Я бот для отслеживания курса криптовалют. Нажми кнопку ниже, чтобы начать мониторинг."
    await context.bot.send_message(chat_id, text=welcome_message)
    await context.bot.send_message(chat_id, text=prices_message)

    # Кнопка для начала мониторинга
    keyboard = [[InlineKeyboardButton("Запустить мониторинг 🚀", callback_data='start_monitoring')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Нажмите кнопку ниже, чтобы начать мониторинг.", reply_markup=reply_markup)


# Обработчик для кнопки "Запустить мониторинг"
async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.callback_query.message.chat_id
    await context.bot.send_message(chat_id, text="Мониторинг курса запущен! Я сообщу, если будут значительные изменения.")
    await set_initial_prices()  # Устанавливаем начальные цены
    # Инициализация JobQueue для отправки сообщений по расписанию
    context.job_queue.run_repeating(check_price_change, interval=60, first=0, chat_id=chat_id)

def main():
    # Инициализация приложения с JobQueue
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Регистрация обработчиков команд и сообщений
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start_monitoring, pattern='start_monitoring'))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
