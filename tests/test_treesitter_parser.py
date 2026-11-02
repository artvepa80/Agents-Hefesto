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


def _declared_names(language: str, code: str) -> list:
    from hefesto.core.ast.generic_ast import NodeType
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    out: list = []

    def walk(node):
        if node.type in (NodeType.FUNCTION, NodeType.METHOD, NodeType.CLASS):
            out.append(node.name)
        for child in node.children:
            walk(child)

    walk(TreeSitterParser(language).parse(code, f"sample.{language}").root)
    return out


@pytest.mark.parametrize(
    "language, code, expected",
    [
        (
            "c_sharp",
            "class A { public async Task WriteLazy() { } }",
            ["A", "WriteLazy"],
        ),
        (
            "c_sharp",
            "class A { private TestClass Make(string s) { return null; } }",
            ["A", "Make"],
        ),
        (
            "c_sharp",
            "class A { public void Throws<T>() where T : Exception { } }",
            ["A", "Throws"],
        ),
        (
            "go",
            "package p\n\nfunc (s *Server) Run(x int) int { return x }\n",
            ["Run"],
        ),
        (
            "c_sharp",
            "class A { public TException Throws<TException>()"
            " where TException : Exception { return null; } }",
            ["A", "Throws"],
        ),
        ("typescript", "class Foo {}", ["Foo"]),
        (
            "java",
            "class A { List<String> items() { return null; } }",
            ["A", "items"],
        ),
    ],
)
def test_declared_name_not_return_type_or_receiver(language: str, code: str, expected) -> None:
    pytest.importorskip("tree_sitter_language_pack")

    assert _declared_names(language, code) == expected


@pytest.mark.parametrize(
    "language, code, expected",
    [
        ("rust", "struct S;\nimpl S { fn run(&self) {} }\n", ["S", "S", "run"]),
        ("rust", "impl<T> Tr for Vec<T> { fn go() {} }\n", ["Vec", "go"]),
        ("rust", "impl a::B { }\n", ["B"]),
        ("rust", "impl<'a> Tr for &'a S { }\n", ["S"]),
        ("rust", "impl Tr for (A, B) { }\n", [None]),
        ("rust", "impl Tr for [u8; 4] { }\n", [None]),
        ("go", "package p\n\ntype Server struct{}\n", ["Server"]),
        ("go", "package p\n\ntype ID = int\n", ["ID"]),
        ("go", "package p\n\ntype (\n\tA int\n\tB string\n)\n", ["A"]),
    ],
)
def test_type_blocks_named_after_their_type(language: str, code: str, expected) -> None:
    """Rust ``impl`` blocks and Go ``type`` declarations carry the type's name."""
    pytest.importorskip("tree_sitter_language_pack")

    assert _declared_names(language, code) == expected


def test_god_class_on_rust_impl_names_the_type() -> None:
    """End to end: GOD_CLASS on a large Rust ``impl`` names the type, not ``<anonymous>``."""
    pytest.importorskip("tree_sitter_language_pack")
    from hefesto.analyzers.code_smells import GOD_CLASS_THRESHOLD, CodeSmellAnalyzer
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    body = "\n".join(f"    fn f{i}() {{}}" for i in range(GOD_CLASS_THRESHOLD + 5))
    code = f"struct Big;\nimpl Big {{\n{body}\n}}\n"
    tree = TreeSitterParser("rust").parse(code, "big.rs")
    issues = CodeSmellAnalyzer()._check_god_classes(tree, "big.rs", code)

    assert [i.message.split(" is ")[0] for i in issues] == ["Class 'Big'"]
