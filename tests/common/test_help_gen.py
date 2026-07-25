from tools.common.help_gen import collect_command_help, render_help_html


def test_collect_command_help_includes_all_processors() -> None:
    commands = collect_command_help()
    names = {c.name for c in commands}
    assert "touka" in names
    assert "clipmd" in names
    assert "help" in names


def test_collect_command_help_sorted_by_name() -> None:
    commands = collect_command_help()
    names = [c.name for c in commands]
    assert names == sorted(names)


def test_collect_command_help_has_summary_and_full_help() -> None:
    commands = collect_command_help()
    touka = next(c for c in commands if c.name == "touka")
    assert touka.summary
    assert "usage:" in touka.full_help


def test_render_help_html_includes_all_commands() -> None:
    commands = collect_command_help()
    html = render_help_html(commands)
    for cmd in commands:
        assert f'id="{cmd.name}"' in html
        assert cmd.summary in html


def test_render_help_html_has_charset_and_no_external_refs() -> None:
    commands = collect_command_help()
    html = render_help_html(commands)
    assert '<meta charset="utf-8">' in html
    style_section = html.split("<style>")[1].split("</style>")[0]
    assert "http://" not in style_section
    assert "https://" not in style_section
