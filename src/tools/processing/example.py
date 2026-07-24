from __future__ import annotations

import argparse
import logging

from tools.processing.base import Processor

logger = logging.getLogger(__name__)


class ExampleProcessor(Processor):
    """Template processor: uppercases the given text.

    Copy this file to add a new processing command.
    """

    name = "example"
    help = "Example processing command (template for new ones)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("text", help="Text to process")

    def run(self, args: argparse.Namespace) -> int:
        logger.info("processing: %s", args.text)
        print(args.text.upper())
        return 0
