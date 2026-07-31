# Changelog

このプロジェクトの変更履歴。[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)
の形式に、[Semantic Versioning](https://semver.org/lang/ja/)を採用する。

## [Unreleased]

## [0.1.27] - 2026-07-31

### Added

- `bunkatsu` — PowerPointで選択中の画像シェイプを、OpenCVのwatershed
  アルゴリズム（マーカーベース領域分割、完全自動）で物体ごとに分割し、
  個別の透過PNGとして元の位置・スケールに再配置する新コマンド。
  - アルファチャンネル（透過部分）を背景、不透明部分を前景として、
    距離変換 + `cv2.watershed`で接触・近接した複数物体を分離する
    （`src/workpytools/common/watershed.py`に切り出し）
  - `--distance-ratio`（既定0.7）で分割の厳しさを調整可能
  - `--dry-run`で検出領域数のみ確認できる
  - 画像シェイプをちょうど1つ選択して実行する必要がある
    （`msoPicture`/`msoLinkedPicture`のみ対象）
  - 検出領域が1つ以下の場合は何も変更しない
  - 他のPowerPoint操作コマンドと同じくUndo境界を打つため、
    Ctrl+Zひと押しで分割前の元画像に戻せる

## [0.1.26] - 2026-07-31

### Added

- `clipview`がクリップボードの画像データ（`touka`の出力等）にも対応。
  HTML/Markdown/SVGのいずれもクリップボードにない場合、画像データを
  市松模様の背景に重ねてブラウザでプレビューするようにした
  （透過部分が黒く塗りつぶされていないかを目視確認しやすくするため）

## [0.1.25] - 2026-07-31

### Fixed

- `copy_image_to_clipboard`（`touka`等が画像データをクリップボードへ直接
  コピーする際に使う共通処理）が、透過PNG画像を`CF_DIB`（アルファ非対応）
  形式のみで載せていたため、Pillowの`RGBA→RGB`変換により透過部分が
  黒く塗りつぶされてしまう不具合を修正。あわせて`CF_DIBV5`単体では
  PowerPointへの貼り付けが無反応になる問題も確認されたため、
  PowerPoint/Word/ブラウザが優先的に読みに行く**"PNG"カスタムクリップ
  ボードフォーマット**（生PNGバイト列）を筆頭に、`CF_DIBV5`（アルファ対応
  DIB）、`CF_DIB`（アルファ非対応、白背景合成）の3形式を同時に提供する
  ように変更した

## [0.1.24] - 2026-07-31

### Added

- `scripts/warmup_exe.py` — 全コマンドのexeを1回ずつ起動し、社内EDR/DLP製品による
  初回スキャンを事前に済ませておくためのウォームアップ用スクリプト
  （開発用ユーティリティ、`tools`のサブコマンドではない）

### Fixed

- `tools shortcut`（`--remove`なしの通常実行）が、リネーム・削除されたコマンドの
  古い`.lnk`をスタートメニューのフォルダに残したままにしていた不具合を修正。
  ショートカット作成前に対象フォルダの既存`.lnk`を一旦すべて削除するようにした
  （`pip install -U`後に`tools shortcut`を再実行した際のゴミ掃除漏れ対策）

### Docs

- README: `pip uninstall`にはアンインストール時フックが存在しないため、
  ショートカットは自動削除されない旨と、アンインストール前に
  `tools shortcut --remove` を実行する手順を明記

### Changed

- 前バージョンで追加したコマンド名`tsunagi`を`tsunagu`にリネーム
  （コネクタを最寄りの接続点へ吸着させるコマンド）

## [0.1.22] - 2026-07-29

### Added

- `tsunagu` — コネクタの端点を最寄りのシェイプ接続点へ吸着させる新コマンド。
  マウスでコネクタをシェイプの接続点にドラッグして合わせる煩わしさを解消する。
  `tbl`と同じく選択状態から動作を自動判定する。
  - コネクタ1つ以上＋シェイプ2つ以上: 各コネクタの両端を、選択中の
    シェイプの最寄り接続点へ`BeginConnect`/`EndConnect`する
  - コネクタなし＋シェイプちょうど2つ: 互いに最も近い接続点同士を繋ぐ
    直線コネクタ（黒・2pt）を新規作成する
  - 接続点はコネクタ端点からの距離で選ぶため、マウスで引いた位置の意図が
    そのまま反映される。吸着先候補は選択に含まれるシェイプのみに限定し、
    意図しない遠くのシェイプへの吸着を防ぐ
  - 接続点の座標を返すCOM APIが存在しないため、外接矩形から算出する
    （4サイトは上・左・下・右、それ以外は外接楕円上に等分配置して近似）。
    ロジックは`common/connector_sites.py`に純粋関数として切り出した

## [0.1.21] - 2026-07-29

### Fixed

- `mdtsv`: `v0.1.19`で行った区切り行誤検出の修正自体が、別のデグレを
  引き起こしていたバグを再修正。「次の行が区切り行の形式かどうか」だけで
  フラットに判定する実装だったため、データ行の直後に区切り行と同じ見た目
  の行（例: `| - | - |`）が来ると、そのデータ行が誤って消えてしまっていた。
  入力を空行で表のブロックに分割し、各ブロック内の2行目だけを区切り行の
  判定対象にする方式に変更し、この種の位置依存の誤検出を構造的に防いだ

### Changed

- `common/table_shapes.py`: `estimate_grid`のdocstringに、
  `_index_of_cluster`が送出しうる`ValueError`（`v0.1.19`で追加した
  防御的チェック）が実際には発生し得ない理由を明記した

## [0.1.20] - 2026-07-29

### Changed

- `CLAUDE.md`に「PyPI配布後のディレクトリ構成を必ず考慮する」セクションを
  追加。`help.html`未同梱バグ（`v0.1.18`）の教訓として、同梱データは
  `importlib.resources`経由で参照すること、`sys.executable`基準のパス解決は
  複数のインストール形態を考慮すること、editable installだけでなく実際に
  wheelをビルドして別venvで動作確認することを明文化した

## [0.1.19] - 2026-07-29

### Fixed

- `mokuji`: `for shape in slide.Shapes:`というCOMコレクションの直接
  イテレーションを、他のPowerPoint操作コマンドと同じ`Count`+`Item(i)`
  方式に修正。レイトバインディングでは動作しない可能性があった
  （テスト側の`MagicMock.__iter__`モックも実機挙動に合わせて修正）
- `mdtsv`: `markdown_table_to_tsv`が、データセルの値がハイフンや
  コロンのみ（例: `| - | - |`）の行を区切り行と誤認してデータごと
  消してしまうバグを修正。区切り行は各表の2行目にしか現れないという
  Markdown表の制約を利用し、直後の行が区切り行の形式である行だけを
  ヘッダー行とみなすように変更した
- `cwc`: ユーザー辞書・同義語辞書の解決で、設定ファイルや`--user-dict`/
  `--synonym-dict`に指定されたパスが存在しない場合、同梱辞書へ
  フォールバックせず辞書なしになっていたバグを修正。各段は「指定パスが
  実在すれば採用、しなければ前段の値を維持する」方式に変更した
- `common/table_shapes.py`: `_index_of_cluster`が、許容誤差を超えて
  離れた値でも常に最も近いクラスタへ強制的に割り当てていた設計上の
  問題に対し、tolerance超過時は例外を送出する防御的チェックを追加
  （`estimate_grid`の通常の呼び出しでは発生しないが、将来の誤用に
  備えた回帰防止）

## [0.1.18] - 2026-07-29

### Fixed

- `help`/`toolh`: PyPI経由で`pip install`した環境では`doc/help.html`
  （リポジトリ直下のパス）が存在せず、`toolh`実行時に必ずエラーになる
  バグを修正。`help.html`をパッケージデータ（`workpytools/data/help.html`）
  として同梱し、`importlib.resources`経由で参照するように変更した。
  `scripts/gen_help.py`は`doc/help.html`（開発用）と
  `src/workpytools/data/help.html`（配布用）の両方を生成する

## [0.1.17] - 2026-07-29

### Added

- `iro` — 既存スライドを独自色化した上でテーマカラーと既定図形の書式を
  統一する新コマンド。以下の3ステップを順に行う。
  1. 全スライド上の全シェイプ（グループ内を再帰的に含む）の塗りつぶし・
     枠線・文字色のうち、テーマカラーを参照しているものを現在の見た目の
     ままRGB固定値に変換する（独自色化）
  2. テーマのアクセント1〜6を新配色（深緑`#1E7145`・レンガ色`#A8493D`・
     グレー`#808080`とそれぞれの薄いバリエーション）に変更する
  3. シェイプ・矢印・テキストボックスのサンプル図形に指定書式
     （線の色・太さ、フォント、オートフィット、折り返し）を適用し、
     CommandBars経由で「既定の図形として設定」を試みる
     （PowerPointを再起動すると失われる一時的な状態。失敗しても
     致命的エラーにはせず警告のみで正常終了する）

## [0.1.16] - 2026-07-28

### Fixed

- `merioall`: テーマ・スライドマスター・スライドの各COMコレクション
  （`Designs`/`Slides`/`CustomLayouts`）を`for x in collection:`という
  直接イテレーションで処理していたのを、他のPowerPoint操作コマンドと
  同じ`Count`+`Item(i)`方式に統一。レイトバインディング
  （`GetActiveObject`経由）では直接イテレーションが動作しない
  リスクがあったため

## [0.1.15] - 2026-07-28

### Changed

- 前バージョンで追加したコマンド名`mfont`を`merioall`にリネーム
  （PowerPoint内の和文フォントをメイリオに一括統一するコマンド）

## [0.1.14] - 2026-07-28

### Added

- `merioall` — テーマ・スライドマスター（レイアウト含む）・全スライド上の
  既存シェイプ（グループ内を再帰的に含む）の和文フォントをメイリオに
  一括統一する。SVGを図形に変換した際にテキストボックスのフォントが
  遊ゴシックのまま残る問題への対処。欧文フォントは変更しない。表・
  SmartArt等は対象外

## [0.1.13] - 2026-07-28

### Added

- `doc/help.html`のサイドバー幅を初回表示時に自動計算するようにした
  （最も長いコマンド名+要約が折り返さずに収まる幅を実測、200〜800pxの
  範囲でクランプ）。ドラッグでの手動調整・幅の記憶は従来通り機能し、
  一度手動調整すると次回以降はその値を優先する

## [0.1.12] - 2026-07-28

### Fixed

- `doc/help.html`: コピーボタンが`navigator.clipboard.writeText()`失敗時に
  無反応になる問題を修正。`execCommand("copy")`によるフォールバックを追加し、
  成功/失敗をボタンの見た目でも区別するようにした
- `shortcut`: `_all_standalone_names()`内の冗長かつ意図の分かりにくい
  `names.update(_ENTRY_POINT_ALIASES)`を削除（実害はなかったが、
  `standalone_entry_point_name()`が既に別名変換を行っているため不要だった）

## [0.1.11] - 2026-07-28

### Added

- `doc/help.html`にコマンド名をクリップボードへコピーするボタンを追加
  （サイドバーの各行と、本文の「単体実行」表示の両方）。ターミナルに
  exe名を目視して手入力する手間を減らすため。Clipboard APIのみを使い、
  何のプロセスも起動しない
- `shortcut` — 全コマンドの単体実行ファイルへのスタートメニューショートカット
  を作成/削除する（`%APPDATA%\Microsoft\Windows\Start Menu\Programs\workpytools\`
  にショートカットファイルを配置するのみで、レジストリやスケジュールタスク
  への登録は行わない）。アイコンは自前描画で新規同梱（`data/app.ico`）

## [0.1.10] - 2026-07-28

### Changed

- `doc/help.html`のサイドバーの行間を詰め、コマンド名と要約を1行に
  横並び表示するように変更
- サイドバーの説明文を、各コマンドのフル説明文ではなく専用の短い要約
  （10文字前後）に変更し、はみ出す場合は末尾を省略表示にした

## [0.1.9] - 2026-07-27

### Fixed

- `doc/help.html`: サイドバーのカテゴリ見出しに適用していた
  `text-transform: uppercase`が、同じ`<li>`内の子要素であるコマンド名
  リンクにも継承され、コマンド名が全て大文字表示になっていたバグを修正
  （カテゴリラベルを専用の`<span>`に分離）

### Changed

- `doc/help.html`のサイドバー幅を18remから36remに拡大
- サイドバーとメイン領域の境界をマウスドラッグでリサイズできるようにし、
  幅は`localStorage`に保存して次回起動時も復元する
  （外部通信・外部ライブラリは使わない、素のJavaScriptのみ）

## [0.1.8] - 2026-07-27

### Changed

- `doc/help.html`のレイアウトを左サイドバー固定のTOC構成に変更
  （`position: sticky`でスクロールに追従、TOC項目はexe名を省略し
  コマンド名と要約のみを表示。画面幅が狭い場合は従来の縦積みに戻る）

## [0.1.7] - 2026-07-27

### Changed

- `doc/help.html`のコマンド一覧を、名前のアルファベット順ではなく
  処理内容によるカテゴリ順（画像処理／テキスト集計／クリップボード処理／
  表形式データ／PowerPoint操作／その他）でグループ化して表示するように変更
  （目次・本文の両方にカテゴリ見出しを追加）

## [0.1.6] - 2026-07-27

### Fixed

- `umekomi`: 1つのテキストボックスの中心が複数のshapeの矩形と重なる場合に
  同じテキストボックスが2つのshapeへ二重に埋め込まれ、2回目の削除処理で
  COMエラーになるバグを修正（面積が最も小さいshapeに一意に割り当てるよう変更）
- `umekomi`: `HasTextFrame`が`False`のshape（コネクタ等）が埋め込み先候補に
  含まれ、埋め込み処理中に例外になる可能性があったため、候補から除外するよう修正

## [0.1.5] - 2026-07-27

### Added

- `umekomi` — PowerPointのシェイプの上に重ねて配置されたテキストボックスを
  シェイプ本体に埋め込む（テキストボックスの中心座標がシェイプの矩形内に
  入っている組み合わせを対象とし、複数重なる場合は上下位置順に結合）

## [0.1.4] - 2026-07-27

### Changed

- GitHubリポジトリ名を`tools`から`workpytools`にリネーム
  （`git remote`のURL、CHANGELOG内の比較リンクを追従）

## [0.1.3] - 2026-07-27

### Changed

- PyPI公開に向けて、パッケージ名・インポート名を`tools`から`workpytools`に変更
  （`src/tools/` → `src/workpytools/`、`import tools` → `import workpytools`）
- 設定ファイル・キャッシュ・プレビューファイルの保存先を`%APPDATA%\workpytools\`・
  `%LOCALAPPDATA%\workpytools\`・`%TEMP%\workpytools_*`に変更
  （旧`%APPDATA%\tools\`等からのデータ移行は行わない）

## [0.1.2] - 2026-07-27

### Added

- `doc/help.html`の各コマンドに、入出力の変化を示すbefore/after図（SVG自前描画）を追加
- `doc/help.html`の各コマンドに、単体実行ファイル名（`xxx.exe`）を明記
  （`help`コマンドのみ`toolh.exe`という別名になるため目次・本文の両方に表示）

## [0.1.1] - 2026-07-27

### Added

- `tbl` — PowerPointの表とシェイプ群を相互変換（表分解/表合成/行分割）
- `seiretsu` — PowerPointのシェイプを表に変換せず格子状に整列
- `nagasa` — PowerPointのシェイプの幅・高さを最大値に統一

### Changed

- コミットのたびにパッチバージョンを自動でインクリメントする運用を
  `CLAUDE.md`・`README.md`に明記

## [0.1.0] - 2026-07-26

初回バージョンタグ。以下のコマンドを実装済み。

### Added

- `touka` — 画像背景透過ツール
- `denoise` — 画像ノイズ除去ツール（OpenCV Non-local Means）
- `kukiri` — JPEG輪郭滲み除去・境界強調ツール
- `cwc` — テキストからワードクラウド画像を生成
- `clipmd` — クリップボードのMarkdown↔リッチテキスト変換
- `mdtsv` — クリップボードのMarkdownの表↔TSV変換
- `clipview` — クリップボードのMarkdown/HTML/SVGをブラウザでプレビュー（Mermaid対応含む）
- `clipfmt` — クリップボードのMarkdown整形
- `vv` — 定型プロンプトをクリップボードにコピー
- `profiler` — 表形式データの列プロファイリング
- `lsdir` — フォルダ配下をExcelで集計できる表形式で一覧化
- `outline` — クリップボードのアウトラインからPowerPointにスライドを追加
- `ikko` — PowerPointのバラバラなテキストボックスを1つに合体
- `mokuji` — PowerPointの全スライドタイトルを一覧化してクリップボードへ
- `help`（`toolh`） — 全コマンドのヘルプ一覧をブラウザで開く
- MIT License

[Unreleased]: https://github.com/kirin123kirin/workpytools/compare/v0.1.23...HEAD
[0.1.23]: https://github.com/kirin123kirin/workpytools/compare/v0.1.22...v0.1.23
[0.1.22]: https://github.com/kirin123kirin/workpytools/compare/v0.1.21...v0.1.22
[0.1.21]: https://github.com/kirin123kirin/workpytools/compare/v0.1.20...v0.1.21
[0.1.20]: https://github.com/kirin123kirin/workpytools/compare/v0.1.19...v0.1.20
[0.1.19]: https://github.com/kirin123kirin/workpytools/compare/v0.1.18...v0.1.19
[0.1.18]: https://github.com/kirin123kirin/workpytools/compare/v0.1.17...v0.1.18
[0.1.17]: https://github.com/kirin123kirin/workpytools/compare/v0.1.16...v0.1.17
[0.1.16]: https://github.com/kirin123kirin/workpytools/compare/v0.1.15...v0.1.16
[0.1.15]: https://github.com/kirin123kirin/workpytools/compare/v0.1.14...v0.1.15
[0.1.14]: https://github.com/kirin123kirin/workpytools/compare/v0.1.13...v0.1.14
[0.1.13]: https://github.com/kirin123kirin/workpytools/compare/v0.1.12...v0.1.13
[0.1.12]: https://github.com/kirin123kirin/workpytools/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/kirin123kirin/workpytools/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/kirin123kirin/workpytools/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/kirin123kirin/workpytools/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/kirin123kirin/workpytools/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/kirin123kirin/workpytools/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/kirin123kirin/workpytools/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/kirin123kirin/workpytools/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/kirin123kirin/workpytools/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/kirin123kirin/workpytools/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/kirin123kirin/workpytools/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/kirin123kirin/workpytools/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kirin123kirin/workpytools/releases/tag/v0.1.0
