# 2026-10-17 — 4.20.2: parse each YAML file once, with CSafeLoader

PR: #139 (runtime under GH-8: opened 2026-10-17 Lima, not merged that day; merging needs Arturo's OK). No tag, release or PyPI publish.

## What was reported

A profile of Kubernetes manifests: 1 MB took 4.7 s on 4.19.0, 8.8 s on 4.20.0 and 7.9 s on 4.20.1; 4 MB took 31.7 s. Since 4.20.0 a normal YAML file was parsed twice (format detection, then the analyzer), both times with the pure-Python `SafeLoader` even when libyaml was installed. One parse of the same file was 3.62 s with `SafeLoader` and 0.44 s with `CSafeLoader`, with the same documents.

## Reproduced here

Machine: Linux, 4 CPUs, Python 3.12.3, PyYAML 6.0.1 (`CSafeLoader` present). Throwaway venvs: `pip install hefesto-ai==4.19.0`, `==4.20.0`, `==4.20.1`. Fixtures generated in this session: `/tmp/yaml-repro/k8s-1mb.yaml` (1,004,184 bytes, 2,808 documents) and `k8s-4mb.yaml` (4,014,906 bytes, 11,142 documents). Multi-document Kubernetes Deployments, Services and ConfigMaps, with anchors and aliases inside each document (an alias does not cross `---`).

Command, best of 2 runs, wall clock, and the tool's "Analysis complete" line on that run:

```bash
HEFESTO_TELEMETRY=0 HEFESTO_NO_UPSELL=1 \
  hefesto analyze FILE --no-config --quiet --severity LOW
```

| version | 1 MB | 4 MB |
| --- | --- | --- |
| 4.19.0 | 1.804 s (1.68 s) | 6.694 s (6.58 s) |
| 4.20.0 | 4.485 s (4.37 s) | 17.828 s (17.71 s) |
| 4.20.1 | 4.504 s (4.39 s) | 17.908 s (17.79 s) |
| 4.20.2, this tree, best of 3, event scan on every file | 0.685 s (0.57 s) | 2.397 s (2.28 s) |

One `yaml.load_all` of the same strings, best of 2:

| file | SafeLoader | CSafeLoader | documents |
| --- | --- | --- | --- |
| 1 MB | 1.404 s | 0.174 s | 2,808 |
| 4 MB | 5.621 s | 0.686 s | 11,142 |

Loader calls inside `AnalyzerEngine.analyze_path` (monkeypatch of `yaml.safe_load`, `safe_load_all`, `load`, `load_all`, `unsafe_load`; `safe_load_all` calls `load_all`, so both increment together). Run from `/tmp` so the venv package is imported, not this tree:

| case | safe_load_all | load_all | safe_load | unsafe_load |
| --- | --- | --- | --- | --- |
| 4.19.0, one file | 1 | 1 | 0 | 0 |
| 4.20.0, one file | 3 | 3 | 0 | 0 |
| 4.20.1, one file | 3 | 3 | 0 | 0 |
| 4.20.1, directory of that file | 2 | 2 | 0 | 0 |
| this tree, one file | 0 | 1 (`CSafeLoader`) | 0 | 0 |

## Where the report does not match

- The absolute seconds are lower here than 4.7 / 8.8 / 7.9 / 31.7 and 3.62 / 0.44. The 4.20.1 worklog's machine was an 8 vCPU Xeon on Python 3.13.5. The shape matches: 4.20.0 and 4.20.1 are much slower than 4.19.0, 4 MB is about four times 1 MB, and `CSafeLoader` is about eight times faster than `SafeLoader` on the same documents.
- 4.20.1 was not faster than 4.20.0 here. The two sit inside run-to-run noise (1 MB 4.485 s vs 4.504 s).
- "Parsed twice" is the directory walk. A file named on the command line is parsed three times: `LanguageDetector.is_supported(path, text)` classifies it, then `_analyze_file` classifies it again, then the analyzer parses it. 4.19.0 parsed once.

## Cause

`hefesto/core/languages/content_classify.py` called `yaml.safe_load_all`. `YamlAnalyzer._check_syntax` called it again, and the CloudFormation, Helm and Serverless analyzers called `yaml.safe_load`. PyYAML's `safe_load` / `safe_load_all` hardcode `SafeLoader`. Discovery of a single path passed the file text into `is_supported`, which classified it before analysis read the file into a different string.

## What 4.20.2 does

- `hefesto/core/config_parse.py` parses with `CSafeLoader` or `SafeLoader` and keeps the result for the string object inside `parse_scope()`, which `_analyze_file` enters around detection and analysis.
- `is_supported` does not read the text when the path is already a known language. Extensionless shebang files still pass the text.
- A loader exception is re-parsed with `SafeLoader` when the C loader was used. SafeLoader's mark and message are the finding, so C and Python runs match. If only the C loader rejects the document, SafeLoader's documents are used. Any `Exception` from the loader (including `ValueError` from a timestamp) stays a syntax finding, and the file's other findings are still reported. A file that cannot be read is still not analyzed.
- Helm templates (`{{` under `<chart>/templates/` next to `Chart.yaml`) are not parsed. A syntax error on a real YAML file is still a `YAML_SYNTAX_ERROR` (HIGH) and fails `--fail-on`. Non-UTF-8 stays on the `latin-1` fallback.
- JSON detection, `JsonAnalyzer`, ARM and CloudFormation JSON share one `json.loads`. TOML was already one `tomli.loads`.
- Tests: `tests/test_yaml_single_parse.py` (findings match with each loader forced, including anchors, `!Ref` / `!GetAtt`, syntax lines, Helm `{{ }}`, multi-document files, a real libyaml `ReaderError`, and a non-UTF-8 file) and `tests/test_config_parse_once.py` (one parse per file; a parser error is one `SafeLoader` load; a C-loader exception after the event scan is the extra `SafeLoader` parse when libyaml is installed).

## Review fixes (still 4.20.2)

- `CSafeLoader` segfaults between 20,000 and 30,000 levels on Python 3.13, flow and block, from a file of about 60 KB. A run of `- `, `[` or `{` misses `[ ` * 30000 and `{a: ` * 30000 (runs of 1). Real collection depth is `yaml.parse` with `CSafeLoader` (events, iterative). The scan runs for every file. `SafeLoader` rejects from depth 486-489 (recursion limit 1000, about 2 frames per level), not at 900 on 3.14. Depth above 256 uses `SafeLoader`. An alternating block (`a:` then `-`, two collections per indent column) at depth 990 has a longest line of about 500, so brackets plus that line used to skip the scan and the HIGH finding disappeared. `tests/test_yaml_loader_guards.py` compares depths 480-505 (one subprocess per shape, still on PR CI), that 990-level file, and both 30,000-level shapes in a subprocess. The module has no skip marker, so the CI matrix (3.10-3.14) runs it. Around depth 483-488 the finding is HIGH where 4.20.1 passed (1,090-run sweep, 107 diffs), because `SafeLoader` has more frames on the stack. Not chased.
- `created: 2001-13-01` raises `ValueError`, not `yaml.YAMLError`. 4.20.1's `except Exception` on `safe_load_all` recorded `YAML syntax error: month must be in 1..12` and still reported the other findings. The first 4.20.2 cut let the `ValueError` become "not analyzed" and dropped them. The loader now catches any `Exception` and keeps `SafeLoader`'s error, so the other findings stay.

## Arturo's decision (option A, still 4.20.2)

- Route to `SafeLoader` when the text has a tab, a line starting with `%`, or `[|>][0-9+-]*#`. The third rule is X4QW (`block: ># comment`).
- Over the 402 yaml-test-suite `in.yaml` files: no invalid document newly accepted, nothing newly rejected, and only JR7V and WZ62 (both valid) stop being flagged. Those two are one class: a `?` or `!` inside a flow collection (`urls: [http://example.com/?a=1, b]`, `{foo: a?}`, `a: [!!str, c]`). 4.20.1 flagged that class; 4.20.2 does not.
- A U+FEFF anywhere, and an empty flow `?` key (`(?:^|[\s\[{,])\?\s*[,\]}]`), also route to `SafeLoader`. Libyaml skips a BOM at the start of any line (a leading BOM hides `%`) and drops an empty `?` together with the next comma or bracket. Fixtures include `\ufeff%YAML 1.1#...`, a double BOM in front of DMG6 and N4JP, a BOM after `---`, `k: [?]]`, and a ConfigMap `hosts: [? ]]`.
- `tests/test_yaml_libyaml_divergence.py` has the 16 libyaml-only cases and the 10 SafeLoader-only cases, named by suite id.
- Left for 4.21.0: align YAML syntax findings with the yaml-test-suite in both directions, and an explicit depth limit that is the same on every Python.
