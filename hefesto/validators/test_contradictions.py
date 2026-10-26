"""
Test Contradiction Detector - Finds tests with contradictory assertions.

This validator detects when multiple tests call the same function with the same
inputs but expect different outputs - a sign of logical inconsistency in the test suite.

Learned from: v4.0.1 release where two tests contradicted on insert_findings([]) behavior.

Real bug caught:
- test_bigquery_operations_fail_gracefully_when_not_configured expected True
- test_all_operations_return_safe_defaults_when_not_configured expected False
- Same function, same input, different expectations = BUG

Copyright (c) 2025 Narapa LLC, Miami, Florida
"""

import ast
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from hefesto.core.safe_parse import SYNTAX, safe_parse


@dataclass
class TestAssertion:
    """Represents a test assertion."""

    test_file: str
    test_function: str
    line_number: int
    function_called: str
    arguments: str
    expected_value: str
    assertion_type: str  # "assert_equal", "assert_true", "assert_false", etc.
    # Facts that precede a no-argument call (env, monkeypatch, platform, clock).
    # Empty for calls that have arguments. Two no-argument calls are the same
    # input only when this string matches.
    environment: str = ""


@dataclass
class Contradiction:
    """Represents a contradiction between two tests."""

    function_called: str
    arguments: str
    test1: TestAssertion
    test2: TestAssertion
    conflict_description: str


class _EnvFact(NamedTuple):
    """One environment-shaping fact found in a test, in source order."""

    lineno: int
    col: int
    text: str
    clock: bool
    freezes: bool


# Attribute calls that change or read the process environment, a monkeypatch,
# a platform check, or the clock. Matched by the attribute name: in a test,
# ``.setenv`` / ``.setattr`` / ``.patch`` is the environment, not a local helper.
_ENV_ATTRS = frozenset(
    {
        "setenv",
        "delenv",
        "putenv",
        "unsetenv",
        "getenv",
        "setattr",
        "delattr",
        "setitem",
        "delitem",
        "syspath_prepend",
        "chdir",
        "freeze_time",
        "frozen_time",
        "patch",
        "skip",
        "skipif",
        "skipIf",
        "skipunless",
        "skipUnless",
    }
)
_DIRECT_ENV_NAMES = frozenset(
    {"putenv", "unsetenv", "getenv", "freeze_time", "frozen_time", "patch"}
)
_PATCH_METHODS = frozenset({"dict", "object", "multiple"})
_PLATFORM_METHODS = frozenset(
    {"system", "machine", "release", "platform", "uname", "node", "python_implementation"}
)
_ENVIRON_METHODS = frozenset({"get", "update", "setdefault", "pop", "clear"})
_DATETIME_CALLS = frozenset({"now", "utcnow"})
_TIME_CALLS = frozenset({"time", "monotonic", "gmtime", "localtime", "time_ns"})
_SKIP_CONDITION_ATTRS = frozenset({"skipif", "skipIf", "skipunless", "skipUnless"})
_FREEZE_NAMES = frozenset({"freeze_time", "frozen_time"})


def _call_head(node: ast.Call) -> tuple[str, ast.AST | None]:
    """``(name, None)`` for ``f()``, ``(attr, receiver)`` for ``obj.f()``."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id, None
    if isinstance(func, ast.Attribute):
        return func.attr, func.value
    return "", None


def _root_name(node: ast.AST) -> str:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return ""


def _has_name(node: ast.AST, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.Attribute):
        return node.attr == name or _has_name(node.value, name)
    return False


def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    )


def _is_environ_target(node: ast.AST) -> bool:
    if _is_os_environ(node):
        return True
    return isinstance(node, ast.Subscript) and _is_os_environ(node.value)


def _is_clock_attr(attr: str, receiver: ast.AST) -> bool:
    if attr in _DATETIME_CALLS and _has_name(receiver, "datetime"):
        return True
    if attr == "today" and _has_name(receiver, "date"):
        return True
    return attr in _TIME_CALLS and _root_name(receiver) == "time"


def _is_platform_call(attr: str, receiver: ast.AST) -> bool:
    return attr in _PLATFORM_METHODS and _root_name(receiver) == "platform"


def _is_environ_method(attr: str, receiver: ast.AST) -> bool:
    return attr in _ENVIRON_METHODS and _is_os_environ(receiver)


def _is_patch_method(attr: str, receiver: ast.AST) -> bool:
    return attr in _PATCH_METHODS and _has_name(receiver, "patch")


def _is_env_attr_call(attr: str, receiver: ast.AST) -> bool:
    if attr in _ENV_ATTRS or _is_clock_attr(attr, receiver):
        return True
    return (
        _is_patch_method(attr, receiver)
        or _is_platform_call(attr, receiver)
        or _is_environ_method(attr, receiver)
    )


def _is_env_call(node: ast.Call) -> bool:
    attr, receiver = _call_head(node)
    if not attr:
        return False
    if receiver is None:
        return attr in _DIRECT_ENV_NAMES
    return _is_env_attr_call(attr, receiver)


def _is_clock_call(node: ast.Call) -> bool:
    attr, receiver = _call_head(node)
    if receiver is None:
        return False
    return _is_clock_attr(attr, receiver)


def _is_freeze_call(node: ast.Call) -> bool:
    attr, _receiver = _call_head(node)
    return attr in _FREEZE_NAMES


def _fact_text(node: ast.Call) -> str:
    """Canonical text of an environment call.

    ``skipif`` / ``skipUnless`` keep only the condition, so two tests that skip
    on the same platform with different ``reason=`` strings still compare.
    ``pytest.skip("...")`` keeps no message: the skip itself is the fact.
    """
    attr, _receiver = _call_head(node)
    if attr in _SKIP_CONDITION_ATTRS and node.args:
        return f"{attr}({ast.unparse(node.args[0])})"
    if attr == "skip":
        return "skip"
    return ast.unparse(node)


def _is_platform_or_environ_attr(node: ast.Attribute) -> bool:
    if not isinstance(node.value, ast.Name):
        return False
    if node.attr == "platform" and node.value.id == "sys":
        return True
    if node.attr == "name" and node.value.id == "os":
        return True
    return node.attr == "environ" and node.value.id == "os"


def _expr_is_ambient(expr: ast.AST) -> bool:
    """True when an ``if`` test reads the platform, the clock, or the environment."""
    for node in ast.walk(expr):
        if isinstance(node, ast.Call) and _is_env_call(node):
            return True
        if isinstance(node, ast.Attribute) and _is_platform_or_environ_attr(node):
            return True
        if isinstance(node, ast.Subscript) and _is_os_environ(node.value):
            return True
    return False


def _call_fact(node: ast.AST) -> _EnvFact | None:
    if not isinstance(node, ast.Call) or not _is_env_call(node):
        return None
    return _EnvFact(
        node.lineno,
        node.col_offset,
        _fact_text(node),
        _is_clock_call(node),
        _is_freeze_call(node),
    )


def _assigns_environ(node: ast.Assign) -> bool:
    return any(_is_environ_target(target) for target in node.targets)


def _assign_fact(node: ast.AST) -> _EnvFact | None:
    if isinstance(node, ast.Assign) and _assigns_environ(node):
        return _EnvFact(node.lineno, node.col_offset, ast.unparse(node), False, False)
    if isinstance(node, ast.AugAssign) and _is_environ_target(node.target):
        return _EnvFact(node.lineno, node.col_offset, ast.unparse(node), False, False)
    if isinstance(node, ast.Delete) and any(_is_environ_target(t) for t in node.targets):
        return _EnvFact(node.lineno, node.col_offset, ast.unparse(node), False, False)
    return None


def _if_fact(node: ast.AST) -> _EnvFact | None:
    if not isinstance(node, ast.If) or not _expr_is_ambient(node.test):
        return None
    return _EnvFact(node.lineno, node.col_offset, ast.unparse(node.test), False, False)


def _fact_from_node(node: ast.AST) -> _EnvFact | None:
    return _call_fact(node) or _assign_fact(node) or _if_fact(node)


def _iter_test_nodes(func: ast.FunctionDef) -> Iterator[ast.AST]:
    """Nodes of a test, including decorators, excluding nested functions."""
    stack: list[ast.AST] = list(func.decorator_list)
    stack.extend(func.body)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _collect_env_facts(func: ast.FunctionDef) -> list[_EnvFact]:
    facts = [fact for node in _iter_test_nodes(func) if (fact := _fact_from_node(node)) is not None]
    facts.sort()
    return facts


def _fact_precedes(fact: _EnvFact, line: int, col: int) -> bool:
    if fact.lineno < line:
        return True
    return fact.lineno == line and fact.col < col


def _clock_is_uncontrolled(facts: list[_EnvFact]) -> bool:
    """A clock read with no ``freeze_time`` is a different value on every test."""
    saw_clock = False
    saw_freeze = False
    for fact in facts:
        saw_clock = saw_clock or fact.clock
        saw_freeze = saw_freeze or fact.freezes
    return saw_clock and not saw_freeze


def _environment_before(facts: list[_EnvFact], line: int, col: int) -> str | None:
    """Environment of a no-argument call, or None when it must not be compared.

    None means the test reads the wall clock without freezing it: the call's
    result is not a function of anything written in the test, so two tests are
    not the same input. A string (possibly empty) is a comparable environment.
    """
    prior = [fact for fact in facts if _fact_precedes(fact, line, col)]
    if _clock_is_uncontrolled(prior):
        return None
    return "\n".join(fact.text for fact in prior)


class TestContradictionDetector:
    """
    Detects contradictory assertions in test suite.

    Usage:
        detector = TestContradictionDetector("tests/")
        contradictions = detector.find_contradictions()
        detector.print_report(contradictions)
    """

    def __init__(self, test_directory: str = "tests"):
        """
        Initialize detector.

        Args:
            test_directory: Path to tests directory
        """
        self.test_dir = Path(test_directory)
        self.assertions: list[TestAssertion] = []
        # (path, reason) for files that could not be read or parsed
        self.skipped_files: list[tuple[Path, str]] = []
        # number of test files actually parsed and checked
        self.checked_files = 0

    def _parse_test_file(self, file_path: Path) -> None:
        """Parse a test file and extract assertions.

        Only a file that cannot be decoded or parsed is skipped, and it is
        recorded in ``skipped_files``. Any other exception is a bug in this
        detector and propagates, so the check never reports PASS without
        having checked anything.
        """
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            self.skipped_files.append((file_path, f"{type(exc).__name__}: {exc}"))
            return
        result = safe_parse(source, str(file_path))
        if result.error == SYNTAX:
            self.skipped_files.append((file_path, f"{result.error_type}: {result.error_message}"))
            return
        if result.tree is None:
            result.reraise()
        tree = result.tree
        self.checked_files += 1

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                self._extract_assertions(node, str(file_path))

    def _extract_assertions(self, func_node: ast.FunctionDef, file_path: str) -> None:
        """Extract assertion statements from a test function."""
        facts = _collect_env_facts(func_node)
        for node in ast.walk(func_node):
            # Handle assert statements (direct assert)
            if isinstance(node, ast.Assert):
                assertion = self._parse_assert_statement(node, func_node.name, file_path)
                call = node.test.left if isinstance(node.test, ast.Compare) else node.test
                self._keep(self._stamp_environment(assertion, facts, node), call)

            # Handle assertEqual, assertTrue, assertFalse, etc.
            elif isinstance(node, ast.Call):
                if hasattr(node.func, "attr"):
                    method_name = node.func.attr
                    if method_name.startswith("assert"):
                        assertion = self._parse_unittest_assertion(
                            node, func_node.name, file_path, method_name
                        )
                        self._keep(
                            self._stamp_environment(assertion, facts, node),
                            self._unittest_call(node),
                        )

    def _parse_assert_statement(
        self, node: ast.Assert, test_func: str, file_path: str
    ) -> TestAssertion | None:
        """Parse a direct assert statement."""
        # Handle: assert func(args) == value
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Call) and hasattr(left.func, "id"):
                function_name = left.func.id
            elif isinstance(left, ast.Call) and hasattr(left.func, "attr"):
                # Handle method calls like client.insert_findings()
                if isinstance(left.func, ast.Attribute) and hasattr(left.func.value, "id"):
                    obj_name = left.func.value.id
                    method_name = left.func.attr
                    function_name = f"{obj_name}.{method_name}"
                else:
                    return None
            else:
                return None

            # Get arguments
            args_str = self._extract_arguments(left)

            # Get expected value
            if node.test.comparators:
                expected = self._extract_value(node.test.comparators[0])
            else:
                return None

            # Get comparison operator
            op = node.test.ops[0]
            if isinstance(op, ast.Eq):
                assertion_type = "assert_equal"
            elif isinstance(op, ast.Is):
                assertion_type = "assert_is"
            else:
                return None

            return TestAssertion(
                test_file=file_path,
                test_function=test_func,
                line_number=node.lineno,
                function_called=function_name,
                arguments=args_str,
                expected_value=expected,
                assertion_type=assertion_type,
            )

        # Handle: assert func(args) (implicit True)
        elif (
            isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Attribute)
            and hasattr(node.test.func.value, "id")
        ):
            obj_name = node.test.func.value.id
            method_name = node.test.func.attr
            function_name = f"{obj_name}.{method_name}"

            args_str = self._extract_arguments(node.test)

            return TestAssertion(
                test_file=file_path,
                test_function=test_func,
                line_number=node.lineno,
                function_called=function_name,
                arguments=args_str,
                expected_value="True",
                assertion_type="assert_implicit_true",
            )

        return None

    def _parse_unittest_assertion(
        self, node: ast.Call, test_func: str, file_path: str, method_name: str
    ) -> TestAssertion | None:
        """Parse unittest-style assertions (assertEqual, assertTrue, etc.)."""
        if method_name == "assertEqual":
            if len(node.args) >= 2:
                first_arg = node.args[0]
                expected = self._extract_value(node.args[1])

                if isinstance(first_arg, ast.Call):
                    function_name = self._extract_function_name(first_arg)
                    args_str = self._extract_arguments(first_arg)

                    return TestAssertion(
                        test_file=file_path,
                        test_function=test_func,
                        line_number=node.lineno,
                        function_called=function_name,
                        arguments=args_str,
                        expected_value=expected,
                        assertion_type="assertEqual",
                    )

        elif method_name in ("assertTrue", "assert_"):
            if len(node.args) >= 1:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Compare):
                    # Handle: assertTrue(func(args) is True)
                    left = first_arg.left
                    if isinstance(left, ast.Call):
                        function_name = self._extract_function_name(left)
                        args_str = self._extract_arguments(left)
                        expected = self._extract_value(first_arg.comparators[0])

                        return TestAssertion(
                            test_file=file_path,
                            test_function=test_func,
                            line_number=node.lineno,
                            function_called=function_name,
                            arguments=args_str,
                            expected_value=expected,
                            assertion_type="assertTrue_compare",
                        )

        elif method_name == "assertFalse" and len(node.args) >= 1:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Compare) and isinstance(first_arg.left, ast.Call):
                left = first_arg.left
                function_name = self._extract_function_name(left)
                args_str = self._extract_arguments(left)

                # assertFalse reverses the expectation
                expected_val = self._extract_value(first_arg.comparators[0])
                # Reverse boolean expectations
                if expected_val == "True":
                    expected = "False"
                elif expected_val == "False":
                    expected = "True"
                else:
                    expected = f"not {expected_val}"

                return TestAssertion(
                    test_file=file_path,
                    test_function=test_func,
                    line_number=node.lineno,
                    function_called=function_name,
                    arguments=args_str,
                    expected_value=expected,
                    assertion_type="assertFalse",
                )

        return None

    @staticmethod
    def _unittest_call(node: ast.Call) -> ast.AST | None:
        """The call under test in assertEqual(call, x) / assertTrue(call == x)."""
        if not node.args:
            return None
        first = node.args[0]
        return first.left if isinstance(first, ast.Compare) else first

    @staticmethod
    def _is_literal(node: ast.AST) -> bool:
        """A Constant, or a list/tuple whose elements are all Constants."""
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, (ast.List, ast.Tuple)):
            return all(isinstance(e, ast.Constant) for e in node.elts)
        return False

    def _is_comparable_call(self, node: ast.AST) -> bool:
        """Only calls whose result depends on nothing but the call itself are compared.

        The target must be a plain function name (``add(...)``, not ``obj.add(...)``)
        and every argument a literal. ``len(issues)`` in two tests reads two different
        local ``issues``, so equal text does not mean equal input.

        A call with no arguments passes here: an empty argument list has no
        non-literal. It is not yet the same input as another no-argument call;
        ``_stamp_environment`` drops it, or separates it, when the tests set
        different environments or read the wall clock.
        """
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            return False
        if any(not self._is_literal(a) for a in node.args):
            return False
        return all(k.arg is not None and self._is_literal(k.value) for k in node.keywords)

    def _extract_function_name(self, call_node: ast.Call) -> str:
        """Extract function name from call node."""
        if hasattr(call_node.func, "id"):
            return str(call_node.func.id)
        if isinstance(call_node.func, ast.Attribute) and hasattr(call_node.func.value, "id"):
            obj_name = call_node.func.value.id
            method_name = call_node.func.attr
            return f"{obj_name}.{method_name}"
        return "unknown"

    def _extract_arguments(self, call_node: ast.Call) -> str:
        """Extract arguments as string representation."""
        args_parts = []

        for arg in call_node.args:
            args_parts.append(self._extract_value(arg))

        for keyword in call_node.keywords:
            value = self._extract_value(keyword.value)
            args_parts.append(f"{keyword.arg}={value}")

        return ", ".join(args_parts)

    def _extract_value(self, node: ast.AST) -> str:
        """Extract value as string."""
        # Literals are ast.Constant on every supported Python (>= 3.10);
        # ast.Num/Str/NameConstant were removed in 3.14.
        if isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.List):
            elements = [self._extract_value(e) for e in node.elts]
            return f"[{', '.join(elements)}]"
        elif isinstance(node, ast.Dict):
            return "{...}"
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            if hasattr(node.value, "id"):
                return f"{node.value.id}.{node.attr}"
            return node.attr
        else:
            return "?"

    def _stamp_environment(
        self,
        assertion: TestAssertion | None,
        facts: list[_EnvFact],
        anchor: ast.AST,
    ) -> TestAssertion | None:
        """Attach the environment of a no-argument call, or drop an unsound one.

        Calls with arguments are unchanged: the literals are the input, whatever
        else the test sets. A no-argument call is compared only with calls whose
        preceding environment facts are the same. A wall-clock read with no
        ``freeze_time`` is not comparable at all (``_environment_before`` is None).
        """
        if assertion is None or assertion.arguments != "":
            return assertion
        line = getattr(anchor, "lineno", None)
        col = getattr(anchor, "col_offset", None)
        if not isinstance(line, int) or not isinstance(col, int):
            return assertion
        env = _environment_before(facts, line, col)
        if env is None:
            return None
        assertion.environment = env
        return assertion

    def _keep(self, assertion: TestAssertion | None, call: ast.AST | None) -> None:
        if assertion is not None and call is not None and self._is_comparable_call(call):
            self.assertions.append(assertion)

    def find_contradictions(self) -> list[Contradiction]:
        """Find all contradictions in test suite."""
        # Parse all test files
        if not self.test_dir.exists():
            return []

        for test_file in self.test_dir.rglob("test_*.py"):
            self._parse_test_file(test_file)

        # Group by function + arguments. A no-argument call also carries the
        # environment facts that precede it, so two tests that set different
        # environments are not the same input.
        groups: dict[tuple[str, str, str], list[TestAssertion]] = defaultdict(list)

        for assertion in self.assertions:
            key = (assertion.function_called, assertion.arguments, assertion.environment)
            groups[key].append(assertion)

        # Find contradictions
        contradictions = []

        for (func_name, args, _environment), assertions in groups.items():
            # Check if there are different expected values
            expectations: dict[str, list[TestAssertion]] = {}
            for assertion in assertions:
                exp_val = assertion.expected_value
                if exp_val not in expectations:
                    expectations[exp_val] = []
                expectations[exp_val].append(assertion)

            # If more than one unique expectation, we have a contradiction
            if len(expectations) > 1:
                # Create contradiction for each pair
                exp_list = list(expectations.items())
                for i, (val1, asserts1) in enumerate(exp_list):
                    for val2, asserts2 in exp_list[i + 1 :]:
                        # Create contradiction between first assertion from each group
                        test1 = asserts1[0]
                        test2 = asserts2[0]

                        contradictions.append(
                            Contradiction(
                                function_called=func_name,
                                arguments=args,
                                test1=test1,
                                test2=test2,
                                conflict_description=(
                                    f"Test 1 expects {val1}, Test 2 expects {val2}"
                                ),
                            )
                        )

        return contradictions

    def print_report(self, contradictions: list[Contradiction]) -> None:
        """Print formatted report of contradictions."""
        if self.skipped_files:
            print(f"\n⚠️  Skipped {len(self.skipped_files)} file(s) that could not be parsed:")
            for path, reason in self.skipped_files:
                print(f"  - {path}: {reason}")
        if self.checked_files == 0:
            print("\n❌ Test Contradiction Check: No test files were checked")
            print(f"0 test files checked, {len(self.skipped_files)} skipped.")
            return
        if not contradictions:
            print("\n✅ Test Contradiction Check: PASS")
            print("No contradictory test assertions found.")
            return

        print("\n⚠️  Test Contradiction Check: CONTRADICTIONS FOUND")
        print("=" * 80)
        print(f"Found {len(contradictions)} contradiction(s) in test suite.\n")

        for i, contradiction in enumerate(contradictions, 1):
            print(f"🔴 Contradiction #{i}")
            print("-" * 80)
            print(f"Function: {contradiction.function_called}({contradiction.arguments})")
            print(f"Conflict: {contradiction.conflict_description}\n")

            print(f"  Test 1: {contradiction.test1.test_function}")
            print(f"    File: {contradiction.test1.test_file}:{contradiction.test1.line_number}")
            print(f"    Expects: {contradiction.test1.expected_value}\n")

            print(f"  Test 2: {contradiction.test2.test_function}")
            print(f"    File: {contradiction.test2.test_file}:{contradiction.test2.line_number}")
            print(f"    Expects: {contradiction.test2.expected_value}\n")

            print("  💡 Fix: Review both tests and determine correct expected behavior.")
            print("     One of these tests has a wrong expectation.\n")

        print("=" * 80)
        print(f"Total: {len(contradictions)} contradiction(s)")
        print("These indicate logical inconsistencies in your test suite.")


def main():
    """CLI entry point."""
    import sys

    test_dir = sys.argv[1] if len(sys.argv) > 1 else "tests"

    detector = TestContradictionDetector(test_dir)
    try:
        contradictions = detector.find_contradictions()
    except Exception as exc:  # noqa: BLE001 - internal error must not report PASS
        print(f"Test Contradiction Check: internal error: {type(exc).__name__}: {exc}")
        sys.exit(2)
    detector.print_report(contradictions)

    if detector.checked_files == 0:
        sys.exit(2)
    # Exit with error code if contradictions found
    if contradictions:
        sys.exit(1)


if __name__ == "__main__":
    main()
