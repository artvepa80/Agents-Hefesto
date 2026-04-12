"""Fixture with ONE real assert statement in production code.

This is the TP that must continue firing after the precision fix.
"""


def configure(options):
    assert options is not None  # line 7 — real Assert
    return options
