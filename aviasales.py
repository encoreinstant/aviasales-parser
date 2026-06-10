"""Запросы к официальному API Aviasales (Travelpayouts Data API, v3).

Тянем односторонние билеты по каждому направлению. Из двух направлений
(туда и обратно) в monitor.py собираются пары с нужным зазором по датам.
"""

from datetime import datetime, timedelta, timezone

import requests

import config


def _fetch_month(origin: str, dest: str, month: str) -> list[dict]:
    """Самые дешёвые односторонние билеты по каждой дате месяца ('YYYY-MM')."""
    params = {
        "origin": origin,
        "destination": dest,
        "departure_at": month,
        "currency": config.CURRENCY,
        "one_way": "true",
        "sorting": "price",
        "direct": "true" if config.DIRECT_ONLY else "false",
        "limit": 1000,
        "page": 1,
        "market": config.MARKET,
        "token": config.TRAVELPAYOUTS_TOKEN,
    }
    resp = requests.get(config.API_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    if not payload.get("success", True):
        raise RuntimeError(f"API вернул ошибку: {payload}")
    return payload.get("data", [])


def _city_offset(code: str) -> int | None:
    return config.CITY_UTC_OFFSET.get(code)


def _arrival_local(dep_iso: str, duration_min: int, dest_airport: str, dest_city: str):
    """Время прилёта в местном времени аэропорта назначения.

    Возвращает (строка 'HH:MM', смещение в днях относительно даты вылета).
    Если часовой пояс назначения неизвестен — показываем в поясе вылета.
    """
    dep = datetime.fromisoformat(dep_iso)  # aware, пояс вылета
    arrive = dep + timedelta(minutes=duration_min or 0)
    off = _city_offset(dest_airport)
    if off is None:
        off = _city_offset(dest_city)
    if off is not None:
        arrive = arrive.astimezone(timezone(timedelta(hours=off)))
    day_shift = (arrive.date() - dep.date()).days
    return arrive.strftime("%H:%M"), day_shift


def _normalize(items: list[dict]) -> dict[str, dict]:
    """Минимальная цена на каждую дату вылета + детали этого билета."""
    by_date: dict[str, dict] = {}
    for item in items:
        price = item.get("price")
        dep_iso = item.get("departure_at") or ""
        if not price or not dep_iso:
            continue
        if config.MAX_PRICE and price > config.MAX_PRICE:
            continue
        if config.DIRECT_ONLY and item.get("transfers", 0) != 0:
            continue
        date = dep_iso[:10]  # YYYY-MM-DD
        if date in by_date and price >= by_date[date]["price"]:
            continue

        dep = datetime.fromisoformat(dep_iso)
        arr_time, day_shift = _arrival_local(
            dep_iso,
            item.get("duration_to") or item.get("duration") or 0,
            item.get("destination_airport", ""),
            item.get("destination", ""),
        )
        link = item.get("link", "")
        full_link = config.AVIASALES_BASE_URL + link if link.startswith("/") else link

        by_date[date] = {
            "date": date,
            "price": price,
            "dep_time": dep.strftime("%H:%M"),
            "arr_time": arr_time,
            "arr_day_shift": day_shift,  # +1 если прилёт на след. день
            "transfers": item.get("transfers", 0),
            "airline": item.get("airline", ""),
            "flight_number": item.get("flight_number", ""),
            "link": full_link,
        }
    return by_date


def fetch_oneway(origin: str, dest: str) -> dict[str, dict]:
    """Словарь {дата вылета: дешёвый билет} по всем месяцам из конфига."""
    items: list[dict] = []
    for month in config.MONTHS:
        items.extend(_fetch_month(origin, dest, month))
    return _normalize(items)
