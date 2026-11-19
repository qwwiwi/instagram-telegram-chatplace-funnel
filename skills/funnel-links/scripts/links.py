#!/usr/bin/env python3
"""Build and check the links a funnel needs: UTM urls, bot deep links, slugs, naming.

Usage:
    python3 links.py utm https://example.com/lesson --source instagram --medium dm --campaign word
    python3 links.py bot-link your_bot word_ig
    python3 links.py slug "Новый Урок"          # -> latin slug candidate
    python3 links.py check https://t.me/+XXXX   # sanity-check an invite link shape

Pure functions, no network.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import urllib.parse

LOG = logging.getLogger("links")

SLUG_RE = re.compile(r"^[a-z0-9_-]+$")
BOT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
INVITE_RE = re.compile(r"^https://t\.me/\+[A-Za-z0-9_-]+$")
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def slugify(text: str) -> str:
    """Turn a (Russian) word or phrase into a latin slug ``[a-z0-9-]``.

    Telegram deep links accept only latin letters, digits, ``-`` and ``_`` after ``start=``.
    """
    out = "".join(TRANSLIT.get(ch, ch) for ch in text.strip().lower())
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out


def add_utm(url: str, source: str, medium: str, campaign: str, content: str = "") -> str:
    """Append UTM parameters to a url, keeping existing query parameters.

    Convention: source = platform (instagram / telegram), medium = place (dm / bot / bio / channel),
    campaign = code word or product, content = post or occasion.
    """
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    wanted = {"utm_source": source, "utm_medium": medium, "utm_campaign": campaign, "utm_content": content}
    query = [(k, v) for k, v in query if k not in wanted]
    query += [(k, v) for k, v in wanted.items() if v]
    return urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))


def bot_link(bot_username: str, ref: str) -> str:
    """Build ``https://t.me/<bot>?start=<ref>`` after validating both parts.

    Raises:
        ValueError: If the username or ref has characters Telegram does not accept.
    """
    name = bot_username.lstrip("@")
    if not BOT_RE.match(name):
        raise ValueError(f"имя бота «{bot_username}» выглядит неверно (латиница, цифры, _; 5–32 знака)")
    if not SLUG_RE.match(ref.lower()) or len(ref) > 64:
        raise ValueError(f"ref «{ref}»: только латиница, цифры, - и _ (до 64 знаков), кириллица не проходит")
    return f"https://t.me/{name}?start={ref}"


def ref_name(word_slug: str, source: str) -> str:
    """Ref-link slug per word and traffic source: ``<word>_<source>`` (for attribution)."""
    return f"{slugify(word_slug).replace('-', '_')}_{slugify(source).replace('-', '_')}"


def check_invite(url: str) -> list[str]:
    """Return problems of an invite link shape (empty list = looks fine)."""
    if INVITE_RE.match(url):
        return []
    return ["ожидается ссылка вида https://t.me/+XXXXXXXX (созданная через createChatInviteLink)"]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="[links] %(message)s")
    ap = argparse.ArgumentParser(description="Funnel link helper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("utm")
    u.add_argument("url")
    u.add_argument("--source", required=True)
    u.add_argument("--medium", required=True)
    u.add_argument("--campaign", required=True)
    u.add_argument("--content", default="")
    b = sub.add_parser("bot-link")
    b.add_argument("bot")
    b.add_argument("ref")
    sub.add_parser("slug").add_argument("text")
    sub.add_parser("check").add_argument("url")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "utm":
            print(add_utm(args.url, args.source, args.medium, args.campaign, args.content))
        elif args.cmd == "bot-link":
            print(bot_link(args.bot, args.ref))
        elif args.cmd == "slug":
            print(slugify(args.text))
        else:
            problems = check_invite(args.url)
            print("\n".join(problems) if problems else "OK")
            return 1 if problems else 0
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
