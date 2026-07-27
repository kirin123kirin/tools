from __future__ import annotations

import argparse
from abc import ABC, abstractmethod


class Processor(ABC):
    """Base class for a single processing command.

    Subclass this in a new module under `tools/processing/` and it will be
    picked up automatically as a `tools <name>` subcommand.
    """

    name: str
    help: str = ""

    @abstractmethod
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register this processor's CLI arguments on `parser`."""

    @abstractmethod
    def run(self, args: argparse.Namespace) -> int:
        """Execute the processing. Return a process exit code."""
