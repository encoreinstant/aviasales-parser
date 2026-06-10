"""Настройки мониторинга. Всё можно переопределить через переменные окружения
(в GitHub Actions они приходят из Secrets / workflow env)."""

import os


def _load_dotenv(path: str = ".env") -> None:
    """Минимальный загрузчик .env (без зависимостей). Не перетирает уже
    заданные переменные окружения — в Actions приоритет у Secrets."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


# --- Направление ---
ORIGIN = _env("ORIGIN", "PEE")          # Пермь
DESTINATION = _env("DESTINATION", "MOW")  # Москва (все аэропорты)

# Месяцы для мониторинга в формате YYYY-MM через запятую.
# По умолчанию — июль–август 2026.
MONTHS = [m.strip() for m in _env("MONTHS", "2026-07,2026-08").split(",") if m.strip()]

CURRENCY = _env("CURRENCY", "rub")
MARKET = _env("MARKET", "ru")

# --- Окно поездки (пара билетов туда+обратно) ---
# Сколько дней пробыть в Москве: ищем обратный билет через MIN..MAX дней.
MIN_STAY = int(_env("MIN_STAY", "7"))    # неделя
MAX_STAY = int(_env("MAX_STAY", "14"))   # две недели

# --- Логика «дёшево» ---
# Алертим пары, которые дешевле средней (медианной) цены такой пары на эту долю.
DROP_THRESHOLD = float(_env("DROP_THRESHOLD", "0.15"))  # 0.15 = на 15% дешевле среднего
# Максимум пар в одном уведомлении (самые дешёвые).
MAX_ALERTS = int(_env("MAX_ALERTS", "5"))
# Только прямые рейсы (без пересадок).
DIRECT_ONLY = _env("DIRECT_ONLY", "true").lower() == "true"
# Абсолютный потолок цены одного билета: дороже — игнор как мусор (0 = выключено).
MAX_PRICE = int(_env("MAX_PRICE", "0"))

# Часовые пояса аэропортов (UTC-смещение) для расчёта времени прилёта.
CITY_UTC_OFFSET = {
    "PEE": 5,                                  # Пермь
    "MOW": 3, "SVO": 3, "DME": 3, "VKO": 3, "ZIA": 3,  # Москва
}

# --- Секреты ---
TRAVELPAYOUTS_TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

# --- Файлы состояния (коммитятся обратно в репозиторий) ---
DATA_DIR = _env("DATA_DIR", "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
ALERTS_FILE = os.path.join(DATA_DIR, "alerts.json")

AVIASALES_BASE_URL = "https://www.aviasales.ru"
API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
