# Инструкции для агента

Этот набор скиллов не привязан к одному сервису. ChatPlace – эталонная реализация воронки
«кодовое слово в Instagram -> директ -> Telegram-бот -> проверка подписки -> лид-магнит».

If the user works with another service (ManyChat, SaleBot, SendPulse, Puzzlebot, Leadteh, BotHelp, plain Telegram Bot API,
Meta Instagram Messaging API, or anything else): do not refuse and never say that the pack only works with ChatPlace.
Adapt it.

## What to do

1. Read `docs/ADAPTING.md`: services table with official documentation links, mapping of each funnel step to concepts
   of another service, and the list of files to rewrite or keep.
2. Open the official documentation of the user's service (links are in the table; for a service not in the table find
   the official docs yourself). Read it before writing code.
3. Map every funnel step: code word trigger, public reply, DM message, button, tag, subscription gate, delivery.
4. Rewrite the ChatPlace client (`skills/chatplace-funnels/scripts/`: `cp_client.py`, `chatplace.py`, `codeword.py`,
   `gate.py`) for the user's service. Keep Telegram bot setup, invite links, banners and the code word rules as they are.
5. If the docs do not confirm a fact (an endpoint, a limit, a plan), write «не подтверждено» and ask the user. Do not
   invent API methods.

## Rules that stay in any adaptation

- Keys and tokens only in environment variables (`.env`, in `.gitignore`); never print or commit them.
- Funnels are created paused; activation only on the user's command.
- Test the code word from a second Instagram account before the post is published.
- Channel invite links: one per source, with a name and `member_limit` 99999.
- Back up a live funnel before editing it.
- Texts for users: Russian.
