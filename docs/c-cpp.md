# C and C++ (experimental)

C and C++ files are parsed with the tree-sitter `c` and `cpp` grammars from the
`[multilang]` extra (`pip install "hefesto-ai[multilang]"`). Without the extra
they are skipped like the other tree-sitter languages.

## What runs

The generic analyzers that run on every tree-sitter language: complexity
(`HIGH_COMPLEXITY`, `VERY_HIGH_COMPLEXITY`), size (`LONG_FUNCTION`,
`LONG_PARAMETER_LIST`, `GOD_CLASS`) and nesting (`DEEP_NESTING`). There are no
C/C++-specific security rules yet.

Functions are named as declared: `alloc_buf`, `Widget::size`,
`Widget::~Widget`, `operator+`. Structs, unions, enums and classes use their
tag, template arguments included (`cache_accessor<double>`). A macro the
grammar reads as a return type in front of `namespace` (for example
`FMT_BEGIN_NAMESPACE namespace detail { ... }`) is not reported as a function.
`f(void)` has no parameters.

## Which files

| Suffix | Language |
|---|---|
| `.c` | C |
| `.cpp`, `.cc`, `.cxx`, `.c++`, `.hpp`, `.hh`, `.hxx` | C++ |
| `.h` | C, unless the header is C++ (below) |

A `.h` header is C++ when, after comments and string/character literals are
removed, it has C++-only syntax: `class` or `namespace` at the start of a line,
`template <`, `std::`, `using namespace`, an access label (`public:`), or an
`#include <name>` without a suffix (`<vector>`). `extern "C"` is not a marker,
since C headers wrap their declarations in it. Otherwise a header is C++ when a
`.cpp`, `.cc`, `.cxx` or `.c++` file with the same name sits next to it.
Otherwise it is C.

A `.h` header is Objective-C, and is skipped (not analyzed, not listed in
`meta.not_analyzed`, never fails the gate), when after comments and literals are
removed it has `@interface`, `@protocol`, `@implementation` or `@end` at the
start of a line, an `#import` directive, or `NS_ASSUME_NONNULL_BEGIN`. This check
runs before the C++ check, so Objective-C++ headers are skipped too. Doxygen
commands such as `@interface` inside comments do not count. Hefesto does not
analyze Objective-C (`.m`, `.mm` are not read either), so a tree with nothing but
Objective-C headers analyzes no file: `--fail-on` then exits 1 unless
`--allow-no-files` is set, as for any tree without supported files.

## Parse errors

Macros often leave tree-sitter with ERROR nodes. A file with ERROR nodes is
still analyzed as long as the grammar recovered at least one function,
declaration, type, namespace, template or preprocessor definition anywhere in
it (ERROR nodes included). A file where nothing was recovered is listed in
`meta.not_analyzed` with `reason: parse_error` and fails `--fail-on` like other
files that were not analyzed (`--allow-not-analyzed` opts out).

On zlib at `51b7f2ab` (74 C/C++ files) and fmt at `12391371` (70 files), every
file was analyzed; no file was reported as `parse_error`. zlib's three
`contrib/iostream*` headers were detected as C++ and its other 25 headers as C.

## Offline grammars

The `c` and `cpp` grammars are downloaded on first use like the others. With
an empty cache and no network, C/C++ files are reported as not analyzed with
`reason: grammar_unavailable`. To fill the cache:
`python -c "import tree_sitter_language_pack as p; p.download(['c','cpp'])"`.
