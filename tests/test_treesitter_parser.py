"""Tests for TreeSitterParser internals.

Covers regression scenarios for language-pack integration that are NOT
exercised by ``tests/test_parser_failures.py`` (which mocks ``ParserFactory``
and focuses on the surfacing layer added in Item 1).

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated_pack_cache(tmp_path: Path):
    """Redirect ``tree-sitter-language-pack``'s cache to ``tmp_path`` for the
    duration of the test, then restore the default.

    ``configure(cache_dir=...)`` is process-global state in the language pack;
    leaving it pointed at a tmp dir would break unrelated tests, so we restore
    on teardown via ``configure(cache_dir=None)``.

    Skips automatically when the ``[multilang]`` extra is not installed.
    """
    try:
        from tree_sitter_language_pack import configure
    except ImportError:
        pytest.skip("[multilang] extra not installed; cannot isolate pack cache")
    configure(cache_dir=str(tmp_path))
    try:
        yield tmp_path
    finally:
        configure(cache_dir=None)


@pytest.mark.integration
def test_csharp_parses_with_cold_cache(isolated_pack_cache: Path) -> None:
    """Regression: ``c_sharp`` must resolve via the language-pack manifest, not
    rely on filesystem fallback from a previously-warmed cache.

    Bug history:
      - ``tree-sitter-language-pack`` 1.6.2 manifest registers C# under the
        canonical name ``csharp``. The legacy alias ``c_sharp`` is NOT in the
        manifest (verified empirically).
      - Hefesto's ``LANG_MAP`` passed through ``c_sharp`` verbatim. With cold
        cache (every CI run, every fresh user install), ``get_parser('c_sharp')``
        failed with ``LanguageNotFoundError`` and the parsers tarball was never
        downloaded — every ``.cs`` file silent-skipped persistently.
      - The bug was masked on warm caches because
        ``libtree_sitter_c_sharp.dylib`` becomes filesystem-resolvable once any
        other call (e.g. ``get_parser('csharp')``) populates the cache, even
        though manifest lookup still fails.

    Regression guard: ``isolated_pack_cache`` redirects the pack's cache to
    ``tmp_path``, guaranteeing a cold cache for this test regardless of host
    state. Without the LANG_MAP fix, ``TreeSitterParser('c_sharp')`` raises
    ``LanguageNotFoundError`` at construction. With the fix, it downloads to
    ``tmp_path`` and parses successfully.
    """
    from hefesto.core.parsers.treesitter_parser import USE_PREBUILT, TreeSitterParser

    if not USE_PREBUILT:
        pytest.skip("[multilang] extra not installed; cannot exercise prebuilt path")

    # Construction is the bug surface: pre-fix this line raises
    # LanguageNotFoundError because LANG_MAP['c_sharp'] = 'c_sharp' (manifest miss).
    parser = TreeSitterParser("c_sharp")

    ast = parser.parse("class Foo { int Bar() { return 1; } }", "a.cs")

    assert ast.root.children, (
        "C# AST has no children — parser loaded grammar but produced "
        "empty tree (degenerate case, not the LANG_MAP regression)"
    )


# --- Names must not shift when non-ASCII text precedes them -----------------
#
# tree-sitter reports byte offsets into the UTF-8 source. Slicing the decoded
# ``str`` with them shifts every name after a BOM (3 bytes, 1 character) or an
# accented comment ("é" is 2 bytes, 1 character).

_NON_ASCII_PREFIXES = {
    "bom": "\ufeff",
    "accented_comment": "// café crème\n",
}

_NAMED_SOURCES = {
    "java": ("class Pedido { void calcularTotal() { } }", "calcularTotal"),
    "go": ("package main\nfunc calcularTotal() {}\n", "calcularTotal"),
    "rust": ("fn calcular_total() {}\n", "calcular_total"),
    "c_sharp": ("class Pedido { void CalcularTotal() { } }", "CalcularTotal"),
    "javascript": ("function calcularTotal() {}\n", "calcularTotal"),
    "typescript": ("function calcularTotal(): void {}\n", "calcularTotal"),
}


def _names(node, out):
    if node.name:
        out.append(node.name)
    for child in node.children:
        _names(child, out)
    return out


@pytest.mark.parametrize("prefix", sorted(_NON_ASCII_PREFIXES))
@pytest.mark.parametrize("language", sorted(_NAMED_SOURCES))
def test_names_survive_non_ascii_prefix(language: str, prefix: str) -> None:
    pytest.importorskip("tree_sitter_language_pack")
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    code, expected = _NAMED_SOURCES[language]
    source = _NON_ASCII_PREFIXES[prefix] + code
    ast = TreeSitterParser(language).parse(source, f"sample.{language}")

    assert expected in _names(ast.root, [])


def test_node_text_is_sliced_by_bytes() -> None:
    pytest.importorskip("tree_sitter_language_pack")
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    source = "// ñandú\nfunction calcularTotal() { return 1; }\n"
    ast = TreeSitterParser("javascript").parse(source, "sample.js")
    func = next(n for n in ast.root.children if n.name == "calcularTotal")

    assert func.text == "function calcularTotal() { return 1; }"
