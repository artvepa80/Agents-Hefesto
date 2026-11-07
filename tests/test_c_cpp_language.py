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
    assert _decls("c", code) == [
        ("alloc_buf", 1, 2),
        ("point", 2, 0),
        ("no_args", 3, 0),
    ]


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
    engine.experimental = frozenset({"c-cpp"})
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


def test_error_at_top_level_with_recovered_functions_is_analyzed(
    tmp_path: Path,
) -> None:
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
        "@class Foo;\nint f(void);\n",
        "@property (nonatomic) int x;\n",
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
        "/* @class Foo;\n@property x */\nint f(void);\n",
        # ``#import`` alone is not enough: GCC accepts it in C too.
        '#import "Other.h"\nint f(void);\n',
    ],
)
def test_c_header_with_objc_words_in_comments_stays_c(tmp_path: Path, content: str) -> None:
    path = tmp_path / "plain.h"
    path.write_text(content)
    assert LanguageDetector.detect(path, content) == Language.C


_RN_TREE = {
    "ios/AppDelegate.h": "#import <UIKit/UIKit.h>\n@interface AppDelegate : UIResponder\n@end\n",
    "ios/RCTBridgeModule.h": _BRIDGE_H,
    # Objective-C++: Objective-C and C++ markers together count as Objective-C.
    "ios/TurboBridge.h": "namespace facebook {\nclass Turbo;\n}\n@class RCTBridge;\n",
    "cpp/jsi.cpp": "namespace jsi {\nint value(int a) { return a; }\n}\n",
    "cpp/util.c": "int add(int a, int b) { return a + b; }\n",
    "index.js": "export const x = 1;\n",
}


def _cli(tmp_path: Path, *args: str):
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "-m", "hefesto.cli.main", "analyze", str(tmp_path), *args],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )


def test_react_native_tree_does_not_fail_the_gate(tmp_path: Path) -> None:
    """``--experimental c-cpp --fail-on HIGH`` on a React Native-like tree exits 0,
    and none of its Objective-C headers is analyzed."""
    pytest.importorskip("tree_sitter_language_pack")
    for rel, text in _RN_TREE.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    result = _cli(
        tmp_path,
        "--experimental",
        "c-cpp",
        "--fail-on",
        "HIGH",
        "--output",
        "json",
        "--quiet",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for header in ("AppDelegate.h", "RCTBridgeModule.h", "TurboBridge.h"):
        assert header not in result.stdout
    assert "jsi.cpp" in result.stdout and "util.c" in result.stdout


def _normalized(text: str) -> str:
    import re

    return re.sub(r"\d+\.\d+s", "<t>", text)


def test_only_objective_c_headers_match_the_default_run(tmp_path: Path) -> None:
    """A tree of Objective-C headers gives the exit code and messages of a run
    without ``c-cpp`` (the files are unrecognized, as before C support)."""
    (tmp_path / "Bridge.h").write_text(_BRIDGE_H)
    default = _cli(tmp_path, "--fail-on", "HIGH")
    on = _cli(tmp_path, "--fail-on", "HIGH", "--experimental", "c-cpp")
    assert default.returncode == on.returncode == 1
    assert "Found 0 file(s)" in on.stdout
    assert "Gate failure: no files were analyzed (exit 1)" in on.stdout
    assert _normalized(on.stdout) == _normalized(default.stdout)
    assert on.stderr == default.stderr


def _measured_complexity(relative_path: str, name: str) -> int:
    """Complexity of the one function named ``name``, from the analyzer."""
    from hefesto.analyzers.complexity import ComplexityAnalyzer
    from hefesto.core.parsers.python_parser import PythonParser

    path = Path(__file__).resolve().parents[1] / relative_path
    code = path.read_text(encoding="utf-8")
    tree = PythonParser().parse(code, relative_path)
    found = [node for node in tree.get_functions() if node.name == name]
    assert len(found) == 1, name
    analyzer = ComplexityAnalyzer()
    score = analyzer._calculate_complexity(found[0])
    for issue in analyzer.analyze(tree, relative_path, code):
        if issue.function_name == name:
            assert issue.metadata["complexity"] == score
    return score


def test_header_language_stays_below_medium_complexity() -> None:
    from hefesto.analyzers.complexity import _THRESHOLDS
    from hefesto.core.analysis_models import AnalysisIssueSeverity

    medium = _THRESHOLDS[AnalysisIssueSeverity.MEDIUM]
    score = _measured_complexity("hefesto/core/languages/content_classify.py", "_header_language")
    assert score < medium, (score, medium)


def test_import_alone_stays_c(tmp_path: Path) -> None:
    """``#import`` by itself is C. Objective-C needs a line-start marker."""
    text = '#import "Other.h"\nint f(void);\n'
    path = tmp_path / "plain.h"
    path.write_text(text)
    assert LanguageDetector.detect(path, text) == Language.C


def test_oserror_on_first_sibling_suffix_keeps_header_c(tmp_path: Path, monkeypatch) -> None:
    """An OSError on ``.cpp`` stops the scan. A later ``.cc`` sibling stays unseen."""
    header = tmp_path / "widget.h"
    text = "int w(void);\n"
    header.write_text(text)
    (tmp_path / "widget.cc").write_text("int w() { return 1; }\n")
    real_is_file = Path.is_file

    def scanned(self: Path) -> bool:
        if self.suffix == ".cpp":
            raise OSError("denied")
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", scanned)
    assert LanguageDetector.detect(header, text) == Language.C


def test_cpp_marker_does_not_scan_siblings(tmp_path: Path, monkeypatch) -> None:
    """C++ syntax wins before any sibling lookup, including one that would fail."""
    header = tmp_path / "widget.h"
    text = "class Foo { int x; };\n"
    header.write_text(text)
    real_is_file = Path.is_file

    def scanned(self: Path) -> bool:
        if self.suffix in {".cpp", ".cc", ".cxx", ".c++"}:
            raise OSError("sibling scan")
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", scanned)
    assert LanguageDetector.detect(header, text) == Language.CPP


def test_c_cpp_rule_families_are_disjoint() -> None:
    """A name belongs to one family, so the check order cannot hide a second rule."""
    from hefesto.analyzers.lang_security_rules import (
        _CC_COPY,
        _CC_FORMAT,
        _CC_SCANF,
        _CC_SHELL,
    )

    families = {
        "copy": set(_CC_COPY),
        "scanf": set(_CC_SCANF),
        "format": set(_CC_FORMAT),
        "shell": set(_CC_SHELL),
    }
    names = list(families)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = families[left] & families[right]
            assert overlap == set(), (left, right, overlap)
    assert "gets" not in set().union(*families.values())


def test_qualification_and_rule_order() -> None:
    """One ``::`` and one ``std::`` strip. Scanf stays before format, then shell."""
    from hefesto.analyzers.lang_security_rules import (
        _cc_func_name,
        _cc_rule,
        _CcScope,
    )
    from hefesto.core.ast.generic_ast import GenericNode, NodeType

    def node(ts_type: str, text: str, children: list | None = None) -> GenericNode:
        return GenericNode(
            type=NodeType.UNKNOWN,
            name=None,
            line_start=1,
            line_end=1,
            column_start=0,
            column_end=0,
            text=text,
            children=children or [],
            metadata={"treesitter_type": ts_type, "named": True},
        )

    def call(func_type: str, func_text: str) -> GenericNode:
        return node(
            "call_expression",
            func_text + "(b)",
            [
                node(func_type, func_text),
                node("argument_list", "(b)", [node("identifier", "b")]),
            ],
        )

    assert _cc_func_name(call("identifier", "gets")) == "gets"
    assert _cc_func_name(call("qualified_identifier", "::std::gets")) == "gets"
    assert _cc_func_name(call("qualified_identifier", "std::std::gets")) is None
    assert _cc_func_name(call("qualified_identifier", "foo::gets")) is None
    assert _cc_func_name(call("field_expression", "obj.gets")) is None

    scope = _CcScope(frozenset(), "")
    buf = node("identifier", "d")
    src = node("identifier", "s")
    fmt_s = node("string_literal", '"%s"')
    assert _cc_rule("gets", [], scope) == "CC001"
    assert _cc_rule("scanf", [fmt_s, buf], scope) == "CC002"
    assert _cc_rule("sprintf", [buf, fmt_s, src], scope) == "CC002"
    assert _cc_rule("printf", [src], scope) == "CC003"
    assert _cc_rule("printf", [src, buf], scope) is None
    assert _cc_rule("system", [src], scope) == "CC004"
