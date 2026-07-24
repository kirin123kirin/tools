import argparse

import pytest

from tools.processing.example import ExampleProcessor


def test_example_processor_run(capsys: pytest.CaptureFixture[str]) -> None:
    proc = ExampleProcessor()
    args = argparse.Namespace(text="hello")

    result = proc.run(args)

    captured = capsys.readouterr()
    assert result == 0
    assert captured.out.strip() == "HELLO"
