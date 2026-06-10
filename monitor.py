"""Главный скрипт: ищет пары билетов (Пермь→Москва→Пермь) с зазором
MIN_STAY..MAX_STAY дней и шлёт в Telegram те, что заметно дешевле средней
цены такой пары.

Запуск: python monitor.py
Состояние (история типичной цены и уже отправленные алерты) хранится в
data/*.json и коммитится обратно в репозиторий.
"""

import json
import os
import statistics
from datetime import date, datetime, timezone

import aviasales
import config
import telegram


def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _days_between(d1: str, d2: str) -> int:
    return (date.fromisoformat(d2) - date.fromisoformat(d1)).days


def build_pairs(outbound: dict[str, dict], inbound: dict[str, dict]) -> list[dict]:
    """Все пары (туда, обратно) с зазором MIN_STAY..MAX_STAY дней."""
    pairs: list[dict] = []
    for out_date, out in sorted(outbound.items()):
        for ret_date, ret in inbound.items():
            stay = _days_between(out_date, ret_date)
            if config.MIN_STAY <= stay <= config.MAX_STAY:
                pairs.append({
                    "key": f"{out_date}|{ret_date}",
                    "out": out,
                    "ret": ret,
                    "stay": stay,
                    "total": out["price"] + ret["price"],
                })
    pairs.sort(key=lambda p: p["total"])
    return pairs


def _leg_line(label: str, leg: dict) -> str:
    arr = leg["arr_time"]
    if leg.get("arr_day_shift"):
        arr += f" (+{leg['arr_day_shift']})"
    transfers = leg["transfers"]
    t = "прямой" if transfers == 0 else f"пересадок: {transfers}"
    return (
        f"{label} <b>{leg['date']}</b>  ✈️ {leg['dep_time']} → 🛬 {arr}\n"
        f"   {leg['price']} {config.CURRENCY.upper()} · {t} · {leg['airline']}{leg['flight_number']}\n"
        f'   <a href="{leg["link"]}">билет на Aviasales</a>'
    )


def format_pair(pair: dict, typical: int) -> str:
    drop_pct = round((1 - pair["total"] / typical) * 100)
    return (
        f"💰 <b>Пара за {pair['total']} {config.CURRENCY.upper()}</b> "
        f"(обычно ~{typical} → дешевле на {drop_pct}%)\n"
        f"🗓 {pair['stay']} дней в Москве\n\n"
        f"{_leg_line('Туда:', pair['out'])}\n\n"
        f"{_leg_line('Обратно:', pair['ret'])}"
    )


def main() -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    history: list[dict] = load_json(config.HISTORY_FILE, [])
    if not isinstance(history, list):  # сброс старого формата
        history = []
    alerts: dict[str, int] = load_json(config.ALERTS_FILE, {})
    if not isinstance(alerts, dict):
        alerts = {}

    outbound = aviasales.fetch_oneway(config.ORIGIN, config.DESTINATION)
    inbound = aviasales.fetch_oneway(config.DESTINATION, config.ORIGIN)
    pairs = build_pairs(outbound, inbound)
    print(f"[{now}] Дат туда: {len(outbound)}, обратно: {len(inbound)}, пар: {len(pairs)}")

    if not pairs:
        print("Подходящих пар не найдено.")
        return

    totals = [p["total"] for p in pairs]
    typical = int(statistics.median(totals))
    threshold = typical * (1 - config.DROP_THRESHOLD)
    print(f"Средняя (медианная) цена пары: {typical}; порог алерта: <= {int(threshold)}")

    # Запоминаем «пульс» рынка для истории.
    history.append({"at": now, "typical": typical, "cheapest": totals[0]})

    # Собираем новые/подешевевшие пары. ВСЕ подходящие помечаем как виденные
    # (даже сверх лимита) — иначе на след. прогонах они будут слаться как «новые».
    fresh: list[dict] = []
    for pair in pairs:
        if pair["total"] > threshold:
            break  # pairs отсортированы по цене — дальше только дороже
        last = alerts.get(pair["key"])
        if last is None or pair["total"] < last:
            alerts[pair["key"]] = pair["total"]
            fresh.append(pair)

    # В уведомление — только самые дешёвые MAX_ALERTS из новых.
    messages: list[str] = []
    for pair in fresh[: config.MAX_ALERTS]:
        messages.append(format_pair(pair, typical))
        print(f"  ALERT {pair['key']}: {pair['total']} (-{round((1 - pair['total']/typical)*100)}%)")
    if len(fresh) > config.MAX_ALERTS:
        print(f"  (ещё {len(fresh) - config.MAX_ALERTS} подходящих пар скрыто, отмечены как виденные)")

    if messages:
        header = (
            f"🔥 <b>Дешёвые пары {config.ORIGIN} → {config.DESTINATION} → {config.ORIGIN}</b> "
            f"({config.MIN_STAY}–{config.MAX_STAY} дней в Москве)"
        )
        telegram.send_message(header + "\n\n" + "\n\n———\n\n".join(messages))
        print(f"Отправлено пар: {len(messages)}")
    else:
        print("Аномально дешёвых пар нет (либо уже отправляли).")

    save_json(config.HISTORY_FILE, history)
    save_json(config.ALERTS_FILE, alerts)


if __name__ == "__main__":
    main()
