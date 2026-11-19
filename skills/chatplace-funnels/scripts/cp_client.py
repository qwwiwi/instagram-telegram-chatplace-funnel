#!/usr/bin/env python3
"""Minimal ChatPlace MCP client (JSON-RPC 2.0 over HTTPS), stdlib only.

The key is read ONLY from the environment (``CHATPLACE_API_KEY``). It is never
printed, never written to disk and is masked in error messages.

Transport notes (from the source material, проверьте в документации ChatPlace):
    * Header must be ``Authorization: Bearer <key>``; ``x-api-key`` gets a Cloudflare 403.
    * Plain urllib was reported to get a Cloudflare 403 even with a valid key, while
      curl worked. This client first tries urllib with an explicit User-Agent and, if
      the answer is HTTP 403 (or the connection fails), retries once through ``curl``.
    * Tool results come back as ``result.content[0].text`` holding a JSON string.

Usage:
    from cp_client import Client
    client = Client.from_env()
    bots = client.call("bots_list", {})
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from typing import Any

LOG = logging.getLogger("chatplace")

MCP_URL = "https://mcp.chatplace.io/mcp"
USER_AGENT = "instagram-telegram-chatplace-funnel/1.0"
KEY_ENV = "CHATPLACE_API_KEY"

# transport(url, headers, body, timeout) -> raw response text
Transport = Callable[[str, dict[str, str], bytes, int], str]


class ChatPlaceError(RuntimeError):
    """Raised when ChatPlace answers with an error or an unreadable payload."""


def mask(text: str, key: str) -> str:
    """Remove the API key from a string before it is logged or raised.

    Args:
        text: Any text that may contain the key.
        key: The secret to hide.

    Returns:
        Text with every occurrence of the key replaced by ``***``.
    """
    return text.replace(key, "***") if key else text


def _curl_transport(url: str, headers: dict[str, str], body: bytes, timeout: int) -> str:
    """POST through curl (fallback for Cloudflare blocks of urllib)."""
    curl = shutil.which("curl")
    if curl is None:
        raise ChatPlaceError("curl не найден, а urllib получил 403 от Cloudflare")
    cmd = [curl, "-sS", "--max-time", str(timeout), url, "-X", "POST", "--data-binary", "@-"]
    for name, value in headers.items():
        cmd += ["-H", f"{name}: {value}"]
    proc = subprocess.run(cmd, input=body, capture_output=True, timeout=timeout + 20, check=False)
    if proc.returncode != 0:
        raise ChatPlaceError(f"curl завершился с кодом {proc.returncode}")
    return proc.stdout.decode("utf-8", errors="replace")


def default_transport(url: str, headers: dict[str, str], body: bytes, timeout: int) -> str:
    """POST with urllib; on HTTP 403 or a connection failure retry once with curl."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code != 403:
            raise ChatPlaceError(f"HTTP {exc.code} от ChatPlace") from exc
        LOG.warning("urllib got 403, retrying through curl")
        return _curl_transport(url, headers, body, timeout)
    except urllib.error.URLError as exc:
        LOG.warning("urllib failed (%s), retrying through curl", exc.reason)
        return _curl_transport(url, headers, body, timeout)


def parse_response(raw: str) -> Any:
    """Parse an MCP HTTP answer (plain JSON or an SSE ``data:`` line).

    Args:
        raw: Raw response text.

    Returns:
        The decoded tool result (JSON if the text payload is JSON, else the text),
        or the whole JSON-RPC object when there is no text content.

    Raises:
        ChatPlaceError: If the body is not JSON or JSON-RPC carries an ``error``.
    """
    text = raw.strip()
    for line in text.splitlines():
        if line.startswith("data: "):
            text = line[6:]
            break
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChatPlaceError(f"ответ не JSON: {raw[:200]!r}") from exc
    if not isinstance(data, dict):
        raise ChatPlaceError("неожиданная форма ответа (не объект)")
    if data.get("error"):
        raise ChatPlaceError(f"JSON-RPC error: {json.dumps(data['error'], ensure_ascii=False)[:300]}")
    result = data.get("result")
    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list) and content and isinstance(content[0], dict) and content[0].get("type") == "text":
        payload = content[0].get("text", "")
        try:
            return json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return payload
    return data


class Client:
    """ChatPlace MCP client bound to one API key."""

    def __init__(self, key: str, transport: Transport | None = None, pause: float = 0.8,
                 url: str = MCP_URL) -> None:
        """Create a client.

        Args:
            key: ChatPlace API key (kept in memory only).
            transport: Function doing the HTTP POST; tests pass a fake.
            pause: Seconds to sleep after every call (ChatPlace may answer 500 on bursts).
            url: MCP endpoint.
        """
        if not key:
            raise ChatPlaceError(f"пустой ключ: задайте переменную окружения {KEY_ENV}")
        self._key = key
        self._transport = transport or default_transport
        self._pause = pause
        self._url = url

    @classmethod
    def from_env(cls, transport: Transport | None = None, pause: float = 0.8,
                 env_name: str = KEY_ENV) -> "Client":
        """Build a client from an environment variable (default ``CHATPLACE_API_KEY``).

        Raises:
            ChatPlaceError: If the variable is missing or empty.
        """
        key = os.environ.get(env_name, "").strip()
        if not key:
            raise ChatPlaceError(f"не задана переменная окружения {env_name} (см. .env.example)")
        return cls(key, transport=transport, pause=pause)

    def call(self, tool: str, args: dict[str, Any] | None = None, timeout: int = 120) -> Any:
        """Call one MCP tool.

        Args:
            tool: Tool name, e.g. ``automations_get_detail``.
            args: Tool arguments.
            timeout: Seconds.

        Returns:
            Decoded result (see ``parse_response``).

        Raises:
            ChatPlaceError: On transport, protocol or tool-level errors.
        """
        body = json.dumps({
            "jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call",
            "params": {"name": tool, "arguments": args or {}},
        }, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
        }
        LOG.debug("call %s", tool)
        try:
            raw = self._transport(self._url, headers, body, timeout)
            result = parse_response(raw)
        except ChatPlaceError as exc:
            raise ChatPlaceError(mask(str(exc), self._key)) from None
        finally:
            if self._pause:
                time.sleep(self._pause)
        if isinstance(result, dict) and result.get("type") == "error":
            raise ChatPlaceError(f"{tool}: {json.dumps(result, ensure_ascii=False)[:300]}")
        return result

    def call_retry(self, tool: str, args: dict[str, Any] | None = None, tries: int = 4,
                   backoff: float = 2.0) -> Any:
        """Call a tool and retry on errors (ChatPlace sometimes answers 500 without text).

        Args:
            tool: Tool name.
            args: Tool arguments.
            tries: Maximum attempts.
            backoff: Seconds multiplied by the attempt number between attempts.

        Raises:
            ChatPlaceError: When every attempt failed.
        """
        last: ChatPlaceError | None = None
        for attempt in range(1, tries + 1):
            try:
                return self.call(tool, args)
            except ChatPlaceError as exc:
                last = exc
                LOG.warning("%s attempt %d/%d failed: %s", tool, attempt, tries, exc)
                if attempt < tries and backoff:
                    time.sleep(backoff * attempt)
        raise ChatPlaceError(f"{tool}: {tries} попыток подряд неудачно: {last}")


_P_WRAPPER = re.compile(r"^\s*<p>(.*)</p>\s*$", re.S)


def strip_p_wrapper(text: str) -> str:
    """Remove the ``<p>…</p>`` wrapper that ``automations_quick_setup`` adds to texts.

    Inner paragraph breaks become blank lines. Text without a wrapper is returned unchanged.
    """
    match = _P_WRAPPER.match(text)
    if not match:
        return text
    inner = match.group(1)
    return re.sub(r"</p>\s*<p>", "\n\n", inner).strip()


def iter_messages(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten ``steps[].messages[]`` of an ``automations_get_detail`` answer."""
    out: list[dict[str, Any]] = []
    for step in detail.get("steps") or []:
        out.extend(m for m in step.get("messages") or [] if isinstance(m, dict))
    return out


def clean_p_wrappers(client: Client, automation_id: str) -> int:
    """Rewrite every text message of an automation without the ``<p>`` wrapper.

    Args:
        client: ChatPlace client.
        automation_id: Automation to clean.

    Returns:
        Number of messages updated.
    """
    detail = client.call_retry("automations_get_detail", {"automationId": automation_id})
    if not isinstance(detail, dict):
        raise ChatPlaceError("automations_get_detail вернул не объект")
    changed = 0
    for message in iter_messages(detail):
        text = message.get("text")
        if not isinstance(text, str):
            continue
        clean = strip_p_wrapper(text)
        if clean != text:
            client.call_retry("automations_messages_update", {"messageId": message["id"], "text": clean})
            changed += 1
    return changed
