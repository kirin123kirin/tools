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


# help.htmlはコマンド名のアルファベット順ではなく、何を処理するコマンドかで
# 固めて並べる（画像処理→テキスト集計→クリップボード処理→表形式データ→
# PowerPoint操作→その他）。カテゴリ内の順序はこの一覧の記載順。
# 各コマンドの2つ目の要素は、左サイドバー表示専用の短い要約（10文字前後）。
# proc.help（argparseのフル説明文）とは別に、サイドバーの行間を詰めるため
# ここで書き起こす。新しい処理を processing/ に追加したら、ここにも
# 追加すること（未登録の場合は「その他」カテゴリの末尾に自動で入り、
# 短い要約はフルのsummaryにフォールバックする）。
_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "画像処理",
        [
            ("touka", "背景を透過"),
            ("denoise", "ノイズ除去"),
            ("kukiri", "輪郭くっきり"),
        ],
    ),
    ("テキスト集計", [("cwc", "ワードクラウド生成")]),
    (
        "クリップボード処理",
        [
            ("clipmd", "Markdown⇔リッチテキスト"),
            ("mdtsv", "Markdown表⇔TSV"),
            ("clipfmt", "Markdown整形"),
            ("clipview", "ブラウザでプレビュー"),
        ],
    ),
    (
        "表形式データ",
        [
            ("profiler", "列をプロファイル"),
            ("lsdir", "フォルダ一覧をExcel化"),
        ],
    ),
    (
        "PowerPoint操作",
        [
            ("outline", "アウトラインからスライド追加"),
            ("ikko", "テキストボックスを合体"),
            ("mokuji", "スライドタイトル一覧"),
            ("tbl", "表とシェイプを相互変換"),
            ("seiretsu", "シェイプを格子状に整列"),
            ("nagasa", "シェイプのサイズを統一"),
            ("umekomi", "テキストボックスを埋め込み"),
            ("merioall", "和文フォントをメイリオに統一"),
            ("iro", "テーマカラーと既定書式を統一"),
            ("tsunagu", "コネクタを最寄りの接続点へ吸着"),
            ("bunkatsu", "画像を物体ごとに領域分割"),
        ],
    ),
    (
        "その他",
        [
            ("vv", "定型プロンプトをコピー"),
            ("help", "ヘルプ一覧を開く"),
            ("shortcut", "スタートメニューに登録"),
        ],
    ),
]

_CATEGORY_BY_COMMAND: dict[str, str] = {
    name: category for category, entries in _CATEGORIES for name, _ in entries
}
_ORDER_BY_COMMAND: dict[str, int] = {
    name: i for _, entries in _CATEGORIES for i, (name, _) in enumerate(entries)
}
_SHORT_SUMMARY_BY_COMMAND: dict[str, str] = {
    name: short for _, entries in _CATEGORIES for name, short in entries
}
_CATEGORY_ORDER: dict[str, int] = {category: i for i, (category, _) in enumerate(_CATEGORIES)}
_UNCATEGORIZED = "その他"


def command_category(command_name: str) -> str:
    """The category a command is grouped under in help.html. Commands not
    yet listed in `_CATEGORIES` fall back to "その他" rather than raising,
    so a newly added processor doesn't break help generation."""
    return _CATEGORY_BY_COMMAND.get(command_name, _UNCATEGORIZED)


def short_summary(command_name: str, fallback: str) -> str:
    """The sidebar-only short summary for a command, or `fallback` (the
    full argparse summary) if none is registered yet."""
    return _SHORT_SUMMARY_BY_COMMAND.get(command_name, fallback)


def _sort_key(command_name: str) -> tuple[int, int, str]:
    category = command_category(command_name)
    return (
        _CATEGORY_ORDER.get(category, len(_CATEGORIES)),
        _ORDER_BY_COMMAND.get(command_name, len(_CATEGORIES)),
        command_name,
    )

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
    "shortcut": (
        # before: コマンドプロンプトのウィンドウに文字入力
        '<rect x="10" y="15" width="80" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<line x1="10" y1="27" x2="90" y2="27" stroke="currentColor" stroke-width="1.5"/>'
        '<text x="16" y="45" font-size="11" font-family="Consolas, monospace" '
        'fill="currentColor">&gt;touka.exe_</text>'
        + _ARROW_CENTER +
        # after: スタートメニューにアイコンが並ぶ
        '<rect x="130" y="12" width="80" height="66" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="138" y="20" width="14" height="14" rx="3" fill="currentColor"/>'
        '<line x1="156" y1="27" x2="202" y2="27" stroke="currentColor" stroke-width="2"/>'
        '<rect x="138" y="40" width="14" height="14" rx="3" fill="currentColor"/>'
        '<line x1="156" y1="47" x2="202" y2="47" stroke="currentColor" stroke-width="2"/>'
        '<rect x="138" y="60" width="14" height="14" rx="3" fill="currentColor"/>'
        '<line x1="156" y1="67" x2="202" y2="67" stroke="currentColor" stroke-width="2"/>'
    ),
    "umekomi": (
        # before: shape（実線の四角形）の上にテキストボックス（破線の四角形）が重なる
        '<rect x="16" y="20" width="64" height="50" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="28" y="35" width="52" height="20" rx="1.5" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-dasharray="3,2"/>'
        '<text x="54" y="49" font-size="11" text-anchor="middle" '
        'fill="currentColor">Text</text>'
        + _ARROW_CENTER +
        # after: shape本体にテキストが収まり、テキストボックスの枠は消える
        '<rect x="136" y="20" width="64" height="50" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<text x="168" y="49" font-size="11" text-anchor="middle" '
        'fill="currentColor">Text</text>'
    ),
    "merioall": (
        # before: 書体がバラバラな「あ」の文字3つ（フォント不統一を表現）
        '<text x="24" y="55" font-size="30" font-family="serif" '
        'fill="currentColor">あ</text>'
        '<text x="52" y="55" font-size="26" font-family="sans-serif" '
        'font-weight="bold" fill="currentColor">あ</text>'
        '<text x="78" y="55" font-size="22" font-family="monospace" '
        'font-style="italic" fill="currentColor">あ</text>'
        + _ARROW_CENTER +
        # after: 同じ書体（メイリオ想定のsans-serif）に揃った「あ」の文字3つ
        '<text x="144" y="55" font-size="26" font-family="sans-serif" '
        'fill="currentColor">あ</text>'
        '<text x="170" y="55" font-size="26" font-family="sans-serif" '
        'fill="currentColor">あ</text>'
        '<text x="196" y="55" font-size="26" font-family="sans-serif" '
        'fill="currentColor">あ</text>'
    ),
    "iro": (
        # before: バラバラな色の四角形3つ（配色不統一を表現）
        '<rect x="14" y="20" width="20" height="50" fill="#8899aa"/>'
        '<rect x="40" y="20" width="20" height="50" fill="#cc8844"/>'
        '<rect x="66" y="20" width="20" height="50" fill="#9955bb"/>'
        + _ARROW_CENTER +
        # after: 統一された配色（深緑・レンガ色・グレー）の四角形3つ
        '<rect x="134" y="20" width="20" height="50" fill="#1E7145"/>'
        '<rect x="160" y="20" width="20" height="50" fill="#A8493D"/>'
        '<rect x="186" y="20" width="20" height="50" fill="#808080"/>'
    ),
    "tsunagu": (
        # before: 2つの四角形の間に、どちらにも繋がっていない浮いた線
        '<rect x="10" y="30" width="26" height="30" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="64" y="30" width="26" height="30" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<line x1="42" y1="38" x2="58" y2="52" stroke="currentColor" '
        'stroke-width="2.2"/>'
        '<circle cx="42" cy="38" r="2.5" fill="none" stroke="#c55" stroke-width="1.8"/>'
        '<circle cx="58" cy="52" r="2.5" fill="none" stroke="#c55" stroke-width="1.8"/>'
        + _ARROW_CENTER +
        # after: 線の両端が各四角形の接続点にぴったり吸着している
        '<rect x="130" y="30" width="26" height="30" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<rect x="184" y="30" width="26" height="30" rx="2" fill="none" '
        'stroke="currentColor" stroke-width="2.2"/>'
        '<line x1="156" y1="45" x2="184" y2="45" stroke="currentColor" '
        'stroke-width="2.2"/>'
        '<circle cx="156" cy="45" r="2.5" fill="currentColor"/>'
        '<circle cx="184" cy="45" r="2.5" fill="currentColor"/>'
    ),
    "bunkatsu": (
        # before: 1枚の画像シェイプの中に、接した/離れた2つの物体（丸）
        '<rect x="14" y="15" width="72" height="60" rx="3" fill="none" '
        'stroke="currentColor" stroke-width="2"/>'
        '<circle cx="38" cy="45" r="16" fill="#cfe3ff" stroke="currentColor" stroke-width="2"/>'
        '<circle cx="64" cy="45" r="14" fill="#ffd699" stroke="currentColor" stroke-width="2"/>'
        + _ARROW_CENTER +
        # after: 分離された2枚の透過画像（市松模様の背景）
        '<rect x="130" y="18" width="34" height="54" rx="2" fill="#eee" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="130" y="18" width="8" height="8" fill="#ccc"/>'
        '<rect x="146" y="18" width="8" height="8" fill="#ccc"/>'
        '<rect x="138" y="26" width="8" height="8" fill="#ccc"/>'
        '<rect x="154" y="26" width="8" height="8" fill="#ccc"/>'
        '<circle cx="147" cy="45" r="15" fill="#cfe3ff" stroke="currentColor" stroke-width="2"/>'
        '<rect x="172" y="24" width="34" height="42" rx="2" fill="#eee" '
        'stroke="currentColor" stroke-width="2"/>'
        '<rect x="172" y="24" width="8" height="8" fill="#ccc"/>'
        '<rect x="188" y="24" width="8" height="8" fill="#ccc"/>'
        '<rect x="180" y="32" width="8" height="8" fill="#ccc"/>'
        '<circle cx="189" cy="45" r="13" fill="#ffd699" stroke="currentColor" stroke-width="2"/>'
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
    category: str
    toc_summary: str


def collect_command_help() -> list[CommandHelp]:
    """Build per-command help text by rendering each Processor's own argparse help."""
    processors = _discover_processors()
    results: list[CommandHelp] = []

    for name in sorted(processors, key=_sort_key):
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
                category=command_category(name),
                toc_summary=short_summary(name, proc.help),
            )
        )

    return results


def _build_standalone_parser(proc: Processor) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=proc.name, description=proc.help)
    proc.add_arguments(parser)
    return parser


def render_help_html(commands: list[CommandHelp]) -> str:
    rows = []
    prev_category: str | None = None
    for cmd in commands:
        if cmd.category != prev_category:
            rows.append(f'<h2 class="category">{html_module.escape(cmd.category)}</h2>')
            prev_category = cmd.category

        diagram_svg = _render_diagram_svg(cmd.name)
        exe_name = f"{cmd.standalone_name}.exe"
        copy_name = html_module.escape(cmd.standalone_name)
        rows.append(
            "<section class=\"command\">\n"
            f"<h3 id=\"{html_module.escape(cmd.name)}\">{html_module.escape(cmd.name)}</h3>\n"
            f"<p class=\"standalone\">単体実行: "
            f"<code>{html_module.escape(exe_name)}</code> "
            f'<button type="button" class="copy-btn" data-copy="{copy_name}">'
            "コマンド名をコピー</button>"
            "</p>\n"
            f"{diagram_svg}\n"
            f"<p class=\"summary\">{html_module.escape(cmd.summary)}</p>\n"
            f"<pre>{html_module.escape(cmd.full_help)}</pre>\n"
            "</section>"
        )

    toc_parts: list[str] = []
    prev_toc_category: str | None = None
    for c in commands:
        if c.category != prev_toc_category:
            if prev_toc_category is not None:
                toc_parts.append("</ul></li>")
            toc_parts.append(
                '<li class="toc-category">'
                f'<span class="toc-category-label">{html_module.escape(c.category)}</span>'
                "<ul>"
            )
            prev_toc_category = c.category
        copy_name = html_module.escape(c.standalone_name)
        toc_parts.append(
            '<li class="toc-command">'
            f'<a href="#{html_module.escape(c.name)}">{html_module.escape(c.name)}'
            f'<span class="toc-summary">{html_module.escape(c.toc_summary)}</span>'
            "</a>"
            f'<button type="button" class="copy-btn toc-copy-btn" data-copy="{copy_name}" '
            f'title="コマンド名をコピー" aria-label="{copy_name}をコピー">⧉</button>'
            "</li>"
        )
    if prev_toc_category is not None:
        toc_parts.append("</ul></li>")
    toc_items = "\n".join(toc_parts)

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta http-equiv="Cache-Control" content="no-store">
<title>tools コマンドヘルプ</title>
<style>
:root {{ color-scheme: light dark; --nav-width: 36rem; }}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: -apple-system, "Segoe UI", sans-serif;
  line-height: 1.6;
  color: #222;
  background: #fff;
}}
.layout {{
  display: flex;
  align-items: flex-start;
}}
nav {{
  flex: 0 0 var(--nav-width);
  width: var(--nav-width);
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  padding: 1.5rem 1rem;
  border-right: 1px solid #ddd;
  background: #fafafa;
}}
#nav-resizer {{
  flex: 0 0 6px;
  width: 6px;
  cursor: col-resize;
  position: sticky;
  top: 0;
  height: 100vh;
  background: transparent;
}}
#nav-resizer:hover, #nav-resizer.dragging {{
  background: #99c2ff;
}}
main {{
  flex: 1 1 auto;
  min-width: 0;
  max-width: 50rem;
  margin: 0 auto;
  padding: 1.5rem 1.5rem 3rem;
}}
nav h1 {{ font-size: 1.15rem; margin: 0 0 1rem; }}
h2.category {{
  font-size: 1.35rem;
  margin-top: 2.5rem;
  padding-bottom: 0.4rem;
  border-bottom: 2px solid #888;
}}
main > h2.category:first-child {{ margin-top: 0; }}
h3 {{
  font-size: 1.1rem;
  margin-top: 1.6rem;
  border-bottom: 1px solid #ccc;
  padding-bottom: 0.3rem;
}}
nav ul {{ list-style: none; padding-left: 0; margin: 0; }}
nav li.toc-category {{ margin-top: 0.7rem; }}
nav li.toc-category:first-child {{ margin-top: 0; }}
.toc-category-label {{
  display: block;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #888;
}}
nav li.toc-category > ul {{ margin-top: 0.15rem; margin-bottom: 0; }}
li.toc-command {{
  display: flex;
  align-items: center;
  gap: 0.15rem;
}}
nav a {{
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  flex: 1 1 auto;
  min-width: 0;
  text-decoration: none;
  padding: 0.08rem 0.4rem;
  border-radius: 4px;
  color: #222;
  line-height: 1.35;
}}
nav a:hover {{ background: #eee; }}
.toc-summary {{
  font-size: 0.72rem;
  color: #777;
  font-weight: normal;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.copy-btn {{
  font: inherit;
  cursor: pointer;
  border: 1px solid #ccc;
  background: #fff;
  border-radius: 4px;
  color: #444;
}}
.toc-copy-btn {{
  flex: 0 0 auto;
  font-size: 0.85rem;
  line-height: 1;
  padding: 0.15rem 0.35rem;
  opacity: 0;
  visibility: hidden;
}}
li.toc-command:hover .toc-copy-btn, .toc-copy-btn:focus-visible {{
  opacity: 1;
  visibility: visible;
}}
.copy-btn:hover {{ background: #eee; }}
.copy-btn.copied {{
  border-color: #4a8f4a;
  color: #2f6e2f;
}}
.copy-btn.copy-failed {{
  border-color: #c0504d;
  color: #a33;
}}
.standalone .copy-btn {{
  font-size: 0.8rem;
  padding: 0.1rem 0.5rem;
  margin-left: 0.3rem;
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
pre {{
  background: #f5f5f5;
  padding: 0.8rem;
  overflow-x: auto;
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.85rem;
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
@media (max-width: 56rem) {{
  .layout {{ display: block; }}
  nav {{
    position: static;
    width: auto;
    height: auto;
    border-right: none;
    border-bottom: 1px solid #ddd;
  }}
  #nav-resizer {{ display: none; }}
  main {{ margin: 0; max-width: none; }}
}}
@media (prefers-color-scheme: dark) {{
  body {{ color: #ddd; background: #1e1e1e; }}
  nav {{ background: #181818; border-right-color: #444; }}
  nav a {{ color: #ddd; }}
  nav a:hover {{ background: #2a2a2a; }}
  .toc-category-label {{ color: #999; }}
  .toc-summary {{ color: #999; }}
  #nav-resizer:hover, #nav-resizer.dragging {{ background: #3a5a8a; }}
  h2.category {{ border-bottom-color: #666; }}
  h3 {{ border-bottom-color: #555; }}
  .summary {{ color: #aaa; }}
  .standalone {{ color: #aaa; }}
  .standalone code {{ background: #333; }}
  .diagram {{ color: #999; }}
  pre {{ background: #2a2a2a; }}
  .copy-btn {{ background: #2a2a2a; border-color: #555; color: #ccc; }}
  .copy-btn:hover {{ background: #333; }}
  .copy-btn.copied {{ border-color: #5cb85c; color: #8fd68f; }}
  .copy-btn.copy-failed {{ border-color: #d9736c; color: #e08a84; }}
}}
@media (max-width: 56rem) {{
  nav {{ border-bottom-color: #444; }}
}}
</style>
</head>
<body>
<div class="layout">
<nav id="nav-sidebar">
<h1>tools コマンド一覧</h1>
<ul>
{toc_items}
</ul>
</nav>
<div id="nav-resizer"></div>
<main>
{chr(10).join(rows)}
</main>
</div>
<script>
(function () {{
  // サイドバー幅をドラッグで調整できるようにする。localStorageに保存し、
  // 次回開いたときも同じ幅を復元する。外部通信・外部ライブラリは使わない。
  var STORAGE_KEY = "workpytools-help-nav-width";
  var MIN_WIDTH = 200;
  var MAX_WIDTH = 800;
  var root = document.documentElement;
  var resizer = document.getElementById("nav-resizer");
  var nav = document.getElementById("nav-sidebar");

  function autofitWidth() {{
    // 最も長いコマンド名+要約の行が折り返さずに収まる幅を実測する。
    // 各<li>のscrollWidthはpadding込みの必要幅を返すため、そのまま
    // navの左右paddingを足せば「はみ出さない幅」になる。
    var items = nav.querySelectorAll("li.toc-command");
    var maxItemWidth = 0;
    items.forEach(function (item) {{
      if (item.scrollWidth > maxItemWidth) maxItemWidth = item.scrollWidth;
    }});
    var navStyle = getComputedStyle(nav);
    var horizontalPadding =
      parseFloat(navStyle.paddingLeft) + parseFloat(navStyle.paddingRight);
    return Math.round(maxItemWidth + horizontalPadding);
  }}

  var saved = window.localStorage.getItem(STORAGE_KEY);
  if (saved) {{
    var width = parseInt(saved, 10);
    if (width >= MIN_WIDTH && width <= MAX_WIDTH) {{
      root.style.setProperty("--nav-width", width + "px");
    }}
  }} else {{
    var fitted = autofitWidth();
    if (fitted < MIN_WIDTH) fitted = MIN_WIDTH;
    if (fitted > MAX_WIDTH) fitted = MAX_WIDTH;
    root.style.setProperty("--nav-width", fitted + "px");
  }}

  var dragging = false;

  resizer.addEventListener("mousedown", function (event) {{
    dragging = true;
    resizer.classList.add("dragging");
    event.preventDefault();
  }});

  document.addEventListener("mousemove", function (event) {{
    if (!dragging) return;
    var width = event.clientX;
    if (width < MIN_WIDTH) width = MIN_WIDTH;
    if (width > MAX_WIDTH) width = MAX_WIDTH;
    root.style.setProperty("--nav-width", width + "px");
  }});

  document.addEventListener("mouseup", function () {{
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove("dragging");
    var current = getComputedStyle(root).getPropertyValue("--nav-width");
    window.localStorage.setItem(STORAGE_KEY, parseInt(current, 10));
  }});
}})();

(function () {{
  // 「コマンド名をコピー」ボタン。単体実行ファイル名（exeの拡張子なし）を
  // クリップボードへコピーするだけで、何のプロセスも起動しない。
  // Clipboard APIというブラウザの標準・公開APIのみを使う。
  function fallbackCopy(text) {{
    // Clipboard APIが使えない環境（file://での制限、権限拒否など）向けの
    // フォールバック。非表示のtextareaを使う非推奨APIだが、コピー機能が
    // 完全に無反応になるよりはよい。
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    var ok = false;
    try {{
      ok = document.execCommand("copy");
    }} catch (e) {{
      ok = false;
    }}
    document.body.removeChild(textarea);
    return ok;
  }}

  document.querySelectorAll(".copy-btn").forEach(function (btn) {{
    var originalLabel = btn.textContent;
    btn.addEventListener("click", function () {{
      var text = btn.getAttribute("data-copy");
      var isIconButton = btn.classList.contains("toc-copy-btn");

      function showResult(ok) {{
        btn.classList.add(ok ? "copied" : "copy-failed");
        if (!isIconButton) {{
          btn.textContent = ok ? "コピーしました" : "コピーできませんでした";
        }}
        window.setTimeout(function () {{
          btn.classList.remove("copied", "copy-failed");
          if (!isIconButton) {{
            btn.textContent = originalLabel;
          }}
        }}, 1200);
      }}

      if (window.navigator.clipboard && window.navigator.clipboard.writeText) {{
        window.navigator.clipboard.writeText(text).then(
          function () {{ showResult(true); }},
          function () {{ showResult(fallbackCopy(text)); }}
        );
      }} else {{
        showResult(fallbackCopy(text));
      }}
    }});
  }});
}})();
</script>
</body>
</html>
"""
