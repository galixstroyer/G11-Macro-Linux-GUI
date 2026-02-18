#!/usr/bin/env python3
"""Entry point for G11 Macro Manager."""
import sys
import os

# Ensure the gui/ directory is on the Python path regardless of CWD
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import G11MacroApp


def main() -> int:
    return G11MacroApp().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
