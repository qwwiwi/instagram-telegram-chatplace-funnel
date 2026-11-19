"""Tests for cp_client.py: parsing, headers, key masking, fallback, retry, <p> cleanup."""
from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from unittest import mock

import helpers  # noqa: F401  (sets sys.path)
import cp_client
from cp_client import ChatPlaceError, Client
from helpers import make_client, mcp_answer


class ParseResponseTests(unittest.TestCase):
    def test_plain_json_with_json_text(self) -> None:
        self.assertEqual(cp_client.parse_response(mcp_answer({"a": 1})), {"a": 1})

    def test_sse_data_line(self) -> None:
        raw = "event: message\ndata: " + mcp_answer([1, 2]) + "\n\n"
        self.assertEqual(cp_client.parse_response(raw), [1, 2])

    def test_plain_text_payload_is_returned_as_text(self) -> None:
        self.assertEqual(cp_client.parse_response(mcp_answer("just text")), "just text")

    def test_jsonrpc_error_raises(self) -> None:
        raw = json.dumps({"jsonrpc": "2.0", "id": "1", "error": {"code": -1, "message": "boom"}})
        with self.assertRaises(ChatPlaceError):
            cp_client.parse_response(raw)

    def test_html_block_page_raises(self) -> None:
        with self.assertRaises(ChatPlaceError):
            cp_client.parse_response("<html>Cloudflare</html>")


class ClientTests(unittest.TestCase):
    def test_call_sends_bearer_and_jsonrpc_body(self) -> None:
        client, transport = make_client(lambda tool, args: {"ok": True})
        self.assertEqual(client.call("bots_list", {}), {"ok": True})
        self.assertEqual(transport.headers[0]["Authorization"], "Bearer test-key-not-real")
        self.assertEqual(transport.calls, [("bots_list", {})])

    def test_tool_level_error_object_raises(self) -> None:
        client, _ = make_client(lambda tool, args: {"type": "error", "message": "nope"})
        with self.assertRaises(ChatPlaceError):
            client.call("x", {})

    def test_key_is_masked_in_errors(self) -> None:
        def leaking(url: str, headers: dict[str, str], body: bytes, timeout: int) -> str:
            raise ChatPlaceError("failed with test-key-not-real inside")

        client = Client("test-key-not-real", transport=leaking, pause=0)
        with self.assertRaises(ChatPlaceError) as ctx:
            client.call("x", {})
        self.assertNotIn("test-key-not-real", str(ctx.exception))

    def test_from_env_requires_key(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ChatPlaceError):
                Client.from_env()
        with mock.patch.dict(os.environ, {"CHATPLACE_API_KEY": "abc"}, clear=True):
            self.assertIsInstance(Client.from_env(pause=0), Client)

    def test_retry_then_success(self) -> None:
        state = {"n": 0}

        def flaky(tool: str, args: dict) -> dict:
            state["n"] += 1
            return {"type": "error"} if state["n"] < 3 else {"id": "ok"}

        client, transport = make_client(flaky)
        self.assertEqual(client.call_retry("t", {}, tries=4, backoff=0), {"id": "ok"})
        self.assertEqual(len(transport.calls), 3)

    def test_retry_gives_up(self) -> None:
        client, _ = make_client(lambda tool, args: {"type": "error"})
        with self.assertRaises(ChatPlaceError):
            client.call_retry("t", {}, tries=2, backoff=0)


class TransportFallbackTests(unittest.TestCase):
    def test_urllib_403_falls_back_to_curl(self) -> None:
        err = urllib.error.HTTPError("https://x", 403, "Forbidden", {}, io.BytesIO(b"<html>"))
        with mock.patch("urllib.request.urlopen", side_effect=err), \
                mock.patch.object(cp_client, "_curl_transport", return_value="CURL-OK") as curl:
            out = cp_client.default_transport("https://x", {"A": "b"}, b"{}", 5)
        self.assertEqual(out, "CURL-OK")
        curl.assert_called_once()

    def test_other_http_error_does_not_fall_back(self) -> None:
        err = urllib.error.HTTPError("https://x", 500, "Server", {}, io.BytesIO(b""))
        with mock.patch("urllib.request.urlopen", side_effect=err), \
                mock.patch.object(cp_client, "_curl_transport") as curl:
            with self.assertRaises(ChatPlaceError):
                cp_client.default_transport("https://x", {}, b"{}", 5)
        curl.assert_not_called()


class StripPTests(unittest.TestCase):
    def test_strip_wrapper(self) -> None:
        self.assertEqual(cp_client.strip_p_wrapper("<p>Привет</p>"), "Привет")

    def test_paragraphs_become_blank_lines(self) -> None:
        self.assertEqual(cp_client.strip_p_wrapper("<p>One</p><p>Two</p>"), "One\n\nTwo")

    def test_plain_text_unchanged(self) -> None:
        self.assertEqual(cp_client.strip_p_wrapper("<b>Bold</b> text"), "<b>Bold</b> text")

    def test_clean_p_wrappers_updates_only_wrapped(self) -> None:
        detail = {"steps": [{"messages": [
            {"id": "m1", "text": "<p>A</p>"}, {"id": "m2", "text": "clean"}, {"id": "m3"}]}]}

        def handler(tool: str, args: dict) -> object:
            return detail if tool == "automations_get_detail" else {"ok": True}

        client, transport = make_client(handler)
        self.assertEqual(cp_client.clean_p_wrappers(client, "a1"), 1)
        self.assertEqual(transport.args_of("automations_messages_update"), [{"messageId": "m1", "text": "A"}])


if __name__ == "__main__":
    unittest.main()
