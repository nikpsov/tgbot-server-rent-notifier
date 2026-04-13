# Lightweight ServerPayBot

Легковесный Telegram-бот для учета арендованных серверов и напоминаний о платежах.

- Хранение данных: локальный `data/servers.json`
- Интерфейс: Telegram-команды + inline-кнопки
- Планировщик: ежедневная проверка в `09:00` (по `TZ`)
- Режим доступа: только `ADMIN_CHAT_ID`

## Возможности

- `/start` - справка по командам
- `/add` - пошаговое добавление сервера
- `/list` - список серверов с кнопками:
  - `✅ Отметить как оплаченный`
  - `🗑 Удалить`
- `/delete <id>` - удаление по ID

Логика оплаты:

- `monthly` = `+30` дней
- `custom` = `+custom_days`
- продление идет от текущего `next_payment_date`, а не от сегодняшней даты

## Требования

- Python `3.11+` (для локального запуска)
- или Docker + Docker Compose (для контейнера)

## Быстрый старт (Docker Compose)

1. Клонируйте репозиторий:

```bash
git clone https://github.com/nikpsov/tgbot-server-rent-notifier.git
cd tgbot-server-rent-notifier
```

2. Создайте `.env` в корне проекта:

```env
BOT_TOKEN=123456:telegram_bot_token
ADMIN_CHAT_ID=123456789
TZ=Europe/Moscow
```

3. Запустите контейнер:

```bash
docker compose up -d --build
```

4. Проверьте логи:

```bash
docker compose logs -f bot
```

5. Остановить:

```bash
docker compose down
```

Данные сохраняются в `./data/servers.json` (volume `./data:/app/data`).

## Локальный запуск (без Docker)

1. Установите зависимости:

```bash
python -m venv .venv
# Linux/Mac
source .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Установите переменные окружения:

```bash
# Linux/Mac
export BOT_TOKEN=123456:telegram_bot_token
export ADMIN_CHAT_ID=123456789
export TZ=Europe/Moscow
```

```powershell
# Windows PowerShell
$env:BOT_TOKEN="123456:telegram_bot_token"
$env:ADMIN_CHAT_ID="123456789"
$env:TZ="Europe/Moscow"
```

3. Запустите:

```bash
python bot.py
```

## Формат данных

Файл `data/servers.json`:

```json
{
  "server_1": {
    "name": "vpn.mydomain.com",
    "ip_address": "192.168.1.15",
    "next_payment_date": "2026-05-01",
    "period_type": "monthly",
    "custom_days": null,
    "reminder_days": 5
  },
  "server_2": {
    "name": "Storage Hetzner",
    "ip_address": "",
    "next_payment_date": "2026-12-15",
    "period_type": "custom",
    "custom_days": 45,
    "reminder_days": 5
  }
}
```

## Пошаговый сценарий `/add`

Бот запрашивает поля в таком порядке:

1. `name`
2. `ip_address` (`-` чтобы пропустить)
3. `next_payment_date` (`YYYY-MM-DD`)
4. `period_type` (`monthly` или `custom`)
5. `custom_days` (только для `custom`)
6. `reminder_days` (`-` = дефолт `5`)

## Уведомления и планировщик

- Ежедневно в `09:00` по `TZ` бот проверяет все записи.
- Если `today + reminder_days >= next_payment_date`, бот отправляет напоминание.
- Напоминания отправляются ежедневно до нажатия кнопки `✅ Отметить как оплаченный`.

## Переменные окружения

- `BOT_TOKEN` - токен Telegram-бота (обязательно)
- `ADMIN_CHAT_ID` - chat id администратора (обязательно)
- `TZ` - таймзона процесса (необязательно, дефолт `Europe/Moscow`)

## Структура проекта

```text
.
├── bot.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── data/
    └── servers.json
```

## Резервное копирование

Бэкап и перенос максимально простые: достаточно сохранить `data/servers.json`.
