#!/usr/bin/env python3
"""
Loop test script using cowsay.

This script demonstrates a simple loop that uses the cowsay library
to print a greeting message.
"""

import sys
from typing import NoReturn

try:
    import cowsay
except ImportError:
    print("Error: cowsay package not installed. Install with: pip install cowsay", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    """Run the main loop demonstration."""
    # Print hello message using cowsay in a simple loop
    for i in range(3):
        cowsay.cow(f"Hello from the loop (iteration {i + 1})")


if __name__ == "__main__":
    main()