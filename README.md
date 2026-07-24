# tools

さまざまな処理をコマンドとして追加していくためのPythonプロジェクト。

## 構成

```
tools/
├── pyproject.toml          # 依存関係・lint(ruff)・型チェック(mypy)・pytest設定
├── src/
│   └── tools/
│       ├── cli.py          # エントリポイント。processing/配下を自動探索してサブコマンド化
│       ├── common/         # 処理間で使い回す共通機能
│       │   ├── logging.py
│       │   └── config.py
│       └── processing/     # 個々の処理。1ファイル=1処理
│           ├── base.py     # Processor基底クラス
│           └── example.py  # サンプル実装（新規追加時のテンプレート）
├── tests/                  # src/tools と同じ階層構造でテストを配置
└── configs/                # 処理ごとの設定ファイル(TOML)を置く場所
```

## 新しい処理の追加方法

1. `src/tools/processing/` に新しいモジュールを作成する
2. `Processor` を継承したクラスを定義し、`name`（サブコマンド名）と
   `add_arguments` / `run` を実装する（`example.py` を参照）
3. それだけでCLIに自動登録される（`cli.py` の編集は不要）

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

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 実行

```bash
tools example "hello"
# または
python -m tools.cli example "hello"
```

## テスト・lint

```bash
pytest
ruff check .
mypy src
```
