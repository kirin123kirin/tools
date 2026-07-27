from pathlib import Path

import pytest

from workpytools.common.tabular import (
    Table,
    format_top,
    is_empty,
    load_tables,
    normalize_value,
    profile_columns,
    read_csv_like,
    read_json_records,
)

# --- normalize_value ---


def test_integer_float_normalized_to_same_string() -> None:
    assert normalize_value(1.0) == normalize_value(1) == "1"


def test_non_integer_float_kept_distinct() -> None:
    assert normalize_value(1.5) != normalize_value(1)


def test_whitespace_trimmed() -> None:
    assert normalize_value("東京 ") == normalize_value("東京") == "東京"


def test_bool_and_string_bool_remain_distinct() -> None:
    assert normalize_value(True) != normalize_value("True")


def test_none_stays_none() -> None:
    assert normalize_value(None) is None


# --- is_empty ---


def test_default_empty_values_detected() -> None:
    from workpytools.common.tabular import DEFAULT_EMPTY_VALUES

    assert is_empty("", DEFAULT_EMPTY_VALUES)
    assert is_empty("N/A", DEFAULT_EMPTY_VALUES)
    assert is_empty(None, DEFAULT_EMPTY_VALUES)
    assert is_empty("   ", DEFAULT_EMPTY_VALUES)
    assert not is_empty("value", DEFAULT_EMPTY_VALUES)


# --- profile_columns ---


def test_all_same_value_is_not_unique_but_is_filled() -> None:
    table = Table(columns=["a"], rows=[("x",), ("x",), ("x",)])
    profiles = profile_columns(table)
    assert profiles[0].is_unique is False
    assert profiles[0].is_filled is True


def test_all_distinct_values_is_unique() -> None:
    table = Table(columns=["a"], rows=[("1",), ("2",), ("3",)])
    profiles = profile_columns(table)
    assert profiles[0].is_unique is True


def test_empty_values_counted_as_empty() -> None:
    table = Table(columns=["a"], rows=[("",), ("N/A",), (None,), ("x",)])
    profiles = profile_columns(table)
    assert profiles[0].empty == 3
    assert profiles[0].filled == 1


def test_custom_empty_values_replace_default() -> None:
    table = Table(columns=["a"], rows=[("N/A",), ("custom",)])
    profiles = profile_columns(table, empty_values=frozenset({"custom"}))
    # N/A はもう空とみなされない
    assert profiles[0].filled == 1
    assert profiles[0].empty == 1


def test_top_n_limits_results() -> None:
    table = Table(columns=["a"], rows=[(str(i),) for i in range(20)])
    profiles = profile_columns(table, top_n=3)
    assert len(profiles[0].top) == 3


def test_top_zero_returns_empty() -> None:
    table = Table(columns=["a"], rows=[("x",), ("y",)])
    profiles = profile_columns(table, top_n=0)
    assert profiles[0].top == []


def test_ragged_rows_padded_with_none() -> None:
    table = Table(columns=["a", "b"], rows=[("1", "2"), ("3",)])
    profiles = profile_columns(table)
    assert profiles[1].rows == 2
    assert profiles[1].empty == 1  # 2番目の行はbが欠けている


def test_zero_rows_does_not_raise() -> None:
    table = Table(columns=["a"], rows=[])
    profiles = profile_columns(table)
    assert profiles[0].fill_rate == 0.0
    assert profiles[0].unique_rate == 0.0


def test_all_empty_column_does_not_crash() -> None:
    table = Table(columns=["a"], rows=[("",), ("",), (None,)])
    profiles = profile_columns(table)
    assert profiles[0].filled == 0
    assert profiles[0].is_filled is False


# --- key_score ---


def test_key_score_max_when_both_rates_are_one() -> None:
    table = Table(columns=["a"], rows=[("1",), ("2",), ("3",)])
    profiles = profile_columns(table)
    assert profiles[0].key_score == pytest.approx(1.0)


def test_key_score_zero_when_either_rate_is_zero() -> None:
    table = Table(columns=["a"], rows=[("",), ("",)])
    profiles = profile_columns(table)
    assert profiles[0].key_score == 0.0


def test_key_score_rewards_balance_over_one_sided_high_value() -> None:
    # 列A: 充填率1.0、一意率0.1（低い方に引っ張られる）
    a_rows = [("x",)] * 9 + [("y",)]
    table_a = Table(columns=["a"], rows=a_rows)
    score_a = profile_columns(table_a)[0].key_score

    # 列B: 充填率0.55、一意率0.55（両方中程度）
    b_rows = [(str(i),) for i in range(5)] + [("",)] * 4 + [("z",)]
    table_b = Table(columns=["b"], rows=b_rows)
    score_b = profile_columns(table_b)[0].key_score

    assert score_b > score_a


# --- format_top ---


def test_format_top_includes_value_and_count() -> None:
    assert format_top([("東京", 3), ("大阪", 1)]) == "東京(3) / 大阪(1)"


def test_format_top_empty_list() -> None:
    assert format_top([]) == ""


def test_format_top_value_with_slash_not_confused() -> None:
    result = format_top([("2026/07/26", 2)])
    assert "2026/07/26" in result


# --- 入力: CSV/TSV ---


def test_read_csv_like_basic() -> None:
    table = read_csv_like("a,b\n1,x\n2,y\n", ",", header_row=0)
    assert table.columns == ["a", "b"]
    assert table.rows == [("1", "x"), ("2", "y")]


def test_read_csv_like_no_header() -> None:
    table = read_csv_like("1,x\n2,y\n", ",", header_row=None)
    assert table.columns == ["0", "1"]
    assert len(table.rows) == 2


def test_read_csv_like_header_not_first_row() -> None:
    table = read_csv_like("skip,this\na,b\n1,x\n", ",", header_row=1)
    assert table.columns == ["a", "b"]
    assert table.rows == [("1", "x")]


def test_read_csv_like_tsv_separator() -> None:
    table = read_csv_like("a\tb\n1\tx\n", "\t", header_row=0)
    assert table.columns == ["a", "b"]


# --- 入力: JSON ---


def test_read_json_array_of_objects() -> None:
    table = read_json_records('[{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]')
    assert table.columns == ["a", "b"]
    assert table.rows == [(1, "x"), (2, "y")]


def test_read_json_lines() -> None:
    text = '{"a": 1}\n{"a": 2}\n'
    table = read_json_records(text)
    assert table.columns == ["a"]
    assert table.rows == [(1,), (2,)]


def test_read_json_nested_value_becomes_json_string() -> None:
    table = read_json_records('[{"a": [1, 2, 3]}]')
    assert table.rows[0][0] == "[1, 2, 3]"


def test_read_json_missing_key_becomes_none() -> None:
    table = read_json_records('[{"a": 1, "b": 2}, {"a": 3}]')
    assert table.rows[1] == (3, None)


# --- load_tables ---


def test_load_tables_unsupported_extension_raises(tmp_path: Path) -> None:
    path = tmp_path / "data.pptx"
    path.write_bytes(b"dummy")
    with pytest.raises(ValueError):
        load_tables(path, sep=None, header_row=0)


def test_load_tables_csv(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,x\n", encoding="utf-8")
    tables = load_tables(path, sep=None, header_row=0)
    assert tables[""].columns == ["a", "b"]


def test_load_tables_cp932_fallback(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_bytes("列,値\n1,あ\n".encode("cp932"))
    tables = load_tables(path, sep=None, header_row=0)
    assert tables[""].columns == ["列", "値"]


def test_load_tables_sep_override(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a;b\n1;x\n", encoding="utf-8")
    tables = load_tables(path, sep=";", header_row=0)
    assert tables[""].columns == ["a", "b"]


def test_load_tables_excel_multiple_sheets(tmp_path: Path) -> None:
    import openpyxl

    path = tmp_path / "data.xlsx"
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "S1"
    ws1.append(["a"])
    ws1.append([1])
    ws2 = wb.create_sheet("S2")
    ws2.append(["b"])
    ws2.append([2])
    wb.save(path)

    tables = load_tables(path, sep=None, header_row=0)
    assert set(tables.keys()) == {"S1", "S2"}
    assert tables["S1"].columns == ["a"]
    assert tables["S2"].columns == ["b"]
