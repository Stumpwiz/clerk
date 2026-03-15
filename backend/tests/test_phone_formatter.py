import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parents[1]
sys.path.append(str(backend_path))

from app.utils.formatters import format_phone

def test_format_phone():
    test_cases = [
        ("4105551212", "(410) 555-1212"),
        ("(410) 555-1212", "(410) 555-1212"),
        ("410-555-1212", "(410) 555-1212"),
        ("", ""),
        (None, ""),
        ("12345", "12345"),
        ("12345678901", "12345678901"),
        ("410.555.1212", "(410) 555-1212"),
        ("  410 555 1212  ", "(410) 555-1212"),
    ]

    for input_val, expected in test_cases:
        actual = format_phone(input_val)
        assert actual == expected, f"Failed for '{input_val}': expected '{expected}', got '{actual}'"
        print(f"Passed: '{input_val}' -> '{actual}'")

if __name__ == "__main__":
    try:
        test_format_phone()
        print("\nAll phone formatting tests passed!")
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
