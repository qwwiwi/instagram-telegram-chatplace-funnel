# Адаптация набора под другой сервис

Набор написан на примере ChatPlace, но схема воронки не зависит от сервиса:

```
слово в комментарии Instagram -> публичный ответ -> директ -> Telegram-бот -> проверка подписки на канал -> выдача материала
```

У ManyChat, SaleBot, SendPulse, Puzzlebot, Leadteh, BotHelp и других есть свои названия для тех же шагов. Если вы
используете не ChatPlace, прочитайте официальную документацию вашего сервиса, сопоставьте шаги по таблице ниже и
перепишите клиентские скрипты. Остальное (бот, канал, ссылки, баннеры, правила слова) работает без изменений.

## Как адаптировать: порядок работы

1. Найдите свой сервис в таблице ниже и откройте его документацию по ссылке. Если сервиса в таблице нет, найдите
   его официальную документацию сами и не придумывайте методы API, которых там нет.
2. Для каждого шага воронки найдите в документации понятие-аналог (раздел «Соответствие шагов»). Если в документации
   этого нет или страница недоступна, так и напишите: «не подтверждено», и уточните у человека.
3. Перепишите или адаптируйте клиентские скрипты (раздел «Что переписать, что оставить»).
4. Оставьте правила набора: ключи только в окружении (`.env`), воронки создаются на паузе, слово проверяется со второго
   аккаунта до публикации поста, пригласительные ссылки канала с `member_limit` 99999.
5. Проверьте воронку целиком на тестовом слове и только потом включайте.

## Сервисы и документация

«Не подтверждено» означает, что факт не найден на открытых страницах документации (страница закрыта, не открылась или
о факте там не сказано). Это не значит «нет»: проверьте вручную. Данные собраны 2026-11-19 по открытым страницам,
часть страниц читалась через резюме, а не дословно.

| Сервис | Документация | Instagram-комментарии | Instagram директ | Telegram-бот | Проверка подписки | API и вебхуки |
|---|---|---|---|---|---|---|
| Telegram Bot API (BotFather) | [bots/api](https://core.telegram.org/bots/api), [bots/features](https://core.telegram.org/bots/features) | нет (не Instagram) | нет | да | да: метод `getChatMember`, статусы creator/administrator/member/restricted/left/kicked; для канала бот должен быть админом (в документации сказано про «chat» в целом) | да: HTTP API и `setWebhook`; токен бота от BotFather в URL `/bot<token>/METHOD` |
| ManyChat | [api.manychat.com/swagger](https://api.manychat.com/swagger) (открывается, но Swagger UI рендерится скриптами и не прочитался) | не подтверждено | не подтверждено | не подтверждено | не подтверждено | не подтверждено (swagger открывается, эндпоинты не прочитаны) |
| SaleBot | [salebot.pro/docs](https://salebot.pro/docs), [API конструктора](https://salebot.pro/docs/rabota-s-api-api-konstruktora) | да: включить «Реагировать на комментарии», колбэки `client_wall_reply_new*` ([страница](https://salebot.pro/docs/chatbots-channels-instagram-comments)) | частично: ответ на комментарий в Direct возможен, но он «НЕ открывает 24-часовое окно»; страница про Direct не открывалась | да ([подключение бота к каналу/группе](https://salebot.pro/docs/chatbots-channels-telegram-group_chatbot)) | не подтверждено текстом: в разделе «Проверка подписок» только ссылка на видео | да: `https://chatter.salebot.pro/api/{api_key}/{action}`; Webhook URL в настройках проекта |
| SendPulse (чат-боты) | [API](https://sendpulse.com/integrations/api), [чат-боты](https://sendpulse.com/integrations/api/chatbot), [вебхуки](https://sendpulse.com/integrations/api/chatbot/webhooks) | да, по маркетинговой странице (post/live comments, keywords) ([страница](https://sendpulse.com/features/chatbot/instagram)); API-эндпоинтов для триггера: не подтверждено | да (там же: «Automated DMs and public replies») | да, через токен @BotFather ([страница](https://sendpulse.com/features/chatbot/telegram)) | частично: заявлено «боты могут проверять членство в группе/канале»; API-метод: не подтверждено | да: REST `https://api.sendpulse.com` и вебхуки событий бота (в интерфейсе: Bot Settings -> Webhooks; создание через API: не подтверждено) |
| Puzzlebot | [API](https://puzzle.bot/help/dokumentaciya-po-api), [входящие запросы](https://puzzle.bot/help/vhodyaschie-zaprosy-api), [подписки на события](https://puzzle.bot/help/podpiski-na-sobytiya) | нет: на страницах помощи и тарифов только Telegram и MAX | не подтверждено (на открытых страницах Instagram не упомянут) | да | да ([проверка подписки](https://puzzle.bot/help/proverka-podpiski)): условие «Наличие подписки», бот должен быть админом канала | да: `https://api.puzzlebot.top/?token=<токен>`, лимит 120 запросов в минуту; исходящие вебхуки через «Подписки на события» |
| Leadteh | [docs.leadteh.ru](https://docs.leadteh.ru/), [основы API](https://docs.leadteh.ru/rabota-s-api/osnovy/) | не подтверждено (в документации нет раздела по Instagram; каналы на главной: Telegram, MAX, ВК, WhatsApp) | не подтверждено | да ([события Telegram](https://docs.leadteh.ru/sobytiya/sobytiya-telegram/)) | не подтверждено | частично: API `https://app.leadteh.ru/api/v1/method`, лимит 2 запроса в секунду; «Входящий вебхук» упомянут на главной, отдельной страницы нет |
| BotHelp | [API](https://help.bothelp.io/api-bothelp/), [реакция на комментарии Instagram](https://help.bothelp.io/reakcziya-na-kommentarii-v-instagram/), [группы и каналы в Telegram](https://help.bothelp.io/rabota-s-gruppami-i-kanalami-v-telegram/) | да: «Реакция на комментарий Instagram» (любой / содержит / соответствует) | частично: после комментария бот сам не запускается, в директ приходит кнопка «Запустить бот», которую подписчик должен нажать; видна только в мобильном приложении | да | да: шаг «Условие» -> «Пользователь в группе/канале», бот должен быть админом | да: API `https://api.bothelp.io` (список методов в [swagger](https://main.bothelp.io/swagger), не открывался); вебхук упомянут, страница не открывалась |
| Instagram Messaging API (Meta, официально) | [Messaging API](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api), [вебхуки](https://developers.facebook.com/documentation/instagram-platform/webhooks), [private replies](https://developers.facebook.com/documentation/instagram-platform/private-replies) | да: поле вебхука `comments` (scope `instagram_business_manage_comments`) | да: `POST graph.instagram.com/<IG_ID>/messages`; писать можно только после первого сообщения пользователя (окно 24 часа); private reply на комментарий: одно сообщение в течение 7 дней | нет (не Telegram) | нет | да: Graph API и вебхуки |
| Botmother (дополнительно) | [комментарии Instagram](https://botmother.com/docs/comment-instagram), [проверка подписки в Telegram](https://botmother.com/docs/checking-channel-group-subscriptions-on-telegram) | да: событие «Comment (Insta)», фильтр по слову или regexp | частично: если пользователь не писал более 24 часов, приходит только текст в message requests | да | да: через `getChatMember` (Native request), бот админ | не подтверждено (страница api-requests не открывалась) |
| Chatfuel (дополнительно) | [public-api](https://chatfuel.com/docs/public-api) | заявлено на главной («Turn viral Reels comments into DMs»); статьи документации не открывались | заявлено на главной | не подтверждено | не подтверждено | частично: GraphQL API (`/docs/public-api`), базовый URL и вебхуки не подтверждены |
| Senler (дополнительно) | [help.senler.ru: API](https://help.senler.ru/senler/help/razrabotchikam/api) | не подтверждено (каналы: ВК, Telegram, MAX) | не подтверждено | да | не подтверждено | да: POST `https://senler.ru/api/METHOD_NAME`; раздел WebHook API есть, но не открывался |

Smartbot Pro в таблицу не включён: сайт не найден (`smartbot.pro` оказался заглушкой продажи домена, документации по
этому адресу нет). Если у сервиса другой адрес, добавьте строку по официальной документации.

Не используйте как документацию: `docs.bothelp.io` (JSON-ошибка), `puzzle.bot/docs` (404), `leadteh.ru/api` и
`leadteh.ru/docs` (404).

### Авторизация и бесплатный тариф

| Сервис | Авторизация | Бесплатный тариф |
|---|---|---|
| Telegram Bot API | токен бота от BotFather | не подтверждено (в документации про цену API ничего нет) |
| ManyChat | не подтверждено | не подтверждено (`manychat.com` и `help.manychat.com` отвечают 403) |
| SaleBot | API-ключ в пути URL | да: 0 руб., до 50 сообщений в сутки; в бесплатном тарифе «API конструктора» отмечен прочерком ([тарифы](https://salebot.pro/docs/nashi-uslugi-tarify)) |
| SendPulse | API-ключ или OAuth2 client_credentials (`/oauth/access_token`, токен 1 час), заголовок `Authorization: Bearer` | да: Free, 3 бота, до 500 подписчиков, «Limited API»; «API and webhooks» включены с тарифа Standard ([тарифы](https://sendpulse.com/pricing/messengers)) |
| Puzzlebot | токен API проекта (Интеграции -> Входящие запросы; отличается от токена BotFather) | да: 0 руб., с рекламой, 50 пользователей, 1 проект ([цены](https://puzzle.bot/price)) |
| Leadteh | `api_token` в GET-параметре | бессрочного нет: 7 дней бесплатно, потом от 1390 руб./мес ([сайт](https://leadteh.ru/)); бессрочный бесплатный тариф не подтверждён |
| BotHelp | OAuth2 client_credentials (`https://oauth.bothelp.io/oauth2/token`), `Authorization: Bearer`, токен 1 час | частично: Free заявлен как 14 дней trial, до 3000 подписчиков, без Instagram в списке; Instagram и «API and Integrations» перечислены только в Pro ([bothelp.io](https://bothelp.io)) |
| Meta Instagram Messaging API | Instagram User access token (Instagram Login) или Page token (Facebook Login); для чужих аккаунтов нужны Advanced Access, App Review и Business Verification | не подтверждено (цена на прочитанных страницах не указана) |
| Botmother | не подтверждено | да: «Free Test plan with no time limit», платные от 49 долларов в месяц (главная страница; страница тарифов не открывалась) |
| Chatfuel | токены (тип не подтверждён) | не подтверждено (на главной «Try for free», условия не прочитаны) |
| Senler | `access_token` | да: 50 сообщений в сутки бесплатно |

Цены с разных страниц указаны в разных валютах и на разные даты. Ограничение для России: BotHelp и Leadteh на своих
страницах помечают Meta как запрещённую организацию. Юридическую сторону мы не проверяли, оцените её сами.

## Соответствие шагов воронки

| Шаг воронки | Как это сделано в ChatPlace (эталон) | Что искать в документации другого сервиса |
|---|---|---|
| Кодовое слово | триггер «комментарий содержит слово» и «сообщение равно слову», несколько написаний на одну воронку | триггер по комментарию Instagram (содержит / равно / regexp), триггер по входящему сообщению; число допустимых написаний на один триггер |
| Публичный ответ под комментарием | ротация коротких фраз в правиле комментария | ответ на комментарий (публичный) или отправка в директ из комментария (private reply); ограничения окна (24 часа, 7 дней) |
| Сообщение в директ | директ 1: баннер, крючок, кнопка; директ 2: «Лови гайд» и кнопка-ссылка | шаг «отправить сообщение» в Instagram, кнопки в Instagram, лимит кнопок; можно ли писать первым после комментария |
| Кнопка | `button_link` – ссылка на бота; в боте кнопки «Подписаться на канал» и «Получить гайд» | типы кнопок канала (ссылка, быстрый ответ, callback), правила обёртки ссылок сервисом |
| Метка | метки на контактах и реф-ссылки с кодом, по ним видно источник | теги, атрибуты, поля пользователя, UTM; как посчитать источник |
| Проверка подписки | шаблон воронки в боте: «подписан на канал?» да / нет, ответ «Пока не вижу подписки» | условие «пользователь в канале» в конструкторе или вызов `getChatMember` из Bot API; бот должен быть админом канала |
| Выдача | баннер выдачи и кнопка на материал (лид-магнит) | шаг «отправить сообщение» после условия, ссылка на материал |
| Реф-ссылка бота | `https://t.me/your_bot?start=gayd_ig`, на каждое слово своя | параметр `start` в ссылке бота и то, как сервис отдаёт его в сценарий |
| Здоровье и аналитика | `chatplace.py health`, `chatplace.py analytics` | статистика сценариев или события через API и вебхуки; вступления по имени пригласительной ссылки видны в Telegram |

Пример для чистого Telegram Bot API: триггеров Instagram у него нет, поэтому первая половина воронки (комментарий и
директ) нужна другой платформы или Meta Messaging API, а вторая половина (бот, подписка через `getChatMember`, выдача)
пишется кодом вашего бота. Готового обработчика бота в этом наборе нет.

## Что переписать, что оставить

Переписать под API вашего сервиса (это клиент ChatPlace и скрипты поверх него):

| Файл | Что делает сейчас |
|---|---|
| `skills/chatplace-funnels/scripts/cp_client.py` | HTTP-клиент ChatPlace (MCP-инструменты) |
| `skills/chatplace-funnels/scripts/chatplace.py` | команды: bots, media-upload, status, backup, health, analytics |
| `skills/chatplace-funnels/scripts/codeword.py` | создание воронки кодового слова из JSON |
| `skills/chatplace-funnels/scripts/gate.py` | воронка в боте с проверкой подписки |
| `skills/chatplace-funnels/references/mcp-tools.md` | справочник инструментов ChatPlace (замените справочником вашего сервиса) |
| `tests/test_cp_client.py`, `tests/test_codeword.py`, `tests/test_gate.py` | тесты клиента и сборщиков под ChatPlace (подгоните под новый клиент) |

Оставить как есть (от сервиса автоворонок не зависит):

| Файл | Зачем |
|---|---|
| `skills/telegram-bot-setup/scripts/tg_api.py` | бот и канал через Telegram Bot API: `me`, `check-admin`, `invite` |
| `skills/funnel-links/scripts/links.py`, `shlink.sh` | реф-ссылки, UTM, пригласительные ссылки, короткие ссылки |
| `skills/funnel-banners/` | бриф, шаблон и рендер баннеров; шаг загрузки баннера в сервис выполняется клиентом вашего сервиса |
| `skills/codex-image/` | генерация картинок |
| `skills/instagram-codewords/` | правила слова, написания, тексты директа, процедура теста (меняются только названия кнопок интерфейса) |
| `.env.example` | оставьте общие переменные (`TELEGRAM_*`, `SHLINK_*`), а `CHATPLACE_*` замените переменными вашего сервиса |

Правила, которые нельзя терять при адаптации:

- ключи и токены только в переменных окружения, не в файлах и не в выводе;
- воронки создаются на паузе, включение по команде человека;
- слово проверяется со второго Instagram-аккаунта до публикации поста;
- пригласительные ссылки канала с именем источника и `member_limit` 99999;
- перед правкой живой воронки делается бэкап.
