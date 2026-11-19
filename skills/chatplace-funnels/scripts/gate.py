#!/usr/bin/env python3
"""Build a channel-gated funnel in a Telegram bot connected to ChatPlace.

Flow:
    /start <ref> or the word  ->  WELCOME (banner) [Subscribe to channel] [Get material]
    -> CONDITION: subscribed to the channel?
         no  -> «not subscribed yet» + the same two buttons
         yes -> DELIVERY (banner 2 + direct url buttons)

Usage:
    python3 gate.py check funnel-gate.json
    python3 gate.py build funnel-gate.json [--bot-id <ID>] [--key-env CHATPLACE_API_KEY] [--dry-run]

Config example: examples/gate.example.json. The channel id (-100XXXXXXXXXX) is taken from
the config or from TELEGRAM_CHANNEL_ID; the bot must be an admin of that channel.

Facts used (from the source material, проверьте в документации ChatPlace):
    * quick_setup with templateType ``checkSubscription`` creates welcome / no-subscription /
      after messages and the condition, and activates the funnel at once, so run ``build``
      in one go; the texts are placeholders until it finishes;
    * button order is creation order, so old buttons are deleted and recreated;
    * ``inline_buttons_create`` defaults to click tracking; url buttons are switched to
      trackClicks=false so that the link opens directly (no ChatPlace wrapper);
    * Telegram bots have no comment triggers: only messageContains / messageEquals / messageAnyValue.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cp_client import ChatPlaceError, Client, iter_messages  # noqa: E402

LOG = logging.getLogger("gate")

BUTTON_LIMIT = 30  # Telegram cuts longer button captions on narrow screens (source note)
CHANNEL_ID = re.compile(r"^-100\d{6,}$")


@dataclass
class GateConfig:
    """Config of one gated funnel."""

    word: str
    slug: str
    invite: str
    get_label: str
    welcome: str
    nosub: str
    after: str
    after_buttons: list[tuple[str, str]]
    channel_id: int
    welcome_media: str = ""
    after_media: str = ""
    ref_sources: list[tuple[str, str]] = field(default_factory=lambda: [("ig", "instagram")])


def load_config(path: Path, env: dict[str, str] | None = None) -> GateConfig:
    """Read the gate config JSON.

    Args:
        path: Config file.
        env: Environment mapping (defaults to ``os.environ``); used for TELEGRAM_CHANNEL_ID.

    Raises:
        ChatPlaceError: If the file or a required field is missing.
    """
    env = os.environ if env is None else env
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ChatPlaceError(f"конфиг не найден: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ChatPlaceError(f"конфиг не JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ChatPlaceError("конфиг должен быть JSON-объектом")
    required = ("word", "slug", "invite", "get_label", "welcome", "nosub", "after", "after_buttons")
    missing = [k for k in required if not raw.get(k)]
    if missing:
        raise ChatPlaceError(f"в конфиге нет полей: {', '.join(missing)}")
    channel = str(raw.get("channel_id") or env.get("TELEGRAM_CHANNEL_ID", "")).strip()
    try:
        channel_id = int(channel)
    except ValueError as exc:
        raise ChatPlaceError("нужен channel_id в конфиге или TELEGRAM_CHANNEL_ID (формат -100XXXXXXXXXX)") from exc
    sources = raw.get("ref_sources") or [["ig", "instagram"]]
    return GateConfig(
        word=str(raw["word"]).strip(), slug=str(raw["slug"]).strip(), invite=str(raw["invite"]).strip(),
        get_label=str(raw["get_label"]), welcome=str(raw["welcome"]), nosub=str(raw["nosub"]),
        after=str(raw["after"]),
        after_buttons=[(str(b[0]), str(b[1])) for b in raw["after_buttons"]],
        channel_id=channel_id,
        welcome_media=str(raw.get("welcome_media") or ""), after_media=str(raw.get("after_media") or ""),
        ref_sources=[(str(s[0]), str(s[1])) for s in sources],
    )


def validate(cfg: GateConfig) -> list[str]:
    """Check a gate config against the funnel rules; returns Russian problems."""
    problems: list[str] = []
    if not CHANNEL_ID.match(str(cfg.channel_id)):
        problems.append(f"channel_id {cfg.channel_id}: ожидается формат -100XXXXXXXXXX")
    if not re.fullmatch(r"[a-z0-9_-]+", cfg.slug):
        problems.append(f"slug «{cfg.slug}»: латиница, цифры, дефис, подчёркивание (Telegram не пропускает кириллицу в start)")
    if not re.fullmatch(r"https://t\.me/\+?[A-Za-z0-9_-]+", cfg.invite):
        problems.append("invite: ожидается ссылка https://t.me/+XXXX (своя на каждое слово, member_limit 99999)")
    labels = [cfg.get_label, "Подписаться на канал", *[b[0] for b in cfg.after_buttons]]
    for label in labels:
        if len(label) > BUTTON_LIMIT:
            problems.append(f"кнопка «{label}»: {len(label)} знаков, держите до {BUTTON_LIMIT}")
    for text, url in cfg.after_buttons:
        if not url.startswith("https://"):
            problems.append(f"кнопка «{text}»: ссылка должна начинаться с https://")
    if not cfg.after_buttons:
        problems.append("after_buttons: нужна хотя бы одна кнопка выдачи")
    for name, text in (("welcome", cfg.welcome), ("nosub", cfg.nosub), ("after", cfg.after)):
        if re.search(r"https?://", text):
            problems.append(f"{name}: ссылки только в кнопках, не в тексте (иначе появится превью)")
        if "<p>" in text:
            problems.append(f"{name}: уберите <p>-обёртки")
    return problems


def quick_setup_args(cfg: GateConfig, bot_id: str) -> dict[str, Any]:
    """Arguments of ``automations_quick_setup`` for the checkSubscription template."""
    first_text, first_url = cfg.after_buttons[0]
    return {
        "botId": bot_id, "templateType": "checkSubscription", "triggerType": "messageEquals",
        "startMessages": [cfg.word], "telegramChannels": [cfg.channel_id],
        "checkSubscriptionWelcomeMessage": "W", "checkSubscriptionWelcomeButton": cfg.get_label,
        "checkSubscriptionNoSubscriptionMessage": "N", "checkSubscriptionNoSubscriptionButton": cfg.get_label,
        "checkSubscriptionAfterMessage": "A", "checkSubscriptionAfterButtonText": first_text,
        "checkSubscriptionAfterButtonUrl": first_url,
    }


def _created(result: Any, tool: str) -> dict[str, Any]:
    """Ensure a *_create call returned an object with an id."""
    if not (isinstance(result, dict) and (result.get("id") or result.get("link"))):
        raise ChatPlaceError(f"{tool}: ответ без id: {str(result)[:200]}")
    return result


def _url_button(client: Client, message_id: str, text: str, url: str, next_id: str | None) -> None:
    """Create a direct url button (no ChatPlace click wrapper)."""
    button = _created(client.call_retry("automations_inline_buttons_create",
                                        {"messageId": message_id, "text": text, "url": url, "position": 0}),
                      "inline_buttons_create")
    client.call_retry("automations_inline_buttons_setup",
                      {"buttonId": button["id"], "subtype": "url", "url": url, "trackClicks": False})
    if next_id:
        client.call_retry("automations_buttons_connect", {"buttonId": button["id"], "nextMessageId": next_id})


def build(client: Client, cfg: GateConfig, bot_id: str) -> str:
    """Create and finish one gated funnel.

    Returns:
        The automation id.

    Raises:
        ChatPlaceError: On validation or API problems.
    """
    problems = validate(cfg)
    if problems:
        raise ChatPlaceError("конфиг не прошёл проверку: " + "; ".join(problems))
    setup = client.call_retry("automations_quick_setup", quick_setup_args(cfg, bot_id), tries=1)
    if not (isinstance(setup, dict) and setup.get("success")):
        raise ChatPlaceError(f"quick_setup не удался: {setup}")
    listing = client.call_retry("automations_list", {"botId": bot_id})
    items = listing if isinstance(listing, list) else (listing or {}).get("items", [])
    matches = [a for a in items if isinstance(a, dict) and f"«{cfg.word}»" in str(a.get("name", ""))]
    if not matches:
        raise ChatPlaceError(f"автоматизация со словом «{cfg.word}» не найдена в списке")
    aid = str(matches[0]["id"])

    detail = client.call_retry("automations_get_detail", {"automationId": aid})
    messages = iter_messages(detail)
    cond = next((m for m in messages if m.get("actionTypeName") == "Condition"), None)
    welcome = next((m for m in messages if m.get("isFirstMessage")), None)
    if cond is None or welcome is None:
        raise ChatPlaceError("в шаблоне нет блока Condition или первого сообщения: структура ответа изменилась")
    buttons = cond.get("conditionButtons") or []
    yes = next(c for c in buttons if not c.get("isNoMatchButton"))["nextMessageId"]
    no = next(c for c in buttons if c.get("isNoMatchButton"))["nextMessageId"]
    by_id = {m["id"]: m for m in messages}

    plan = [(welcome, cfg.welcome, "gate"), (by_id[no], cfg.nosub, "gate"), (by_id[yes], cfg.after, "after")]
    for message, text, kind in plan:
        client.call_retry("automations_messages_update", {"messageId": message["id"], "text": text})
        old = message.get("inlineButtons") or []
        next_id = old[0].get("nextMessageId") if old else None
        for button in old:
            client.call_retry("automations_inline_buttons_delete", {"buttonId": button["id"]})
        if kind == "gate":
            _url_button(client, message["id"], "Подписаться на канал", cfg.invite, None)
            get_button = _created(client.call_retry(
                "automations_inline_buttons_create",
                {"messageId": message["id"], "text": cfg.get_label, "position": 0}), "inline_buttons_create")
            client.call_retry("automations_buttons_connect",
                              {"buttonId": get_button["id"], "nextMessageId": cond["id"]})
        else:
            for text_, url in cfg.after_buttons:
                _url_button(client, message["id"], text_, url, next_id)

    if cfg.welcome_media:
        client.call_retry("automations_messages_attach_media",
                          {"messageId": welcome["id"], "mediaFileId": cfg.welcome_media})
    if cfg.after_media:
        client.call_retry("automations_messages_attach_media", {"messageId": yes, "mediaFileId": cfg.after_media})

    for suffix, utm in cfg.ref_sources:
        slug = f"{cfg.slug}_{suffix}"
        result = client.call_retry("ref_links_create", {
            "name": slug, "automationId": aid, "status": "active", "keepPriority": False,
            "slug": slug, "utm": utm})
        LOG.info("ref link: %s", result.get("link") if isinstance(result, dict) else result)
    return aid


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    logging.basicConfig(level=logging.INFO, format="[gate] %(message)s")
    ap = argparse.ArgumentParser(description="Telegram channel-gate funnel builder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="validate a gate config").add_argument("config", type=Path)
    bd = sub.add_parser("build", help="build the funnel in ChatPlace")
    bd.add_argument("config", type=Path)
    bd.add_argument("--bot-id", default=os.environ.get("CHATPLACE_TG_BOT_ID", ""))
    bd.add_argument("--key-env", default="CHATPLACE_API_KEY", help="env var holding the key of the Telegram workspace")
    bd.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    try:
        cfg = load_config(args.config)
        problems = validate(cfg)
        if args.cmd == "check" or args.dry_run:
            for item in problems:
                print(f"- {item}", file=sys.stderr)
            if args.dry_run and not problems:
                print(json.dumps(quick_setup_args(cfg, args.bot_id or "<BOT_ID>"), ensure_ascii=False, indent=2))
            print("конфиг готов" if not problems else f"проблем: {len(problems)}")
            return 1 if problems else 0
        if not args.bot_id:
            raise ChatPlaceError("нужен --bot-id или CHATPLACE_TG_BOT_ID (id Telegram-бота из bots_list)")
        aid = build(Client.from_env(env_name=args.key_env), cfg, args.bot_id)
        print(f"automation {aid}")
        return 0
    except ChatPlaceError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
