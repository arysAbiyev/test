import requests
import time
import logging
import threading
from datetime import datetime, timedelta, time as dt_time
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich import print as rprint
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext
import nest_asyncio
nest_asyncio.apply()  # Фикс для async в Colab/Jupyter

console = Console()
logging.basicConfig(filename='booking.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ================== ТВОИ ДАННЫЕ (захардкожены) ==================
TOKEN = "gtcwf654agufy25gsadh"
X_APP_SIGNATURE = "601d38b09459ae72d5e83a268bb932889bb194fd0fbc7804729df4bd76ff6063"
X_APP_CLIENT_CONTEXT = "HssF6Hs9XsToktU/:YmHDelYmJJamo31MhAyxX4uTBadoWdyknQHLhH/ispFpVgYTQcPk0LxzF55jtviPyIH07kWWiOclnQhM2f47MkSIxGXLdOUYf0VZcPM4Bww8vJQ8yDr1sPH/07VTfclhmzi8QXGmpUEkJ1wxMa0ZTJrQEogHP5LhIiKTJEM8yYuQIOIaWrN+gXMxQKp+GSgjgf8gIunCtclVR/bNlFcsAo7iVAbv99VE/w6b0mtyhti+Z+zd7883QpgBhFMwyLejHDy9zd6lpqnbCy0xan/7A1unqA+WZY0HGsNbl3vu/ly4FUrjDunzJU+doY+QwwFlRD9nBFoMMk7BiewLyOV1hxmQUFX2gVb9aVDTmN3RRfNRqfB3rmrp0m2L33OlotaImbWAsof5DD+XX6At9F79sHoAMFLDHVW0As8d0CZZDv9x5vJ44OPXjPQpp1txZ2ExG1ux0k7dkgrgAJwxFkwePHqy2z7gGlB7x33pci0jLhLBT15c"

LOCATION_ID = 521176
SERVICE_ID = 7790744
PHONE = "77064089616"
EMAIL = "abiev.arystanbek@gmail.com"
FULLNAME = "Арыстанбек"

# ================== TELEGRAM BOT SETTINGS ==================
TELEGRAM_BOT_TOKEN = "8464145238:AAFxA56ipw9i-iUxz9M4lFg3o49SKFDrvd0"
TELEGRAM_CHAT_ID = 902019383

# ================== УПРАВЛЯЕМЫЕ ПЕРЕМЕННЫЕ (через TG) ==================
# Времена по умолчанию
TARGET_TIMES = ["20:00", "21:00", "22:00"]

# Даты по умолчанию (ближайшие 3 дня)
def get_default_dates():
    today = datetime.now()
    return [
        today.strftime("%Y-%m-%d"),
        (today + timedelta(days=1)).strftime("%Y-%m-%d"),
        (today + timedelta(days=2)).strftime("%Y-%m-%d")
    ]

TARGET_DATES = get_default_dates()

# Только крытые корты
ALL_COURTS = [
    {"id": 1513587, "name": "Корт 1", "type": "Крытый"},
    {"id": 1521552, "name": "Корт 2", "type": "Крытый"},
    {"id": 1521553, "name": "Корт 3", "type": "Крытый"},
    {"id": 1521555, "name": "Корт 4", "type": "Крытый"},
    {"id": 1521557, "name": "Корт 5", "type": "Крытый"},
    {"id": 1521558, "name": "Корт 6", "type": "Крытый"},
    {"id": 1521559, "name": "Корт 7", "type": "Крытый"},
    {"id": 1521561, "name": "Корт 8", "type": "Крытый"},
]

# Состояние бота: вкл/выкл
is_running = True

# Таймер включения (None по умолчанию)
scheduled_start_time = None  # Формат: dt_time object, e.g., time(6, 58)

# =====================================================

BASE_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "ru-RU",
    "authorization": f"Bearer {TOKEN}",
    "content-type": "application/json",
    "origin": "https://b551098.alteg.io",
    "priority": "u=1, i",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Brave";v="145", "Chromium";v="145"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sec-gpc": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "x-altegio-application-name": "client.booking",
    "x-altegio-application-platform": "angular-18.2.13",
    "x-altegio-application-version": "196393.b70ad6ed",
}

BOOK_HEADERS = {
    **BASE_HEADERS,
    "x-app-client-context": X_APP_CLIENT_CONTEXT,
    "x-app-signature": X_APP_SIGNATURE,
    "referer": f"https://b551098.alteg.io/company/{LOCATION_ID}/create-record/record",
}

def create_session_with_retries():
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504, 429])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

session = create_session_with_retries()

def log(msg, level="info"):
    if level == "success":
        rprint(f"[green]✅ {msg}[/green]")
        logging.info(msg)
    elif level == "error":
        rprint(f"[red]❌ {msg}[/red]")
        logging.error(msg)
    elif level == "warning":
        rprint(f"[yellow]⚠️ {msg}[/yellow]")
        logging.warning(msg)
    else:
        rprint(f"[cyan]{msg}[/cyan]")
        logging.info(msg)

def send_telegram_message(message):
    """Отправляет сообщение в Telegram через API"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        log(f"Ошибка отправки в Telegram: {e}", "error")

def check_available_time_and_court(target_date, target_time):
    """Проверяет слот на дату/время, если доступен - проверяет available_staff через calculate. Возвращает (date, time, staff_id) или None"""
    # Шаг 1: Проверка timeslots
    url_timeslots = "https://b551098.alteg.io/api/v1/booking/search/timeslots"
    payload_timeslots = {
        "context": {"location_id": LOCATION_ID},
        "filter": {
            "date": target_date,
            "records": [{"attendance_service_items": []}]
        }
    }
    try:
        r = session.post(url_timeslots, json=payload_timeslots, headers=BASE_HEADERS, timeout=30)
        r.raise_for_status()
        slots = r.json().get("data", [])
        for slot in slots:
            if slot["attributes"]["time"] == target_time and slot["attributes"]["is_bookable"]:
                # Шаг 2: Проверка calculate для available_staff
                url_calculate = f"https://b551098.alteg.io/api/v1/booking/locations/{LOCATION_ID}/attendances/calculate"
                datetime_str = f"{target_date}T{target_time}:00+05:00"
                payload_calculate = {
                    "datetime": datetime_str,
                    "records": [{
                        "staff_id": -1,
                        "attendance_service_items": [{"type": "service", "id": SERVICE_ID}]
                    }]
                }
                r_calc = session.post(url_calculate, json=payload_calculate, headers=BASE_HEADERS, timeout=30)
                r_calc.raise_for_status()
                calc_data = r_calc.json()
                included = calc_data.get("included", [])
                for item in included:
                    if item["type"] == "booking_attendances_calculations_records":
                        available_staff_ids = item["attributes"].get("available_staff_ids", [])
                        # Фильтруем только крытые корты
                        covered_court_ids = [court["id"] for court in ALL_COURTS]
                        available_covered = [sid for sid in available_staff_ids if sid in covered_court_ids]
                        if available_covered:
                            # Выбираем первый доступный крытый корт
                            selected_staff_id = available_covered[0]
                            return target_date, target_time, selected_staff_id
        return None, None, None
    except Exception as e:
        log(f"Ошибка проверки слотов/кортов на {target_date} {target_time}: {str(e)}", "error")
        return None, None, None

def book_court(target_date, target_time, staff_id):
    url = f"https://b551098.alteg.io/api/v1/book_record/{LOCATION_ID}"
    datetime_str = f"{target_date}T{target_time}:00"

    # Находим имя корта для лога
    court_name = next((court["name"] for court in ALL_COURTS if court["id"] == staff_id), "Неизвестный корт")

    payload = {
        "fullname": FULLNAME,
        "surname": None,
        "patronymic": None,
        "phone": PHONE,
        "email": EMAIL,
        "comment": "",
        "custom_fields": {},
        "is_newsletter_allowed": None,
        "is_personal_data_processing_allowed": None,
        "appointments": [{
            "services": [SERVICE_ID],
            "staff_id": -1,
            "datetime": datetime_str,
            "chargeStatus": "",
            "custom_fields": {},
            "id": 0,
            "available_staff_ids": [staff_id]  # Подставляем выбранный корт
        }],
        "bookform_id": 551098,
        "isMobile": False,
        "notify_by_sms": "6",
        "referrer": "",
        "is_charge_required_priority": True,
        "is_support_charge": False,
        "appointments_charges": [{"id": 0, "services": [], "prepaid": []}],
        "redirect_url": f"https://b551098.alteg.io/company/{LOCATION_ID}/success-order/{{recordId}}/{{recordHash}}"
    }

    try:
        r = session.post(url, json=payload, headers=BOOK_HEADERS, timeout=30)
        if r.status_code in [200, 201]:
            resp = r.json()
            record = resp[0]["record"]
            record_id = record["id"]
            record_hash = resp[0]["record_hash"]
            success_url = f"https://b551098.alteg.io/company/{LOCATION_ID}/success-order/{record_id}/{record_hash}"

            log(f"ЗАБРОНИРОВАНО {court_name} НА {target_date} {target_time}! ID: {record_id}", "success")
            log(f"Ссылка: {success_url}", "success")
            rprint(f"\n[bold green]🎾 {court_name} ЗАБРОНИРОВАН НА {target_date} {target_time} 🎾[/bold green]")

            # Уведомление в Telegram
            send_telegram_message(f"🎾 УСПЕШНО ЗАБРОНИРОВАНО!\nКорт: {court_name}\nДата: {target_date} {target_time}\nID: {record_id}\nСсылка: {success_url}")

            return True
        else:
            log(f"Ошибка бронирования ({r.status_code}): {r.text[:400]}", "error")
            send_telegram_message(f"❌ Ошибка бронирования на {target_date} {target_time}: {r.text[:200]}")
            return False
    except Exception as e:
        log(f"Exception при бронировании: {e}", "error")
        send_telegram_message(f"❌ Exception при бронировании: {str(e)}")
        return False

# ====================== TELEGRAM BOT HANDLERS ======================
async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Привет! Я бот для управления бронированием кортов.\nКоманды:\n/settime <время1,время2> - Установить времена\n/setdates <дата1,дата2> - Установить даты (YYYY-MM-DD)\n/startbot - Включить бота\n/stopbot - Выключить бота\n/schedulestart <HH:MM> - Установить таймер включения\n/list - Показать настройки\n/status - Статус бота")

async def set_time(update: Update, context: CallbackContext) -> None:
    global TARGET_TIMES
    if context.args:
        new_times = context.args[0].split(',')
        TARGET_TIMES = [t.strip() for t in new_times if t.strip()]
        await update.message.reply_text(f"Времена обновлены: {', '.join(TARGET_TIMES)}")
        log(f"Обновлены времена: {TARGET_TIMES}", "info")
    else:
        await update.message.reply_text("Использование: /settime 20:00,21:00,22:00")

async def set_dates(update: Update, context: CallbackContext) -> None:
    global TARGET_DATES
    if context.args:
        new_dates = context.args[0].split(',')
        TARGET_DATES = [d.strip() for d in new_dates if d.strip()]
        await update.message.reply_text(f"Даты обновлены: {', '.join(TARGET_DATES)}")
        log(f"Обновлены даты: {TARGET_DATES}", "info")
    else:
        await update.message.reply_text("Использование: /setdates 2026-02-22,2026-02-23,2026-02-24")

async def start_bot(update: Update, context: CallbackContext) -> None:
    global is_running
    is_running = True
    await update.message.reply_text("Бот включен! Мониторинг запущен.")
    log("Бот включен через TG", "info")

async def stop_bot(update: Update, context: CallbackContext) -> None:
    global is_running
    is_running = False
    await update.message.reply_text("Бот выключен! Мониторинг остановлен.")
    log("Бот выключен через TG", "info")

async def schedule_start(update: Update, context: CallbackContext) -> None:
    global scheduled_start_time
    if context.args:
        try:
            start_time_str = context.args[0]
            scheduled_start_time = datetime.strptime(start_time_str, "%H:%M").time()
            await update.message.reply_text(f"Таймер включения установлен на {start_time_str}.")
            log(f"Таймер включения: {start_time_str}", "info")
        except ValueError:
            await update.message.reply_text("Неверный формат! Использование: /schedulestart 06:58")
    else:
        await update.message.reply_text("Использование: /schedulestart 06:58")

async def list_settings(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f"Текущие времена: {', '.join(TARGET_TIMES)}\nДаты: {', '.join(TARGET_DATES)}")

async def status(update: Update, context: CallbackContext) -> None:
    global is_running, scheduled_start_time
    status_msg = f"Статус: {'Включен' if is_running else 'Выключен'}\nТаймер: {scheduled_start_time.strftime('%H:%M') if scheduled_start_time else 'Не установлен'}"
    await update.message.reply_text(status_msg)

# Функция для мониторинга (теперь в потоке)
def monitoring_loop():
    global is_running, scheduled_start_time  # Объявляем глобальными

    with Live(console=console, refresh_per_second=4) as live:
        while True:
            # Проверка таймера включения
            if not is_running and scheduled_start_time:
                current_time = datetime.now().time()
                if current_time >= scheduled_start_time:
                    is_running = True
                    scheduled_start_time = None
                    log("Бот автоматически включен по таймеру", "info")
                    send_telegram_message("✅ Бот автоматически включен по таймеру!")

            if not is_running:
                time.sleep(60)  # Если выключен, проверяем реже
                continue

            now = datetime.now().strftime("%H:%M:%S")
            table = Table()
            table.add_column("Время", style="cyan")
            table.add_column("Статус", style="green")
            table.add_row(now, "Проверка слотов и кортов...")

            live.update(table)

            for target_date in TARGET_DATES:
                for target_time in TARGET_TIMES:
                    available_date, available_time, available_staff_id = check_available_time_and_court(target_date, target_time)
                    if available_date and available_time and available_staff_id:
                        log(f"✅ Слот {available_time} СВОБОДЕН на {available_date} на корте ID {available_staff_id}! Бронирую...", "warning")
                        book_court(available_date, available_time, available_staff_id)
                        # НЕ break - продолжаем мониторить все даты/времена/корты

            log("Цикл завершён, ждём 5 сек перед следующей проверкой...", "info")
            time.sleep(5)

def run_telegram_bot():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settime", set_time))
    app.add_handler(CommandHandler("setdates", set_dates))
    app.add_handler(CommandHandler("startbot", start_bot))
    app.add_handler(CommandHandler("stopbot", stop_bot))
    app.add_handler(CommandHandler("schedulestart", schedule_start))
    app.add_handler(CommandHandler("list", list_settings))
    app.add_handler(CommandHandler("status", status))

    app.run_polling()

# ====================== ЗАПУСК ======================
if __name__ == "__main__":
    rprint("[bold magenta]🚀 Altegio Tennis Booker v6.2 ЗАПУЩЕН (фикс global в monitoring)[/bold magenta]")
    rprint(f"Даты: {', '.join(TARGET_DATES)} (редактируй /setdates)")
    rprint(f"Ищем слоты: {', '.join(TARGET_TIMES)} (редактируй /settime)")
    rprint(f"Мониторим ТОЛЬКО КРЫТЫЕ корты: {len(ALL_COURTS)} шт")
    rprint("Управляй ботом через TG: /startbot, /stopbot, /schedulestart и др.\n")

    # Запуск мониторинга в отдельном потоке
    monitoring_thread = threading.Thread(target=monitoring_loop)
    monitoring_thread.start()

    # Telegram-бот в главном потоке
    run_telegram_bot()