#!/usr/bin/env python3
"""
core/test_hello.py

A minimal, production‑quality script that prints a greeting.
"""

def main() -> None:
    """
    Entry point of the script.
    Prints the word 'Hello' to standard output.
    """
    print("Hello")


if __name__ == "__main__":
    # Execute main() only when the script is run directly,
    # not when imported as a module.
    main()