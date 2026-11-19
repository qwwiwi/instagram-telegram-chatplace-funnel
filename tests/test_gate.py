"""Tests for gate.py: config validation and the build flow on a fake ChatPlace API."""
from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

import helpers
import gate
from cp_client import ChatPlaceError
from helpers import make_client

EXAMPLE = helpers.ROOT / "skills" / "chatplace-funnels" / "examples" / "gate.example.json"

DETAIL = {"steps": [{"messages": [
    {"id": "w", "isFirstMessage": True, "actionTypeName": "Message", "text": "W",
     "inlineButtons": [{"id": "wb", "nextMessageId": "c"}]},
    {"id": "c", "actionTypeName": "Condition", "conditionButtons": [
        {"isNoMatchButton": False, "nextMessageId": "yes"}, {"isNoMatchButton": True, "nextMessageId": "no"}]},
    {"id": "no", "actionTypeName": "Message", "text": "N", "inlineButtons": [{"id": "nb"}]},
    {"id": "yes", "actionTypeName": "Message", "text": "A", "inlineButtons": [{"id": "ab", "nextMessageId": "fin"}]},
]}]}


def handler(tool: str, args: dict) -> object:
    if tool == "automations_quick_setup":
        return {"success": True}
    if tool == "automations_list":
        return [{"id": "g1", "name": "Проверка подписки «ГАЙД»"}]
    if tool == "automations_get_detail":
        return DETAIL
    if tool.endswith("_create"):
        return {"id": f"new-{tool}", "link": "https://t.me/your_bot?start=gayd_ig"}
    return {"ok": True}


class ConfigTests(unittest.TestCase):
    def test_example_loads_and_validates(self) -> None:
        cfg = gate.load_config(EXAMPLE, env={})
        self.assertEqual(gate.validate(cfg), [])
        self.assertEqual(cfg.channel_id, -1001234567890)

    def test_channel_from_env_when_not_in_config(self) -> None:
        raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        del raw["channel_id"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "g.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            self.assertEqual(gate.load_config(path, env={"TELEGRAM_CHANNEL_ID": "-1009999999999"}).channel_id,
                             -1009999999999)
            with self.assertRaises(ChatPlaceError):
                gate.load_config(path, env={})

    def problems(self, **changes: object) -> str:
        cfg = dataclasses.replace(gate.load_config(EXAMPLE, env={}), **changes)
        return " | ".join(gate.validate(cfg))

    def test_rules(self) -> None:
        self.assertIn("кнопка", self.problems(get_label="я" * 31))
        self.assertIn("invite", self.problems(invite="https://example.com/x"))
        self.assertIn("ссылки только в кнопках", self.problems(welcome="см. https://example.com"))
        self.assertIn("channel_id", self.problems(channel_id=123))
        self.assertIn("slug", self.problems(slug="гайд"))
        self.assertIn("https", self.problems(after_buttons=[("Открыть", "http://example.com")]))


class BuildTests(unittest.TestCase):
    def test_build_flow(self) -> None:
        cfg = dataclasses.replace(gate.load_config(EXAMPLE, env={}), welcome_media="media-1", after_media="media-2")
        client, transport = make_client(handler)
        self.assertEqual(gate.build(client, cfg, "TG-BOT"), "g1")

        setup = transport.args_of("automations_quick_setup")[0]
        self.assertEqual(setup["templateType"], "checkSubscription")
        self.assertEqual(setup["telegramChannels"], [-1001234567890])
        # old buttons removed, then url buttons made direct (trackClicks false)
        self.assertEqual({a["buttonId"] for a in transport.args_of("automations_inline_buttons_delete")},
                         {"wb", "nb", "ab"})
        setups = transport.args_of("automations_inline_buttons_setup")
        self.assertTrue(setups and all(a["trackClicks"] is False and a["subtype"] == "url" for a in setups))
        # the «get» button of both gate messages is connected to the condition block
        connected = [a for a in transport.args_of("automations_buttons_connect") if a["nextMessageId"] == "c"]
        self.assertEqual(len(connected), 2)
        # banners and ref link
        self.assertEqual({a["mediaFileId"] for a in transport.args_of("automations_messages_attach_media")},
                         {"media-1", "media-2"})
        ref = transport.args_of("ref_links_create")[0]
        self.assertEqual((ref["slug"], ref["utm"], ref["automationId"]), ("gayd_ig", "instagram", "g1"))

    def test_missing_automation_raises(self) -> None:
        def no_list(tool: str, args: dict) -> object:
            return [] if tool == "automations_list" else handler(tool, args)

        client, _ = make_client(no_list)
        with self.assertRaises(ChatPlaceError):
            gate.build(client, gate.load_config(EXAMPLE, env={}), "TG-BOT")

    def test_create_without_id_raises(self) -> None:
        def broken(tool: str, args: dict) -> object:
            return {} if tool == "automations_inline_buttons_create" else handler(tool, args)

        client, _ = make_client(broken)
        with self.assertRaises(ChatPlaceError):
            gate.build(client, gate.load_config(EXAMPLE, env={}), "TG-BOT")

    def test_invalid_config_makes_no_calls(self) -> None:
        client, transport = make_client(handler)
        bad = dataclasses.replace(gate.load_config(EXAMPLE, env={}), invite="nope")
        with self.assertRaises(ChatPlaceError):
            gate.build(client, bad, "TG-BOT")
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
