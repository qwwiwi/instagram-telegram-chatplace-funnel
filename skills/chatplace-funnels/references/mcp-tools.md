# Инструменты ChatPlace MCP (по рабочим заметкам)

Список взят из заметок авторов; актуальный список получите вызовом `tools/list` (проверьте в документации ChatPlace).
Группы: `ai_agent_*`, `automations_*`, `comments_*`, `bots_*`, `chats_*`, `mailings_*`, `products_*`, `ref_links_*`,
`tags_*`, `variables_*`, `virale_*`, `media_*` (около 120 инструментов).

```bash
curl -sS -X POST "https://mcp.chatplace.io/mcp" \
  -H "Authorization: Bearer $CHATPLACE_API_KEY" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## Чтение

| Инструмент | Что отдаёт |
|---|---|
| `bots_list`, `bots_get` | боты; статус, имя, подписчики |
| `automations_list`, `automations_get`, `automations_get_detail` | воронки; полная структура (триггеры, шаги, сообщения, кнопки) |
| `automations_analytics`, `automations_step_analytics`, `automations_quick_setup_analytics`, `automations_list_with_stats`, `automations_total_report` | аналитика |
| `automations_triggers_list_instagram_media`, `automations_triggers_list_telegram_channels` | посты Instagram, каналы Telegram |
| `automations_reference_actions`, `automations_reference_conditions` | справочник действий и условий |
| `tags_list`, `variables_list`, `chats_list`, `chats_messages`, `media_files_list` | метки, переменные, чаты, переписка, медиа |
| `comments_list`, `comments_get` | правила публичных ответов |
| `ref_links_list`, `mailings_list`, `mailings_predict_clients` | реф-ссылки, рассылки |

## Запись

| Инструмент | Что делает |
|---|---|
| `automations_quick_setup` | воронка целиком одним вызовом (`base`, `checkSubscription`) |
| `automations_create`, `_update`, `_delete`, `_change_status` | черновик, имя, удаление, `active`/`paused` |
| `automations_triggers_set` | триггеры и слова (`triggerTypes`, `startMessages`, `startFrequency`) |
| `automations_steps_*` | шаги |
| `automations_messages_create/update/delete/connect` | блоки и автопереходы |
| `automations_messages_attach_media`, `_detach_media`, `_set_form_type` | картинки; тип формы (после создания не меняется) |
| `automations_inline_buttons_create/setup/update/delete` | кнопки; `setup` задаёт `subtype: "url"` и `trackClicks` |
| `automations_buttons_connect` | переход по нажатию кнопки |
| `automations_actions_setup/delete` | метки, задержка, телефон, почта, запуск другой воронки |
| `automations_condition_buttons_create`, `automations_conditions_setup/delete` | условия |
| `tags_create/update/delete`, `variables_create/update/delete` | метки и переменные |
| `comments_create/update/delete/change_status` | правила публичных ответов |
| `ref_links_create/update/delete/change_status` | реф-ссылки |
| `mailings_create/update/delete/cancel/copy` | рассылки |
| `media_files_upload` | загрузка картинки по публичному URL |
| `bots_register_telegram`, `bots_update_telegram` | подключение Telegram-бота, смена токена |

## Типы триггеров

- Instagram: `messageContains`, `messageEquals`, `messageAnyValue`, `commentContains`, `commentEquals`, `commentAnyValue`,
  `storyReaction`, `storyMention`, `storyReply`, `liveCommentContains`, `liveCommentEquals`, `liveCommentAnyValue`.
- Telegram: `messageContains`, `messageEquals`, `messageAnyValue`.

## Метки действий и условий

Действия: `add_tag`, `remove_tag`, `delay`, `http_request`, `telegram_notifications`, `request_phone`, `user_response`,
`save_message_to_variable`, `set_variable`, `run_automation` и другие. Условия: `has_tags`, `check_variable`,
`check_subscription`, `check_payment`. Полный список: `automations_reference_actions` и `automations_reference_conditions`.

## Опциональный AI-агент

Инструменты `ai_agent_*` требуют, чтобы агент был создан в кабинете, и оплаченный AI-пакет. Для воронки по кодовым
словам он не нужен и в этом репозитории не используется.
