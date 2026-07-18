"""Notification backends, selected via environment variables.

Priority: if TELEGRAM_BOT_TOKEN is set, use Telegram; else if NTFY_TOPIC is
set, use ntfy; else just print (useful for local dry runs).

    ntfy      NTFY_TOPIC              (required)
              NTFY_SERVER             (optional, default https://ntfy.sh)
    telegram  TELEGRAM_BOT_TOKEN      (required)
              TELEGRAM_CHAT_ID        (required)
"""
import os
import requests

TIMEOUT = 20


def _ntfy(title, body, url):
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    topic = os.environ["NTFY_TOPIC"]
    requests.post(
        f"{server}/{topic}",
        data=body.encode("utf-8"),
        headers={"Title": title, "Click": url, "Tags": "briefcase"},
        timeout=TIMEOUT,
    )


def _telegram(title, body, url):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat = os.environ["TELEGRAM_CHAT_ID"]
    text = f"*{title}*\n{body}\n{url}"
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": text, "parse_mode": "Markdown"},
        timeout=TIMEOUT,
    )


def send(company, job):
    title = f"New role at {company}"
    body = f"{job['title']}\n{job['location']}".strip()
    url = job["url"]
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        _telegram(title, body, url)
    elif os.environ.get("NTFY_TOPIC"):
        _ntfy(title, body, url)
    else:
        print(f"[no notifier configured] {title} | {body} | {url}")
