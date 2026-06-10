"""Отправка уведомлений в Telegram через Bot API."""

import requests

import config


def send_message(text: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[telegram] Токен или chat_id не заданы — сообщение не отправлено:")
        print(text)
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        data={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
        },
        timeout=30,
    )
    resp.raise_for_status()
