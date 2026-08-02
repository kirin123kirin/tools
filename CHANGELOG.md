# Changelog

このプロジェクトの変更履歴。[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)
の形式に、[Semantic Versioning](https://semver.org/lang/ja/)を採用する。

## [Unreleased]

## [0.1.38] - 2026-08-02

### Changed

- `iro`のアクセントカラー配色を変更。アクセント1を`#1E7145`（深緑）から
  `#00B258`（緑）へ、アクセント3を`#A8493D`（レンガ色）から`#CC0033`
  （レンガ色）へ変更し、それぞれの薄めたバリエーションであるアクセント2・4も
  新しい基準色に合わせて再計算（白方向に約30%ブレンド、
  `#4DC98A`/`#DB4D70`）した。アクセント5・6（グレー系）は変更なし

## [0.1.37] - 2026-08-02

### Fixed

- `iro`が、スライド上に表（msoTable）シェイプが存在すると
  「PowerPointの操作中にエラーが発生しました」（指定された値は境界を
  超えています）で必ず失敗していた不具合を修正。表シェイプは`.Fill`/
  `.Line`プロパティへのアクセス自体がCOMレベルの例外
  （`pywintypes.com_error`、`AttributeError`ではない）になることが実機で
  判明した。`getattr()`の既定値フォールバックは`AttributeError`しか
  吸収しないため、それ以外の例外も含めて広く捕捉し「読み取れない
  シェイプは独自色化の対象外としてスキップする」ように修正した

### Changed

- `Processor`基底クラス、`help`コマンドのヘルプ文言のdocstring・説明文が
  リポジトリ直下のパス（`tools/processing/`、`doc/help.html`）を誤って
  参照していたため、実際の配置（`src/workpytools/processing/`、
  パッケージデータ経由）に合わせて修正
- 未使用となっていた`get_clipboard_html_raw()`（`common/clipboard.py`）を削除

### Verified

- `iro`/`meirio`以外の全PowerPoint操作コマンド（`outline`/`ikko`/
  `mokuji`/`tbl`/`seiretsu`/`nagasa`/`umekomi`/`tsunagu`/`bunkatsu`）を
  実機で横断的に再検証し、同種の不具合がないことを確認した

## [0.1.36] - 2026-08-02

### Changed

- コマンド名`merioall`を`meirio`にリネーム
  （テーマ・マスター・全スライドの和文フォントをメイリオに統一するコマンド）

### Fixed

- `meirio`（旧`merioall`）が、`ThemeFontScheme.MajorFont.NameFarEast`/
  `MinorFont.NameFarEast`への代入で必ず
  `Property '<unknown>.NameFarEast' can not be set`エラーになっていた
  不具合を修正。実機調査の結果、`ThemeFontScheme.MajorFont`/`MinorFont`は
  単一の`Font`オブジェクトではなく3要素のコレクション
  （1=Latin, 2=EastAsian, 3=ComplexScript）であり、pywin32のダイナミック
  ディスパッチ経由では`NameFarEast`という名前のメンバー自体が存在しない
  ことが判明した。`MajorFont.Item(2).Name = ...`という、コレクション
  経由でのアクセスに変更して解決した（テストのモックも実装に合わせて修正）。
  新規プレゼンテーションに限らず、`meirio`は常にこのエラーで失敗していた

## [0.1.35] - 2026-08-02

### Fixed

- `iro`が、新規作成直後のPowerPointプレゼンテーションで実行すると
  「PowerPointの操作中にエラーが発生しました」で必ず失敗していた
  不具合を修正。`ThemeColorScheme.Item(index)`という明示メソッド
  呼び出しが、pywin32のダイナミックディスパッチ経由では型情報が
  実行時に完全解決されず`AttributeError`になる実機特有の挙動が
  原因だった。COMの既定メンバー呼び出し構文`ThemeColorScheme(index)`
  に変更して解決した（テストのモックも実装に合わせて修正）
- `iro`実行時のログを強化し、独自色化・テーマカラー変更の各ステップの
  開始・完了と、失敗時の例外の型名・詳細（repr）を出力するようにした

## [0.1.34] - 2026-08-02

### Added

- `vv`の説明文に、プロンプトファイルの配置先
  （`%APPDATA%\workpytools\vv\`）を明記。`tools --help`のサブコマンド
  一覧、`tools vv --help`、`help.html`のいずれにも反映される

### Fixed

- `tools --help`が、`%APPDATA%`のように`%`を含む`help`文字列を持つ
  サブコマンドが存在すると`ValueError`でクラッシュする不具合を修正。
  `add_subparsers().add_parser(..., help=...)`のhelp引数はargparseの
  `%`展開（`%(default)s`等）の対象になるため、サブコマンド一覧表示の
  ためだけに`%`を`%%`へエスケープするようにした
  （`description=`等の他の用途では`proc.help`を未加工のまま使うため、
  影響範囲はサブコマンド一覧のみ）

## [0.1.33] - 2026-08-02

### Docs

- README: 実装済みだが記載が漏れていたオプションを追記
  （設計・実装・ドキュメントの整合性を全面点検した結果、判明した記載漏れ）
  - `cwc`: `--encoding`・`--synonym-dict`/`--no-synonym-dict`・
    `--user-dict`/`--no-user-dict`・`--stopwords`/`--stopwords-file`・
    `--no-default-stopwords`・`--font`・`--similar-threshold`・
    `--similar-model`・`--similar-max-length`
  - `ikko`: `--left-tolerance`・`--line-step-min`・`--line-step-max`
  - `lsdir`: `--exclude`・`--include-temp`・`--encoding`
  - `profiler`: `--sep`・`--header`・`--no-header`・`--top`・
    `--empty-values`・`--no-default-empty-values`
  - `clipview`: `--markdown`・`--html`・`--svg`・`--no-open`
  - `bunkatsu`: `--background-color-distance`

## [0.1.32] - 2026-08-02

### Docs

- README: 全コマンド共通でショートオプションが利用可能であることを
  「実行」セクション冒頭に一行注記（v0.1.31でショートオプションを
  全コマンドに追加した際、README本文のコマンド例に未反映だった記載漏れの是正）

## [0.1.31] - 2026-08-02

### Added

- 全コマンドの`--`オプションにショートオプションを付与（`-h`/`--help`と
  既存の`-o`/`-w`を除く全てが対象）。フラグ・値指定オプションを問わず、
  各コマンド内で衝突しない1文字を割り当てた
  （例: `touka -a`は`--alpha-matting`、`cwc -w`は`--wakachi`など）

## [0.1.30] - 2026-08-02

### Added

- `touka`にrembgのパラメータ調整用オプションを追加。
  - `--alpha-matting`（アルファマッティング有効化、髪の毛など細かい輪郭の
    透過精度を上げる）と、それに付随する`--alpha-matting-foreground-threshold`
    ・`--alpha-matting-background-threshold`・`--alpha-matting-erode-size`
  - `--bgcolor R G B A`（背景を透過ではなく指定色で塗りつぶす）
  - `--only-mask`（前景/背景の二値マスク画像のみを出力）
  - `--post-process-mask`（マスクのノイズ除去・穴埋め後処理）

## [0.1.29] - 2026-08-01

### Fixed

- `bunkatsu`の実機PowerPoint検証で見つかった複数の不具合を修正。
  - **不透過画像が分割対象にできない**: `common/watershed.py`が、
    アルファチャンネルなし（PowerPointの通常の画像シェイプを
    `shape.Export`した結果は不透過PNGになる）の画像を分割対象にできず、
    常に「分割できる領域が見つかりませんでした」となっていた
  - **位置・サイズのズレ**: `Shapes.AddPicture`をキーワード引数
    （`Left=..., Top=...`）で呼んでいたため、pywin32のレイトバインディング
    経由では名前付き引数が正しくCOMへ渡らず、無視されて既定値扱いになり
    意図しない位置・サイズに配置されていた。全て位置引数で呼ぶように修正
  - **エクスポート解像度の不整合**: `Shape.Export`のScaleWidth/ScaleHeightを
    省略すると、shape自身のサイズではなくスライド全体のサイズ・解像度
    設定を基準にピクセルサイズが決まってしまい、`shape.Width / 出力px`の
    比率計算の前提が崩れていた。ScaleWidth/ScaleHeightとExportMode
    (`ppScaleXY`)を明示指定し、出力ピクセルサイズをshape自身のサイズに
    正比例させるよう修正
  - **薄い塗り色での過分割**: 大津の二値化は画像全体を1つの閾値で2クラス
    化するため、背景の白に近い薄い塗り色（例: 薄ピンク）の図形は内部が
    背景側に誤分類され、「輪郭線」と「内部」が別領域として過分割されて
    いた。四隅サンプルとの色差（RGBユークリッド距離）で前景/背景を判定
    する方式に変更（新規`--background-color-distance`、既定20.0）。
    線のみ図形が消える副作用は`RETR_CCOMP`による輪郭内側の穴埋めを
    引き続き併用して解決
  - `--distance-ratio`の既定値を0.7から0.15に変更。元記事は接触した
    コインの分離を想定した値だが、PowerPointのシェイプは大半が既に
    分離されているため、より緩い既定値の方が実用上安定する

## [0.1.28] - 2026-08-01

### Fixed

- `bunkatsu`（`common/watershed.py`）が、不透過画像（アルファチャンネル
  なし、または実質すべて不透明な画像）を分割対象にできず、常に
  「分割できる領域が見つかりませんでした」となっていた不具合を修正。
  PowerPointの通常の画像シェイプ（アルファなしの写真・スクリーンショット等）
  を`shape.Export`した結果は不透過PNGになるため、実質的にすべてのケースで
  分割が失敗していた。
  - アルファチャンネルが実質すべて不透明な場合、大津の二値化に
    フォールバックするようにした（後の`0.1.29`で色差方式に置き換え）。
    二値化のどちらのクラスが背景かは大津の結果だけでは判定できないため、
    画像四隅のサンプルで多数派のクラスを背景とみなす方式にした
  - 塗りつぶしなし（線のみ）のPowerPoint図形は、線幅が細くモルフォロジー
    のオープニング処理で完全に消えてしまい分割対象にならなかったため、
    大津の二値化で得た輪郭を`findContours`+`drawContours`で塗りつぶして
    から後続処理に渡すようにした（線のみの図形も、輪郭の内側全体を
    1つの物体として検出・分割できるようになった）

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
