"""Shared test helpers: path setup and a fake ChatPlace transport (no network)."""
from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for rel in ("skills/chatplace-funnels/scripts", "skills/telegram-bot-setup/scripts",
            "skills/funnel-links/scripts", "skills/codex-image/scripts"):
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from cp_client import Client  # noqa: E402

Handler = Callable[[str, dict[str, Any]], Any]


def mcp_answer(result: Any) -> str:
    """Wrap a tool result the way the MCP endpoint does (text content holding JSON)."""
    text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    return json.dumps({"jsonrpc": "2.0", "id": "1", "result": {"content": [{"type": "text", "text": text}]}})


class FakeTransport:
    """Records every MCP call and answers through a handler."""

    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.headers: list[dict[str, str]] = []

    def __call__(self, url: str, headers: dict[str, str], body: bytes, timeout: int) -> str:
        payload = json.loads(body.decode("utf-8"))
        tool = payload["params"]["name"]
        args = payload["params"]["arguments"]
        self.calls.append((tool, args))
        self.headers.append(headers)
        return mcp_answer(self.handler(tool, args))

    def tools(self) -> list[str]:
        """Names of the called tools in order."""
        return [t for t, _ in self.calls]

    def args_of(self, tool: str) -> list[dict[str, Any]]:
        """Arguments of every call to one tool."""
        return [a for t, a in self.calls if t == tool]


def make_client(handler: Handler) -> tuple[Client, FakeTransport]:
    """Build a Client on a fake transport with no sleeping."""
    transport = FakeTransport(handler)
    return Client("test-key-not-real", transport=transport, pause=0), transport
