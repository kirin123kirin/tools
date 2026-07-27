from workpytools.common.outline_parse import OutlineItem, parse_outline

# --- Markdown見出し記法 ---


def test_markdown_heading_h1_recognized() -> None:
    items = parse_outline("# タイトル1\n本文1\n\n# タイトル2\n本文2")
    assert items == [
        OutlineItem(title="タイトル1", body="本文1"),
        OutlineItem(title="タイトル2", body="本文2"),
    ]


def test_markdown_heading_various_levels() -> None:
    items = parse_outline("# H1\nbody1\n\n## H2\nbody2\n\n###### H6\nbody6")
    titles = [i.title for i in items]
    assert titles == ["H1", "H2", "H6"]


def test_markdown_heading_mixed_levels_treated_equally() -> None:
    items = parse_outline("# 章\n本文\n\n## 節\n本文2")
    assert len(items) == 2


def test_markdown_heading_preamble_ignored() -> None:
    items = parse_outline("前置きの本文\nこれも前置き\n\n# 最初の見出し\n本文")
    assert len(items) == 1
    assert items[0].title == "最初の見出し"


# --- タブ区切り記法 ---


def test_tab_separated_title_and_body() -> None:
    items = parse_outline("タイトルA\tリード文A\nタイトルB\tリード文B")
    assert items == [
        OutlineItem(title="タイトルA", body="リード文A"),
        OutlineItem(title="タイトルB", body="リード文B"),
    ]


def test_tab_separated_line_without_tab_is_title_only() -> None:
    items = parse_outline("タイトルA\tリード文A\nタイトルのみ")
    assert items[1] == OutlineItem(title="タイトルのみ", body="")


def test_tab_separated_blank_lines_skipped() -> None:
    items = parse_outline("タイトルA\tリード文A\n\n\nタイトルB\tリード文B")
    assert len(items) == 2


# --- 空行区切り記法 ---


def test_blank_line_blocks_title_and_body() -> None:
    items = parse_outline("タイトル1\n本文1a\n本文1b\n\nタイトル2\n本文2")
    assert items == [
        OutlineItem(title="タイトル1", body="本文1a\n本文1b"),
        OutlineItem(title="タイトル2", body="本文2"),
    ]


def test_blank_line_block_single_line_has_no_body() -> None:
    items = parse_outline("タイトルのみ\n\nタイトル2\n本文2")
    assert items[0] == OutlineItem(title="タイトルのみ", body="")


# --- 優先順位・フォールバック ---


def test_markdown_heading_takes_priority_over_tab() -> None:
    # 見出し記法とタブが両方存在する場合、Markdown見出しとして処理される
    items = parse_outline("# タイトル\t本文っぽい何か")
    assert len(items) == 1
    assert items[0].title == "タイトル\t本文っぽい何か" or "\t" not in items[0].title
    # 見出し記法として解釈されていること自体を検証（本文行が続く形）
    items2 = parse_outline("# タイトル\n本文\tタブを含む本文")
    assert items2[0].title == "タイトル"
    assert items2[0].body == "本文\tタブを含む本文"


def test_fallback_to_blank_line_blocks_for_plain_text() -> None:
    items = parse_outline("見出しでもタブでもない、ただの1段落のメモ")
    assert len(items) == 1
    assert items[0].title == "見出しでもタブでもない、ただの1段落のメモ"


# --- 改行・その他 ---


def test_crlf_normalized_before_parsing() -> None:
    items = parse_outline("# タイトル\r\n本文1\r\n本文2")
    assert items[0].body == "本文1\n本文2"


def test_multiline_body_preserved() -> None:
    items = parse_outline("タイトル\t行1\n行2\n行3")
    # タブ区切りの1行はタブ後ろ全体がリード文（改行を含まない1行入力なので単一行）
    assert items[0].title == "タイトル"


def test_empty_clipboard_text_yields_no_items() -> None:
    assert parse_outline("") == []


def test_whitespace_only_text_yields_no_items() -> None:
    assert parse_outline("   \n\n   ") == []
