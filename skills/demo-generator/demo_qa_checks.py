#!/usr/bin/env python3
"""
Programmatic QA checks for generated demo packages.

Runs a battery of validation checks on the main demo guide (.md) and
companion scripts/files that catch common generation issues WITHOUT
requiring manual review.  Returns a structured JSON report with
severity-tagged findings.

Usage:
    python skills/demo-generator/demo_qa_checks.py <guide-path> [--companion-dir DIR] [--expected-demos N]

Exit codes:
    0 = CLEAN (no CRITICAL or MAJOR issues)
    1 = ISSUES_FOUND (at least one CRITICAL or MAJOR)
    2 = ERROR (could not open file)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

# Placeholder / TODO patterns
PLACEHOLDER_RE = re.compile(
    r"xxxx|lorem\s+ipsum|placeholder|TODO|FIXME|insert\s+here|TBD|sample\s+text",
    re.IGNORECASE,
)

# Emoji detection (common emoji Unicode ranges)
_EMOJI_RANGES = (
    (0x1F600, 0x1F64F),
    (0x1F300, 0x1F5FF),
    (0x1F680, 0x1F6FF),
    (0x1F900, 0x1F9FF),
    (0x2702, 0x27B0),
    (0xFE00, 0xFE0F),
    (0x200D, 0x200D),
    (0x2600, 0x26FF),
)


class _EmojiMatch:
    def __init__(self, char: str) -> None:
        self._char = char

    def group(self) -> str:
        return self._char


def _is_emoji(char: str) -> bool:
    codepoint = ord(char)
    return any(start <= codepoint <= end for start, end in _EMOJI_RANGES)


class _EmojiMatcher:
    def finditer(self, text: str):
        for char in text:
            if _is_emoji(char):
                yield _EmojiMatch(char)

    def findall(self, text: str) -> list[str]:
        return [match.group() for match in self.finditer(text)]


EMOJI_RE = _EmojiMatcher()

# Em-dash
EM_DASH_RE = re.compile(r"\u2014")

# Japanese AI tells -- formulaic phrases that read as machine-translated or
# committee-written Japanese. Detected only when language='ja'.
JAPANESE_AI_TELL_PATTERNS = [
    (re.compile(r"\u3068\u8a00\u3048\u308b\u3067\u3057\u3087\u3046"),
     "Hedging cliche '\u3068\u8a00\u3048\u308b\u3067\u3057\u3087\u3046'"),
    (re.compile(r"\u306b\u3064\u3044\u3066\u8ff0\u3079\u307e\u3059"),
     "Formulaic narration '\u306b\u3064\u3044\u3066\u8ff0\u3079\u307e\u3059'"),
    (re.compile(r"\u304c\u6328\u3052\u3089\u308c\u307e\u3059"),
     "Formulaic enumeration '\u304c\u6328\u3052\u3089\u308c\u307e\u3059'"),
    (re.compile(r"\u3059\u308b\u3053\u3068\u304c\u3067\u304d\u307e\u3059"),
     "Verbose construction '\u3059\u308b\u3053\u3068\u304c\u3067\u304d\u307e\u3059' (use '\u3067\u304d\u307e\u3059')"),
    (re.compile(r"\u3059\u308b\u3053\u3068\u304c\u53ef\u80fd\u3067\u3059"),
     "Verbose construction '\u3059\u308b\u3053\u3068\u304c\u53ef\u80fd\u3067\u3059' (use '\u3067\u304d\u307e\u3059')"),
    (re.compile(r"\u3068\u8003\u3048\u3089\u308c\u307e\u3059"),
     "Vague hedge '\u3068\u8003\u3048\u3089\u308c\u307e\u3059'"),
    (re.compile(r"\u3068\u8a00\u3063\u3066\u3082\u904e\u8a00\u3067\u306f\u3042\u308a\u307e\u305b\u3093"),
     "Cliche hyperbole '\u3068\u8a00\u3063\u3066\u3082\u904e\u8a00\u3067\u306f\u3042\u308a\u307e\u305b\u3093'"),
    (re.compile(r"\u4ee5\u4e0a\u306e\u3053\u3068\u304b\u3089"),
     "Formulaic conclusion '\u4ee5\u4e0a\u306e\u3053\u3068\u304b\u3089'"),
]

_JA_POLITE_RE = re.compile(r"(\u3067\u3059\u3002|\u307e\u3059\u3002|\u307e\u3057\u305f\u3002)")
_JA_PLAIN_RE = re.compile(r"(\u3060\u3002|\u3067\u3042\u308b\u3002|\u3060\u3063\u305f\u3002|\u3067\u3042\u3063\u305f\u3002)")
_JA_MIXED_THRESHOLD = 3

# URL-like patterns
URL_RE = re.compile(r"https?://[^\s)>\]\"']+")


# ── Individual check functions ────────────────────────────────────────────────


def check_guide_exists(guide_path: str) -> list[dict]:
    """Check that the main guide file exists and is non-empty."""
    issues = []
    if not os.path.exists(guide_path):
        issues.append(
            {
                "file": guide_path,
                "severity": "CRITICAL",
                "check": "guide_exists",
                "message": f"Guide file does not exist: {guide_path}",
            }
        )
        return issues
    if os.path.getsize(guide_path) == 0:
        issues.append(
            {
                "file": guide_path,
                "severity": "CRITICAL",
                "check": "guide_exists",
                "message": "Guide file is empty (0 bytes)",
            }
        )
    return issues


def check_demo_count(guide_text: str, expected: int | None) -> list[dict]:
    """Check that the guide contains the expected number of demo sections."""
    issues = []
    # Count H2 headers that look like demo sections (## Demo 1, ## Demo 2, etc.)
    demo_headers = re.findall(
        r"^##\s+Demo\s+\d+",
        guide_text,
        re.MULTILINE | re.IGNORECASE,
    )
    actual = len(demo_headers)
    if expected is not None and actual != expected:
        issues.append(
            {
                "file": "guide",
                "severity": "CRITICAL" if abs(actual - expected) > 1 else "MAJOR",
                "check": "demo_count",
                "message": f"Expected {expected} demo sections, found {actual}",
            }
        )
    if actual == 0:
        issues.append(
            {
                "file": "guide",
                "severity": "CRITICAL",
                "check": "demo_count",
                "message": "No demo sections (## Demo N) found in the guide",
            }
        )
    return issues


def check_placeholders(text: str, filename: str) -> list[dict]:
    """Scan for leftover placeholder / TODO text."""
    issues = []
    for line_num, line in enumerate(text.splitlines(), 1):
        for match in PLACEHOLDER_RE.finditer(line):
            issues.append(
                {
                    "file": filename,
                    "severity": "CRITICAL",
                    "check": "placeholder_text",
                    "message": (
                        f"Placeholder text '{match.group()}' at line {line_num}: "
                        f"{line.strip()[:100]}"
                    ),
                }
            )
    return issues


def check_emoji(text: str, filename: str) -> list[dict]:
    """Scan for emoji characters (prohibited)."""
    issues = []
    for line_num, line in enumerate(text.splitlines(), 1):
        for match in EMOJI_RE.finditer(line):
            issues.append(
                {
                    "file": filename,
                    "severity": "MAJOR",
                    "check": "emoji",
                    "message": (
                        f"Emoji character U+{ord(match.group()):04X} at line {line_num}: "
                        f"{line.strip()[:100]}"
                    ),
                }
            )
    return issues


def check_em_dashes(text: str, filename: str) -> list[dict]:
    """Scan for em-dashes (prohibited - use hyphens)."""
    issues = []
    for line_num, line in enumerate(text.splitlines(), 1):
        for match in EM_DASH_RE.finditer(line):
            issues.append(
                {
                    "file": filename,
                    "severity": "MAJOR",
                    "check": "em_dash",
                    "message": f"Em-dash at line {line_num}: {line.strip()[:100]}",
                }
            )
    return issues


def check_japanese_ai_tells(text: str, filename: str) -> list[dict]:
    """Detect formulaic Japanese AI tells. Caller decides when to invoke."""
    issues: list[dict] = []
    for line_num, line in enumerate(text.splitlines(), 1):
        for pattern, label in JAPANESE_AI_TELL_PATTERNS:
            for match in pattern.finditer(line):
                issues.append(
                    {
                        "file": filename,
                        "severity": "MAJOR",
                        "check": "japanese_ai_tell",
                        "message": (
                            f"{label} at line {line_num}: {line.strip()[:100]}"
                        ),
                    }
                )
    return issues


def check_japanese_mixed_styles(text: str, filename: str) -> list[dict]:
    """Flag files that mix polite (\u3067\u3059/\u307e\u3059) and plain (\u3060/\u3067\u3042\u308b) registers."""
    issues: list[dict] = []
    polite = len(_JA_POLITE_RE.findall(text))
    plain = len(_JA_PLAIN_RE.findall(text))
    if polite >= _JA_MIXED_THRESHOLD and plain >= _JA_MIXED_THRESHOLD:
        issues.append(
            {
                "file": filename,
                "severity": "MINOR",
                "check": "japanese_mixed_styles",
                "message": (
                    f"Mixes polite ({polite}) and plain ({plain}) sentence "
                    f"endings - pick one register"
                ),
            }
        )
    return issues


def check_companion_files_referenced(
    guide_text: str,
    companion_dir: str | None,
) -> list[dict]:
    """Verify that files referenced in the guide actually exist."""
    issues = []
    if not companion_dir or not os.path.isdir(companion_dir):
        return issues

    # Find file references like demo-1-xxx.sh, demo-2-yyy.py, etc.
    file_refs = re.findall(r"demo-\d+-[\w.-]+\.\w+", guide_text)
    seen = set()
    for ref in file_refs:
        if ref in seen:
            continue
        seen.add(ref)
        full_path = os.path.join(companion_dir, ref)
        if not os.path.exists(full_path):
            issues.append(
                {
                    "file": ref,
                    "severity": "CRITICAL",
                    "check": "file_reference",
                    "message": f"Guide references '{ref}' but it does not exist in {companion_dir}",
                }
            )
    return issues


def check_companion_dir_exists(
    companion_dir: str | None, expected_demos: int | None
) -> list[dict]:
    """Check companion directory exists and has files."""
    issues = []
    if companion_dir is None:
        return issues
    if not os.path.isdir(companion_dir):
        issues.append(
            {
                "file": companion_dir,
                "severity": "CRITICAL",
                "check": "companion_dir",
                "message": f"Companion directory does not exist: {companion_dir}",
            }
        )
        return issues
    files = [f for f in os.listdir(companion_dir) if not f.startswith(".")]
    if not files:
        issues.append(
            {
                "file": companion_dir,
                "severity": "CRITICAL",
                "check": "companion_dir",
                "message": "Companion directory is empty",
            }
        )
    return issues


def check_script_syntax(companion_dir: str | None) -> list[dict]:
    """Run syntax checks on companion scripts (bash -n, py_compile)."""
    issues = []
    if not companion_dir or not os.path.isdir(companion_dir):
        return issues

    for fname in sorted(os.listdir(companion_dir)):
        fpath = os.path.join(companion_dir, fname)
        if not os.path.isfile(fpath):
            continue

        if fname.endswith(".sh"):
            try:
                result = subprocess.run(
                    ["bash", "-n", fpath],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    issues.append(
                        {
                            "file": fname,
                            "severity": "CRITICAL",
                            "check": "bash_syntax",
                            "message": f"bash -n failed: {result.stderr.strip()[:200]}",
                        }
                    )
            except Exception as e:
                issues.append(
                    {
                        "file": fname,
                        "severity": "MINOR",
                        "check": "bash_syntax",
                        "message": f"Could not run bash -n: {e}",
                    }
                )

        elif fname.endswith(".py"):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", fpath],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    issues.append(
                        {
                            "file": fname,
                            "severity": "CRITICAL",
                            "check": "python_syntax",
                            "message": f"py_compile failed: {result.stderr.strip()[:200]}",
                        }
                    )
            except Exception as e:
                issues.append(
                    {
                        "file": fname,
                        "severity": "MINOR",
                        "check": "python_syntax",
                        "message": f"Could not run py_compile: {e}",
                    }
                )

    return issues


def check_script_headers(companion_dir: str | None) -> list[dict]:
    """Check that scripts have header comments with usage/prerequisites."""
    issues = []
    if not companion_dir or not os.path.isdir(companion_dir):
        return issues

    for fname in sorted(os.listdir(companion_dir)):
        fpath = os.path.join(companion_dir, fname)
        if not os.path.isfile(fpath):
            continue
        if not (fname.endswith(".sh") or fname.endswith(".py")):
            continue

        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(500)
        except Exception:
            continue

        # Check for header comment in first 500 chars
        has_comment = (
            head.lstrip().startswith("#")
            or head.lstrip().startswith('"""')
            or head.lstrip().startswith("'''")
        )
        if not has_comment:
            issues.append(
                {
                    "file": fname,
                    "severity": "MAJOR",
                    "check": "script_header",
                    "message": "Script lacks header comments (usage/prerequisites)",
                }
            )
    return issues


def check_guide_structure(guide_text: str) -> list[dict]:
    """Check that the guide has expected structural elements."""
    issues = []

    # Must have a top-level title
    if not re.search(r"^#\s+", guide_text, re.MULTILINE):
        issues.append(
            {
                "file": "guide",
                "severity": "MAJOR",
                "check": "guide_structure",
                "message": "Guide is missing a top-level heading (# Title)",
            }
        )

    # Should have an environment/prerequisites section
    if not re.search(
        r"(prerequisit|environment|setup|requirements)",
        guide_text,
        re.IGNORECASE,
    ):
        issues.append(
            {
                "file": "guide",
                "severity": "MAJOR",
                "check": "guide_structure",
                "message": "Guide is missing a prerequisites/environment setup section",
            }
        )

    # Should have a demo overview table
    if not re.search(r"\|.*\|.*\|", guide_text):
        issues.append(
            {
                "file": "guide",
                "severity": "MINOR",
                "check": "guide_structure",
                "message": "Guide is missing a demo overview table",
            }
        )

    # Each demo should have steps or numbered items
    demos = re.split(
        r"^##\s+Demo\s+\d+", guide_text, flags=re.MULTILINE | re.IGNORECASE
    )
    for i, section in enumerate(demos[1:], 1):
        # Check for step markers (numbered lists, ### Step, etc.)
        has_steps = bool(
            re.search(r"(^\d+\.|^###\s+Step|^-\s+\[)", section, re.MULTILINE)
        )
        if not has_steps:
            issues.append(
                {
                    "file": "guide",
                    "severity": "MAJOR",
                    "check": "guide_structure",
                    "message": f"Demo {i} section has no numbered steps or step headings",
                }
            )

    return issues


def check_guide_length(guide_text: str, expected_demos: int | None) -> list[dict]:
    """Check that the guide has reasonable content length."""
    issues = []
    word_count = len(guide_text.split())

    # Very short guide is suspicious
    if word_count < 200:
        issues.append(
            {
                "file": "guide",
                "severity": "CRITICAL",
                "check": "guide_length",
                "message": f"Guide is very short ({word_count} words) - likely incomplete",
            }
        )
    elif expected_demos and word_count < expected_demos * 150:
        issues.append(
            {
                "file": "guide",
                "severity": "MAJOR",
                "check": "guide_length",
                "message": (
                    f"Guide has {word_count} words for {expected_demos} demos - "
                    f"expected at least ~{expected_demos * 150} words"
                ),
            }
        )

    return issues


# ── Main runner ───────────────────────────────────────────────────────────────


def run_all_checks(
    guide_path: str,
    companion_dir: str | None = None,
    expected_demos: int | None = None,
    *,
    language: str = "en",
) -> dict:
    """Run all demo QA checks and return a structured report.

    ``language`` selects locale-specific behaviour:
      - ``"en"`` (default): em-dash check is enforced.
      - ``"ja"``: em-dash check is skipped; Japanese AI tell + mixed-style
        checks are added.
    """

    # Phase 0: file existence
    existence_issues = check_guide_exists(guide_path)
    if any(i["severity"] == "CRITICAL" for i in existence_issues):
        return {
            "status": "ERROR",
            "guide": guide_path,
            "companion_dir": companion_dir,
            "language": language,
            "issues": existence_issues,
            "summary": {"CRITICAL": len(existence_issues), "MAJOR": 0, "MINOR": 0},
        }

    # Read guide content
    try:
        with open(guide_path, "r", encoding="utf-8", errors="replace") as f:
            guide_text = f.read()
    except Exception as e:
        return {
            "status": "ERROR",
            "guide": guide_path,
            "companion_dir": companion_dir,
            "language": language,
            "error": str(e),
            "issues": [],
            "summary": {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0},
        }

    # Auto-detect companion dir if not provided
    if companion_dir is None:
        # Try stripping -demos.md suffix to get directory name
        base = guide_path.replace("-demos.md", "").replace(".md", "")
        if os.path.isdir(base):
            companion_dir = base

    all_issues: list[dict] = []

    # Guide-level checks
    checks = [
        ("demo_count", lambda: check_demo_count(guide_text, expected_demos)),
        ("guide_structure", lambda: check_guide_structure(guide_text)),
        ("guide_length", lambda: check_guide_length(guide_text, expected_demos)),
        ("guide_placeholders", lambda: check_placeholders(guide_text, "guide")),
        ("guide_emoji", lambda: check_emoji(guide_text, "guide")),
        (
            "file_references",
            lambda: check_companion_files_referenced(guide_text, companion_dir),
        ),
        (
            "companion_dir",
            lambda: check_companion_dir_exists(companion_dir, expected_demos),
        ),
        ("script_syntax", lambda: check_script_syntax(companion_dir)),
        ("script_headers", lambda: check_script_headers(companion_dir)),
    ]
    if language == "ja":
        checks.append(
            (
                "guide_japanese_ai_tells",
                lambda: check_japanese_ai_tells(guide_text, "guide"),
            )
        )
        checks.append(
            (
                "guide_japanese_mixed_styles",
                lambda: check_japanese_mixed_styles(guide_text, "guide"),
            )
        )
    else:
        checks.append(
            ("guide_em_dashes", lambda: check_em_dashes(guide_text, "guide"))
        )

    for check_name, check_fn in checks:
        try:
            issues = check_fn()
            all_issues.extend(issues)
        except Exception as e:
            all_issues.append(
                {
                    "file": "runner",
                    "severity": "MINOR",
                    "check": check_name,
                    "message": f"Check failed with error: {e}",
                }
            )

    # Also scan companion files for placeholders, emoji, em-dashes
    if companion_dir and os.path.isdir(companion_dir):
        for fname in sorted(os.listdir(companion_dir)):
            fpath = os.path.join(companion_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                all_issues.extend(check_placeholders(content, fname))
                all_issues.extend(check_emoji(content, fname))
                # Companion scripts must stay in English regardless of guide
                # language, so em-dashes are always disallowed there.
                all_issues.extend(check_em_dashes(content, fname))
            except Exception:
                pass

    # Summarize
    summary: dict[str, int] = defaultdict(int)
    for issue in all_issues:
        summary[issue["severity"]] += 1

    # Group by file
    by_file: dict[str, list[dict]] = defaultdict(list)
    for issue in all_issues:
        by_file[issue["file"]].append(issue)

    has_critical_or_major = (
        summary.get("CRITICAL", 0) > 0 or summary.get("MAJOR", 0) > 0
    )
    status = "ISSUES_FOUND" if has_critical_or_major else "CLEAN"

    return {
        "status": status,
        "guide": guide_path,
        "companion_dir": companion_dir,
        "expected_demos": expected_demos,
        "language": language,
        "issues": all_issues,
        "issues_by_file": {k: v for k, v in sorted(by_file.items())},
        "summary": dict(summary),
    }


def format_report(report: dict) -> str:
    """Format the report as human-readable text."""
    lines = []
    lines.append("## Demo QA Report")
    lines.append("")
    lines.append(f"**Status:** {report['status']}")
    lines.append(f"**Guide:** {report['guide']}")
    if report.get("companion_dir"):
        lines.append(f"**Companion dir:** {report['companion_dir']}")
    if report.get("expected_demos"):
        lines.append(f"**Expected demos:** {report['expected_demos']}")
    lines.append("")
    lines.append("### Summary")
    summary = report.get("summary", {})
    lines.append(f"- CRITICAL: {summary.get('CRITICAL', 0)}")
    lines.append(f"- MAJOR: {summary.get('MAJOR', 0)}")
    lines.append(f"- MINOR: {summary.get('MINOR', 0)}")
    lines.append("")

    if not report.get("issues"):
        lines.append("No issues found.")
    else:
        lines.append("### Issues by File")
        lines.append("")
        by_file = report.get("issues_by_file", {})
        for filename in sorted(by_file.keys()):
            file_issues = by_file[filename]
            lines.append(f"#### {filename}")
            for issue in file_issues:
                lines.append(
                    f"- **[{issue['severity']}]** ({issue['check']}) {issue['message']}"
                )
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo package QA checks")
    parser.add_argument("guide_path", help="Path to the main demo guide .md file")
    parser.add_argument(
        "--companion-dir",
        default=None,
        help="Path to companion scripts directory (auto-detected if omitted)",
    )
    parser.add_argument(
        "--expected-demos",
        type=int,
        default=None,
        help="Expected number of demos",
    )
    parser.add_argument(
        "--language",
        choices=["en", "ja"],
        default="en",
        help="Output language; 'ja' skips em-dash check and adds Japanese checks",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of text",
    )
    args = parser.parse_args()

    report = run_all_checks(
        args.guide_path,
        args.companion_dir,
        args.expected_demos,
        language=args.language,
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_report(report))

    sys.exit(
        0 if report["status"] == "CLEAN" else 2 if report["status"] == "ERROR" else 1
    )
