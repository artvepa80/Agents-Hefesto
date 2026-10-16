"""Scratch probe: one typed helper for the HefestoAI dogfood check."""


def clamp(value: int, low: int, high: int) -> int:
    """Return ``value`` limited to the inclusive range ``[low, high]``."""
    if low > high:
        raise ValueError("low must not exceed high")
    if value < low:
        return low
    if value > high:
        return high
    return value
