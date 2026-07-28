from workpytools.common.theme_colors import ACCENT_HEX_COLORS, hex_to_ppt_rgb


def test_hex_to_ppt_rgb_reverses_byte_order() -> None:
    # #1E7145 -> R=0x1E, G=0x71, B=0x45 -> 0x00457 1 1E = 0x00457 1 1E
    assert hex_to_ppt_rgb("#1E7145") == 0x00457_11E


def test_hex_to_ppt_rgb_accepts_without_hash() -> None:
    assert hex_to_ppt_rgb("1E7145") == hex_to_ppt_rgb("#1E7145")


def test_hex_to_ppt_rgb_black_and_white() -> None:
    assert hex_to_ppt_rgb("#000000") == 0x000000
    assert hex_to_ppt_rgb("#FFFFFF") == 0xFFFFFF


def test_hex_to_ppt_rgb_pure_red_is_lowest_byte() -> None:
    # Rのみの色はPowerPoint RGB表現では最下位バイトになる
    assert hex_to_ppt_rgb("#FF0000") == 0x0000FF


def test_hex_to_ppt_rgb_pure_blue_is_highest_byte() -> None:
    # Bのみの色はPowerPoint RGB表現では最上位バイトになる
    assert hex_to_ppt_rgb("#0000FF") == 0xFF0000


def test_accent_hex_colors_has_six_entries_for_accent1_to_6() -> None:
    assert set(ACCENT_HEX_COLORS.keys()) == {5, 6, 7, 8, 9, 10}


def test_accent_hex_colors_are_valid_hex_strings() -> None:
    for value in ACCENT_HEX_COLORS.values():
        assert value.startswith("#")
        assert len(value) == 7
        hex_to_ppt_rgb(value)  # 例外にならないこと
