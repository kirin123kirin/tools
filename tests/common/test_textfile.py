from pathlib import Path

import pytest

from workpytools.common.textfile import (
    TextFileError,
    display_width,
    normalize_newlines,
    pad_to_width,
    read_text_with_fallback,
    to_crlf,
    truncate_to_width,
)

# --- 改行コード ---


def test_normalize_newlines_handles_crlf_cr_and_lf() -> None:
    assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_to_crlf_from_lf() -> None:
    assert to_crlf("a\nb\n") == "a\r\nb\r\n"


def test_to_crlf_is_idempotent_on_crlf() -> None:
    assert to_crlf("a\r\nb\r\n") == "a\r\nb\r\n"


def test_to_crlf_normalizes_mixed_newlines() -> None:
    assert to_crlf("a\rb\nc\r\nd") == "a\r\nb\r\nc\r\nd"


# --- 表示幅 ---


def test_display_width_counts_fullwidth_as_two() -> None:
    assert display_width("abc") == 3
    assert display_width("あいう") == 6
    assert display_width("aあb") == 4


def test_pad_to_width_aligns_mixed_text() -> None:
    padded_full = pad_to_width("あい", 10)
    padded_half = pad_to_width("abcd", 10)
    assert display_width(padded_full) == 10
    assert display_width(padded_half) == 10


def test_pad_to_width_does_not_shrink_longer_text() -> None:
    assert pad_to_width("あいうえお", 4) == "あいうえお"


def test_truncate_to_width_keeps_short_text() -> None:
    assert truncate_to_width("あい", 10) == "あい"


def test_truncate_to_width_adds_ellipsis_within_budget() -> None:
    result = truncate_to_width("あ" * 20, 12)
    assert result.endswith("...")
    assert display_width(result) <= 12


def test_truncate_to_width_halfwidth() -> None:
    result = truncate_to_width("a" * 40, 10)
    assert result.endswith("...")
    assert display_width(result) <= 10


def test_truncate_to_width_extremely_small_budget() -> None:
    result = truncate_to_width("あいうえお", 2)
    assert display_width(result) <= 2


# --- ファイル読み込み ---


def test_reads_utf8(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("日本語テキスト", encoding="utf-8")
    assert read_text_with_fallback(path) == "日本語テキスト"


def test_reads_utf8_with_bom(tmp_path: Path) -> None:
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbf" + "BOM付き".encode())
    assert read_text_with_fallback(path) == "BOM付き"


def test_falls_back_to_cp932(tmp_path: Path) -> None:
    path = tmp_path / "sjis.txt"
    path.write_bytes("シフトJIS".encode("cp932"))
    assert read_text_with_fallback(path) == "シフトJIS"


def test_explicit_encoding_does_not_fall_back(tmp_path: Path) -> None:
    path = tmp_path / "sjis.txt"
    path.write_bytes("シフトJIS".encode("cp932"))

    with pytest.raises(TextFileError):
        read_text_with_fallback(path, encoding="utf-8")


def test_explicit_encoding_succeeds_when_correct(tmp_path: Path) -> None:
    path = tmp_path / "sjis.txt"
    path.write_bytes("シフトJIS".encode("cp932"))
    assert read_text_with_fallback(path, encoding="cp932") == "シフトJIS"


def test_undecodable_bytes_raise(tmp_path: Path) -> None:
    path = tmp_path / "bin.txt"
    # UTF-8でもCP932でもデコードできないバイト列
    path.write_bytes(b"\xff\xfe\x00\x01\x82")

    with pytest.raises(TextFileError):
        read_text_with_fallback(path)
