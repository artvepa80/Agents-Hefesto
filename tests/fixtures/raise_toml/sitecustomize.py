"""Test hook: make TomlAnalyzer.analyze raise inside a CLI subprocess."""

from hefesto.analyzers.devops import toml_analyzer


def _raise(self, file_path, content):
    raise RuntimeError("analyzer exploded")


toml_analyzer.TomlAnalyzer.analyze = _raise  # type: ignore[method-assign]
