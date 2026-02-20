"""CLI entry point for validator."""

from __future__ import annotations

import argparse
import sys

from validate.validator import run_validation, setup_logging


def main() -> int:
    """Parse arguments and run validation."""
    parser = argparse.ArgumentParser(
        description="Validate all reviewer calls in data/calls.yaml",
        prog="python -m validate",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview results without writing to files",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output (sets log level to ERROR)",
    )

    args = parser.parse_args()
    setup_logging(args)
    return run_validation(args)


if __name__ == "__main__":
    sys.exit(main())
