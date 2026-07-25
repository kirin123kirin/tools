# tools

さまざまな処理をコマンドとして追加していくためのPythonプロジェクト。

**動作環境: Windows 11 専用**（クリップボード連携等はWindows APIに依存するため、他OSは考慮しない）

## 構成

```
tools/
├── pyproject.toml          # 依存関係・lint(ruff)・型チェック(mypy)・pytest設定
├── src/
│   └── tools/
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
│           └── clipfmt.py          # クリップボードのMarkdown整形
├── tests/                  # src/tools と同じ階層構造でテストを配置
├── configs/                # 処理ごとの設定ファイル(TOML)を置く場所（common/config.py で読み込み）
├── scripts/                # 動作確認用の使い捨てスクリプト（.gitignore対象。
│                            # ただし gen_help.py と pre-commit は例外的にバージョン管理する）
└── tmp/                    # 一時ファイル・実行結果ダンプなど（.gitignore対象）
```

## 新しい処理の追加方法

1. `src/tools/processing/` に新しいモジュールを作成する
2. `Processor` を継承したクラスを定義し、`name`（サブコマンド名）と
   `add_arguments` / `run` を実装する（`touka.py` や `denoise.py` を参照）
3. それだけで`tools <name>`としてCLIに自動登録される（`cli.py` の編集は不要）
4. **単体実行用のエントリーポイントも追加する**: `pyproject.toml` の
   `[project.scripts]` に `name`（`Processor.name`と同じ文字列）を
   `tools.cli:run_as_subcommand` として登録する。これにより
   `pip install -e .` 後、`tools <name> ...` に加えて `<name> ...`
   （Windowsでは `<name>.exe ...`）としても直接実行できるようになる。

```toml
[project.scripts]
my-process = "tools.cli:run_as_subcommand"
```

```python
# src/tools/processing/my_process.py
from tools.processing.base import Processor


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

`doc/help.html`（全コマンドのヘルプ一覧、`help`/`tool-h.exe`が開くページ）は
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

# クリップボードのMarkdownを整形（表の桁揃え、見出し統一、リスト記号統一など）
tools clipfmt

# 全コマンドのヘルプ一覧（doc/help.html）をブラウザで開く
tools help
# 単体実行ファイルはtool-h.exe（他コマンドと違いhelp.exeという名前ではない）
tool-h
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
`%LOCALAPPDATA%\tools\models\` にキャッシュされ、2回目以降は再ダウンロードしません。

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

`clipview`のみ、プレビュー用に `%TEMP%\tools_clipview_preview.html` を固定名で生成します
（毎回上書きするためファイルは増殖しません）。

各サブコマンドは `tools <name>` の他に、単体の実行ファイルとしても呼び出せます
（`pip install -e .` でインストールされる `touka.exe` / `denoise.exe` / `kukiri.exe` / `cwc.exe` /
`clipmd.exe` / `mdtsv.exe` / `clipview.exe` / `clipfmt.exe` など）。

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

## テスト・lint

```bash
pytest
ruff check .
mypy src
```
