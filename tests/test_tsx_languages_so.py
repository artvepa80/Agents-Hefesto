"""The ``languages.so`` fallback selects a grammar per suffix.

``.tsx`` loads the ``tsx`` symbol. ``.ts`` loads ``typescript``. The fallback
used to build one parser (the ``tsx`` symbol) for every TypeScript file, so
an angle-bracket cast and a JSX element could not both parse.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_JSX = "export const View = (name: string) => <div id={name} />;\n"
_CAST = "export function id<T>(expr: T): T {\n  return <T>expr;\n}\n"
# tree-sitter-typescript commit whose parser.c links against tree-sitter 0.26.
_GRAMMAR_SHA = "75b3874edb2dc714fb1fd77a32013d0f8699989f"


def _types(parser, code: str, path: str) -> set:
    ast = parser.parse(code, path)
    assert ast.language == "typescript"
    return {str(node.metadata.get("treesitter_type")) for node in ast.walk()}


def test_manual_fallback_requests_typescript_for_ts_and_tsx_for_tsx(monkeypatch) -> None:
    """Suffix chooses the symbol. The ``tsx`` parser is built once and cached."""
    from hefesto.core.parsers import treesitter_parser as mod

    loaded: list[str] = []

    class _Parser:
        def __init__(self, name: str) -> None:
            self.name = name

        def parse(self, data: bytes):
            raise AssertionError(data)

    def fake(grammar_name: str) -> _Parser:
        loaded.append(grammar_name)
        return _Parser(grammar_name)

    monkeypatch.setattr(mod, "USE_PREBUILT", False)
    monkeypatch.setattr(mod, "_manual_parser", fake)
    parser = mod.TreeSitterParser("typescript")
    assert loaded == ["typescript"]
    tsx = parser._parser_for("src/View.tsx")
    assert loaded == ["typescript", "tsx"]
    assert parser._parser_for("src/Other.tsx") is tsx
    assert loaded == ["typescript", "tsx"]
    assert parser._parser_for("src/cast.ts") is parser.parser
    assert parser._parser_for("src/App.jsx") is parser.parser
    js = mod.TreeSitterParser("javascript")
    assert loaded == ["typescript", "tsx", "javascript"]
    assert js._parser_for("src/View.tsx") is js.parser


def _build_languages_so(tmp_path: Path) -> Path:
    gcc = shutil.which("gcc")
    git = shutil.which("git")
    if gcc is None or git is None:
        pytest.skip("gcc and git are required to build languages.so")
    src = tmp_path / "tree-sitter-typescript"
    fetched = subprocess.run(
        ["git", "init", str(src)],
        capture_output=True,
        text=True,
        check=False,
    )
    if fetched.returncode != 0:
        pytest.skip(fetched.stderr.strip())
    subprocess.run(["git", "-C", str(src), "remote", "add", "origin", _REMOTE], check=True)
    fetched = subprocess.run(
        ["git", "-C", str(src), "fetch", "--depth", "1", "origin", _GRAMMAR_SHA],
        capture_output=True,
        text=True,
        check=False,
    )
    if fetched.returncode != 0:
        pytest.skip(fetched.stderr.strip())
    subprocess.run(["git", "-C", str(src), "checkout", "--detach", "FETCH_HEAD"], check=True)
    objects: list[str] = []
    for name in ("typescript", "tsx"):
        base = src / name / "src"
        for unit in ("parser.c", "scanner.c"):
            obj = tmp_path / f"{name}-{unit}.o"
            built = subprocess.run(
                [gcc, "-fPIC", "-c", f"-I{base}", str(base / unit), "-o", str(obj)],
                capture_output=True,
                text=True,
                check=False,
            )
            if built.returncode != 0:
                pytest.skip(built.stderr.strip())
            objects.append(str(obj))
    library = tmp_path / "languages.so"
    linked = subprocess.run(
        [gcc, "-shared", "-o", str(library), *objects],
        capture_output=True,
        text=True,
        check=False,
    )
    if linked.returncode != 0:
        pytest.skip(linked.stderr.strip())
    return library


_REMOTE = "https://github.com/tree-sitter/tree-sitter-typescript.git"


def test_languages_so_parses_jsx_in_tsx_and_casts_in_ts(tmp_path: Path, monkeypatch) -> None:
    """A real ``languages.so`` follows the same split as the prebuilt pack."""
    from hefesto.core.parsers import treesitter_parser as mod

    library = _build_languages_so(tmp_path)
    monkeypatch.setattr(mod, "USE_PREBUILT", False)
    monkeypatch.setattr(mod, "_languages_so", lambda: library)
    parser = mod.TreeSitterParser("typescript")

    tsx_types = _types(parser, _JSX, "src/View.tsx")
    assert "ERROR" not in tsx_types
    assert "jsx_self_closing_element" in tsx_types

    ts_types = _types(parser, _CAST, "src/cast.ts")
    assert "ERROR" not in ts_types
    assert "type_assertion" in ts_types

    cast_in_tsx = _types(parser, _CAST, "src/cast.tsx")
    assert "ERROR" in cast_in_tsx
    assert "type_assertion" not in cast_in_tsx
