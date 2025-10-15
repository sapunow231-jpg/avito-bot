import os
import logging
import threading
import time
from typing import List, Dict, Set
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urljoin

from telegram import Update, ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === НАСТРОЙКИ ===
TELEGRAM_BOT_TOKEN = "8385878027:AAEz6A6koSZ3mwvZkvt4xMGvCkIfdvR7FWA"
RESULTS_PER_SEARCH = 5
POLL_INTERVAL_SECONDS = 120
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "              "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"

subscriptions: Dict[str, Set[int]] = {}
seen_ads: Dict[str, Set[str]] = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_avito(query: str, max_results: int = 5) -> List[Dict]:
    base = "https://www.avito.ru"
    q = quote_plus(query)
    url = f"{base}/rossiya?q={q}"
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    results = []
    items = soup.select("[data-marker='item']")
    if not items:
        items = soup.select(".iva-item-root")

    for item in items:
        if len(results) >= max_results:
            break
        try:
            ad_id = item.get("data-item-id") or item.get("data-marker") or ""
            title_el = item.select_one("[itemprop='name']") or item.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else "без заголовка"
            price_el = item.select_one("[itemprop='price']") or item.select_one(".price")
            price = price_el.get_text(strip=True) if price_el else "—"
            a = item.select_one("a")
            link = urljoin(base, a['href']) if a and a.get('href') else None
            loc_el = item.select_one(".geo") or item.select_one("[data-marker='item-location']")
            location = loc_el.get_text(strip=True) if loc_el else ""
            results.append({
                "id": ad_id or link or title,
                "title": title,
                "price": price,
                "link": link or url,
                "location": location,
            })
        except Exception as e:
            logger.exception("Ошибка парсинга объявления: %s", e)
            continue
    return results

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я ищу объявления на Авито.
"
        "Используй /search <запрос> — чтобы найти сейчас.
"
        "Используй /subscribe <запрос> — получать новые объявления автоматически.
"
        "Используй /unsubscribe <запрос> — убрать подписку.
"
        "Используй /list — показать подписки."

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Использование: /search <запрос>")
        return
    await update.message.reply_text(f"Ищу: {query} ...")
    try:
        ads = search_avito(query, max_results=RESULTS_PER_SEARCH)
    except Exception as e:
        logger.exception("search error")
        await update.message.reply_text(f"Ошибка при поиске: {e}")
        return
    if not ads:
        await update.message.reply_text("Ничего не нашёл.")
        return
    for ad in ads:
        text = f"*{ad['title']}*
{ad['price']} — {ad['location']}
{ad['link']}"
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Использование: /subscribe <запрос>")
        return
    subs = subscriptions.setdefault(query.lower(), set())
    subs.add(chat_id)
    seen_ads.setdefault(query.lower(), set())
    await update.message.reply_text(f"Подписал(а) на '{query}'.")

async def unsubscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Использование: /unsubscribe <запрос>")
        return
    q = query.lower()
    if q in subscriptions and chat_id in subscriptions[q]:
        subscriptions[q].remove(chat_id)
        await update.message.reply_text(f"Отписал(а) от '{query}'.")
    else:
        await update.message.reply_text("У вас нет такой подписки.")

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    your = [q for q, chats in subscriptions.items() if chat_id in chats]
    if not your:
        await update.message.reply_text("У вас нет подписок.")
    else:
        await update.message.reply_text("Ваши подписки:
" + "
".join(f"- {q}" for q in your))

def polling_thread(application):
    logger.info("Запущен поток проверки подписок. Интервал %s сек", POLL_INTERVAL_SECONDS)
    while True:
        try:
            for query, chats in list(subscriptions.items()):
                if not chats:
                    continue
                try:
                    ads = search_avito(query, max_results=10)
                except Exception as e:
                    logger.exception("Ошибка при запросе для подписки %s: %s", query, e)
                    continue
                new = []
                seen_set = seen_ads.setdefault(query, set())
                for ad in ads:
                    if ad["id"] not in seen_set:
                        new.append(ad)
                        seen_set.add(ad["id"])
                if new:
                    for chat_id in list(chats):
                        for ad in new:
                            text = f"🔔 *Новый* — {ad['title']}
{ad['price']} — {ad['location']}
{ad['link']}"
                            try:
                                application.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
                            except Exception as e:
                                logger.exception("Не удалось отправить сообщение %s", e)
            time.sleep(POLL_INTERVAL_SECONDS)
        except Exception:
            logger.exception("Ошибка в polling_thread")

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    t = threading.Thread(target=polling_thread, args=(app,), daemon=True)
    t.start()
    logger.info("Запуск бота...")
    app.run_polling()

if __name__ == "__main__":
    main()
