# Changelog

このプロジェクトの変更履歴。[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)
の形式に、[Semantic Versioning](https://semver.org/lang/ja/)を採用する。

## [Unreleased]

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

[Unreleased]: https://github.com/kirin123kirin/workpytools/compare/v0.1.9...HEAD
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
