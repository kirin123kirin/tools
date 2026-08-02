from __future__ import annotations


def hex_to_ppt_rgb(hex_color: str) -> int:
    """Convert a "#RRGGBB" or "RRGGBB" string to PowerPoint's ColorFormat.RGB
    integer, which packs channels as 0x00BBGGRR (the reverse byte order of
    the hex string, matching the Win32 COLORREF layout)."""
    text = hex_color.lstrip("#")
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return (b << 16) | (g << 8) | r


# アクセント1〜6の新配色。緑(1)とレンガ色(3)を基準に、それぞれの
# 薄めたバリエーション（白方向に約30%ブレンド）を2/4に、グレー系を
# 5/6に割り当てる。キーはMsoThemeColorSchemeIndex（ppAccent1=5 〜 ppAccent6=10）。
ACCENT_HEX_COLORS: dict[int, str] = {
    5: "#00B258",  # ppAccent1
    6: "#4DC98A",  # ppAccent2
    7: "#CC0033",  # ppAccent3
    8: "#DB4D70",  # ppAccent4
    9: "#808080",  # ppAccent5
    10: "#BFBFBF",  # ppAccent6
}
