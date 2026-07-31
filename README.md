# workpytools

さまざまな処理をコマンドとして追加していくためのPythonプロジェクト。

**動作環境: Windows 11 専用**（クリップボード連携等はWindows APIに依存するため、他OSは考慮しない）

## 構成

```
workpytools/
├── pyproject.toml          # 依存関係・lint(ruff)・型チェック(mypy)・pytest設定
├── src/
│   └── workpytools/
│       ├── cli.py          # エントリポイント。processing/配下を自動探索してサブコマンド化
│       ├── common/         # 処理間で使い回す共通機能
│       │   ├── logging.py
│       │   ├── config.py
│       │   └── clipboard.py # クリップボードからの画像/ファイル取得（Windows専用）
│       └── processing/     # 個々の処理。1ファイル=1処理
│           ├── base.py             # Processor基底クラス
│           ├── touka.py            # 画像背景透過ツール
│           ├── denoise.py          # 画像ノイズ除去ツール（OpenCV Non-local Means）
│           ├── kukiri.py           # JPEG輪郭滲み除去・境界強調ツール（バイラテラル+アンシャープマスク）
│           ├── cwc.py              # テキストからワードクラウド画像を生成するツール
│           ├── clipmd.py           # クリップボードのMarkdown↔リッチテキスト変換
│           ├── mdtsv.py            # クリップボードのMarkdownの表↔TSV変換
│           ├── clipview.py         # クリップボードのMarkdown/HTMLをブラウザでプレビュー
│           ├── clipfmt.py          # クリップボードのMarkdown整形
│           ├── vv.py               # 定型プロンプトをクリップボードにコピー
│           ├── profiler.py         # 表形式データの列プロファイリング（欠損・一意性・主キー候補）
│           ├── lsdir.py            # フォルダ配下をExcelで集計できる表形式で一覧化
│           ├── outline.py          # クリップボードのアウトラインからPowerPointにスライドを追加
│           ├── ikko.py             # PowerPointのバラバラなテキストボックスを1つに合体
│           ├── mokuji.py           # PowerPointの全スライドタイトルを一覧化してクリップボードへ
│           ├── tbl.py              # PowerPointの表とシェイプ群を相互変換（分解/合成/行分割）
│           ├── seiretsu.py         # PowerPointのシェイプを表に変換せず格子状に整列
│           ├── nagasa.py           # PowerPointのシェイプの幅・高さを最大値に統一
│           ├── umekomi.py          # PowerPointのテキストボックスをシェイプに埋め込む
│           ├── merioall.py         # テーマ・マスター・全スライドの和文フォントをメイリオに統一
│           ├── iro.py              # 既存スライドの独自色化・テーマカラー変更・既定書式の一時適用
│           ├── tsunagu.py          # コネクタを最寄りのシェイプ接続点に吸着（2つ選択で新規作成）
│           ├── help.py             # 全コマンドのヘルプ一覧をブラウザで開く
│           └── shortcut.py         # 全コマンドのスタートメニューショートカットを作成/削除
├── tests/                  # src/workpytools と同じ階層構造でテストを配置
├── configs/                # 処理ごとの設定ファイル(TOML)を置く場所（common/config.py で読み込み）
├── scripts/                # 動作確認用の使い捨てスクリプト（.gitignore対象。
│                            # ただし gen_help.py と pre-commit は例外的にバージョン管理する）
└── tmp/                    # 一時ファイル・実行結果ダンプなど（.gitignore対象）
```

## 新しい処理の追加方法

1. `src/workpytools/processing/` に新しいモジュールを作成する
2. `Processor` を継承したクラスを定義し、`name`（サブコマンド名）と
   `add_arguments` / `run` を実装する（`touka.py` や `denoise.py` を参照）
3. それだけで`tools <name>`としてCLIに自動登録される（`cli.py` の編集は不要）
4. **単体実行用のエントリーポイントも追加する**: `pyproject.toml` の
   `[project.scripts]` に `name`（`Processor.name`と同じ文字列）を
   `workpytools.cli:run_as_subcommand` として登録する。これにより
   `pip install -e .` 後、`tools <name> ...` に加えて `<name> ...`
   （Windowsでは `<name>.exe ...`）としても直接実行できるようになる。

```toml
[project.scripts]
my-process = "workpytools.cli:run_as_subcommand"
```

```python
# src/workpytools/processing/my_process.py
from workpytools.processing.base import Processor


class MyProcess(Processor):
    name = "my-process"
    help = "何をする処理か"

    def add_arguments(self, parser):
        parser.add_argument("input")

    def run(self, args) -> int:
        ...
        return 0
```

## セットアップ（Windows / PowerShell）

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### pre-commitフックの導入（`doc/help.html`の自動更新）

`doc/help.html`（全コマンドのヘルプ一覧、`help`/`toolh.exe`が開くページ）は
コミット時に自動再生成されるようにしています。`.git/hooks/`はリポジトリに含まれないため、
クローン後に一度だけ導入してください。

```powershell
Copy-Item scripts\pre-commit .git\hooks\pre-commit
```

以降、`git commit`のたびに `python scripts/gen_help.py` が実行され、
`doc/help.html`に変更があればコミットに自動で含まれます。

## 実行

```powershell
# 画像の背景を透過（ファイルパス指定）
tools touka C:\path\to\photo.jpg

# 画像の背景を透過（クリップボードから取得）
# - 画像編集ソフトで「画像をコピー」した場合、または
# - Explorerで画像ファイルをコピー（Ctrl+C）した場合
tools touka

# 出力先を指定
tools touka C:\path\to\photo.jpg -o C:\path\to\out.png

# 画像のノイズ除去（ファイルパス指定）
tools denoise C:\path\to\photo.jpg

# 画像のノイズ除去（クリップボードから取得）
tools denoise

# ノイズ除去強度を指定（デフォルト: 10.0、大きいほど強くノイズを除去）
tools denoise C:\path\to\photo.jpg --strength 15

# 出力先を指定
tools denoise C:\path\to\photo.jpg -o C:\path\to\out.png

# JPEGの輪郭滲みを除去し境界をくっきりさせる（フラットイラスト向け）
tools kukiri C:\path\to\illustration.jpg

# 平滑化・シャープ強度を指定（デフォルト: smooth=75.0, sharpen=0.5）
tools kukiri C:\path\to\illustration.jpg --smooth 90 --sharpen 0.8

# 出力先を指定
tools kukiri C:\path\to\illustration.jpg -o C:\path\to\out.png

# テキストからワードクラウド画像を生成（ファイルパス指定）
tools cwc C:\path\to\memo.txt

# クリップボードのテキストから生成
tools cwc

# Janomeによる分かち書きで分割
tools cwc C:\path\to\memo.txt -w

# 名詞・動詞のみを集計（分かち書きを自動的に使用）
tools cwc C:\path\to\memo.txt --hinshi 名詞 動詞

# 同義語辞書で表記ゆれを1語に寄せる（既定の区切り文字分割専用）
tools cwc C:\path\to\memo.txt --semantic

# 集計単位を文にし、埋め込みベクトルの類似度で似た文をまとめる
# （アンケート自由記述など、表現違いの同趣旨回答をまとめたい場合向け）
tools cwc C:\path\to\answers.txt --similar

# 出力先を指定
tools cwc C:\path\to\memo.txt -o C:\path\to\out.png

# クリップボードのMarkdownとリッチテキストを相互変換（クリップボードの状態から自動判別）
# - リッチテキストがコピーされていればMarkdownに変換
# - Markdown（プレーンテキスト）がコピーされていればリッチテキストに変換
tools clipmd

# 変換方向を明示指定
tools clipmd --to-markdown
tools clipmd --to-rich

# クリップボードのMarkdownの表とTSVを相互変換（Excelとのやり取り用）
tools mdtsv

# クリップボードのMarkdown/HTMLをブラウザでプレビュー
tools clipview

# クリップボードに画像データがある場合（toukaの出力等）は、
# 透過を確認しやすいよう市松模様の背景に重ねてプレビューする
tools clipview

# クリップボードのMarkdownを整形（表の桁揃え、見出し統一、リスト記号統一など）
tools clipfmt

# 定型プロンプトの一覧を表示（クリップボードには何も入れない）
tools vv

# 番号を指定して、そのプロンプトをクリップボードにコピー（あとはCtrl+Vで貼るだけ）
tools vv 3

# 表形式データ（CSV/TSV/Excel/JSON）の各列をプロファイル（ファイルパス指定）
tools profiler C:\path\to\data.csv

# クリップボードのTSV（Excelで範囲コピーしたものなど）をプロファイル
tools profiler

# 結果をExcelファイルに書き出す（欠損・重複が疑わしいセルを赤塗り）
tools profiler C:\path\to\data.xlsx -o C:\path\to\profile.xlsx

# 結果をブラウザでプレビュー
tools profiler C:\path\to\data.csv --view

# フォルダ配下をExcelで集計できる表形式で一覧化
tools lsdir C:\path\to\folder

# ファイルのみ／フォルダのみに絞り込む
tools lsdir C:\path\to\folder --files-only
tools lsdir C:\path\to\folder --dirs-only

# フォルダ配下の合計サイズも計算する（全走査後に出力するため待ち時間が発生する）
tools lsdir C:\path\to\folder --total-size

# .lnkショートカットのリンク先も解決する
tools lsdir C:\path\to\folder --resolve-link

# 結果をExcelファイルに書き出す
tools lsdir C:\path\to\folder -o C:\path\to\list.xlsx

# クリップボードのアウトライン（Markdown見出し/タブ区切り/空行区切り）から
# アクティブなPowerPointにスライドを追加する
tools outline

# PowerPointのスライド上でバラバラなテキストボックスを1つに合体する
# （選択中ならその範囲のみ、未選択ならアクティブスライド全体が対象）
tools ikko

# 実際には変更せず、合体対象になる組み合わせだけを確認する
tools ikko --dry-run

# アクティブなPowerPointの全スライドタイトルを一覧化してクリップボードにコピーする
tools mokuji

# PowerPointの表とシェイプ群を相互変換する（選択状態から自動判定）
# - 表を選択 → セルごとの四角形に分解
# - 四角形群を2つ以上選択 → 座標から表を推定して合成
# - 複数行テキストのシェイプを1つ選択 → 行ごとのシェイプに分割
tools tbl

# 選択したシェイプを表に変換せず、位置だけを格子状に整列する
tools seiretsu

# 選択したシェイプの幅・高さを最大値に統一する（中心を保ったまま拡大）
tools nagasa

# shapeの上に重ねて配置されたテキストボックスをshapeに埋め込む
# （選択したシェイプ群が対象。中心座標が重なるテキストボックスをshapeに統合し、
#  元のテキストボックスは削除する）
tools umekomi

# 実際には変更せず、埋め込み対象になる組み合わせだけを確認する
tools umekomi --dry-run

# テーマ・スライドマスター・全スライドの和文フォントをメイリオに統一する
# （欧文フォントは変更しない。表・SmartArt等は対象外）
tools merioall

# 既存スライドを独自色化した上で、テーマカラー（アクセント1〜6）を
# 新配色に変更し、シェイプ・矢印・テキストボックスの既定書式を一時適用する
tools iro

# コネクタとシェイプを選択して実行し、コネクタの両端を最寄りの
# 接続点へ吸着させる（マウスでのドラッグ接続が不要になる）
tools tsunagu

# シェイプをちょうど2つ選択して実行すると、それらを繋ぐ直線コネクタを
# 新規作成する（黒・2pt、互いに最も近い接続点同士を繋ぐ）
tools tsunagu

# 全コマンドのヘルプ一覧（doc/help.html）をブラウザで開く
tools help
# 単体実行ファイルはtoolh.exe（他コマンドと違いhelp.exeという名前ではない）
toolh

# 全コマンドのスタートメニューショートカットを作成する
tools shortcut

# 作成済みのショートカットを削除する
tools shortcut --remove
```

`touka` は初回実行時に背景除去モデル（U2Net, rembg）をインターネットからダウンロードします。
`denoise`・`kukiri`はOpenCVの古典的アルゴリズムのみを使用し、モデルダウンロードは行いません（外部通信なし）。

`kukiri`は`denoise`とは異なり、ランダムノイズではなくJPEG圧縮特有の輪郭のにじみ・リンギングを
対象にしています。バイラテラルフィルタ（輪郭を保ったまま平滑化）→アンシャープマスク（輪郭強調）
の順に処理し、フラットデザインのイラストなど「境界をくっきりさせたい」用途向けです。

`cwc`はテキストを単語に分割して頻度を集計し、`wordcloud`ライブラリでワードクラウド画像を
生成します。既定は句点・かっこ・空白類による単純な区切り文字分割で、外部モデルのダウンロードは
不要です。日本語を分かち書きしたい場合は`-w`（Janome、純Python実装で外部辞書のインストール不要）
を指定します。フォントは既定でWindows標準搭載のメイリオ（`C:\Windows\Fonts\meiryo.ttc`）を使うため、
別途フォントの用意は不要です。

`--similar`は集計単位を語ではなく文にし、埋め込みベクトルの類似度で似た文をまとめて集計します。
**初回実行時にのみ**埋め込みモデル（ONNX形式、`Xenova/paraphrase-multilingual-MiniLM-L12-v2`の
量子化版、約120MB）を `https://huggingface.co` からダウンロードします。IT部門でプロキシ/EDRの
アローリスト登録が必要な場合は、このホストを登録してください。ダウンロードしたモデルは
`%LOCALAPPDATA%\workpytools\models\` にキャッシュされ、2回目以降は再ダウンロードしません。

`clipmd`/`mdtsv`/`clipview`/`clipfmt`はクリップボードの内容をその場で変換・表示するツール群です。
入力も出力もファイルではなくクリップボード経由（`clipview`のみプレビュー用に一時HTMLを生成）で、
`tools <name>` を実行した瞬間にクリップボードの中身を読み書きします（バックグラウンド監視はしません）。
役割の違いは以下の通りです。

| コマンド | 役割 |
|---|---|
| `clipmd` | Markdown ↔ リッチテキスト の文書全体の形式変換 |
| `mdtsv` | Markdownの表 ↔ TSV の表だけの変換（Excelとの橋渡し） |
| `clipview` | Markdown/HTML をブラウザでプレビュー（クリップボードは変更しない） |
| `clipfmt` | Markdown の整形（表の桁揃え、見出し・リスト記号の統一など） |

`clipview`のみ、プレビュー用に `%TEMP%\workpytools_clipview_preview.html` を固定名で生成します
（毎回上書きするためファイルは増殖しません）。

### shortcut（スタートメニューへのショートカット登録）

`pip install` だけではスタートメニューにアイコンが並ばないため、`tools shortcut`
を1回実行すると `%APPDATA%\Microsoft\Windows\Start Menu\Programs\workpytools\` に
全コマンド分の単体実行ファイル（`touka.exe`等）へのショートカットを作成します。
これにより、コマンド名を覚えて打ち込まなくても、スタートメニューの検索や
一覧からクリックして起動できるようになります（引数が必要なコマンドは
クリップボード入力モードで起動します）。

- `pip install` 実行時に自動では作られません（勝手にファイルを配置しない
  という方針のため）。導入後に一度だけ手動で実行してください
- アイコンは同梱の `data/app.ico`（自前描画のシンプルな図形）を使います
- `tools shortcut --remove` で作成済みのショートカットを一括削除できます
- レジストリの変更、スケジュールタスクの登録などの永続化は一切行いません
  （スタートメニューフォルダへのショートカットファイル配置のみです）

```powershell
tools shortcut          # 全コマンド分のショートカットを作成
tools shortcut --remove # 作成済みのショートカットを削除
```

**アンインストール前に必ず `tools shortcut --remove` を実行してください。**
`pip uninstall` にはアンインストール時に任意の処理を自動実行するフック機構が
存在しないため、`shortcut`が作成したショートカットは`pip uninstall`だけでは
削除されません。削除しないまま`pip uninstall`すると、実体のないexeを指す
リンク切れの`.lnk`がスタートメニューに残ります。

```powershell
tools shortcut --remove
pip uninstall workpytools
```

### vv（定型プロンプトの呼び出し）

よく使う長文プロンプトを、フォルダを開いて探して全選択コピーする手間なしに
クリップボードへ入れるコマンドです。

`%APPDATA%\workpytools\vv\` に **1ファイル1プロンプトの `.txt`** を置いておくと、
ファイル名がそのままプロンプト名として一覧に出ます。

```powershell
# 一覧を見る（クリップボードには何も入らない）
vv
#  1: 01_企画書雛形              以下の要件で企画書のドラフトを作成してくだ...
#  2: 02_謝罪メール              下記の状況について、取引先向けの謝罪メール...

# 番号を指定して即コピー（一覧は出ない）→ あとは貼りたい場所で Ctrl+V
vv 1
```

- 並び順はファイル名順です。よく使うものを上に出したい場合は
  `01_` のような接頭辞をファイル名に付けてください
  （日本語名はUnicode順のため五十音順にはなりません）
- 貼り付け（Ctrl+V）は利用者が行います。キー入力の自動送信は行いません
- 改行はWindowsの慣習に合わせてCRLFに統一してクリップボードへ入れます

### profiler（表形式データのプロファイリング）

CSV/TSV/Excel/JSONの各列について、行数・欠損数・充填率・一意数・一意率・
頻度上位・主キー候補らしさ（`key_score`、充填率と一意率の調和平均）を算出します。
ファイルパスを指定しない場合はクリップボードのTSV（Excelで範囲コピーした内容など）を読みます。
Excel入力を含むときのみ`sheet`列が追加されます。`--clip`でクリップボードへ、
`--view`でブラウザプレビュー、`-o`でTSV/xlsxファイルへ出力できます
（既定は標準出力）。

### lsdir（フォルダ一覧のExcel向け表形式出力）

指定フォルダ配下を再帰的に走査し、`source, type, name, fullpath, parent, ext,
size, mtime, depth`の固定列で一覧化します。サイズは既定でKB（小数第2位）、
`--unit b/kb/mb/gb`で切り替え可能です（1KB=1024）。`--total-size`は
フォルダ配下の合計サイズも計算しますが、全走査完了後でないと出せないため
オプトインです。`.lnk`ショートカットのリンク先は`--resolve-link`を指定した
場合のみ解決します（`WScript.Shell`経由）。複数フォルダを指定して起点が
重複する場合はフルパスで自動的に重複除去されます。

### PowerPointをCOM操作するコマンド（outline / ikko / mokuji / tbl / seiretsu / nagasa / umekomi / merioall / iro / tsunagu）

いずれも実行中のPowerPointを対象にします（`pywin32`経由、`python-pptx`は
「開いているファイル」を操作できないため使いません）。役割は以下の通りです。

| コマンド | 役割 |
| --- | --- |
| `outline` | クリップボードのアウトラインからスライドを新規に追加する |
| `ikko` | すでにあるスライド上のバラバラなテキストボックスを1つに合体する |
| `mokuji` | 全スライドのタイトルを一覧化してクリップボードにコピーする |
| `tbl` | PowerPointの表とシェイプ群を相互変換する（選択状態から自動判定） |
| `seiretsu` | 選択したシェイプを表に変換せず格子状の位置に整列する |
| `nagasa` | 選択したシェイプの幅・高さを最大値に統一する |
| `umekomi` | 選択したシェイプの上に重ねて置かれたテキストボックスをシェイプ本体に埋め込む |
| `merioall` | テーマ・スライドマスター・全スライドの和文フォントをメイリオに統一する |
| `iro` | 既存スライドを独自色化した上でテーマカラーと既定図形の書式を統一する |
| `tsunagu` | コネクタの端点を最寄りのシェイプ接続点に吸着させる（2つ選択で新規作成） |

- `outline`はクリップボードのテキストを**Markdown見出し（`#`等）／タブ区切り
  ／空行区切り**の3形式から自動判別し、抽出した項目ぶんのスライドを
  アクティブなプレゼンテーションの末尾に追加します。PowerPointが
  起動していない場合は新規に起動し、新規プレゼンテーションを作成して
  続行します。目次スライドの生成は行いません（`mokuji`が担います）
- `ikko`はSVGを「図形に変換」した際に1行ずつ分割されてしまった
  テキストボックス群を、フォント・座標・行送りが揃った隣接シェイプの
  かたまりとして検出し、1つのテキストボックス（複数段落）に合体します。
  処理直前に必ずUndo境界を打つため、**Ctrl+Zひと押しで合体前の状態に
  戻せます**。`--dry-run`で実際に変更せず対象を確認できます。
  PowerPointが起動していない、またはプレゼンテーションが開かれていない
  場合は新規起動せずエラーになります（既存のスライドを加工する
  コマンドのため）
- `mokuji`はタイトルプレースホルダーが空でも、スライド上で最も上にある
  テキストを代用してタイトルを推定します。結果はタイトルのみを1行1件で
  クリップボードにコピーします（番号は付きません）。`ikko`と同じく
  PowerPointが起動していない場合はエラーになります
- `tbl`は選択状態から変換方向を自動判定します。**表を選択**すればセルごとの
  四角形に分解し（隣接シェイプ同士が重ならないよう、セルサイズの5%を目安に
  上下左右へ間隔を空けます）、**四角形群を2つ以上選択**すれば座標から行・列を
  推定して表に合成します（間隔が不揃いでも推定できます）。**複数行テキストの
  シェイプを1つだけ選択**した場合は行ごとに独立したシェイプへ分割します
  （空行はスキップ）。`ikko`と同じくUndo境界を必ず打つため、Ctrl+Z一回で
  元に戻せます。何も選択していない場合はエラーになります（分解・合成・
  行分割のどれを行うか自動推測しないため）
- `seiretsu`は`tbl`の合成方向と似た状況（座標がバラバラなシェイプ群）を
  対象にしますが、**表オブジェクトへの変換は行わず**、選択したシェイプの
  個数・形状・書式をそのまま保ったうえで**位置（`Left`/`Top`）だけ**を
  格子状に並べ直します。各列・各行のセルサイズはその列・行内で最大の
  シェイプに合わせるため、サイズが大きく異なるシェイプが混在していても
  重なりません。2つ以上選択されていない場合はエラーになります
- `nagasa`は選択したシェイプの幅・高さを、それぞれの最大値へ統一します。
  各シェイプは**中心座標を固定**したまま拡大するため、`seiretsu`で
  整列した後に使っても位置関係が崩れません。**「テキストに合わせて図形の
  サイズを調整する」設定（`AutoSize`）が有効だと、リサイズ後にテキストを
  編集した際にサイズが自動調整で巻き戻る事故が実機で確認されたため、
  リサイズ前に対象シェイプの`AutoSize`を無効化します**。2つ以上選択
  されていない場合はエラーになります
- `umekomi`は選択したシェイプ群の中から、図形種別が**テキストボックス
  （`msoTextBox`）のもの**とそれ以外（埋め込み先シェイプ）を区別し、
  テキストボックスの**中心座標**が埋め込み先シェイプの矩形内に入っている
  組み合わせを埋め込み対象とします。1つのシェイプに複数のテキストボックスが
  重なる場合は、上下位置（`Top`）の順に改行区切りで結合します。
  埋め込み先シェイプに元々テキストがある場合は、テキストボックスが
  シェイプの垂直中心より下にあれば末尾へ、上にあれば先頭へ追加します。
  書式（フォント名・サイズ・太字・色・配置）は最も上にあるテキストボックス
  のものを採用します。埋め込み後、元のテキストボックスは削除されます。
  `ikko`と同じくUndo境界を必ず打つため、Ctrl+Z一回で元に戻せます。
  `--dry-run`で実際に変更せず対象を確認できます。2つ以上選択されていない
  場合はエラーになります
- `merioall`は、SVGを図形に変換した際などにテキストボックスのフォントが
  遊ゴシックのまま残る問題への対処として、プレゼンテーション内の
  **和文（東アジア言語）フォントだけ**をメイリオへ一括統一します
  （欧文フォントは変更しません）。対象は次の3箇所です。
  1. **テーマのフォント**（`ThemeFontScheme`の`MajorFont`/`MinorFont`）
     — `+本文のフォント`/`+見出しのフォント`を参照している文字に影響
  2. **スライドマスター・スライドレイアウト上の全プレースホルダー**
  3. **全スライド上の既存シェイプ内の文字**
     （グループ化されたシェイプは再帰的に中まで辿ります）

  引数はなく、選択状態に関わらずプレゼンテーション全体が対象です。
  表・SmartArt等の特殊オブジェクトは対象外（`HasTextFrame`を持つ
  シェイプのみ処理）です。他のPowerPoint操作コマンドと同じくUndo境界を
  必ず打つため、Ctrl+Z一回で元に戻せます
- `iro`は、資料の配色を「深緑×レンガ色×グレー」の対比配色に統一
  したいという用途向けに、以下の3ステップを順番に行います。

  1. **既存スライドの独自色化**: 全スライド上の全シェイプ（グループ内も
     再帰的に含む）の塗りつぶし色・枠線色・文字色のうち、テーマカラーを
     参照しているものを検出し、**現在の見た目のままRGB固定値に変換**
     します。これにより、次のステップでテーマカラーを変更しても
     既存スライドの見た目は変わりません
  2. **テーマカラーの変更**: アクセント1〜6を新配色（`#1E7145`の深緑、
     `#A8493D`のレンガ色、`#808080`のグレーとそれぞれの薄いバリエー
     ション）に変更します。テキスト/背景色・ハイパーリンク色は変更しません
  3. **既定書式の一時適用**: シェイプ（黒枠1pt・メイリオ・折り返しあり・
     オートフィットなし）、矢印（黒・2pt）、テキストボックス（メイリオ
     12pt・黒・折り返しなし・「枠に合わせて図形のサイズを変更する」）の
     サンプル図形を作成して書式を適用し、PowerPointの「既定の図形として
     設定」をCommandBars経由で試みます。**この既定値はファイルに保存
     されず、PowerPointを再起動すると失われる一時的な状態です。**
     失敗しても致命的エラーにはせず、手動設定を促す警告を出して
     正常終了します

  引数はなく、選択状態に関わらずプレゼンテーション全体が対象です。
  独自色化・テーマカラー変更にはUndo境界を打つため、Ctrl+Zで戻せます
  （既定書式の一時適用はファイルに保存されない状態のためUndo対象外です）
- `tsunagu`は、コネクタをマウスでシェイプの接続点（●印）にドラッグして
  合わせる煩わしさを解消します。`tbl`と同じく**選択状態から動作を自動判定**
  します。

  | 選択内容 | 動作 |
  | --- | --- |
  | コネクタを1つ以上＋シェイプを2つ以上 | 各コネクタの両端を、選択中のシェイプの最寄り接続点へ接続する |
  | コネクタなし＋シェイプちょうど2つ | 2つを繋ぐ直線コネクタ（黒・2pt）を新規作成する |

  - 接続点は**コネクタの端点座標から物理的に最も近いもの**を選ぶため、
    「この辺に繋ぎたい」というマウスで引いた位置の意図がそのまま反映されます
  - 吸着先の候補は**選択に含まれるシェイプのみ**です（スライド上の全シェイプを
    候補にすると、意図しない遠くのシェイプへ吸着する事故が起きるため）
  - 既に接続済みのコネクタも、現在の見た目の端点位置を基準に繋ぎ直します
  - **吸着モードではコネクタの線の色・太さを一切変更しません**
    （新規作成時のみ黒・2ptを設定します）
  - コネクタの両端が同じシェイプに最も近い場合は、接続先を判断できないため
    エラーになります
  - 他のPowerPoint操作コマンドと同じくUndo境界を打つため、Ctrl+Zで戻せます

各サブコマンドは `tools <name>` の他に、単体の実行ファイルとしても呼び出せます
（`pip install -e .` でインストールされる `touka.exe` / `denoise.exe` / `kukiri.exe` / `cwc.exe` /
`clipmd.exe` / `mdtsv.exe` / `clipview.exe` / `clipfmt.exe` / `vv.exe` /
`profiler.exe` / `lsdir.exe` / `outline.exe` / `ikko.exe` / `mokuji.exe` /
`tbl.exe` / `seiretsu.exe` / `nagasa.exe` / `umekomi.exe` / `merioall.exe` /
`iro.exe` / `tsunagu.exe` / `shortcut.exe` など）。

### 出力先のデフォルト（`-o`省略時）

入力パターンごとに、出力の扱いが異なります（`cwc`は入力がテキストになりますが同じ規約に従います）。

| 入力パターン | デフォルトの挙動 |
|---|---|
| ファイルパス指定 | 元ファイルと同じ場所に `{元のファイル名}_<コマンド名>.png` を保存 |
| クリップボードのファイルオブジェクト（Explorerでコピーした実ファイル） | OS一時ディレクトリ（`%TEMP%`）に `{元のファイル名}_<コマンド名>.png` を保存し、そのファイルをクリップボードにコピー（Ctrl+Vで貼り付け可能な状態にする） |
| クリップボードの画像データ（画像ソフトの「コピー」等、元ファイルなし） | ファイルには保存せず、処理後の画像データをそのままクリップボードにコピー（Ctrl+Vで貼り付け可能な状態にする） |

```powershell
denoise C:\path\to\photo.jpg
touka C:\path\to\photo.jpg
kukiri C:\path\to\illustration.jpg
```

## 起動が遅いとき（社内EDR/DLP製品によるスキャン対策）

社内配布のEDR/DLP製品の実行時スキャンにより、各`*.exe`は**初回実行時のみ**
起動が遅くなることがある（同じコマンドの2回目以降は速い）。導入直後などに
まとめて解消しておきたい場合は、以下を1回実行すると全コマンドのexeを
順番に起動してスキャンを済ませておける。

```powershell
python scripts/warmup_exe.py
```

`shortcut.exe`は引数なし実行で実際にスタートメニューへショートカットを
作成する（意図した副作用）。根本的な解決にはIT部門へのアローリスト登録が
必要な場合がある（該当exeの一覧は`tools shortcut`実行時、または上記スクリプトの
出力で確認できる）。

## テスト・lint

```bash
pytest
ruff check .
mypy src
```

## バージョン管理

[Semantic Versioning](https://semver.org/lang/ja/)（`MAJOR.MINOR.PATCH`）を採用する。

- バージョン番号は `pyproject.toml` の `version` で管理する
- **コミットのたびにパッチ番号（`PATCH`）を+1する運用**とする
  （例: `0.1.0` → `0.1.1`）。MINOR/MAJORの繰り上げは、破壊的変更や
  まとまった機能追加の際に人間が明示的に指示した場合のみ行う
- コミットのたびに以下を同時に行う
  1. `pyproject.toml` の `version` のパッチ番号を+1する
  2. `CHANGELOG.md` に変更内容を追記する
  3. コミット後、`git tag -a vX.Y.Z -m "..."` でタグを打つ
     （`pyproject.toml`のversionとgit tagは常に一致させる）
- 変更履歴は [CHANGELOG.md](CHANGELOG.md) を参照

## ライセンス

MIT License（[LICENSE](LICENSE)を参照）。

依存ライブラリはMIT/BSD/Apache 2.0などの寛容型ライセンスのみで構成しており、
本プロジェクトをMITとすること自体に支障はない。ただし`opencv-python-headless`・
`janome`・`tokenizers`はApache 2.0であり、**exe化して配布する場合**は
同梱ライブラリとしてその旨・著作権表示を配布物に添付することが望ましい
（PyPI経由でインストールして使うだけの開発環境では、各パッケージの
`dist-info`がライセンス表示を担うため追加対応は不要）。
