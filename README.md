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
│           └── kukiri.py           # JPEG輪郭滲み除去・境界強調ツール（バイラテラル+アンシャープマスク）
├── tests/                  # src/tools と同じ階層構造でテストを配置
├── configs/                # 処理ごとの設定ファイル(TOML)を置く場所（common/config.py で読み込み）
├── scripts/                # 動作確認用の使い捨てスクリプト（.gitignore対象）
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
```

`touka` は初回実行時に背景除去モデル（U2Net, rembg）をインターネットからダウンロードします。
`denoise`・`kukiri`はOpenCVの古典的アルゴリズムのみを使用し、モデルダウンロードは行いません（外部通信なし）。

`kukiri`は`denoise`とは異なり、ランダムノイズではなくJPEG圧縮特有の輪郭のにじみ・リンギングを
対象にしています。バイラテラルフィルタ（輪郭を保ったまま平滑化）→アンシャープマスク（輪郭強調）
の順に処理し、フラットデザインのイラストなど「境界をくっきりさせたい」用途向けです。

各サブコマンドは `tools <name>` の他に、単体の実行ファイルとしても呼び出せます
（`pip install -e .` でインストールされる `touka.exe` / `denoise.exe` / `kukiri.exe` など）。

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
