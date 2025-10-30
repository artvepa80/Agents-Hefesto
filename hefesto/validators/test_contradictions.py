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
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


@dataclass
class Contradiction:
    """Represents a contradiction between two tests."""

    function_called: str
    arguments: str
    test1: TestAssertion
    test2: TestAssertion
    conflict_description: str


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
        self.assertions: List[TestAssertion] = []

    def _parse_test_file(self, file_path: Path) -> None:
        """Parse a test file and extract assertions."""
        try:
            with open(file_path) as f:
                tree = ast.parse(f.read(), filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                    self._extract_assertions(node, str(file_path))

        except Exception:
            # Skip files that can't be parsed
            pass

    def _extract_assertions(self, func_node: ast.FunctionDef, file_path: str) -> None:
        """Extract assertion statements from a test function."""
        for node in ast.walk(func_node):
            # Handle assert statements (direct assert)
            if isinstance(node, ast.Assert):
                assertion = self._parse_assert_statement(node, func_node.name, file_path)
                if assertion:
                    self.assertions.append(assertion)

            # Handle assertEqual, assertTrue, assertFalse, etc.
            elif isinstance(node, ast.Call):
                if hasattr(node.func, "attr"):
                    method_name = node.func.attr
                    if method_name.startswith("assert"):
                        assertion = self._parse_unittest_assertion(
                            node, func_node.name, file_path, method_name
                        )
                        if assertion:
                            self.assertions.append(assertion)

    def _parse_assert_statement(
        self, node: ast.Assert, test_func: str, file_path: str
    ) -> Optional[TestAssertion]:
        """Parse a direct assert statement."""
        # Handle: assert func(args) == value
        if isinstance(node.test, ast.Compare):
            left = node.test.left
            if isinstance(left, ast.Call) and hasattr(left.func, "id"):
                function_name = left.func.id
            elif isinstance(left, ast.Call) and hasattr(left.func, "attr"):
                # Handle method calls like client.insert_findings()
                if hasattr(left.func.value, "id"):
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
        elif isinstance(node.test, ast.Call):
            if hasattr(node.test.func, "attr"):
                if hasattr(node.test.func.value, "id"):
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
    ) -> Optional[TestAssertion]:
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

        elif method_name == "assertFalse":
            if len(node.args) >= 1:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Compare):
                    left = first_arg.left
                    if isinstance(left, ast.Call):
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

    def _extract_function_name(self, call_node: ast.Call) -> str:
        """Extract function name from call node."""
        if hasattr(call_node.func, "id"):
            return call_node.func.id
        elif hasattr(call_node.func, "attr"):
            if hasattr(call_node.func.value, "id"):
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
        if isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Num):
            return str(node.n)
        elif isinstance(node, ast.Str):
            return repr(node.s)
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
        elif isinstance(node, ast.NameConstant):
            return str(node.value)
        else:
            return "?"

    def find_contradictions(self) -> List[Contradiction]:
        """Find all contradictions in test suite."""
        # Parse all test files
        if not self.test_dir.exists():
            return []

        for test_file in self.test_dir.rglob("test_*.py"):
            self._parse_test_file(test_file)

        # Group assertions by function + arguments
        groups: Dict[Tuple[str, str], List[TestAssertion]] = defaultdict(list)

        for assertion in self.assertions:
            key = (assertion.function_called, assertion.arguments)
            groups[key].append(assertion)

        # Find contradictions
        contradictions = []

        for (func_name, args), assertions in groups.items():
            # Check if there are different expected values
            expectations = {}
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
                                conflict_description=f"Test 1 expects {val1}, Test 2 expects {val2}",  # noqa: E501
                            )
                        )

        return contradictions

    def print_report(self, contradictions: List[Contradiction]) -> None:
        """Print formatted report of contradictions."""
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
    contradictions = detector.find_contradictions()
    detector.print_report(contradictions)

    # Exit with error code if contradictions found
    if contradictions:
        sys.exit(1)


if __name__ == "__main__":
    main()
