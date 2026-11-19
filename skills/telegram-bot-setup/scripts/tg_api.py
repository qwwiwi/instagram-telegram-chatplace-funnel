#!/usr/bin/env python3
"""Telegram Bot API helper for the funnel: bot check, admin check, subscription check, invites.

The bot token is read ONLY from ``TELEGRAM_BOT_TOKEN`` and is masked in every message.

Commands:
    python3 tg_api.py me
    python3 tg_api.py check-admin  --channel -100XXXXXXXXXX
    python3 tg_api.py is-subscribed --channel -100XXXXXXXXXX --user-id 123456789
    python3 tg_api.py invite --channel -100XXXXXXXXXX --name word-ig [--registry invites.json]

Rules baked in (see SKILL.md):
    * every invite link gets a NAME = traffic source (so joins can be attributed);
    * every invite link gets member_limit 99999 (links without a limit sometimes break);
    * Telegram limits: invite name up to 32 characters, member_limit 1..99999.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

LOG = logging.getLogger("tg_api")

API_BASE = "https://api.telegram.org"
TOKEN_ENV = "TELEGRAM_BOT_TOKEN"
MEMBER_LIMIT = 99999
NAME_MAX = 32
SUBSCRIBED = {"creator", "administrator", "member", "restricted"}

# post(url, json_body, timeout) -> parsed JSON dict
Post = Callable[[str, dict[str, Any], int], dict[str, Any]]


class TelegramError(RuntimeError):
    """Raised when the Bot API answers ok=false or the request fails."""


def _post(url: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    """POST JSON with urllib and return the parsed answer (Bot API errors are JSON too)."""
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise TelegramError(f"HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        raise TelegramError(f"сеть недоступна: {exc.reason}") from None


class Bot:
    """Thin Bot API client bound to one token."""

    def __init__(self, token: str, post: Post | None = None) -> None:
        """Create a client.

        Args:
            token: Bot token from @BotFather (kept in memory only).
            post: HTTP function; tests pass a fake.
        """
        if not token:
            raise TelegramError(f"не задана переменная окружения {TOKEN_ENV} (см. .env.example)")
        self._token = token
        self._post = post or _post

    @classmethod
    def from_env(cls, post: Post | None = None) -> "Bot":
        """Build a client from ``TELEGRAM_BOT_TOKEN``."""
        return cls(os.environ.get(TOKEN_ENV, "").strip(), post)

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: int = 30) -> Any:
        """Call a Bot API method and return ``result``.

        Raises:
            TelegramError: If ``ok`` is false (description is passed through, token masked).
        """
        try:
            answer = self._post(f"{API_BASE}/bot{self._token}/{method}", params or {}, timeout)
        except TelegramError as exc:
            raise TelegramError(str(exc).replace(self._token, "***")) from None
        if not answer.get("ok"):
            description = str(answer.get("description", "unknown error")).replace(self._token, "***")
            raise TelegramError(f"{method}: {description}")
        return answer.get("result")


def check_admin(bot: Bot, channel: int) -> list[str]:
    """Check that the bot is an administrator of the channel with the invite right.

    Returns:
        Problems in Russian; empty means the bot is ready for the subscription check and invites.
    """
    me = bot.call("getMe")
    member = bot.call("getChatMember", {"chat_id": channel, "user_id": me["id"]})
    status = member.get("status")
    if status == "creator":
        return []
    if status != "administrator":
        return [f"бот @{me.get('username')} в канале со статусом «{status}»: сделайте его администратором"]
    if member.get("can_invite_users") is False:
        return ["у бота нет права «Добавление подписчиков» (can_invite_users): включите его в правах админа"]
    return []


def is_subscribed(bot: Bot, channel: int, user_id: int) -> bool:
    """Return True if the user is in the channel (member, administrator or creator)."""
    try:
        member = bot.call("getChatMember", {"chat_id": channel, "user_id": user_id})
    except TelegramError as exc:
        if "user not found" in str(exc).lower():
            return False
        raise
    return member.get("status") in SUBSCRIBED


def validate_invite_name(name: str) -> str:
    """Validate an invite name (traffic source); returns it or raises ValueError."""
    clean = name.strip()
    if not clean:
        raise ValueError("имя ссылки пустое: назовите её по источнику, например word-ig")
    if len(clean) > NAME_MAX:
        raise ValueError(f"имя ссылки {len(clean)} знаков, Telegram принимает до {NAME_MAX}")
    return clean


def create_invite(bot: Bot, channel: int, name: str, registry: Path | None = None) -> dict[str, Any]:
    """Create a named invite link with ``member_limit`` 99999 and optionally record it.

    Args:
        bot: Bot client.
        channel: Channel id (-100XXXXXXXXXX).
        name: Source name (up to 32 characters).
        registry: Optional JSON file ``{source: link}``; an existing source is NOT recreated.

    Returns:
        Dict with ``name``, ``link`` and ``created`` (False if taken from the registry).
    """
    clean = validate_invite_name(name)
    known: dict[str, str] = {}
    if registry is not None and registry.is_file():
        known = json.loads(registry.read_text(encoding="utf-8"))
        if clean in known:
            return {"name": clean, "link": known[clean], "created": False}
    result = bot.call("createChatInviteLink", {"chat_id": channel, "name": clean, "member_limit": MEMBER_LIMIT})
    link = result.get("invite_link")
    if not link:
        raise TelegramError("createChatInviteLink вернул ответ без invite_link")
    if registry is not None:
        known[clean] = link
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps(known, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"name": clean, "link": link, "created": True}


def main(argv: list[str] | None = None, bot: Bot | None = None) -> int:
    """CLI entry point; ``bot`` is injectable for tests."""
    logging.basicConfig(level=logging.INFO, format="[tg_api] %(message)s")
    ap = argparse.ArgumentParser(description="Telegram Bot API helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("me")
    for name in ("check-admin", "is-subscribed", "invite"):
        p = sub.add_parser(name)
        p.add_argument("--channel", type=int, default=int(os.environ.get("TELEGRAM_CHANNEL_ID") or 0))
        if name == "is-subscribed":
            p.add_argument("--user-id", type=int, required=True)
        if name == "invite":
            p.add_argument("--name", required=True)
            p.add_argument("--registry", type=Path, default=None)
    args = ap.parse_args(argv)
    try:
        client = bot or Bot.from_env()
        if args.cmd == "me":
            me = client.call("getMe")
            print(f"@{me.get('username')} id={me.get('id')}")
            return 0
        if not args.channel:
            raise TelegramError("нужен --channel или TELEGRAM_CHANNEL_ID (формат -100XXXXXXXXXX)")
        if args.cmd == "check-admin":
            problems = check_admin(client, args.channel)
            print("\n".join(problems) if problems else "OK: бот администратор с правом приглашать")
            return 1 if problems else 0
        if args.cmd == "is-subscribed":
            ok = is_subscribed(client, args.channel, args.user_id)
            print("subscribed" if ok else "not subscribed")
            return 0 if ok else 1
        info = create_invite(client, args.channel, args.name, args.registry)
        print(f"{info['name']} {info['link']}" + ("" if info["created"] else " (already)"))
        return 0
    except (TelegramError, ValueError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
