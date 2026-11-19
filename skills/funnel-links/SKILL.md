---
name: funnel-links
description: >-
  Ссылки воронки: реф-ссылки бота с латинским кодом, пригласительные ссылки канала на каждый источник, UTM,
  необязательные короткие ссылки через собственный Shlink, проверка. Используй для «ссылка», «slug», «реф-ссылка»,
  «инвайт», «utm», «короткая ссылка», «переставь ссылку».
---

# Ссылки воронки

> Используете другой сервис, а не ChatPlace? Не отказывайтесь: набор адаптируется, см. `docs/ADAPTING.md` в корне репозитория.

Скрипты: `scripts/links.py` (строит и проверяет ссылки, без сети) и `scripts/shlink.sh` (необязательные короткие ссылки).

## Какие ссылки есть в воронке

| Ссылка | Откуда | Пример |
|---|---|---|
| Реф-ссылка бота | `ref_links_create` в ChatPlace | `https://t.me/your_bot?start=gayd_ig` |
| Инвайт канала | `tg_api.py invite` (скилл `telegram-bot-setup`) | `https://t.me/+AbCdEfGh` |
| Страница материала | ваш сайт или гайд | `https://example.com/guide?utm_source=telegram&utm_medium=bot&utm_campaign=gayd` |
| Короткая ссылка | необязательно: свой Shlink | `https://go.example.com/gayd-ig` |

## Правила

1. **Латинский код в `start`.** После `start=` Telegram принимает только латиницу, цифры, `-` и `_`; кириллица не проходит.
   `links.py slug "Гайд"` даёт `gayd`.
2. **Имя реф-ссылки: `<слово>_<источник>`** (`gayd_ig`, `gayd_bio`). Под разные источники – разные ссылки на одну воронку, у каждой свой `utm`.
3. **Инвайт канала – по одному на источник, имя = источник, `member_limit` 99999** (ссылки без лимита иногда ломаются).
4. **Ссылки только в кнопках**, не в тексте сообщения: так нет превью. Ссылочные кнопки без обёртки ChatPlace (`trackClicks: false`).
5. **UTM:** `utm_source` – платформа (instagram, telegram), `utm_medium` – место (dm, bot, bio, channel), `utm_campaign` – слово
   или продукт, `utm_content` – пост или повод.
6. **Одна проверка перед запуском:** откройте ссылку с чистого аккаунта; убедитесь, что ведёт туда, куда нужно.

## Команды

```bash
python3 scripts/links.py slug "Новый Урок"                       # novyy-urok
python3 scripts/links.py bot-link your_bot gayd_ig               # https://t.me/your_bot?start=gayd_ig
python3 scripts/links.py utm https://example.com/guide --source telegram --medium bot --campaign gayd
python3 scripts/links.py check "https://t.me/+AbCdEfGh"          # форма инвайта
```

## Короткие ссылки (необязательно)

Короткая ссылка нужна, если вы хотите менять адрес назначения, не трогая кнопки в уже запущенных воронках, и считать клики.
Для этого понадобится свой сервер Shlink (https://shlink.io, открытый проект) – в репозитории только клиент:

```bash
export SHLINK_BASE_URL=https://go.example.com   # ваш домен, не чужой
export SHLINK_API_KEY=...                        # ключ Shlink, в .env
scripts/shlink.sh create  gayd-ig "https://t.me/your_bot?start=gayd_ig" "Гайд, Instagram"
scripts/shlink.sh check   gayd-ig       # ожидается 302 и адрес назначения
scripts/shlink.sh repoint gayd-ig "https://t.me/your_bot?start=gayd_bio"
scripts/shlink.sh visits  gayd-ig 2026-01-31T12:00:00Z
```

Слаг – латиница, цифры, дефис. Не занимайте чужие слаги: сначала `get`. Эндпоинты REST v3 и формат запросов взяты
из рабочего скрипта авторов; сверьтесь с документацией вашей версии Shlink.

Без Shlink воронка работает: кнопка Instagram ведёт прямо на `https://t.me/your_bot?start=gayd_ig`.
