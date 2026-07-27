from __future__ import annotations

import argparse
import html as html_module
from dataclasses import dataclass

from workpytools.cli import _ENTRY_POINT_ALIASES, _discover_processors
from workpytools.processing.base import Processor

# コマンド名 -> 単体実行ファイル名（拡張子なし）。pyproject.tomlの
# [project.scripts]は基本的にコマンド名と同名のエントリーポイントを
# 登録するため、既定はコマンド名そのものとする。help だけは toolh という
# 別名（help.exeだと紛らわしいため）で登録されているため、cli.pyの
# _ENTRY_POINT_ALIASES（エントリーポイント名->コマンド名）を逆引きして
# 例外を反映する。
_STANDALONE_NAME_OVERRIDES: dict[str, str] = {
    command: entry_point for entry_point, command in _ENTRY_POINT_ALIASES.items()
}


def standalone_entry_point_name(command_name: str) -> str:
    """The name of the standalone executable for a command (e.g. "outline"
    for `outline.exe`, "toolh" for the `help` command's `toolh.exe`)."""
    return _STANDALONE_NAME_OVERRIDES.get(command_name, command_name)

# --- Before/After 図 ----------------------------------------------------
#
# help.htmlは説明文だけだと頭に入りにくいため、各コマンドが「何を」
# 「どう変える」のかを示すbefore/after図をSVGで自前描画して埋め込む。
# 汎用アイコンの並びではなく、コマンドごとに専用の絵を1枚ずつ用意する
# （合体・分解・整列・サイズ統一のような紐しい系のコマンドを見分ける
# ため）。外部画像・CDNには一切依存しない。

_DIAGRAM_VIEWBOX = "0 0 220 90"
_ARROW_CENTER = (
    '<path d="M96 45 H124 M116 37 L124 45 L116 53" fill="none" '
    'stroke="currentColor" stroke-width="2.5" stroke-linecap="round" '
    'stroke-linejoin="round"/>'
)

# コマンド名 -> before/after図のSVG中身（<g>の中に入れる要素）。
# 左半分(x=10-90)がbefore、中央に矢印、右半分(x=130-210)がafterの構図で揃える。
_DIAGRAMS: dict[str, str] = {
    "touka": (
        # before: 市松模様なしの背景に円（不透明な背景）
        '<rect x="10" y="15" width="80" height="60" rx="3" fill="#cfe3ff" '
        'stroke="currentColor" stroke-width="2"/>'
        '<circle cx="50" cy="45" r="18" fill="#ffb100"/>'
        + _ARROW_CENTER +
        # after: 市松模様の背景（透過を表す）に同じ円
        '<g>'
        '<rect x="130" y="15" width="80" height="60" rx="3" fill="#eee" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="130" y="15" width="10" height="10" fill="#ccc"/>'
        '<rect x="150" y="15" width="10" height="10" fill="#ccc"/>'
        '<rect x="170" y="15" width="10" height="10" fill="#ccc"/>'
        '<rect x="190" y="15" width="10" height="10" fill="#ccc"/>'
        '<rect x="140" y="25" width="10" height="10" fill="#ccc"/>'
        '<rect x="160" y="25" width="10" height="10" fill="#ccc"/>'
        '<rect x="180" y="25" width="10" height="10" fill="#ccc"/>'
        '<rect x="130" y="35" width="10" height="10" fill="#ccc"/>'
        '<rect x="150" y="35" width="10" height="10" fill="#ccc"/>'
        '<rect x="170" y="35" width="10" height="10" fill="#ccc"/>'
        '<rect x="190" y="35" width="10" height="10" fill="#ccc"/>'
        '<circle cx="170" cy="45" r="18" fill="#ffb100"/>'
        "</g>"
    ),
    "denoise": (
        # before: ザラついた（ノイズ粒の乗った）円
        '<circle cx="50" cy="45" r="26" fill="#cfe3ff" stroke="currentColor" stroke-width="2"/>'
        + "".join(
            f'<circle cx="{x}" cy="{y}" r="1.4" fill="#557" />'
            for x, y in [
                (38, 32), (52, 28), (61, 40), (44, 48), (58, 55),
                (35, 50), (48, 58), (63, 30), (40, 40), (55, 45),
            ]
        )
        + _ARROW_CENTER +
        # after: 同じ円だがなめらか（ノイズ粒なし）
        '<circle cx="170" cy="45" r="26" fill="#cfe3ff" stroke="currentColor" stroke-width="2"/>'
    ),
    "kukiri": (
        # before: 輪郭がぼやけた（複数の薄い同心円で滲みを表現）四角形
        '<rect x="24" y="19" width="52" height="52" rx="4" fill="none" '
        'stroke="#99a" stroke-width="6" opacity="0.35"/>'
        '<rect x="24" y="19" width="52" height="52" rx="4" fill="#cfe3ff" '
        'stroke="#99a" stroke-width="2" opacity="0.7"/>'
        + _ARROW_CENTER +
        # after: 輪郭がくっきりした同じ四角形
        '<rect x="144" y="19" width="52" height="52" rx="4" fill="#cfe3ff" '
        'stroke="currentColor" stroke-width="3"/>'
    ),
    "cwc": (
        # before: テキスト行
        '<rect x="14" y="15" width="72" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<line x1="22" y1="28" x2="78" y2="28" stroke="currentColor" stroke-width="2.5"/>'
        '<line x1="22" y1="40" x2="78" y2="40" stroke="currentColor" stroke-width="2.5"/>'
        '<line x1="22" y1="52" x2="78" y2="52" stroke="currentColor" stroke-width="2.5"/>'
        '<line x1="22" y1="64" x2="60" y2="64" stroke="currentColor" stroke-width="2.5"/>'
        + _ARROW_CENTER +
        # after: 大小の単語が散らばったワードクラウド
        '<text x="145" y="35" font-size="16" font-weight="bold" '
        'fill="currentColor">単語</text>'
        '<text x="185" y="30" font-size="9" fill="currentColor">語</text>'
        '<text x="140" y="55" font-size="10" fill="currentColor">頻度</text>'
        '<text x="170" y="60" font-size="20" font-weight="bold" '
        'fill="currentColor">多い</text>'
        '<text x="150" y="75" font-size="8" fill="currentColor">少</text>'
    ),
    "clipmd": (
        # before: Markdown記法
        '<rect x="10" y="15" width="80" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<text x="18" y="35" font-size="12" font-family="Consolas, monospace" '
        'fill="currentColor"># 見出し</text>'
        '<text x="18" y="52" font-size="12" font-family="Consolas, monospace" '
        'fill="currentColor">**太字**</text>'
        '<text x="18" y="69" font-size="12" font-family="Consolas, monospace" '
        'fill="currentColor">- 項目</text>'
        + _ARROW_CENTER +
        # after: リッチテキスト（実際に大きく・太くレンダリングされた見た目）
        '<rect x="130" y="15" width="80" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<text x="138" y="34" font-size="15" font-weight="bold" '
        'fill="currentColor">見出し</text>'
        '<text x="138" y="52" font-size="12" font-weight="bold" '
        'fill="currentColor">太字</text>'
        '<circle cx="140" cy="63" r="1.8" fill="currentColor"/>'
        '<text x="146" y="67" font-size="12" fill="currentColor">項目</text>'
    ),
    "mdtsv": (
        # before: Markdownの表記法
        '<rect x="10" y="15" width="80" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<text x="16" y="35" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">|a|b|</text>'
        '<text x="16" y="50" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">|-|-|</text>'
        '<text x="16" y="65" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">|1|2|</text>'
        + _ARROW_CENTER +
        # after: Excel風のグリッド（TSV貼り付け後の見た目）
        '<rect x="130" y="15" width="80" height="60" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<line x1="130" y1="45" x2="210" y2="45" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="170" y1="15" x2="170" y2="75" stroke="currentColor" stroke-width="1.5"/>'
        '<text x="145" y="35" font-size="12" fill="currentColor">a</text>'
        '<text x="185" y="35" font-size="12" fill="currentColor">b</text>'
        '<text x="145" y="65" font-size="12" fill="currentColor">1</text>'
        '<text x="185" y="65" font-size="12" fill="currentColor">2</text>'
    ),
    "clipfmt": (
        # before: 列がずれた表
        '<rect x="10" y="15" width="80" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<text x="16" y="35" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">|a|bb|c|</text>'
        '<text x="16" y="50" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">|-|-|-|</text>'
        '<text x="16" y="65" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">|1|2|3|</text>'
        + _ARROW_CENTER +
        # after: 列幅が揃ったMarkdown
        '<rect x="130" y="15" width="80" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<text x="136" y="35" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">| a  | bb | c |</text>'
        '<text x="136" y="50" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">| -- | -- | - |</text>'
        '<text x="136" y="65" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">| 1  | 2  | 3 |</text>'
    ),
    "clipview": (
        # before: クリップボード
        '<rect x="24" y="15" width="52" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2.5"/>'
        '<rect x="38" y="10" width="24" height="10" rx="2" fill="currentColor"/>'
        '<line x1="32" y1="35" x2="68" y2="35" stroke="currentColor" stroke-width="2"/>'
        '<line x1="32" y1="47" x2="68" y2="47" stroke="currentColor" stroke-width="2"/>'
        '<line x1="32" y1="59" x2="56" y2="59" stroke="currentColor" stroke-width="2"/>'
        + _ARROW_CENTER +
        # after: ブラウザウィンドウにレンダリング済みの見出し・段落
        '<rect x="130" y="12" width="80" height="66" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<line x1="130" y1="24" x2="210" y2="24" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="137" cy="18" r="1.6" fill="currentColor"/>'
        '<circle cx="144" cy="18" r="1.6" fill="currentColor"/>'
        '<text x="138" y="42" font-size="13" font-weight="bold" '
        'fill="currentColor">見出し</text>'
        '<line x1="138" y1="52" x2="200" y2="52" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="138" y1="61" x2="200" y2="61" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="138" y1="70" x2="180" y2="70" stroke="currentColor" stroke-width="1.5"/>'
    ),
    "vv": (
        # before: 番号付きの一覧
        '<circle cx="18" cy="24" r="2" fill="currentColor"/>'
        '<line x1="26" y1="24" x2="86" y2="24" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="18" cy="45" r="2" fill="currentColor" opacity="0.4"/>'
        '<line x1="26" y1="45" x2="86" y2="45" stroke="currentColor" '
        'stroke-width="2" opacity="0.4"/>'
        '<circle cx="18" cy="66" r="2" fill="currentColor" opacity="0.4"/>'
        '<line x1="26" y1="66" x2="86" y2="66" stroke="currentColor" '
        'stroke-width="2" opacity="0.4"/>'
        + _ARROW_CENTER +
        # after: 選んだ1件だけがクリップボードへ
        '<rect x="150" y="15" width="52" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2.5"/>'
        '<rect x="164" y="10" width="24" height="10" rx="2" fill="currentColor"/>'
        '<line x1="158" y1="40" x2="194" y2="40" stroke="currentColor" stroke-width="2.5"/>'
        '<line x1="158" y1="52" x2="194" y2="52" stroke="currentColor" stroke-width="2.5"/>'
    ),
    "profiler": (
        # before: ふぞろいなセル（欠損混じり）の生データ
        '<rect x="10" y="15" width="80" height="60" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<line x1="10" y1="35" x2="90" y2="35" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="10" y1="55" x2="90" y2="55" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="45" y1="15" x2="45" y2="75" stroke="currentColor" stroke-width="1.5"/>'
        '<text x="20" y="30" font-size="11" fill="currentColor">12</text>'
        '<text x="55" y="30" font-size="11" fill="currentColor">A</text>'
        '<text x="20" y="50" font-size="11" fill="#c55" opacity="0.7">?</text>'
        '<text x="55" y="50" font-size="11" fill="currentColor">B</text>'
        '<text x="20" y="70" font-size="11" fill="currentColor">7</text>'
        '<text x="55" y="70" font-size="11" fill="#c55" opacity="0.7">?</text>'
        + _ARROW_CENTER +
        # after: 列ごとの統計（充填率バー）
        '<text x="136" y="26" font-size="10" fill="currentColor">列A 充填 67%</text>'
        '<rect x="136" y="30" width="60" height="6" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="1"/>'
        '<rect x="136" y="30" width="40" height="6" rx="2" fill="currentColor"/>'
        '<text x="136" y="52" font-size="10" fill="currentColor">列B 一意 100%</text>'
        '<rect x="136" y="56" width="60" height="6" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="1"/>'
        '<rect x="136" y="56" width="60" height="6" rx="2" fill="currentColor"/>'
    ),
    "lsdir": (
        # before: フォルダツリー
        '<path d="M14 22 L28 22 L32 27 L54 27 L54 40 L14 40 Z" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>'
        '<path d="M20 46 L34 46 L38 51 L60 51 L60 64 L20 64 Z" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linejoin="round" opacity="0.6"/>'
        + _ARROW_CENTER +
        # after: フラットな一覧表
        '<rect x="130" y="15" width="80" height="60" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<line x1="130" y1="30" x2="210" y2="30" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="130" y1="45" x2="210" y2="45" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="130" y1="60" x2="210" y2="60" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="170" y1="15" x2="170" y2="75" stroke="currentColor" stroke-width="1.5"/>'
    ),
    "outline": (
        # before: 箇条書きテキスト（アウトライン）
        '<text x="14" y="30" font-size="12" font-family="Consolas, monospace" '
        'fill="currentColor"># 章1</text>'
        '<text x="14" y="46" font-size="12" font-family="Consolas, monospace" '
        'fill="currentColor"># 章2</text>'
        '<text x="14" y="62" font-size="12" font-family="Consolas, monospace" '
        'fill="currentColor"># 章3</text>'
        + _ARROW_CENTER +
        # after: スライドのサムネイル列
        '<rect x="130" y="18" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="165" y="18" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="130" y="45" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="165" y="45" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
    ),
    "mokuji": (
        # before: スライドのサムネイル列
        '<rect x="14" y="18" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="49" y="18" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="14" y="45" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="49" y="45" width="30" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        + _ARROW_CENTER +
        # after: 番号付きタイトル一覧（クリップボードへ）
        '<rect x="150" y="10" width="52" height="66" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2.5"/>'
        '<rect x="164" y="5" width="24" height="10" rx="2" fill="currentColor"/>'
        '<line x1="158" y1="34" x2="194" y2="34" stroke="currentColor" stroke-width="2"/>'
        '<line x1="158" y1="46" x2="194" y2="46" stroke="currentColor" stroke-width="2"/>'
        '<line x1="158" y1="58" x2="188" y2="58" stroke="currentColor" stroke-width="2"/>'
    ),
    "ikko": (
        # before: 3つの小さな四角形（縦積み・バラバラなテキストボックス）
        '<rect x="16" y="16" width="68" height="14" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="16" y="38" width="68" height="14" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="16" y="60" width="68" height="14" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        + _ARROW_CENTER +
        # after: 1つの大きな四角形（3行のテキスト）
        '<rect x="136" y="16" width="68" height="58" rx="2.5" fill="none" '
        'stroke="currentColor" stroke-width="2.5"/>'
        '<line x1="144" y1="34" x2="196" y2="34" stroke="currentColor" stroke-width="2"/>'
        '<line x1="144" y1="46" x2="196" y2="46" stroke="currentColor" stroke-width="2"/>'
        '<line x1="144" y1="58" x2="196" y2="58" stroke="currentColor" stroke-width="2"/>'
    ),
    "tbl": (
        # before/after: 表と四角形群を両矢印でつなぐ（相互変換）
        '<rect x="10" y="15" width="80" height="60" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<line x1="10" y1="35" x2="90" y2="35" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="10" y1="55" x2="90" y2="55" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="36" y1="15" x2="36" y2="75" stroke="currentColor" stroke-width="1.5"/>'
        '<line x1="63" y1="15" x2="63" y2="75" stroke="currentColor" stroke-width="1.5"/>'
        '<path d="M96 39 H124 M116 33 L124 39 L116 45" fill="none" '
        'stroke="currentColor" stroke-width="2.3" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        '<path d="M124 51 H96 M104 45 L96 51 L104 57" fill="none" '
        'stroke="currentColor" stroke-width="2.3" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        '<rect x="130" y="16" width="34" height="26" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="170" y="16" width="34" height="26" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="130" y="48" width="34" height="26" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="170" y="48" width="34" height="26" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
    ),
    "seiretsu": (
        # before: 傾いてバラバラな四角形群
        '<rect x="10" y="12" width="24" height="18" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2" transform="rotate(-10 22 21)"/>'
        '<rect x="55" y="8" width="24" height="18" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2" transform="rotate(7 67 17)"/>'
        '<rect x="18" y="50" width="24" height="18" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2" transform="rotate(4 30 59)"/>'
        '<rect x="60" y="55" width="24" height="18" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2" transform="rotate(-6 72 64)"/>'
        + _ARROW_CENTER +
        # after: きれいな格子状に整列
        '<rect x="132" y="15" width="30" height="24" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="172" y="15" width="30" height="24" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="132" y="49" width="30" height="24" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="172" y="49" width="30" height="24" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
    ),
    "nagasa": (
        # before: サイズが不揃いな四角形群（横並び）
        '<rect x="12" y="35" width="16" height="16" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="34" y="12" width="20" height="40" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="60" y="45" width="24" height="10" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        + _ARROW_CENTER +
        # after: 同じサイズに揃った四角形群
        '<rect x="130" y="15" width="20" height="40" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="156" y="15" width="20" height="40" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="182" y="15" width="20" height="40" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
    ),
    "help": (
        '<rect x="70" y="12" width="80" height="66" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<line x1="70" y1="24" x2="150" y2="24" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="77" cy="18" r="1.6" fill="currentColor"/>'
        '<circle cx="84" cy="18" r="1.6" fill="currentColor"/>'
        '<text x="95" y="52" font-size="24" font-weight="bold" '
        'text-anchor="middle" fill="currentColor">?</text>'
    ),
}


def _render_diagram_svg(name: str) -> str:
    """Render the before/after diagram for one command, or an empty string
    if the command has no registered diagram (falls back to text-only)."""
    body = _DIAGRAMS.get(name)
    if body is None:
        return ""

    return (
        f'<div class="diagram" aria-hidden="true">'
        f'<svg viewBox="{_DIAGRAM_VIEWBOX}"><g>{body}</g></svg>'
        f"</div>"
    )


@dataclass(frozen=True)
class CommandHelp:
    name: str
    summary: str
    usage: str
    full_help: str
    standalone_name: str


def collect_command_help() -> list[CommandHelp]:
    """Build per-command help text by rendering each Processor's own argparse help."""
    processors = _discover_processors()
    results: list[CommandHelp] = []

    for name in sorted(processors):
        proc = processors[name]
        parser = _build_standalone_parser(proc)
        full_help = parser.format_help()
        results.append(
            CommandHelp(
                name=name,
                summary=proc.help,
                usage=parser.format_usage(),
                full_help=full_help,
                standalone_name=standalone_entry_point_name(name),
            )
        )

    return results


def _build_standalone_parser(proc: Processor) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=proc.name, description=proc.help)
    proc.add_arguments(parser)
    return parser


def render_help_html(commands: list[CommandHelp]) -> str:
    rows = []
    for cmd in commands:
        diagram_svg = _render_diagram_svg(cmd.name)
        exe_name = f"{cmd.standalone_name}.exe"
        rows.append(
            "<section class=\"command\">\n"
            f"<h2 id=\"{html_module.escape(cmd.name)}\">{html_module.escape(cmd.name)}</h2>\n"
            f"<p class=\"standalone\">単体実行: "
            f"<code>{html_module.escape(exe_name)}</code></p>\n"
            f"{diagram_svg}\n"
            f"<p class=\"summary\">{html_module.escape(cmd.summary)}</p>\n"
            f"<pre>{html_module.escape(cmd.full_help)}</pre>\n"
            "</section>"
        )

    toc_items = "\n".join(
        f'<li><a href="#{html_module.escape(c.name)}">{html_module.escape(c.name)}</a>'
        f' <code>({html_module.escape(c.standalone_name)}.exe)</code>'
        f" — {html_module.escape(c.summary)}</li>"
        for c in commands
    )

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-store">
<title>tools コマンドヘルプ</title>
<style>
:root {{ color-scheme: light dark; }}
body {{
  max-width: 50rem;
  margin: 2rem auto;
  padding: 0 1rem;
  font-family: -apple-system, "Segoe UI", sans-serif;
  line-height: 1.6;
  color: #222;
  background: #fff;
}}
h1 {{ font-size: 1.6rem; }}
h2 {{
  font-size: 1.2rem;
  margin-top: 2rem;
  border-bottom: 1px solid #ccc;
  padding-bottom: 0.3rem;
}}
.summary {{ color: #555; margin: 0.3rem 0 0.8rem; }}
.standalone {{
  color: #666;
  font-size: 0.85rem;
  margin: 0.2rem 0;
}}
.standalone code {{
  background: #eee;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  font-family: Consolas, "Courier New", monospace;
}}
nav .standalone-hint {{
  font-size: 0.8rem;
  color: #888;
}}
pre {{
  background: #f5f5f5;
  padding: 0.8rem;
  overflow-x: auto;
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.85rem;
}}
nav ul {{ padding-left: 1.2rem; }}
nav a {{ text-decoration: none; }}
nav a:hover {{ text-decoration: underline; }}
nav code {{
  background: #eee;
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.8rem;
}}
.diagram {{
  margin: 0.4rem 0 0.6rem;
  color: #666;
}}
.diagram svg {{
  width: 100%;
  max-width: 22rem;
  height: auto;
}}
@media (prefers-color-scheme: dark) {{
  body {{ color: #ddd; background: #1e1e1e; }}
  h2 {{ border-bottom-color: #555; }}
  .summary {{ color: #aaa; }}
  .standalone {{ color: #aaa; }}
  .standalone code {{ background: #333; }}
  nav code {{ background: #333; }}
  nav .standalone-hint {{ color: #888; }}
  .diagram {{ color: #999; }}
  pre {{ background: #2a2a2a; }}
}}
</style>
</head>
<body>
<h1>tools コマンド一覧</h1>
<nav>
<ul>
{toc_items}
</ul>
</nav>
{chr(10).join(rows)}
</body>
</html>
"""
