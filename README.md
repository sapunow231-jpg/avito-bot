# Telegram Avito Bot

Простой Telegram-бот для поиска объявлений на Авито.

## Установка

1. Вставьте ваш токен Telegram-бота в `avito_bot.py`:
```python
TELEGRAM_BOT_TOKEN = "8385878027:AAEz6A6koSZ3mwvZkvt4xMGvCkIfdvR7FWA"
```

2. Установите зависимости:
```bash
pip install -r requirements.txt
```

3. Запустите локально:
```bash
python avito_bot.py
```

## Размещение на Render

1. Создайте репозиторий на GitHub с этими файлами.
2. Подключите его к Render.com → New Web Service → выберите репозиторий.
3. Environment: Python
4. Build command: `pip install -r requirements.txt`
5. Start command: `python avito_bot.py`
6. Добавьте Environment Variable:
```
TELEGRAM_BOT_TOKEN=ваш_токен
```
7. Нажмите Deploy.
