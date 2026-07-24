from tools.cli import _discover_processors, build_parser


def test_discover_processors_finds_example() -> None:
    processors = _discover_processors()
    assert "example" in processors


def test_build_parser_registers_subcommand() -> None:
    processors = _discover_processors()
    parser = build_parser(processors)
    args = parser.parse_args(["example", "hi"])
    assert args.command == "example"
    assert args.text == "hi"
