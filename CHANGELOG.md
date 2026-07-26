# Changelog

このプロジェクトの変更履歴。[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)
の形式に、[Semantic Versioning](https://semver.org/lang/ja/)を採用する。

## [Unreleased]

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

[Unreleased]: https://github.com/kirin123kirin/tools/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/kirin123kirin/tools/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/kirin123kirin/tools/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kirin123kirin/tools/releases/tag/v0.1.0
