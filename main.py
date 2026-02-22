#!/usr/bin/env python3
"""World Card AI — A terminal card survival game powered by LLM agents."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="World Card AI — Survive. Decide. Be Reborn.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Controls:
  Left Arrow / A    Swipe left
  Right Arrow / D   Swipe right
  Q                 Quit

Examples:
  python main.py              Start normally (requires OPENROUTER_API_KEY)
  python main.py --demo       Play demo world without API key
""",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode with a pre-built world (no API key needed)",
    )
    args = parser.parse_args()

    from ui.app import WorldCardApp

    app = WorldCardApp(demo=args.demo)
    app.run()


if __name__ == "__main__":
    main()
