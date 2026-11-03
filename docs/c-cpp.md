# C and C++ (experimental)

C and C++ support is an experimental feature, named `c-cpp`. Turn it on with

```bash
hefesto analyze . --experimental c-cpp
```

or in `.hefesto.yaml`:

```yaml
experimental:
  - c-cpp
```

**Experimental** means: off by default; its results have not been measured
yet; and a run without it gives the same output as a run of a release that did
not have it (C and C++ files are not even found). A name given on the command
line replaces the list in `.hefesto.yaml`. An unknown name stops the run with
exit code 2; a name that is no longer experimental only prints a warning. When
the feature is on, the JSON report lists it in `meta.experimental` and the SARIF
run in `properties.experimental`. The GitHub Action has no input for it, and the
MCP server never turns it on.

C and C++ files are parsed with the tree-sitter `c` and `cpp` grammars from the
`[multilang]` extra (`pip install "hefesto-ai[multilang]"`). Without the extra
they are skipped like the other tree-sitter languages.

### Memory and time

Measured on this machine (one run each, `--output json`; peak resident memory
of the `hefesto` process):

| Tree | Off | `--experimental c-cpp` | C/C++ files |
|---|---|---|---|
| zlib `51b7f2ab` | 42 MB, 1.4 s | 107 MB, 3.0 s | 74 |
| fmt `12391371` | 39 MB, 1.3 s | 122 MB, 5.5 s | 69 |
| react-native (shallow clone, 2026-11-02) | 175 MB, 32 s | 196 MB, 41 s | 1,682 |

Most of the extra memory is the two grammars, loaded once per run. The rest
grows with the size of the largest file, not with the number of files.

## What runs

The generic analyzers that run on every tree-sitter language: complexity
(`HIGH_COMPLEXITY`, `VERY_HIGH_COMPLEXITY`), size (`LONG_FUNCTION`,
`LONG_PARAMETER_LIST`, `GOD_CLASS`) and nesting (`DEEP_NESTING`). With `--experimental c-cpp,lang-security`, the
C/C++ security rules CC001-CC004 also run: `gets`, unbounded copies
(`strcpy`/`strcat`, `sprintf` with `%s`, `scanf` `%s`), format strings that
are not literals, and `system`/`popen` with a non-literal command. See the rule
table in `docs/ANALYSIS_RULES.md`. They are experimental.

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
removed it has `@interface`, `@protocol`, `@implementation`, `@end`, `@class`,
`@property` or `NS_ASSUME_NONNULL_BEGIN` at the start of a line. `#import` alone
does not count (GCC accepts it in C). This check runs before the C++ check, so a
header with both Objective-C and C++ syntax is Objective-C and is skipped too.
Doxygen commands such as `@interface` inside comments do not count. An
Objective-C header is treated like any file Hefesto does not recognize: it is
not found, so a tree with nothing but Objective-C headers gives the same exit
code and messages as without `--experimental c-cpp`.

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
