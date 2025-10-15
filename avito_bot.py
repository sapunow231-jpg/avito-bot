import asyncio
import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "8385878027:AAEz6A6koSZ3mwvZkvt4xMGvCkIfdvR7FWA"
BASE_URL = "https://www.avito.ru/samarskaya_oblast"
HEADERS = {"User-Agent": "Mozilla/5.0"}

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Хранилище запросов для "отслеживания"
watchlist = {}  # {user_id: {query: [ссылки_объявлений]}}


def get_avito_results(query: str, limit: int = 5):
    """Парсит первые limit объявлений по запросу в Самарской области"""
    url = f"{BASE_URL}?q={query.replace(' ', '+')}"
    r = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    items = []
    for ad in soup.select('div[itemtype="http://schema.org/Product"]')[:limit]:
        title = ad.select_one("h3")
        link_tag = ad.select_one("a")
        price_tag = ad.select_one('meta[itemprop="price"]')
        img_tag = ad.select_one("img")

        if not (title and link_tag):
            continue

        title_text = title.get_text(strip=True)
        link = "https://www.avito.ru" + link_tag["href"]
        price = price_tag["content"] + " ₽" if price_tag else "Цена не указана"
        img = img_tag["src"] if img_tag else None
        items.append({"title": title_text, "price": price, "link": link, "img": img})
    return items


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я бот для поиска объявлений на Авито (Самарская область).\n"
        "Отправь мне, что искать, например: `велосипед` или `iPhone 13`.",
        parse_mode="Markdown"
    )


@dp.message()
async def handle_query(message: types.Message):
    query = message.text.strip()
    results = get_avito_results(query)

    if not results:
        await message.answer("😔 Ничего не найдено.")
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="🔔 Следить за этим запросом", callback_data=f"watch:{query}")
    builder.adjust(1)

    await message.answer(f"🔎 Результаты по запросу: *{query}*", parse_mode="Markdown")

    for item in results:
        caption = f"**{item['title']}**\n{item['price']}\n👉 [Открыть объявление]({item['link']})"
        if item["img"]:
            await message.answer_photo(item["img"], caption=caption, parse_mode="Markdown")
        else:
            await message.answer(caption, parse_mode="Markdown")

    await message.answer("Хочешь следить за новыми объявлениями?", reply_markup=builder.as_markup())


@dp.callback_query(lambda c: c.data.startswith("watch:"))
async def watch_query(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    query = callback.data.split(":", 1)[1]

    if user_id not in watchlist:
        watchlist[user_id] = {}
    watchlist[user_id][query] = [item["link"] for item in get_avito_results(query, 10)]

    await callback.message.answer(f"✅ Теперь я слежу за запросом: *{query}*", parse_mode="Markdown")
    await callback.answer()


async def watch_loop():
    """Фоновая задача: проверяет новые объявления каждые 5 минут"""
    while True:
        await asyncio.sleep(300)
        for user_id, queries in watchlist.items():
            for query, old_links in queries.items():
                new_ads = get_avito_results(query, 10)
                new_items = [ad for ad in new_ads if ad["link"] not in old_links]

                if new_items:
                    text = f"🆕 Новые объявления по запросу *{query}*:"
                    await bot.send_message(user_id, text, parse_mode="Markdown")
                    for item in new_items:
                        caption = f"**{item['title']}**\n{item['price']}\n👉 [Смотреть объявление]({item['link']})"
                        if item["img"]:
                            await bot.send_photo(user_id, item["img"], caption=caption, parse_mode="Markdown")
                        else:
                            await bot.send_message(user_id, caption, parse_mode="Markdown")
                    # Обновляем сохранённые ссылки
                    watchlist[user_id][query] = [ad["link"] for ad in new_ads]


async def main():
    asyncio.create_task(watch_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
