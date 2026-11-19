---
name: chatplace-funnels
description: >-
  Воронки в ChatPlace через API (MCP): создать, посмотреть, обновить воронку, шаги, кнопки, метки, реф-ссылки;
  воронка в Telegram-боте с проверкой подписки на канал и выдачей материала; аналитика и проверка здоровья.
  Используй для «ChatPlace», «воронка в директ», «воронка в боте», «проверка подписки», «кнопка не работает»,
  «статистика по слову».
---

# Воронки в ChatPlace

Скрипты лежат в `scripts/` (только стандартная библиотека Python 3, без установки пакетов):

| Скрипт | Что делает |
|---|---|
| `cp_client.py` | клиент ChatPlace MCP: ключ из окружения, повторы, маскирование ключа, очистка `<p>`-обёрток |
| `codeword.py` | воронка по кодовому слову Instagram из JSON: проверка правил, `create`, `--dry-run` |
| `gate.py` | воронка в Telegram-боте: приветствие, подписка на канал, выдача, реф-ссылки |
| `chatplace.py` | списки, детали, бэкап, пауза/старт, метки, реф-ссылки, загрузка картинок, health, аналитика |

Все скрипты читают секреты **только из переменных окружения** (`CHATPLACE_API_KEY`, `CHATPLACE_BOT_ID`,
`CHATPLACE_TG_BOT_ID`, `TELEGRAM_CHANNEL_ID`); образец – `.env.example` в корне репозитория. Ключ нигде не печатается.

## Доступ

- Эндпоинт MCP: `https://mcp.chatplace.io/mcp`, протокол JSON-RPC 2.0, метод `tools/call`.
- Заголовок строго `Authorization: Bearer <ключ>`. С `x-api-key` и без `Bearer` Cloudflare отвечает 403.
- В исходных материалах сказано, что Python `urllib` получал 403 от Cloudflare даже с верным ключом, а `curl` проходил.
  Поэтому `cp_client.py` сначала пробует `urllib` с явным `User-Agent`, а на 403 один раз повторяет запрос через `curl`.
  Нужен установленный `curl`. Не проверено на вашей сети – проверьте.
- Ключ и Bot id: ключ берётся по актуальной инструкции ChatPlace (раздел выдачи ключей и нужный тариф –
  проверьте в документации ChatPlace). Bot id: `python3 scripts/chatplace.py bots` (вызов `bots_list`).
- Instagram-бот и Telegram-бот в ChatPlace – разные боты. В исходниках у каждого пространства был свой ключ, и ключ одного
  не видел бота другого. Если у вас так же – второй ключ положите в другую переменную и передайте `--key-env`
  (например `gate.py build ... --key-env CHATPLACE_TG_API_KEY`). Если ключ один – ничего менять не нужно.

```bash
cp .env.example .env            # заполните своими значениями
set -a; . ./.env; set +a        # загрузить в текущий терминал
python3 skills/chatplace-funnels/scripts/chatplace.py bots
```

## Модель воронки

Воронка (automation) – это шаги (`steps`), в шаге блоки (`messages`). Блок бывает:

- `message` – видимое сообщение (текст, картинка, кнопки);
- `action` – служебный: метка, задержка, ожидание ответа, запуск другой воронки; ничего не рисует;
- `condition` – ветвление (например, «подписан на канал»).

Стрелок два вида: `automations_messages_connect(triggerMessageId, sendMessageId)` – автопереход блок -> блок;
`automations_buttons_connect(buttonId, nextMessageId)` – переход по нажатию кнопки.

Рантайм нигде не останавливается сам. Точек ожидания две: нажатие inline-кнопки и action-блок `request_phone` /
`user_response`. Всё остальное улетает пачкой за секунду, поэтому после каждого сообщения, которое должно «повисеть»,
нужна кнопка или action-блок.

## Главные правила

1. **Тип формы `Template`, не `QuickAnswer`.** У `Template` кнопка внутри пузыря и ссылка открывается; у `QuickAnswer` кнопка
   серой пилюлей сбоку, и по нажатию боту уходит текст кнопки – наружу ничего не открывается. В каждом
   `automations_messages_create` передавайте `"formType": "template"`. Тип потом не поменять
   (`set_form_type` отвечает `You can not change type`) – только пересобрать блок.
2. **Начинайте воронку с `automations_quick_setup`.** `automations_create` заводит первый блок в `QuickAnswer`, и удалить
   первый блок API не даёт. `quick_setup` создаёт первые сообщения сразу в `Template`.
3. **Кнопку нельзя вешать на action-блок:** API примет, `get_detail` покажет, человек не увидит ничего.
4. **`quick_setup` оборачивает тексты в `<p>…</p>`** – снимайте (`cp_client.clean_p_wrappers`, скрипты делают это сами).
5. **Связи создаются один раз.** `automations_messages_connect` накапливает связи, а не заменяет; переподключить блок
   нельзя. Ошиблись в схеме – проще пересобрать воронку (`automations_delete`, затем заново).
6. **Порядок кнопок = порядок создания.** `inline_buttons_update` меняет только текст и ссылку. Другой порядок – удалить и создать заново.
7. **Ссылочные кнопки без обёртки ChatPlace.** `inline_buttons_create` по умолчанию включает отслеживание кликов (ссылка идёт
   через `l.chatplace.io`); после создания вызовите `automations_inline_buttons_setup` с `trackClicks: false`. Скрипт `gate.py` это делает.
8. **Картинка:** ChatPlace загружает медиа только по публичному URL – `media_files_upload {url, type: "image", platform}`;
   потом `automations_messages_attach_media`. Замена: сначала `automations_messages_detach_media` (нужны оба параметра –
   `messageId` и `mediaFileId`), затем `attach`. После `attach` перечитайте `get_detail`: `attach` иногда отвечает без ошибки,
   а картинка не прикрепляется.
9. **Перед правкой – бэкап, после – проверка живым запросом.** `chatplace.py backup <id> файл.json`, затем `detail` и тест в директе.
10. **Много вызовов подряд на одну воронку (больше ~6) могут давать 500.** Клиент делает паузы (0,8 с) и повторы; структуру
    и отложенную часть собирайте отдельными проходами.

## Воронка Instagram по кодовому слову

См. скилл `instagram-codewords`. Коротко: `codeword.py create funnel.json --bot-id <ID>`.
Что делает скрипт: `automations_quick_setup` (шаблон `base`, триггеры `commentContains` + `messageEquals`, одно написание,
тексты, кнопки, `autoAnswers`) -> ищет созданную воронку -> снимает `<p>` -> добавляет остальные написания по одному через
`automations_triggers_set` -> ставит паузу. Включение – отдельно: `chatplace.py status <id> active` или `--activate`.

Поля `quick_setup` для `base`: `botId`, `templateType`, `triggerType` (список), `startMessages`, `welcomeMessage`,
`welcomeButton`, `photoId` (id картинки из `media_files_upload`), `messageWithLink`, `buttonText`, `buttonLink`,
`reminderMessage`, `autoAnswers`. Отложенная карточка: `additionalMaterialMessage`, `additionalMaterialDelayType`,
`additionalMaterialDelayValue`. Что вернёт `quick_setup` и как называется созданная воронка в списке – скрипт ищет её по
слову в названии; если не нашёл, передайте `--automation-id`.

Отдельное правило публичного ответа (`comments_create`, `type: "equals"`, `startMessages`, `answers`) включается
флагом `--comment-rule`. Если `autoAnswers` в `quick_setup` уже создаёт публичные ответы, второе правило может дублировать –
не включайте оба, пока не проверили на тестовом посте.

## Воронка в Telegram-боте с проверкой подписки

См. скилл `telegram-bot-setup` (создание бота, права, инвайты). Сборка воронки:

```bash
python3 scripts/gate.py check gate.json
python3 scripts/gate.py build gate.json --bot-id <ID Telegram-бота в ChatPlace>
```

Схема:

```
/start gayd_ig  (реф-ссылка)  или сообщение со словом
  -> ПРИВЕТСТВИЕ [баннер]   [Подписаться на канал] (url = инвайт слова)   [Получить гайд]
  -> УСЛОВИЕ: подписан на канал?
       нет -> «Пока не вижу подписки…»  те же две кнопки
       да  -> ВЫДАЧА [баннер 2]  кнопки-ссылки на материал
```

Что делает `gate.py`: `automations_quick_setup` с `templateType: "checkSubscription"` (`telegramChannels: [id канала]`,
триггер `messageEquals`) -> находит воронку по названию `«слово»` -> переписывает тексты -> удаляет шаблонные кнопки и
создаёт свои по порядку (`Подписаться на канал` – ссылка-инвайт без обёртки; `Получить…` – подключена к блоку условия) ->
прикрепляет баннеры -> создаёт реф-ссылку `ref_links_create` (`<slug>_<источник>`).

Нюансы:

- `quick_setup` для проверки подписки **сразу включает** воронку, а тексты на этот момент – заглушки `W`/`N`/`A`.
  Запускайте `build` одним проходом на тестовом слове; не делайте это на живом триггере в час пик.
- Приостановленная (`paused`) воронка на `/start` отправляет приветствие, но нажатия кнопок молча игнорирует.
  Жалоба «кнопка не работает» – сначала проверьте статус.
- Голый `/start` без параметра воронку слова не запускает – только слово или реф-ссылка.
- Условие проверки подписки: `check_subscription` с `{chatId: [-100…]}`; бот должен быть админом канала; список каналов –
  `automations_triggers_list_telegram_channels`.
- Оформление: `<b>` в тексте работает; ссылки только в кнопках, не в тексте (иначе превью); подпись кнопки до 30 знаков.
- Текст выдачи должен совпадать с обещанием в директе.

### Реф-ссылки

`ref_links_create {name, automationId, status: "active", keepPriority, slug, utm, tagIds?}` -> ссылка
`https://t.me/<бот>?start=<slug>`. Под разные источники – разные ссылки на одну воронку с разными `utm`.
Именование: `<слово>_<источник>`, например `gayd_ig`. В `start` – только латиница, цифры, `-` и `_`.
Если у человека чат с ботом уже открыт, клиент может прислать голый `/start`; для новых людей параметр доезжает – проверяйте с чистого аккаунта.

## Метки, переменные, сбор данных (по необходимости)

- Метка: `tags_create {name, color}` (без `botId`); на сообщении – `automations_actions_setup` с под-действием
  `{"actionLabel": "add_tag", "tagIds": [...]}` (метки по UUID из `tags_list`).
  Метку факта («оставил телефон») ставьте на блок **после** ожидания, а не рядом с `request_phone`.
- Телефон одним нажатием: action `request_phone` `{requestPhoneText, requestPhoneButtonName}`; почта: `user_response`
  `{typeId: 2, isSave: true, saveToVariable: <uuid>, validationMessage, responseRetryType: 1}`.
  Ожидание живёт **только на отдельном action-блоке**: на блоке-сообщении API его принимает, но рантайм пропускает.
- Задержка: action `delay` `{type: 1..7, delay: "N"}` (1 секунды, 2 минуты, 3 часы, 4 дни).
- Рассылки по меткам: `mailings_create`, `mailings_update` (поля `tags`, `withoutTags`, `sentAt` – целым Unix-временем,
  `sentTimezone`), `mailings_predict_clients`. Перед боевой отправкой пошлите себе тест с редким словом-триггером.
  Тексты рассылки отправляйте только после явного решения владельца аккаунта.
- Полный список инструментов: `references/mcp-tools.md`. Актуальный список: вызов `tools/list`.

## Аналитика и проверка здоровья

```bash
python3 scripts/chatplace.py health --bot-id <ID>            # статус бота + клиенты и конверсии по каждой воронке
python3 scripts/chatplace.py analytics <id> --from 2026-01-01 --to 2026-01-31   # totalClients.currentPeriod
```

`health` использует `bots_get` (`statusName`, `username`, `followersCount`) и `automations_list_with_stats`
(`name`, `totalClients`, `totalConversions`, `lastRunAt`, `statusName`). Воронка не в статусе `Active` помечается `WARN`.

Кто на каком шаге: `automations_clients {automationId}` (кто вошёл), `chats_messages {chatId, limit}` – переписка по секундам;
это главный инструмент диагностики «не работает». Метка события ничего не доказывает: реф-ссылка вешает её при первом
переходе. Считайте по фактам переписки.

Статистику подписок по источникам даёт имя инвайт-ссылки канала (скилл `telegram-bot-setup`) и клики по коротким
ссылкам (`funnel-links`).

## Чек-лист перед запуском

1. После каждого «висящего» сообщения есть кнопка или action-блок.
2. У каждой карточки есть входящая кнопка (иначе человек её не увидит).
3. Видимые сообщения – `message` + `Template`; у action-блоков кнопок нет.
4. Ссылочные кнопки – `trackClicks: false`.
5. Реф-ссылка ведёт на актуальную воронку (`ref_links_list`); старую воронку – на паузу.
6. Первый живой заход с чистого аккаунта; прочитать `chats_messages` и сверить секунды между сообщениями.
7. Бэкап (`backup`) до любой правки живой воронки.

## Что не проверено (проверьте в документации ChatPlace)

Тариф и место выдачи API-ключа; формат ответа `quick_setup` для `base` и `checkSubscription` (id воронки, имя в списке);
поведение `commentContains` на регистр; способ подключить Telegram-бота в кабинете (в списке инструментов есть
`bots_register_telegram` и `bots_update_telegram`, аргументы в исходниках не описаны); задержка и условие напоминания в
Instagram-воронке; лимиты текста кнопки Instagram. Все описания в этом файле взяты из рабочих заметок авторов и тестовых запусков
на их аккаунтах, а не из официальной документации.
