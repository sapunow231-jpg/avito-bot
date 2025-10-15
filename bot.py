import os
import requests
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import schedule
import time

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 2))
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "samara")
DEFAULT_QUERY = os.getenv("DEFAULT_QUERY", "iphone")

bot = Bot(TOKEN)
sent_ads = set()

search_city = DEFAULT_CITY
search_query = DEFAULT_QUERY

def build_search_url(city: str, query: str) -> str:
    query_encoded = "+".join(query.strip().split())
    return f"https://www.avito.ru/{city}/telefony?p=1&q={query_encoded}"

def get_avito_ads() -> list:
    url = build_search_url(search_city, search_query)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка при запросе: {e}")
        return []
    soup = BeautifulSoup(response.text, "html.parser")
    ads = []
    for item in soup.select("div[data-marker='item']"):
        title_tag = item.select_one("h3")
        price_tag = item.select_one("span[data-marker='item-price']")
        link_tag = item.select_one("a[href]")
        if not title_tag or not price_tag or not link_tag:
            continue
        title = title_tag.text.strip()
        price = price_tag.text.strip()
        link = "https://www.avito.ru" + link_tag["href"]
        ad_id = link.split("/")[-1]
        ads.append({"id": ad_id, "text": f"{title}\n{price}\n{link}"})
    return ads

def send_new_ads():
    ads = get_avito_ads()
    new_count = 0
    for ad in ads:
        if ad["id"] not in sent_ads:
            try:
                bot.send_message(chat_id=CHAT_ID, text=ad["text"])
                sent_ads.add(ad["id"])
                new_count += 1
            except Exception as e:
                print(f"Ошибка при отправке: {e}")
    print(f"Отправлено новых объявлений: {new_count}")

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        f"Бот запущен! Проверка объявлений каждые {CHECK_INTERVAL} минуты(ы).\n"
        "Используйте команды:\n"
        "/city <город> — изменить город поиска\n"
        "/query <запрос> — изменить поисковый запрос"
    )

def set_city(update: Update, context: CallbackContext):
    global search_city, sent_ads
    if context.args:
        search_city = context.args[0].lower()
        sent_ads.clear()
        update.message.reply_text(f"Город поиска изменен на: {search_city}")
    else:
        update.message.reply_text("Укажите город после команды. Пример: /city kazan")

def set_query(update: Update, context: CallbackContext):
    global search_query, sent_ads
    if context.args:
        search_query = " ".join(context.args).lower()
        sent_ads.clear()
        update.message.reply_text(f"Поисковый запрос изменен на: {search_query}")
    else:
        update.message.reply_text("Укажите запрос после команды. Пример: /query ноутбук")

updater = Updater(TOKEN)
dp = updater.dispatcher
dp.add_handler(CommandHandler("start", start))
dp.add_handler(CommandHandler("city", set_city))
dp.add_handler(CommandHandler("query", set_query))

schedule.every(CHECK_INTERVAL).minutes.do(send_new_ads)

updater.start_polling()
print("Бот запущен и готов к работе!")

while True:
    schedule.run_pending()
    time.sleep(1)