"""Tests for render_banner.py, install.sh and repository layout. Offline."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers

ROOT = helpers.ROOT
sys.path.insert(0, str(ROOT / "skills" / "funnel-banners" / "scripts"))

import render_banner  # noqa: E402

SKILLS = ("instagram-codewords", "chatplace-funnels", "telegram-bot-setup", "funnel-banners", "funnel-links", "codex-image")


class RenderBannerTests(unittest.TestCase):
    VALUES = {"BRAND": "Brand", "PILL": "ПОДАРОК", "TITLE_1": "Доступ", "TITLE_2": "открыт", "SUB": "Гайд", "HINT": "ниже"}

    def test_fill_template_escapes_html(self) -> None:
        out = render_banner.fill_template(render_banner.TEMPLATE.read_text(encoding="utf-8"),
                                          {**self.VALUES, "SUB": "<script>x</script> & «q»"})
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>", out)
        self.assertNotIn("{{", out)

    def test_missing_value_raises(self) -> None:
        values = dict(self.VALUES)
        del values["HINT"]
        with self.assertRaises(ValueError):
            render_banner.fill_template("{{HINT}}", values)

    def test_main_writes_html_and_copies_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cover = Path(tmp) / "c.jpg"
            cover.write_bytes(b"jpg")
            out = Path(tmp) / "out"
            code = render_banner.main([str(out), "--brand", "B", "--sub", "Гайд", "--cover", str(cover)])
            self.assertEqual(code, 0)
            self.assertIn("Гайд", (out / "banner.html").read_text(encoding="utf-8"))
            self.assertTrue((out / "cover.jpg").is_file())

    def test_png_without_chrome_bin_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(render_banner.main([tmp, "--brand", "B", "--sub", "S", "--png"]), 1)


class InstallTests(unittest.TestCase):
    def test_install_copies_every_skill_and_skips_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = subprocess.run(["bash", str(ROOT / "scripts" / "install.sh"), "--target", tmp],
                                   capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            for name in SKILLS:
                self.assertTrue((Path(tmp) / name / "SKILL.md").is_file(), name)
            second = subprocess.run(["bash", str(ROOT / "scripts" / "install.sh"), "--target", tmp],
                                    capture_output=True, text=True, check=False)
            self.assertIn("skip", second.stdout)

    def test_link_mode_makes_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["bash", str(ROOT / "scripts" / "install.sh"), "--target", tmp, "--link"],
                           capture_output=True, text=True, check=True)
            self.assertTrue((Path(tmp) / "chatplace-funnels").is_symlink())


class LayoutTests(unittest.TestCase):
    def test_every_skill_has_frontmatter_name_and_description(self) -> None:
        for name in SKILLS:
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), name)
            head = text.split("---", 2)[1]
            self.assertIn(f"name: {name}", head)
            self.assertIn("description:", head)

    def test_required_files_exist_and_private_source_is_gone(self) -> None:
        for rel in ("README.md", "LICENSE", ".gitignore", ".env.example", "scripts/check.sh"):
            self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertFalse((ROOT / "_src").exists())
        self.assertFalse((ROOT / "skills" / "codex-image" / ".venv").exists())

    def test_env_example_has_only_fake_values(self) -> None:
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("FAKE", text)
        self.assertNotRegex(text, r"\d{8,10}:AA[A-Za-z0-9_-]{30,}")

    def test_scripts_use_strict_bash(self) -> None:
        for path in ROOT.rglob("*.sh"):
            if ".venv" in path.parts or ".git" in path.parts:
                continue
            self.assertIn("set -euo pipefail", path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
