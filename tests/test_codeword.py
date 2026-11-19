"""Tests for codeword.py: variants, validation, call plan and the create flow on a fake API."""
from __future__ import annotations

import contextlib
import dataclasses
import io
import os
import unittest
from pathlib import Path
from unittest import mock

import helpers
import codeword
from cp_client import ChatPlaceError
from helpers import make_client

EXAMPLE = helpers.ROOT / "skills" / "chatplace-funnels" / "examples" / "codeword.example.json"


def good_config() -> codeword.CodewordConfig:
    return codeword.load_config(EXAMPLE)


class VariantsTests(unittest.TestCase):
    def test_case_variants_order_and_dedup(self) -> None:
        self.assertEqual(codeword.case_variants("ГАЙД"), ["ГАЙД", "Гайд", "гайд"])
        self.assertEqual(codeword.case_variants("123"), ["123"])

    def test_extra_words_are_appended(self) -> None:
        cfg = dataclasses.replace(good_config(), extra_words=["guide"])
        self.assertEqual(codeword.all_variants(cfg),
                         ["ГАЙД", "Гайд", "гайд", "GUIDE", "Guide", "guide"])


class ValidateTests(unittest.TestCase):
    def test_example_config_is_valid(self) -> None:
        self.assertEqual(codeword.validate(good_config()), [])

    def problems(self, **changes: object) -> str:
        return " | ".join(codeword.validate(dataclasses.replace(good_config(), **changes)))

    def test_link_in_first_message_rejected(self) -> None:
        self.assertIn("ссылка в первом сообщении", self.problems(welcome_message="Тут https://example.com"))

    def test_too_few_or_duplicate_answers(self) -> None:
        self.assertIn("минимум", self.problems(auto_answers=["Кинул в директ", "Смотри директ"]))
        self.assertIn("повторы", self.problems(auto_answers=["Кинул в директ"] * 3))

    def test_emoji_and_long_answers_rejected(self) -> None:
        answers = ["Кинул в директ \U0001F525", "Смотри директ", "Уже в личке",]
        self.assertIn("без эмодзи", self.problems(auto_answers=answers))
        long = ["Это слишком длинный публичный ответ", "Смотри директ", "Уже в личке"]
        self.assertIn("2–4 слова", self.problems(auto_answers=long))

    def test_dm_limit_and_bad_slug_and_bad_word(self) -> None:
        self.assertIn("лимит директа", self.problems(link_message="я" * 1001))
        self.assertIn("slug", self.problems(slug="Плохой Slug"))
        self.assertIn("одно слово", self.problems(word="два слова"))

    def test_button_link_must_be_https(self) -> None:
        self.assertIn("https", self.problems(button_link="http://example.com"))


class ArgsTests(unittest.TestCase):
    def test_quick_setup_uses_one_spelling_and_base_template(self) -> None:
        args = codeword.quick_setup_args(good_config(), "BOT")
        self.assertEqual(args["startMessages"], ["ГАЙД"])
        self.assertEqual(args["templateType"], "base")
        self.assertEqual(args["triggerType"], ["commentContains", "messageEquals"])
        self.assertEqual(len(args["autoAnswers"]), 15)
        self.assertNotIn("photoId", args)

    def test_triggers_are_cumulative(self) -> None:
        cfg = good_config()
        self.assertEqual(codeword.triggers_args(cfg, "A", 2)["startMessages"], ["ГАЙД", "Гайд"])
        self.assertEqual(codeword.triggers_args(cfg, "A", 3)["startFrequency"], 0)

    def test_plan_ends_paused(self) -> None:
        calls = codeword.plan(good_config(), "BOT", comment_rule=True)
        self.assertEqual(calls[0][0], "automations_quick_setup")
        self.assertEqual(calls[-1], ("automations_change_status", {"automationId": "<AUTOMATION_ID>", "status": "paused"}))
        self.assertIn("comments_create", [t for t, _ in calls])


class CreateFlowTests(unittest.TestCase):
    @staticmethod
    def handler(tool: str, args: dict) -> object:
        if tool == "automations_quick_setup":
            return {"success": True}
        if tool == "automations_list":
            return [{"id": "other", "name": "Другая"}, {"id": "auto-1", "name": "Слово «ГАЙД»"}]
        if tool == "automations_get_detail":
            return {"status": "paused", "steps": [{"messages": [{"id": "m1", "text": "<p>Привет</p>"}]}]}
        return {"ok": True}

    def test_create_runs_steps_in_order_and_stays_paused(self) -> None:
        client, transport = make_client(self.handler)
        aid = codeword.create(client, good_config(), "BOT", comment_rule=True)
        self.assertEqual(aid, "auto-1")
        self.assertEqual(transport.tools(), [
            "automations_quick_setup", "automations_list", "automations_get_detail",
            "automations_messages_update", "automations_triggers_set", "automations_triggers_set",
            "comments_create", "automations_change_status"])
        self.assertEqual(transport.args_of("automations_messages_update"), [{"messageId": "m1", "text": "Привет"}])
        self.assertEqual(transport.args_of("automations_change_status")[0]["status"], "paused")
        self.assertEqual(transport.args_of("comments_create")[0]["type"], "equals")

    def test_activate_flag_sets_active(self) -> None:
        client, transport = make_client(self.handler)
        codeword.create(client, good_config(), "BOT", activate=True)
        self.assertEqual(transport.args_of("automations_change_status")[0]["status"], "active")

    def test_invalid_config_makes_no_calls(self) -> None:
        client, transport = make_client(self.handler)
        bad = dataclasses.replace(good_config(), auto_answers=["Один"])
        with self.assertRaises(ChatPlaceError):
            codeword.create(client, bad, "BOT")
        self.assertEqual(transport.calls, [])

    def test_ambiguous_automation_name_raises(self) -> None:
        def handler(tool: str, args: dict) -> object:
            if tool == "automations_list":
                return [{"id": "1", "name": "ГАЙД"}, {"id": "2", "name": "гайд копия"}]
            return {"success": True}

        client, _ = make_client(handler)
        with self.assertRaises(ChatPlaceError):
            codeword.create(client, good_config(), "BOT")

    def test_id_from_quick_setup_answer_is_used(self) -> None:
        def handler(tool: str, args: dict) -> object:
            if tool == "automations_quick_setup":
                return {"success": True, "automationId": "from-answer"}
            return self.handler(tool, args)

        client, transport = make_client(handler)
        self.assertEqual(codeword.create(client, good_config(), "BOT"), "from-answer")
        self.assertNotIn("automations_list", transport.tools())


class CliTests(unittest.TestCase):
    def run_cli(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = codeword.main(list(argv))
        return code, out.getvalue()

    def test_dry_run_needs_no_key_and_prints_plan(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            code, out = self.run_cli("create", str(EXAMPLE), "--bot-id", "BOT", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("automations_quick_setup", out)
        self.assertNotIn("Bearer", out)

    def test_check_example_ok(self) -> None:
        code, out = self.run_cli("check", str(EXAMPLE))
        self.assertEqual((code, "готов" in out), (0, True))

    def test_create_without_bot_id_fails(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            code, _ = self.run_cli("create", str(EXAMPLE))
        self.assertEqual(code, 1)

    def test_missing_config(self) -> None:
        code, _ = self.run_cli("check", str(Path("/nonexistent/none.json")))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
