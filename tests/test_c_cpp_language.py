"""C and C++ language support: detection, the ``.h`` heuristic, names and parse errors."""

from __future__ import annotations

from pathlib import Path

import pytest

from hefesto.core.language_detector import LanguageDetector
from hefesto.core.languages.specs import Language


@pytest.mark.parametrize(
    "name, expected",
    [
        ("a.c", Language.C),
        ("a.cpp", Language.CPP),
        ("a.cc", Language.CPP),
        ("a.cxx", Language.CPP),
        ("a.c++", Language.CPP),
        ("a.hpp", Language.CPP),
        ("a.hh", Language.CPP),
        ("a.hxx", Language.CPP),
        ("A.C", Language.C),  # suffixes are matched lower-case
    ],
)
def test_extension_detection(name: str, expected: Language) -> None:
    assert LanguageDetector.detect(Path(name)) == expected


C_HEADER = """#ifndef ZLIB_H
#define ZLIB_H
#ifdef __cplusplus
extern "C" {
#endif
typedef struct z_stream_s { int avail_in; } z_stream;
int deflate(z_stream *strm, int flush);
#ifdef __cplusplus
}
#endif
#endif
"""


@pytest.mark.parametrize(
    "content, expected",
    [
        (C_HEADER, Language.C),
        ("int add(int a, int b);\n", Language.C),
        ("// class Foo is documented elsewhere\nint f(void);\n", Language.C),
        ("/* namespace note\n   template<T> */\nint f(void);\n", Language.C),
        ('const char *s = "class X {";\n', Language.C),
        ("class Foo { public: int x; };\n", Language.CPP),
        ("namespace util {\nint f();\n}\n", Language.CPP),
        ("template <typename T> T max(T a, T b);\n", Language.CPP),
        ("#include <vector>\nstd::vector<int> v();\n", Language.CPP),
        ("using namespace std;\n", Language.CPP),
    ],
)
def test_h_header_content_heuristic(tmp_path: Path, content: str, expected: Language) -> None:
    path = tmp_path / "x.h"
    path.write_text(content)
    assert LanguageDetector.detect(path, content) == expected


def test_h_header_with_cpp_sibling_is_cpp(tmp_path: Path) -> None:
    (tmp_path / "widget.cpp").write_text("int w() { return 1; }\n")
    header = tmp_path / "widget.h"
    header.write_text("int w();\n")
    assert LanguageDetector.detect(header, "int w();\n") == Language.CPP


def test_h_header_with_c_sibling_stays_c(tmp_path: Path) -> None:
    (tmp_path / "widget.c").write_text("int w(void) { return 1; }\n")
    header = tmp_path / "widget.h"
    header.write_text("int w(void);\n")
    assert LanguageDetector.detect(header, "int w(void);\n") == Language.C


def _decls(language: str, code: str) -> list:
    pytest.importorskip("tree_sitter_language_pack")
    from hefesto.core.ast.generic_ast import NodeType
    from hefesto.core.parsers.treesitter_parser import TreeSitterParser

    out: list = []

    def walk(node):
        if node.type in (NodeType.FUNCTION, NodeType.METHOD, NodeType.CLASS):
            out.append((node.name, node.line_start, node.metadata["param_count"]))
        for child in node.children:
            walk(child)

    walk(TreeSitterParser(language).parse(code, "x").root)
    return out


def test_c_function_and_struct_names() -> None:
    code = (
        "static int *alloc_buf(int n, char **out) { return 0; }\n"
        "struct point { int x; };\n"
        "int no_args(void) { return 0; }\n"
    )
    assert _decls("c", code) == [("alloc_buf", 1, 2), ("point", 2, 0), ("no_args", 3, 0)]


def test_cpp_method_names() -> None:
    code = (
        "namespace n {\n"
        "class Widget {\n"
        " public:\n"
        "  void draw(int x) {}\n"
        "};\n"
        "}\n"
        "int Widget::size() const { return 1; }\n"
        "Widget::~Widget() {}\n"
        "template <typename T> T clamp(T v, T lo, T hi) { return v; }\n"
    )
    assert _decls("cpp", code) == [
        ("Widget", 2, 0),
        ("draw", 4, 1),
        ("Widget::size", 7, 0),
        ("Widget::~Widget", 8, 0),
        ("clamp", 9, 3),
    ]


def test_cpp_template_specialization_and_macro_wrapper() -> None:
    code = (
        "template <> struct cache<double> {\n  int x;\n};\n"
        "FMT_BEGIN_NAMESPACE\nnamespace detail {\nint f(int a) { return a; }\n}\n"
    )
    names = [n for n, _, _ in _decls("cpp", code)]
    # The macro before ``namespace`` is not reported as an unnamed function.
    assert names == ["cache<double>", "f"]


def _engine_run(tmp_path: Path, name: str, code: str):
    pytest.importorskip("tree_sitter_language_pack")
    from hefesto.core.analyzer_engine import AnalyzerEngine

    path = tmp_path / name
    path.write_text(code)
    engine = AnalyzerEngine(severity_threshold="LOW", quiet=True)
    report = engine.analyze_files([str(path)], project_root=str(tmp_path))
    return engine, report


def test_c_file_is_analyzed(tmp_path: Path) -> None:
    engine, report = _engine_run(tmp_path, "a.c", "int main(void) { return 0; }\n")
    assert [f.language for f in report.file_results] == ["c"]
    assert engine._not_analyzed == []


def test_partial_parse_is_analyzed(tmp_path: Path) -> None:
    """A macro the grammar cannot read leaves ERROR nodes; the rest is still analyzed."""
    code = "#define DECL(x) int x\nDECL(a) OF((int b));\nint ok(void) { return 0; }\n"
    engine, report = _engine_run(tmp_path, "m.c", code)
    assert [f.language for f in report.file_results] == ["c"]
    assert engine._not_analyzed == []


def test_unparseable_file_is_not_analyzed(tmp_path: Path) -> None:
    engine, report = _engine_run(tmp_path, "junk.c", "}}}} ))) @@@ ### !!!\n")
    assert report.file_results == []
    assert [(e["reason"], e["language"]) for e in engine._not_analyzed] == [("parse_error", "c")]


def test_error_at_top_level_with_recovered_functions_is_analyzed(tmp_path: Path) -> None:
    """A file whose whole body is one ERROR node, but with functions inside it, is analyzed.

    Real headers do this when a macro breaks the top level (fmt's format.h).
    """
    code = "FMT_BEGIN_NAMESPACE\nnamespace detail {\nint f(int a) { return a; }\n}\nFMT_END(\n"
    pytest.importorskip("tree_sitter_language_pack")
    from tree_sitter_language_pack import get_parser

    root = get_parser("cpp").parse(code.encode()).root_node
    assert root.has_error
    engine, report = _engine_run(tmp_path, "f.hpp", code)
    assert [f.language for f in report.file_results] == ["cpp"]
    assert engine._not_analyzed == []


# --- Objective-C headers ------------------------------------------------------

_BRIDGE_H = """\
#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@protocol BridgeDelegate <NSObject>
- (void)bridgeDidFinish:(NSString *)name;
@end

NS_ASSUME_NONNULL_END
"""


@pytest.mark.parametrize(
    "content",
    [
        _BRIDGE_H,
        "@interface Foo : NSObject\n@property int x;\n@end\n",
        "@protocol P\n- (void)run;\n@end\n",
        '#import "Other.h"\nint f(void);\n',
        "NS_ASSUME_NONNULL_BEGIN\nint f(void);\nNS_ASSUME_NONNULL_END\n",
        "  @end\n",
    ],
)
def test_objective_c_header_is_skipped(tmp_path: Path, content: str) -> None:
    """A ``.h`` with Objective-C syntax is not C: it is skipped, not analyzed as C."""
    path = tmp_path / "Bridge.h"
    path.write_text(content)
    assert LanguageDetector.detect(path, content) == Language.UNKNOWN


@pytest.mark.parametrize(
    "content",
    [
        # Doxygen @-commands and #import in comments or strings are not Objective-C.
        "/** @interface Foo\n * @protocol bar\n * @end\n */\nint f(void);\n",
        "// #import <x.h>\n// NS_ASSUME_NONNULL_BEGIN\nint f(void);\n",
        'const char *s = "@interface @end #import";\n',
        "int at_end(void); /* @end */\n",
    ],
)
def test_c_header_with_objc_words_in_comments_stays_c(tmp_path: Path, content: str) -> None:
    path = tmp_path / "plain.h"
    path.write_text(content)
    assert LanguageDetector.detect(path, content) == Language.C


def test_objective_c_header_does_not_fail_the_gate(tmp_path: Path) -> None:
    """``--fail-on HIGH`` on a tree with an Objective-C ``Bridge.h`` exits 0."""
    import subprocess
    import sys

    pytest.importorskip("tree_sitter_language_pack")
    (tmp_path / "Bridge.h").write_text(_BRIDGE_H)
    (tmp_path / "util.c").write_text("int add(int a, int b) { return a + b; }\n")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "hefesto.cli.main",
            "analyze",
            str(tmp_path),
            "--fail-on",
            "HIGH",
            "--output",
            "json",
            "--quiet",
        ],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Bridge.h" not in result.stdout


def test_only_objective_c_headers_need_allow_no_files(tmp_path: Path) -> None:
    """A tree with nothing but Objective-C headers analyzes no file, like a tree of
    ``.m`` files: ``--fail-on`` exits 1 unless ``--allow-no-files`` is set."""
    import subprocess
    import sys

    (tmp_path / "Bridge.h").write_text(_BRIDGE_H)
    base = [sys.executable, "-m", "hefesto.cli.main", "analyze", str(tmp_path), "--quiet"]
    root = str(Path(__file__).resolve().parents[1])
    strict = subprocess.run(base + ["--fail-on", "HIGH"], capture_output=True, cwd=root)
    allowed = subprocess.run(
        base + ["--fail-on", "HIGH", "--allow-no-files"], capture_output=True, cwd=root
    )
    assert (strict.returncode, allowed.returncode) == (1, 0)
