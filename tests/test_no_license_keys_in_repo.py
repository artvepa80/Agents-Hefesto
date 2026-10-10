"""No real HefestoAI license keys in the public repo.

Two internal keys (revoked 2026-10-06) were still printed in CHANGELOG.md and
scripts/README.md, and CHANGELOG.md ships in every sdist. Only the documented
placeholder and the fabricated test key below may appear.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = re.compile(r"\bHFST-[A-Z0-9]{4}(?:-[A-Z0-9]{4}){4}\b")
ALLOWED = {
    "HFST-XXXX-XXXX-XXXX-XXXX-XXXX",  # documented placeholder
    "HFST-1234-5678-9ABC-DEF0-1234",  # fabricated example
}
SKIP_DIRS = {".git", "htmlcov", "venv", ".venv", "node_modules", "build", "dist"}
SUFFIXES = {".md", ".py", ".txt", ".toml", ".yml", ".yaml", ".json", ".cfg", ".ini"}


def _text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
            continue
        yield path


def test_only_placeholder_license_keys():
    offenders = []
    for path in _text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for match in KEY.findall(text):
            if match not in ALLOWED:
                offenders.append(f"{path.relative_to(ROOT)}: {match[:9]}…")
    assert not offenders, "Non-placeholder license keys found:\n" + "\n".join(offenders)


def test_changelog_ships_without_revoked_keys():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "HFST-XXXX-XXXX-XXXX-XXXX-XXXX" in text
    assert not [k for k in KEY.findall(text) if k not in ALLOWED]
