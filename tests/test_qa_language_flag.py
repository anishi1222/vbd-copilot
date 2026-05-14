"""Tests for the ``language`` flag on the four QA scripts.

Verifies that:
  - ``language='en'`` (default) keeps existing behaviour, including em-dash
    detection.
  - ``language='ja'`` skips em-dash detection in markdown content and runs
    the new Japanese AI tell + mixed-style checks instead.
  - The ``language`` field is propagated into the returned report.

Each QA script lives under ``skills/<skill-name>/`` with a hyphenated
directory name, so we load them via ``importlib`` (mirroring the other
QA test modules in this directory).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(module_name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pptx_qa = _load("pptx_qa_checks_lang", "skills/pptx-generator/pptx_qa_checks.py")
demo_qa = _load("demo_qa_checks_lang", "skills/demo-generator/demo_qa_checks.py")
hack_qa = _load(
    "hackathon_qa_checks_lang",
    "skills/hackathon-generator/hackathon_qa_checks.py",
)
docs_qa = _load("docs_qa_checks_lang", "skills/code-project/docs_qa_checks.py")


# Sample Japanese fragments used in tests.
JA_AI_TELL_LINE = "\u672c\u8cc7\u6599\u3067\u306f\u30b5\u30fc\u30d3\u30b9\u306b\u3064\u3044\u3066\u8ff0\u3079\u307e\u3059\u3002"  # 「〜について述べます」
JA_VERBOSE = "\u3053\u308c\u306b\u3088\u308a\u30c7\u30fc\u30bf\u3092\u53d6\u5f97\u3059\u308b\u3053\u3068\u304c\u3067\u304d\u307e\u3059\u3002"  # 「することができます」
JA_POLITE_LINE = "\u3053\u308c\u306f\u30b5\u30f3\u30d7\u30eb\u3067\u3059\u3002"  # 「です。」
JA_PLAIN_LINE = "\u3053\u308c\u306f\u30b5\u30f3\u30d7\u30eb\u3060\u3002"  # 「だ。」
JA_FORMAL_LINE = "\u3053\u308c\u306f\u898f\u5b9a\u3067\u3042\u308b\u3002"  # 「である。」
EM_DASH_LINE = "Microsoft Azure \u2014 the cloud platform."


# ──────────────────────────────────────────────────────────────────────────────
# pptx_qa_checks
# ──────────────────────────────────────────────────────────────────────────────


def _make_pptx_prs(body_texts: list[str], notes_texts: list[str] | None = None):
    """Build a minimal Mock Presentation. One shape per slide carries body text."""
    notes_texts = notes_texts or [""] * len(body_texts)
    assert len(body_texts) == len(notes_texts)
    prs = MagicMock()
    slides = []
    for body, notes in zip(body_texts, notes_texts):
        slide = MagicMock()
        # Notes
        slide.has_notes_slide = bool(notes)
        if notes:
            notes_frame = MagicMock()
            notes_frame.text = notes
            slide.notes_slide.notes_text_frame = notes_frame
        # One body shape
        shape = MagicMock()
        shape.has_text_frame = True
        shape.text_frame.text = body
        shape.text_frame.paragraphs = []
        shape.left = 914400
        shape.top = 914400
        shape.width = 914400 * 8
        shape.height = 914400 * 2
        shape.name = "Body"
        shape._element = MagicMock()
        parent = MagicMock()
        parent.tag = "p:spTree"
        shape._element.getparent.return_value = parent
        type(shape).shapes = PropertyMock(side_effect=AttributeError)
        slide.shapes = [shape]
        slides.append(slide)
    prs.slides = slides
    return prs


class TestPptxLanguageFlag:
    def test_run_all_checks_default_language_is_en(self, tmp_path):
        # Mock Presentation by patching the module-level constructor.
        prs = _make_pptx_prs(["Title", "Body content"])
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(pptx_qa, "Presentation", lambda _path: prs)
            report = pptx_qa.run_all_checks(str(tmp_path / "fake.pptx"))
        assert report["language"] == "en"

    def test_run_all_checks_language_ja_propagated(self, tmp_path):
        prs = _make_pptx_prs(["Title", "Body content"])
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(pptx_qa, "Presentation", lambda _path: prs)
            report = pptx_qa.run_all_checks(
                str(tmp_path / "fake.pptx"), language="ja"
            )
        assert report["language"] == "ja"

    def test_japanese_ai_tells_only_run_when_ja(self):
        prs = _make_pptx_prs([JA_AI_TELL_LINE], notes_texts=[JA_VERBOSE])
        # English: no Japanese check should fire.
        en_issues = pptx_qa.check_japanese_ai_tells(prs, language="en")
        assert en_issues == []
        # Japanese: both body and notes phrases are flagged.
        ja_issues = pptx_qa.check_japanese_ai_tells(prs, language="ja")
        checks = {i["check"] for i in ja_issues}
        assert checks == {"japanese_ai_tell"}
        messages = " ".join(i["message"] for i in ja_issues)
        assert "body text" in messages
        assert "speaker notes" in messages

    def test_japanese_mixed_styles_flag_only_when_threshold_met(self):
        # Polite count = 4, plain count = 4 -> should flag.
        notes = (
            (JA_POLITE_LINE + "\n") * 4 + (JA_PLAIN_LINE + "\n") * 2
            + (JA_FORMAL_LINE + "\n") * 2
        )
        prs = _make_pptx_prs([""], notes_texts=[notes])
        issues = pptx_qa.check_japanese_mixed_styles(prs, language="ja")
        assert len(issues) == 1
        assert issues[0]["check"] == "japanese_mixed_styles"

    def test_japanese_mixed_styles_no_flag_when_one_style_dominates(self):
        notes = (JA_POLITE_LINE + "\n") * 5 + (JA_PLAIN_LINE + "\n") * 1
        prs = _make_pptx_prs([""], notes_texts=[notes])
        issues = pptx_qa.check_japanese_mixed_styles(prs, language="ja")
        assert issues == []

    def test_japanese_mixed_styles_skipped_in_en_mode(self):
        notes = (JA_POLITE_LINE + "\n") * 4 + (JA_PLAIN_LINE + "\n") * 4
        prs = _make_pptx_prs([""], notes_texts=[notes])
        issues = pptx_qa.check_japanese_mixed_styles(prs, language="en")
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────────
# demo_qa_checks
# ──────────────────────────────────────────────────────────────────────────────


def _write_demo_guide(tmp_path: Path, body: str, demos: int = 2) -> Path:
    """Write a minimal demo guide passing baseline structure checks."""
    sections = [
        "# Demo Guide",
        "",
        "## Prerequisites",
        "- one",
        "",
        "## Setup",
        "- step",
        "",
    ]
    for i in range(1, demos + 1):
        sections.extend(
            [
                f"## Demo {i}: Sample",
                "",
                "**Goal:** show something",
                "**WOW moment:** the audience reacts",
                "",
                "### Walkthrough",
                "Say this line.",
                "",
            ]
        )
    sections.extend(["## Cleanup", "- step", ""])
    sections.append(body)
    guide = tmp_path / "guide-demos.md"
    guide.write_text("\n".join(sections), encoding="utf-8")
    return guide


class TestDemoLanguageFlag:
    def test_default_language_runs_em_dash_check(self, tmp_path):
        guide = _write_demo_guide(tmp_path, EM_DASH_LINE)
        report = demo_qa.run_all_checks(str(guide), expected_demos=2)
        assert report["language"] == "en"
        em_dash = [i for i in report["issues"] if i["check"] == "em_dash"]
        assert em_dash, "em-dash should be flagged in en mode"

    def test_ja_skips_em_dash_in_guide(self, tmp_path):
        guide = _write_demo_guide(tmp_path, EM_DASH_LINE)
        report = demo_qa.run_all_checks(
            str(guide), expected_demos=2, language="ja"
        )
        assert report["language"] == "ja"
        guide_em_dash = [
            i
            for i in report["issues"]
            if i["check"] == "em_dash" and i["file"] == "guide"
        ]
        assert guide_em_dash == [], "em-dash check must be skipped on guide in ja mode"

    def test_ja_runs_japanese_ai_tells(self, tmp_path):
        guide = _write_demo_guide(tmp_path, JA_AI_TELL_LINE)
        report = demo_qa.run_all_checks(
            str(guide), expected_demos=2, language="ja"
        )
        ai_tell = [i for i in report["issues"] if i["check"] == "japanese_ai_tell"]
        assert ai_tell, "Japanese AI tell should be flagged in ja mode"

    def test_ja_runs_mixed_styles_check(self, tmp_path):
        # Build content with >= 3 polite and >= 3 plain endings.
        body = "\n".join(
            [JA_POLITE_LINE] * 4 + [JA_PLAIN_LINE] * 2 + [JA_FORMAL_LINE] * 2
        )
        guide = _write_demo_guide(tmp_path, body)
        report = demo_qa.run_all_checks(
            str(guide), expected_demos=2, language="ja"
        )
        mixed = [
            i for i in report["issues"] if i["check"] == "japanese_mixed_styles"
        ]
        assert mixed, "mixed styles should be flagged when both registers exceed threshold"

    def test_companion_files_em_dash_always_enforced(self, tmp_path):
        """Companion scripts stay in English regardless of guide language."""
        guide = _write_demo_guide(tmp_path, "Plain content.")
        comp = tmp_path / "guide"
        comp.mkdir()
        # Use a .txt file; the script_syntax/header checks ignore non .py/.sh,
        # but the file is still scanned for em-dashes.
        (comp / "notes.txt").write_text(EM_DASH_LINE, encoding="utf-8")
        report = demo_qa.run_all_checks(
            str(guide),
            companion_dir=str(comp),
            expected_demos=2,
            language="ja",
        )
        comp_em_dash = [
            i
            for i in report["issues"]
            if i["check"] == "em_dash" and i["file"] == "notes.txt"
        ]
        assert comp_em_dash, "em-dash in companion file must still be flagged"


# ──────────────────────────────────────────────────────────────────────────────
# hackathon_qa_checks
# ──────────────────────────────────────────────────────────────────────────────


def _make_minimal_hackathon(tmp_path: Path, body_extra: str = "") -> Path:
    """Build a minimal hackathon directory tree.

    The structural checks (numbering, sections, devcontainer, README, reference
    architecture) require many files to pass; for these language-flag tests we
    only need to drive the ``check_em_dashes`` / ``check_japanese_ai_tells``
    paths, so we simply create one challenge markdown file plus required
    container directories. The structural checks may surface unrelated issues
    but they don't interfere with the language-specific assertions below.
    """
    root = tmp_path / "hack"
    challenges = root / "challenges"
    coach = root / "coach"
    resources = root / "resources"
    devc = root / ".devcontainer"
    for d in (challenges, coach, resources, devc):
        d.mkdir(parents=True)
    (root / "README.md").write_text(
        "# Hackathon\nOverview text.\n" + body_extra, encoding="utf-8"
    )
    (challenges / "challenge-00.md").write_text(
        "# Challenge 0\nIntro\n" + body_extra, encoding="utf-8"
    )
    (challenges / "challenge-01.md").write_text(
        "# Challenge 1\nFirst real challenge\n", encoding="utf-8"
    )
    (coach / "facilitation-guide.md").write_text(
        "# Facilitation Guide\n", encoding="utf-8"
    )
    (coach / "scoring-rubric.md").write_text(
        "# Scoring Rubric\n", encoding="utf-8"
    )
    (resources / "reference-architecture.md").write_text(
        "# Reference Architecture\n", encoding="utf-8"
    )
    (devc / "devcontainer.json").write_text("{}", encoding="utf-8")
    return root


class TestHackathonLanguageFlag:
    def test_default_language_runs_em_dash_check(self, tmp_path):
        root = _make_minimal_hackathon(tmp_path, EM_DASH_LINE)
        report = hack_qa.run_all_checks(str(root))
        assert report["language"] == "en"
        em_dash = [i for i in report["issues"] if i["check"] == "em_dash"]
        assert em_dash, "em-dash should be flagged in en mode"

    def test_ja_skips_em_dash_check(self, tmp_path):
        root = _make_minimal_hackathon(tmp_path, EM_DASH_LINE)
        report = hack_qa.run_all_checks(str(root), language="ja")
        assert report["language"] == "ja"
        em_dash = [i for i in report["issues"] if i["check"] == "em_dash"]
        assert em_dash == [], "em-dash check must be skipped in ja mode"

    def test_ja_runs_japanese_ai_tells(self, tmp_path):
        root = _make_minimal_hackathon(tmp_path, JA_AI_TELL_LINE)
        report = hack_qa.run_all_checks(str(root), language="ja")
        ai_tell = [i for i in report["issues"] if i["check"] == "japanese_ai_tell"]
        assert ai_tell, "Japanese AI tell should be flagged in ja mode"


# ──────────────────────────────────────────────────────────────────────────────
# docs_qa_checks
# ──────────────────────────────────────────────────────────────────────────────


def _make_minimal_project(tmp_path: Path, readme_extra: str = "") -> Path:
    """Build a minimal project directory with README + docs/architecture.md."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "README.md").write_text(
        "# Project\n## Overview\nText\n" + readme_extra, encoding="utf-8"
    )
    docs = root / "docs"
    docs.mkdir()
    (docs / "architecture.md").write_text(
        "# Architecture\nDescription.\n" + readme_extra, encoding="utf-8"
    )
    return root


class TestDocsLanguageFlag:
    def test_default_language_runs_em_dash_check(self, tmp_path):
        root = _make_minimal_project(tmp_path, EM_DASH_LINE)
        report = docs_qa.run_all_checks(str(root))
        assert report["language"] == "en"
        em_dash = [i for i in report["issues"] if i["check"] == "em_dashes"]
        assert em_dash, "em-dash should be flagged in en mode"

    def test_ja_skips_em_dash_check(self, tmp_path):
        root = _make_minimal_project(tmp_path, EM_DASH_LINE)
        report = docs_qa.run_all_checks(str(root), language="ja")
        assert report["language"] == "ja"
        em_dash = [i for i in report["issues"] if i["check"] == "em_dashes"]
        assert em_dash == [], "em-dash check must be skipped in ja mode"

    def test_ja_runs_japanese_ai_tells_in_readme_and_docs(self, tmp_path):
        root = _make_minimal_project(tmp_path, JA_AI_TELL_LINE)
        report = docs_qa.run_all_checks(str(root), language="ja")
        ai_tell = [i for i in report["issues"] if i["check"] == "japanese_ai_tell"]
        files_with_ai_tell = {i["file"] for i in ai_tell}
        assert "README.md" in files_with_ai_tell
        # docs/architecture.md should also be scanned (path uses os.sep).
        assert any("architecture.md" in f for f in files_with_ai_tell)
