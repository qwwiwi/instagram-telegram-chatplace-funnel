#!/usr/bin/env python3
"""Render the delivery banner (banner 2) from the HTML template to HTML and, optionally, PNG.

Usage:
    python3 render_banner.py out_dir --brand "Your Brand" --pill "ТВОЙ ПОДАРОК" \
        --title1 "Доступ" --title2 "открыт" --sub "Гайд «Первый AI-агент»" \
        --hint "забирай по кнопке ниже" [--cover cover.jpg] [--png]

``--png`` needs a Chromium/Chrome binary: pass it in the ``CHROME_BIN`` environment variable
(for example the path printed by ``which chromium``). Without ``--png`` only ``banner.html`` is written,
and you can open it in a browser and take a 1280x720 screenshot yourself.

The output files carry no secrets and no upload happens here: ChatPlace takes media from a PUBLIC url,
so host the finished jpg yourself (see SKILL.md).
"""
from __future__ import annotations

import argparse
import html
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

LOG = logging.getLogger("render_banner")

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "delivery-template.html"
WIDTH, HEIGHT = 1280, 720
PLACEHOLDERS = ("BRAND", "PILL", "TITLE_1", "TITLE_2", "SUB", "HINT")


def fill_template(template: str, values: dict[str, str]) -> str:
    """Fill ``{{NAME}}`` placeholders with HTML-escaped values.

    Args:
        template: HTML with placeholders.
        values: Mapping placeholder name -> text.

    Returns:
        Filled HTML.

    Raises:
        ValueError: If a placeholder has no value or one remains unfilled.
    """
    out = template
    for name in PLACEHOLDERS:
        if name not in values:
            raise ValueError(f"нет значения для {{{{{name}}}}}")
        out = out.replace("{{" + name + "}}", html.escape(values[name]))
    if "{{" in out:
        raise ValueError("в шаблоне остались незаполненные поля")
    return out


def screenshot(chrome: str, html_path: Path, png_path: Path) -> None:
    """Take a 1280x720 screenshot with headless Chrome/Chromium."""
    cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           f"--window-size={WIDTH},{HEIGHT}", "--virtual-time-budget=4000",
           f"--screenshot={png_path}", html_path.resolve().as_uri()]
    proc = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    if proc.returncode != 0 or not png_path.is_file():
        raise RuntimeError(f"браузер не сделал скриншот (код {proc.returncode})")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns the exit code."""
    logging.basicConfig(level=logging.INFO, format="[render_banner] %(message)s")
    ap = argparse.ArgumentParser(description="Render the delivery banner")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--brand", required=True)
    ap.add_argument("--pill", default="ТВОЙ ПОДАРОК")
    ap.add_argument("--title1", default="Доступ")
    ap.add_argument("--title2", default="открыт")
    ap.add_argument("--sub", required=True, help="material name, for example Гайд «Первый AI-агент»")
    ap.add_argument("--hint", default="забирай по кнопке ниже")
    ap.add_argument("--cover", type=Path, default=None, help="cover image shown on the right (jpg/png)")
    ap.add_argument("--png", action="store_true", help="also render banner.png (needs CHROME_BIN)")
    args = ap.parse_args(argv)

    try:
        page = fill_template(TEMPLATE.read_text(encoding="utf-8"), {
            "BRAND": args.brand, "PILL": args.pill, "TITLE_1": args.title1, "TITLE_2": args.title2,
            "SUB": args.sub, "HINT": args.hint})
    except ValueError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.cover is not None:
        if not args.cover.is_file():
            print(f"Ошибка: обложка не найдена: {args.cover}", file=sys.stderr)
            return 1
        shutil.copyfile(args.cover, args.out_dir / "cover.jpg")
    html_path = args.out_dir / "banner.html"
    html_path.write_text(page, encoding="utf-8")
    LOG.info("written %s", html_path)
    if args.png:
        chrome = os.environ.get("CHROME_BIN", "")
        if not chrome or shutil.which(chrome) is None:
            print("Ошибка: задайте CHROME_BIN – путь к Chromium/Chrome", file=sys.stderr)
            return 1
        try:
            screenshot(chrome, html_path, args.out_dir / "banner.png")
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"Ошибка: {exc}", file=sys.stderr)
            return 1
        LOG.info("written %s", args.out_dir / "banner.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
