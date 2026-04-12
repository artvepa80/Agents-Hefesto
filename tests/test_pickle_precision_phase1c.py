"""Phase 1c regression tests — PICKLE_USAGE precision cleanup.

The legacy detector walked the GenericAST and flagged any ``IMPORT``
node whose text contained the substring ``pickle``. Imports whose
module names merely *contain* the substring — e.g. ``unpickler_utils``,
``PickleHandler``, ``pickling_config`` — were flagged as ``pickle``
imports even though they are unrelated modules.

The fix uses Python's ``ast`` module and checks the exact imported
module name.

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

from __future__ import annotations

from hefesto.analyzers.security import SecurityAnalyzer
from hefesto.core.analysis_models import AnalysisIssueType
from hefesto.core.language_detector import Language
from hefesto.core.parsers.parser_factory import ParserFactory


def _run(code: str, file_path: str = "prod/module.py"):
    parser = ParserFactory.get_parser(Language.PYTHON)
    tree = parser.parse(code, file_path)
    issues = SecurityAnalyzer().analyze(tree, file_path, code)
    return [i for i in issues if i.issue_type == AnalysisIssueType.PICKLE_USAGE]


def test_unpickler_utils_is_not_flagged() -> None:
    code = "from unpickler_utils import safe_load\n"
    assert _run(code) == []


def test_pickle_substring_in_identifier_is_not_flagged() -> None:
    code = "from hefesto_pro import PickleHandler\n"
    assert _run(code) == []


def test_pickling_config_module_is_not_flagged() -> None:
    code = "import pickling_config\n"
    assert _run(code) == []


def test_real_import_pickle_still_fires() -> None:
    code = "import pickle\n"
    issues = _run(code)
    assert len(issues) == 1
    assert issues[0].line == 1


def test_real_from_pickle_import_still_fires() -> None:
    code = "from pickle import loads\n"
    issues = _run(code)
    assert len(issues) == 1


def test_real_cpickle_still_fires() -> None:
    code = "import cPickle\n"
    issues = _run(code)
    assert len(issues) == 1


def test_from_pickle_multi_import_fires_once() -> None:
    """O5: ``from pickle import loads, dumps`` must fire once."""
    code = "from pickle import loads, dumps\n"
    issues = _run(code)
    assert len(issues) == 1


def test_import_pickle_aliased_still_fires() -> None:
    """``import pickle as p`` uses alias.name == 'pickle'."""
    code = "import pickle as p\n"
    issues = _run(code)
    assert len(issues) == 1


def test_from_pickle_star_still_fires() -> None:
    """``from pickle import *`` has node.module == 'pickle'."""
    code = "from pickle import *\n"
    issues = _run(code)
    assert len(issues) == 1


def test_mixed_imports_on_same_line_still_fires() -> None:
    """``import pickle, json`` — the pickle alias triggers one finding."""
    code = "import pickle, json\n"
    issues = _run(code)
    assert len(issues) == 1


def test_docstring_mentioning_pickle_is_not_flagged() -> None:
    code = '''"""Module docstring that mentions pickle serialization."""

def describe():
    return "Note: do not use pickle with untrusted input."
'''
    assert _run(code) == []
