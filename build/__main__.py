"""CLI entry point: python -m build"""

import argparse
import logging
import sys

from build.main import main


def setup_logging(args: argparse.Namespace) -> None:
    """Configure logging based on arguments.

    :param args: Parsed command line arguments with quiet and log_level
    """
    if args.quiet:
        log_level = logging.ERROR
    else:
        log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=log_level, format="%(levelname).1s %(name)s %(message)s")


def cli() -> int:
    """Parse arguments and run build."""
    parser = argparse.ArgumentParser(
        description="Build JSON output files from calls.yaml and conferences.yaml",
        prog="python -m build",
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
    return main()


if __name__ == "__main__":
    sys.exit(cli())
