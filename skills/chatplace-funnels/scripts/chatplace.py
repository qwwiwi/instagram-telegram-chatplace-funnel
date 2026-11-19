#!/usr/bin/env python3
"""ChatPlace helper CLI: list, inspect, switch, tag, link, upload and health-check.

Everything goes through ``cp_client.Client`` (key from ``CHATPLACE_API_KEY`` only).

Usage examples:
    python3 chatplace.py bots
    python3 chatplace.py automations --bot-id <ID>
    python3 chatplace.py detail <AUTOMATION_ID>
    python3 chatplace.py backup <AUTOMATION_ID> backups/word.json
    python3 chatplace.py status <AUTOMATION_ID> paused
    python3 chatplace.py comments --bot-id <ID>
    python3 chatplace.py tags-create kw_word --color "#FF5733"
    python3 chatplace.py ref-create --name word_ig --automation-id <ID> --slug word_ig --utm instagram
    python3 chatplace.py media-upload https://example.com/banner.jpg --platform telegram
    python3 chatplace.py health --bot-id <ID>
    python3 chatplace.py analytics <AUTOMATION_ID> --from 2026-01-01 --to 2026-01-31

Tool names and fields are taken from the source material; anything not verified there is marked
«проверьте в документации ChatPlace» in SKILL.md.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cp_client import ChatPlaceError, Client  # noqa: E402

LOG = logging.getLogger("chatplace")


def as_items(result: Any) -> list[dict[str, Any]]:
    """Normalise a list answer (plain list or object with ``items``)."""
    if isinstance(result, list):
        return [r for r in result if isinstance(r, dict)]
    if isinstance(result, dict) and isinstance(result.get("items"), list):
        return [r for r in result["items"] if isinstance(r, dict)]
    return []


def format_health(bot: Any, automations: list[dict[str, Any]]) -> list[str]:
    """Format a bot status line and one line per automation (plain text, no emoji).

    Args:
        bot: Answer of ``bots_get``.
        automations: Items of ``automations_list_with_stats``.

    Returns:
        Lines to print. Non-active automations are flagged ``WARN``.
    """
    status = bot.get("statusName", "UNKNOWN") if isinstance(bot, dict) else "UNKNOWN"
    name = bot.get("username", "?") if isinstance(bot, dict) else "?"
    followers = bot.get("followersCount", "?") if isinstance(bot, dict) else "?"
    lines = [f"{'OK' if status == 'Active' else 'WARN'} bot {name}: {status} | followers: {followers}"]
    total_clients = total_conv = 0
    for item in automations:
        clients = int(item.get("totalClients") or 0)
        conv = int(item.get("totalConversions") or 0)
        total_clients += clients
        total_conv += conv
        flag = "OK" if item.get("statusName") == "Active" else "WARN"
        lines.append(f"{flag:<4} {str(item.get('name', '?'))[:28]:<30} clients={clients:<5} "
                     f"conv={conv:<5} last={item.get('lastRunAt') or 'never'}")
    lines.append(f"--- total: {total_clients} clients, {total_conv} conversions")
    return lines


def period_clients(analytics: Any) -> int | None:
    """Pick ``totalClients.currentPeriod`` out of an ``automations_analytics`` answer."""
    if isinstance(analytics, dict):
        total = analytics.get("totalClients")
        if isinstance(total, dict) and isinstance(total.get("currentPeriod"), int):
            return total["currentPeriod"]
    return None


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    ap = argparse.ArgumentParser(description="ChatPlace helper CLI")
    ap.add_argument("--key-env", default="CHATPLACE_API_KEY", help="env var holding the API key")
    sub = ap.add_subparsers(dest="cmd", required=True)
    default_bot = os.environ.get("CHATPLACE_BOT_ID", "")

    sub.add_parser("bots", help="bots_list")
    for name in ("automations", "comments", "health"):
        p = sub.add_parser(name)
        p.add_argument("--bot-id", default=default_bot)
    sub.add_parser("detail").add_argument("automation_id")
    bk = sub.add_parser("backup", help="save automations_get_detail to a file BEFORE editing")
    bk.add_argument("automation_id")
    bk.add_argument("out", type=Path)
    st = sub.add_parser("status", help="automations_change_status")
    st.add_argument("automation_id")
    st.add_argument("status", choices=["active", "paused"])
    tg = sub.add_parser("tags-create")
    tg.add_argument("name")
    tg.add_argument("--color", default="#FF5733")
    sub.add_parser("tags-list")
    rl = sub.add_parser("ref-create", help="ref_links_create (Telegram deep link ?start=<slug>)")
    rl.add_argument("--name", required=True)
    rl.add_argument("--automation-id", required=True)
    rl.add_argument("--slug", required=True)
    rl.add_argument("--utm", default="")
    rl.add_argument("--keep-priority", action="store_true")
    sub.add_parser("ref-list")
    mu = sub.add_parser("media-upload", help="media_files_upload from a PUBLIC url")
    mu.add_argument("url")
    mu.add_argument("--type", default="image")
    mu.add_argument("--platform", choices=["instagram", "telegram"], required=True)
    an = sub.add_parser("analytics", help="automations_analytics for a period")
    an.add_argument("automation_id")
    an.add_argument("--from", dest="start", required=True)
    an.add_argument("--to", dest="end", required=True)
    return ap


def run(args: argparse.Namespace, client: Client) -> Any:
    """Execute one parsed command and return the data to print."""
    cmd = args.cmd
    if cmd == "bots":
        return client.call_retry("bots_list", {})
    if cmd in ("automations", "comments", "health") and not args.bot_id:
        raise ChatPlaceError("нужен --bot-id или CHATPLACE_BOT_ID (id из команды bots)")
    if cmd == "automations":
        return client.call_retry("automations_list", {"botId": args.bot_id})
    if cmd == "comments":
        return client.call_retry("comments_list", {"botId": args.bot_id})
    if cmd == "detail":
        return client.call_retry("automations_get_detail", {"automationId": args.automation_id})
    if cmd == "backup":
        data = client.call_retry("automations_get_detail", {"automationId": args.automation_id})
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"saved": str(args.out)}
    if cmd == "status":
        return client.call_retry("automations_change_status",
                                 {"automationId": args.automation_id, "status": args.status})
    if cmd == "tags-create":
        return client.call_retry("tags_create", {"name": args.name, "color": args.color})
    if cmd == "tags-list":
        return client.call_retry("tags_list", {})
    if cmd == "ref-create":
        payload: dict[str, Any] = {"name": args.name, "automationId": args.automation_id, "status": "active",
                                   "keepPriority": args.keep_priority, "slug": args.slug}
        if args.utm:
            payload["utm"] = args.utm
        return client.call_retry("ref_links_create", payload)
    if cmd == "ref-list":
        return client.call_retry("ref_links_list", {})
    if cmd == "media-upload":
        return client.call_retry("media_files_upload",
                                 {"url": args.url, "type": args.type, "platform": args.platform})
    if cmd == "analytics":
        result = client.call_retry("automations_analytics", {
            "automationId": args.automation_id, "startDate": args.start, "endDate": args.end})
        return {"totalClients.currentPeriod": period_clients(result), "raw": result}
    if cmd == "health":
        bot = client.call_retry("bots_get", {"botId": args.bot_id})
        stats = as_items(client.call_retry("automations_list_with_stats", {"botId": args.bot_id}))
        return format_health(bot, stats)
    raise ChatPlaceError(f"неизвестная команда: {cmd}")


def main(argv: list[str] | None = None, client: Client | None = None) -> int:
    """CLI entry point; ``client`` is injectable for tests."""
    logging.basicConfig(level=logging.INFO, format="[chatplace] %(message)s")
    args = build_parser().parse_args(argv)
    try:
        result = run(args, client or Client.from_env(env_name=args.key_env))
    except ChatPlaceError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    if isinstance(result, list) and result and all(isinstance(r, str) for r in result):
        print("\n".join(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
