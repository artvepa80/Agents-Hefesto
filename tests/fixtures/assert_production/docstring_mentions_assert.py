"""Module-level docstring that mentions assert statements.

The word ``assert`` appears in the docstring above this line but there
is no real ``ast.Assert`` statement in the module. The detector must
not flag this file.
"""


def parse(text):
    message = "assert_mode is now legacy — do not rely on it."
    return message


def render():
    # This comment mentions 'assert ' as a keyword example.
    return None
