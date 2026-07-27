from workpytools.common.help_gen import (
    _CATEGORIES,
    _DIAGRAMS,
    collect_command_help,
    command_category,
    render_help_html,
    standalone_entry_point_name,
)


def test_collect_command_help_includes_all_processors() -> None:
    commands = collect_command_help()
    names = {c.name for c in commands}
    assert "touka" in names
    assert "clipmd" in names
    assert "help" in names


def test_collect_command_help_grouped_by_category_in_declared_order() -> None:
    commands = collect_command_help()
    categories = [c.category for c in commands]
    expected_order = [category for category, _ in _CATEGORIES]
    # 出現するカテゴリの順序が_CATEGORIESの宣言順と一致し、
    # かつ同じカテゴリが連続してまとまっていること
    seen_order = []
    for category in categories:
        if not seen_order or seen_order[-1] != category:
            seen_order.append(category)
    assert len(seen_order) == len(set(categories)), "同じカテゴリが分断されている"
    assert [c for c in expected_order if c in seen_order] == seen_order


def test_collect_command_help_ungrouped_command_falls_back_to_other() -> None:
    assert command_category("no_such_command") == "その他"


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


# --- Before/After 図 ---


def test_every_registered_processor_has_a_diagram() -> None:
    commands = collect_command_help()
    names = {c.name for c in commands}
    missing = names - set(_DIAGRAMS)
    assert not missing, f"before/after図が未登録のコマンド: {missing}"


def test_rendered_html_embeds_diagram_svg_for_each_command() -> None:
    commands = collect_command_help()
    html = render_help_html(commands)
    for cmd in commands:
        section = html.split(f'id="{cmd.name}"')[1].split("</section>")[0]
        assert "<svg" in section


def test_diagram_svg_contains_no_external_references() -> None:
    commands = collect_command_help()
    html = render_help_html(commands)
    diagram_section = "\n".join(
        line for line in html.splitlines() if "diagram" in line or "<svg" in line
    )
    assert "http://" not in diagram_section
    assert "https://" not in diagram_section


# --- 単体実行ファイル名 ---


def test_standalone_name_defaults_to_command_name() -> None:
    assert standalone_entry_point_name("outline") == "outline"
    assert standalone_entry_point_name("ikko") == "ikko"


def test_help_command_uses_toolh_as_standalone_name() -> None:
    assert standalone_entry_point_name("help") == "toolh"


def test_collect_command_help_includes_standalone_name() -> None:
    commands = collect_command_help()
    help_cmd = next(c for c in commands if c.name == "help")
    outline_cmd = next(c for c in commands if c.name == "outline")
    assert help_cmd.standalone_name == "toolh"
    assert outline_cmd.standalone_name == "outline"


def test_rendered_html_shows_exe_name_for_every_command() -> None:
    commands = collect_command_help()
    html = render_help_html(commands)
    for cmd in commands:
        section = html.split(f'id="{cmd.name}"')[1].split("</section>")[0]
        assert f"{cmd.standalone_name}.exe" in section


def test_rendered_html_toc_omits_exe_name_shows_only_summary() -> None:
    # TOCはサイドバー表示のためコマンド名と要約のみとし、exe名は
    # 本文側（<section>内）でのみ表示する
    commands = collect_command_help()
    html = render_help_html(commands)
    nav_section = html.split("<nav>")[1].split("</nav>")[0]
    assert "toolh.exe" not in nav_section
    for cmd in commands:
        assert f'href="#{cmd.name}"' in nav_section
        assert cmd.summary in nav_section
