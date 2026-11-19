#!/usr/bin/env python3
"""Create an Instagram code-word funnel in ChatPlace from a JSON config.

Flow (see skills/instagram-codewords/SKILL.md):
    comment or DM with the word -> public reply under the comment (rotating answers)
    -> DM 1 (hook + button) -> DM 2 (link button) -> optional reminder.

Steps performed by ``create``:
    1. ``automations_quick_setup`` with ONE spelling of the word (several Cyrillic
       spellings at once failed with «keyword is already used» in the source material);
    2. find the new automation id (by response or by name);
    3. strip the ``<p>`` wrappers quick_setup puts around texts;
    4. add the other spellings one by one via ``automations_triggers_set`` (cumulative);
    5. keep the automation PAUSED unless ``--activate`` is passed.

Usage:
    python3 codeword.py check  funnel.json
    python3 codeword.py variants ГАЙД
    python3 codeword.py create funnel.json --bot-id <ID> [--comment-rule] [--activate] [--dry-run]

Config example: examples/codeword.example.json
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

from cp_client import ChatPlaceError, Client, clean_p_wrappers, iter_messages  # noqa: E402

LOG = logging.getLogger("codeword")

DM_LIMIT = 1000          # Instagram DM text limit from the source notes
MIN_ANSWERS = 3          # public rule: at least 3 rotating public replies
RECOMMENDED_ANSWERS = 15  # private practice: 15 variants against repeated-reply bans
DEFAULT_TRIGGERS = ["commentContains", "messageEquals"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
URL = re.compile(r"https?://|t\.me/|www\.", re.I)
WORD_OK = re.compile(r"^[A-Za-zА-Яа-яЁё0-9]+$")


@dataclass
class CodewordConfig:
    """Everything needed to build one code-word funnel (one word = one funnel)."""

    word: str
    slug: str
    welcome_message: str
    welcome_button: str
    link_message: str
    button_text: str
    button_link: str
    auto_answers: list[str]
    extra_words: list[str] = field(default_factory=list)
    reminder_message: str = ""
    photo_id: str = ""
    trigger_types: list[str] = field(default_factory=lambda: list(DEFAULT_TRIGGERS))


def load_config(path: Path) -> CodewordConfig:
    """Read a funnel config JSON file.

    Raises:
        ChatPlaceError: If the file is missing, not JSON or lacks a required field.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ChatPlaceError(f"конфиг не найден: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ChatPlaceError(f"конфиг не JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ChatPlaceError("конфиг должен быть JSON-объектом")
    required = ("word", "slug", "welcome_message", "welcome_button", "link_message",
                "button_text", "button_link", "auto_answers")
    missing = [k for k in required if not raw.get(k)]
    if missing:
        raise ChatPlaceError(f"в конфиге нет полей: {', '.join(missing)}")
    return CodewordConfig(
        word=str(raw["word"]).strip(), slug=str(raw["slug"]).strip(),
        welcome_message=str(raw["welcome_message"]), welcome_button=str(raw["welcome_button"]),
        link_message=str(raw["link_message"]), button_text=str(raw["button_text"]),
        button_link=str(raw["button_link"]),
        auto_answers=[str(a).strip() for a in raw["auto_answers"]],
        extra_words=[str(w).strip() for w in raw.get("extra_words") or []],
        reminder_message=str(raw.get("reminder_message") or ""),
        photo_id=str(raw.get("photo_id") or ""),
        trigger_types=[str(t) for t in raw.get("trigger_types") or DEFAULT_TRIGGERS],
    )


def case_variants(word: str) -> list[str]:
    """Return the spellings of a word: UPPER, Capitalized, lower (deduplicated, in this order)."""
    seen: list[str] = []
    for variant in (word.upper(), word.capitalize(), word.lower()):
        if variant not in seen:
            seen.append(variant)
    return seen


def all_variants(cfg: CodewordConfig) -> list[str]:
    """Spellings of the main word and of every extra word (for example the English one)."""
    out: list[str] = []
    for base in [cfg.word, *cfg.extra_words]:
        for variant in case_variants(base):
            if variant not in out:
                out.append(variant)
    return out


def validate(cfg: CodewordConfig) -> list[str]:
    """Check a config against the funnel rules.

    Returns:
        Problems in Russian; an empty list means the config is ready.
    """
    problems: list[str] = []
    for base in [cfg.word, *cfg.extra_words]:
        if not WORD_OK.match(base):
            problems.append(f"слово «{base}»: одно слово без пробелов и знаков")
    if not re.fullmatch(r"[a-z0-9-]+", cfg.slug):
        problems.append(f"slug «{cfg.slug}»: только латиница в нижнем регистре, цифры и дефис")
    for name, text in (("welcome_message", cfg.welcome_message), ("link_message", cfg.link_message),
                       ("reminder_message", cfg.reminder_message)):
        if len(text) > DM_LIMIT:
            problems.append(f"{name}: {len(text)} знаков, лимит директа {DM_LIMIT}")
    if URL.search(cfg.welcome_message):
        problems.append("welcome_message: ссылка в первом сообщении – оставьте её только во втором, после клика")
    if not cfg.button_link.startswith("https://"):
        problems.append("button_link: нужна ссылка https://")
    if len(cfg.auto_answers) < MIN_ANSWERS:
        problems.append(f"auto_answers: минимум {MIN_ANSWERS} варианта, лучше {RECOMMENDED_ANSWERS}")
    if len(set(cfg.auto_answers)) != len(cfg.auto_answers):
        problems.append("auto_answers: есть повторы – одинаковые публичные ответы Instagram может счесть спамом")
    for answer in cfg.auto_answers:
        if EMOJI.search(answer) or URL.search(answer):
            problems.append(f"auto_answers «{answer}»: без эмодзи и ссылок")
        if not 1 <= len(answer.split()) <= 4:
            problems.append(f"auto_answers «{answer}»: держите ответ коротким, 2–4 слова")
    for name, text in (("welcome_message", cfg.welcome_message), ("link_message", cfg.link_message)):
        if "<p>" in text:
            problems.append(f"{name}: уберите <p>-обёртки")
    return problems


def quick_setup_args(cfg: CodewordConfig, bot_id: str) -> dict[str, Any]:
    """Arguments of ``automations_quick_setup`` (template ``base``, ONE spelling of the word)."""
    args: dict[str, Any] = {
        "botId": bot_id,
        "templateType": "base",
        "triggerType": cfg.trigger_types,
        "startMessages": [all_variants(cfg)[0]],
        "welcomeMessage": cfg.welcome_message,
        "welcomeButton": cfg.welcome_button,
        "messageWithLink": cfg.link_message,
        "buttonText": cfg.button_text,
        "buttonLink": cfg.button_link,
        "autoAnswers": cfg.auto_answers,
    }
    if cfg.photo_id:
        args["photoId"] = cfg.photo_id
    if cfg.reminder_message:
        args["reminderMessage"] = cfg.reminder_message
    return args


def triggers_args(cfg: CodewordConfig, automation_id: str, count: int) -> dict[str, Any]:
    """Arguments of ``automations_triggers_set`` with the first ``count`` spellings."""
    return {
        "automationId": automation_id,
        "triggerTypes": cfg.trigger_types,
        "startMessages": all_variants(cfg)[:count],
        "startFrequency": 0,
    }


def comment_rule_args(cfg: CodewordConfig, bot_id: str) -> dict[str, Any]:
    """Arguments of ``comments_create``: a separate public-reply rule (type ``equals``)."""
    return {
        "botId": bot_id,
        "name": f"{cfg.word.upper()} comment reply",
        "type": "equals",
        "startMessages": all_variants(cfg),
        "answers": cfg.auto_answers,
    }


def plan(cfg: CodewordConfig, bot_id: str, comment_rule: bool = False) -> list[tuple[str, dict[str, Any]]]:
    """List the MCP calls ``create`` would make (automation id shown as a placeholder)."""
    placeholder = "<AUTOMATION_ID>"
    calls: list[tuple[str, dict[str, Any]]] = [("automations_quick_setup", quick_setup_args(cfg, bot_id))]
    calls.append(("automations_get_detail + automations_messages_update", {"automationId": placeholder, "note": "strip <p>"}))
    for count in range(2, len(all_variants(cfg)) + 1):
        calls.append(("automations_triggers_set", triggers_args(cfg, placeholder, count)))
    if comment_rule:
        calls.append(("comments_create", comment_rule_args(cfg, bot_id)))
    calls.append(("automations_change_status", {"automationId": placeholder, "status": "paused"}))
    return calls


def _items(result: Any) -> list[dict[str, Any]]:
    """Normalise a list answer (plain list or object with ``items``)."""
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return [r for r in result["items"] if isinstance(r, dict)]
    return []


def find_automation_id(client: Client, bot_id: str, word: str, response: Any = None) -> str:
    """Find the automation created by quick_setup.

    Uses an id from the quick_setup answer when present, otherwise looks for an automation
    whose name contains the word (the name format is проверьте в документации ChatPlace).

    Raises:
        ChatPlaceError: If no automation or several automations match.
    """
    if isinstance(response, dict):
        for key in ("automationId", "id"):
            if isinstance(response.get(key), str):
                return response[key]
    wanted = word.lower()
    matches = [a for a in _items(client.call_retry("automations_list", {"botId": bot_id}))
               if wanted in str(a.get("name", "")).lower()]
    if len(matches) != 1:
        raise ChatPlaceError(
            f"нашлось автоматизаций со словом «{word}»: {len(matches)}; передайте --automation-id вручную")
    return str(matches[0]["id"])


def verify(client: Client, automation_id: str) -> list[str]:
    """Summarise an automation (status, texts, buttons) for a manual check."""
    detail = client.call_retry("automations_get_detail", {"automationId": automation_id})
    if not isinstance(detail, dict):
        raise ChatPlaceError("automations_get_detail вернул не объект")
    lines = [f"status: {detail.get('status') or detail.get('statusName')}"]
    for message in iter_messages(detail):
        if message.get("text"):
            lines.append(f"MSG {str(message.get('id'))[-6:]} form={message.get('formTypeName')} "
                         f"{str(message['text'])[:60]!r}")
            for button in message.get("inlineButtons") or []:
                lines.append(f"    button {button.get('text')!r} url={button.get('url')}")
    return lines


def create(client: Client, cfg: CodewordConfig, bot_id: str, comment_rule: bool = False,
           activate: bool = False, automation_id: str = "") -> str:
    """Build the funnel in ChatPlace and return the automation id.

    Args:
        client: ChatPlace client.
        cfg: Validated config.
        bot_id: Instagram bot id from ``bots_list``.
        comment_rule: Also create a separate ``comments_create`` rule.
        activate: Switch the automation to active (default: leave paused).
        automation_id: Skip discovery and use this id for the follow-up calls.

    Raises:
        ChatPlaceError: On validation or API problems.
    """
    problems = validate(cfg)
    if problems:
        raise ChatPlaceError("конфиг не прошёл проверку: " + "; ".join(problems))
    response = client.call_retry("automations_quick_setup", quick_setup_args(cfg, bot_id), tries=1)
    if isinstance(response, dict) and response.get("success") is False:
        raise ChatPlaceError(f"quick_setup отклонён: {response}")
    aid = automation_id or find_automation_id(client, bot_id, cfg.word, response)
    LOG.info("automation %s created", aid)
    clean_p_wrappers(client, aid)
    for count in range(2, len(all_variants(cfg)) + 1):
        client.call_retry("automations_triggers_set", triggers_args(cfg, aid, count))
    if comment_rule:
        client.call_retry("comments_create", comment_rule_args(cfg, bot_id))
    client.call_retry("automations_change_status", {"automationId": aid, "status": "active" if activate else "paused"})
    return aid


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the process exit code."""
    logging.basicConfig(level=logging.INFO, format="[codeword] %(message)s")
    ap = argparse.ArgumentParser(description="Instagram code-word funnel builder")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("variants", help="print the spellings of a word").add_argument("word")
    sub.add_parser("check", help="validate a funnel config").add_argument("config", type=Path)
    cr = sub.add_parser("create", help="create the funnel in ChatPlace (paused by default)")
    cr.add_argument("config", type=Path)
    cr.add_argument("--bot-id", default=os.environ.get("CHATPLACE_BOT_ID", ""))
    cr.add_argument("--comment-rule", action="store_true", help="also create a comments_create rule")
    cr.add_argument("--activate", action="store_true", help="set status active (only after the word is approved)")
    cr.add_argument("--automation-id", default="", help="use this id instead of searching by name")
    cr.add_argument("--dry-run", action="store_true", help="print the planned calls, change nothing")
    args = ap.parse_args(argv)

    if args.cmd == "variants":
        print("\n".join(case_variants(args.word)))
        return 0
    try:
        cfg = load_config(args.config)
        problems = validate(cfg)
        if args.cmd == "check":
            for item in problems:
                print(f"- {item}", file=sys.stderr)
            print("конфиг готов" if not problems else f"проблем: {len(problems)}")
            return 1 if problems else 0
        if not args.bot_id:
            raise ChatPlaceError("нужен --bot-id или переменная CHATPLACE_BOT_ID (id из bots_list)")
        if args.dry_run:
            for tool, call_args in plan(cfg, args.bot_id, args.comment_rule):
                print(tool, json.dumps(call_args, ensure_ascii=False))
            return 1 if problems else 0
        aid = create(Client.from_env(), cfg, args.bot_id, args.comment_rule, args.activate, args.automation_id)
        print(f"automation {aid}")
        print("\n".join(verify(Client.from_env(), aid)))
        return 0
    except ChatPlaceError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
