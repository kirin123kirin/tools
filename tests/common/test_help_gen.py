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


def test_collect_command_help_has_short_toc_summary_for_every_command() -> None:
    # サイドバーの行間を詰めるため、全コマンドに短い専用要約が
    # 登録されていること（未登録ならフルsummaryにフォールバックするが、
    # それだと長すぎて行間を詰める意味が薄れるため、明示登録を必須にする）
    commands = collect_command_help()
    for cmd in commands:
        assert cmd.toc_summary
        assert len(cmd.toc_summary) < len(cmd.summary) or cmd.toc_summary == cmd.summary


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


def test_render_help_html_script_has_no_external_refs_or_src() -> None:
    # サイドバーのドラッグリサイズ用JSはlocalStorageのみを使い、
    # 外部ホストへの通信や外部スクリプトの読み込みを一切行わない
    commands = collect_command_help()
    html = render_help_html(commands)
    assert "<script>" in html
    script_section = html.split("<script>")[1].split("</script>")[0]
    assert "http://" not in script_section
    assert "https://" not in script_section
    assert "<script src=" not in html


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


def test_toc_command_name_not_wrapped_in_category_uppercase_element() -> None:
    # カテゴリ見出しのuppercase装飾がコマンド名側の<a>に継承されないよう、
    # カテゴリラベルは専用の<span class="toc-category-label">に分離されている
    # べきで、コマンド名の<a>がそのtext-transformの対象にならないようにする
    commands = collect_command_help()
    html = render_help_html(commands)
    assert "toc-category-label" in html
    for cmd in commands:
        anchor_start = html.index(f'href="#{cmd.name}"')
        li_start = html.rindex('<li class="toc-command">', 0, anchor_start)
        li_fragment = html[li_start : anchor_start + 1]
        assert "toc-category-label" not in li_fragment


def test_copy_button_uses_standalone_name_without_exe_suffix() -> None:
    # コピーボタンはexe名（xxx.exe）ではなく拡張子なしのコマンド名を
    # クリップボードにコピーする（ユーザーがタイプするのはxxxの方であり、
    # ターミナルで".exe"まで打つ必要はないため）
    commands = collect_command_help()
    html = render_help_html(commands)
    for cmd in commands:
        assert f'data-copy="{cmd.standalone_name}"' in html
        assert f'data-copy="{cmd.standalone_name}.exe"' not in html


def test_copy_button_script_has_fallback_when_clipboard_api_unavailable() -> None:
    # navigator.clipboard.writeTextはfile://で開いた場合や特定のブラウザ
    # 設定下では存在しない/失敗しうるため、execCommand("copy")によるフォール
    # バックを備えていること（コピーが完全に無反応になるのを防ぐ）
    commands = collect_command_help()
    html = render_help_html(commands)
    script_section = html.split("<script>")[-1].split("</script>")[0]
    assert "fallbackCopy" in script_section
    assert 'execCommand("copy")' in script_section
    assert "navigator.clipboard" in script_section


def test_copy_button_click_does_not_navigate_or_submit() -> None:
    # コピーボタンはtype="button"でなければならない（フォーム内での暴発や
    # デフォルトのsubmit挙動を防ぐため。今回フォームはないが将来の事故防止）
    commands = collect_command_help()
    html = render_help_html(commands)
    assert 'class="copy-btn"' in html or 'class="copy-btn toc-copy-btn"' in html
    for line in html.splitlines():
        if "copy-btn" in line and "<button" in line:
            assert 'type="button"' in line


def test_rendered_html_toc_omits_exe_name_shows_only_summary() -> None:
    # TOCはサイドバー表示のためコマンド名と短い要約のみとし、exe名や
    # フルの説明文は本文側（<section>内）でのみ表示する
    commands = collect_command_help()
    html = render_help_html(commands)
    nav_section = html.split("<nav ")[1].split("</nav>")[0]
    assert "toolh.exe" not in nav_section
    for cmd in commands:
        assert f'href="#{cmd.name}"' in nav_section
        assert cmd.toc_summary in nav_section
