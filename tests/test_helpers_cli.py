"""Tests for chatplace.py (CLI), tg_api.py, links.py and shlink.sh. All offline."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import helpers
import chatplace
import links
import tg_api
from helpers import make_client

ROOT = helpers.ROOT


class ChatplaceCliTests(unittest.TestCase):
    def run_cli(self, handler: Any, *argv: str) -> tuple[int, str, Any]:
        client, transport = make_client(handler)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = chatplace.main(list(argv), client=client)
        return code, out.getvalue(), transport

    def test_status_calls_change_status(self) -> None:
        code, _, transport = self.run_cli(lambda t, a: {"ok": True}, "status", "A1", "paused")
        self.assertEqual(code, 0)
        self.assertEqual(transport.calls, [("automations_change_status", {"automationId": "A1", "status": "paused"})])

    def test_backup_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b" / "word.json"
            code, _, _ = self.run_cli(lambda t, a: {"steps": []}, "backup", "A1", str(out))
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.read_text(encoding="utf-8")), {"steps": []})

    def test_health_formats_lines(self) -> None:
        def handler(tool: str, args: dict) -> object:
            if tool == "bots_get":
                return {"username": "your_account", "statusName": "Active", "followersCount": 10}
            return [{"name": "Слово ГАЙД", "totalClients": 5, "totalConversions": 2,
                     "statusName": "Paused", "lastRunAt": None}]

        code, out, _ = self.run_cli(handler, "health", "--bot-id", "B")
        self.assertEqual(code, 0)
        self.assertIn("OK bot your_account: Active", out)
        self.assertIn("WARN", out)
        self.assertIn("total: 5 clients, 2 conversions", out)

    def test_health_requires_bot_id(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            code, _, transport = self.run_cli(lambda t, a: {}, "health")
        self.assertEqual((code, transport.calls), (1, []))

    def test_analytics_picks_period_clients(self) -> None:
        self.assertEqual(chatplace.period_clients({"totalClients": {"currentPeriod": 7}}), 7)
        self.assertIsNone(chatplace.period_clients({"x": 1}))

    def test_media_upload_args(self) -> None:
        _, _, transport = self.run_cli(lambda t, a: {"id": "m"}, "media-upload", "https://example.com/a.jpg",
                                       "--platform", "telegram")
        self.assertEqual(transport.calls[0], ("media_files_upload", {
            "url": "https://example.com/a.jpg", "type": "image", "platform": "telegram"}))


class FakePost:
    """Scripted Bot API answers by method name."""

    def __init__(self, answers: dict[str, Any]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
        method = url.rsplit("/", 1)[1]
        self.calls.append((method, body))
        answer = self.answers[method]
        return answer(body) if callable(answer) else answer


class TgApiTests(unittest.TestCase):
    def bot(self, answers: dict[str, Any]) -> tuple[tg_api.Bot, FakePost]:
        post = FakePost(answers)
        return tg_api.Bot("123:FAKE-TOKEN", post), post

    def test_check_admin_ok_and_problems(self) -> None:
        me = {"ok": True, "result": {"id": 42, "username": "your_bot"}}
        bot, _ = self.bot({"getMe": me, "getChatMember": {"ok": True, "result": {"status": "administrator", "can_invite_users": True}}})
        self.assertEqual(tg_api.check_admin(bot, -1001234567890), [])
        bot, _ = self.bot({"getMe": me, "getChatMember": {"ok": True, "result": {"status": "member"}}})
        self.assertIn("администратором", tg_api.check_admin(bot, -1001234567890)[0])
        bot, _ = self.bot({"getMe": me, "getChatMember": {"ok": True, "result": {"status": "administrator", "can_invite_users": False}}})
        self.assertIn("can_invite_users", tg_api.check_admin(bot, -1001234567890)[0])

    def test_is_subscribed(self) -> None:
        bot, _ = self.bot({"getChatMember": {"ok": True, "result": {"status": "member"}}})
        self.assertTrue(tg_api.is_subscribed(bot, -1001, 5))
        bot, _ = self.bot({"getChatMember": {"ok": True, "result": {"status": "left"}}})
        self.assertFalse(tg_api.is_subscribed(bot, -1001, 5))
        bot, _ = self.bot({"getChatMember": {"ok": False, "description": "Bad Request: user not found"}})
        self.assertFalse(tg_api.is_subscribed(bot, -1001, 5))

    def test_invite_has_name_and_member_limit_99999(self) -> None:
        bot, post = self.bot({"createChatInviteLink": {"ok": True, "result": {"invite_link": "https://t.me/+AbCd"}}})
        info = tg_api.create_invite(bot, -1001234567890, "word-ig")
        self.assertEqual(info, {"name": "word-ig", "link": "https://t.me/+AbCd", "created": True})
        self.assertEqual(post.calls[0][1], {"chat_id": -1001234567890, "name": "word-ig", "member_limit": 99999})

    def test_invite_registry_prevents_duplicates(self) -> None:
        bot, post = self.bot({"createChatInviteLink": {"ok": True, "result": {"invite_link": "https://t.me/+AbCd"}}})
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "invites.json"
            tg_api.create_invite(bot, -1001, "word-ig", registry)
            again = tg_api.create_invite(bot, -1001, "word-ig", registry)
        self.assertFalse(again["created"])
        self.assertEqual(len(post.calls), 1)

    def test_invite_name_rules(self) -> None:
        bot, _ = self.bot({})
        with self.assertRaises(ValueError):
            tg_api.create_invite(bot, -1001, "x" * 33)
        with self.assertRaises(ValueError):
            tg_api.create_invite(bot, -1001, "  ")

    def test_token_is_masked_in_errors(self) -> None:
        bot, _ = self.bot({"getMe": {"ok": False, "description": "bad 123:FAKE-TOKEN"}})
        with self.assertRaises(tg_api.TelegramError) as ctx:
            bot.call("getMe")
        self.assertNotIn("FAKE-TOKEN", str(ctx.exception))

    def test_missing_token(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(tg_api.TelegramError):
                tg_api.Bot.from_env()


class LinksTests(unittest.TestCase):
    def test_slugify_transliterates(self) -> None:
        self.assertEqual(links.slugify("Новый Урок"), "novyy-urok")
        self.assertEqual(links.slugify("  ГАЙД!! "), "gayd")

    def test_add_utm_keeps_existing_query(self) -> None:
        url = links.add_utm("https://example.com/p?a=1", "instagram", "dm", "gayd")
        self.assertEqual(url, "https://example.com/p?a=1&utm_source=instagram&utm_medium=dm&utm_campaign=gayd")

    def test_add_utm_replaces_old_values(self) -> None:
        url = links.add_utm("https://example.com/?utm_source=old", "telegram", "bot", "w", "post1")
        self.assertIn("utm_source=telegram", url)
        self.assertNotIn("old", url)
        self.assertIn("utm_content=post1", url)

    def test_bot_link_rules(self) -> None:
        self.assertEqual(links.bot_link("@your_bot", "gayd_ig"), "https://t.me/your_bot?start=gayd_ig")
        with self.assertRaises(ValueError):
            links.bot_link("your_bot", "гайд")
        with self.assertRaises(ValueError):
            links.bot_link("bad name", "x")

    def test_ref_name_and_invite_shape(self) -> None:
        self.assertEqual(links.ref_name("gayd", "ig"), "gayd_ig")
        self.assertEqual(links.check_invite("https://t.me/+AbCd123"), [])
        self.assertTrue(links.check_invite("https://t.me/your_channel"))


class ShlinkScriptTests(unittest.TestCase):
    SCRIPT = ROOT / "skills" / "funnel-links" / "scripts" / "shlink.sh"

    def test_syntax_ok(self) -> None:
        self.assertEqual(subprocess.run(["bash", "-n", str(self.SCRIPT)], check=False).returncode, 0)

    def test_requires_env_and_never_calls_network_without_it(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("SHLINK_")}
        proc = subprocess.run(["bash", str(self.SCRIPT), "get", "x"], env=env, capture_output=True, text=True, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("SHLINK_BASE_URL", proc.stderr)

    def test_has_strict_mode(self) -> None:
        self.assertIn("set -euo pipefail", self.SCRIPT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
