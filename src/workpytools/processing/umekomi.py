from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass

from workpytools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_SELECTION_SHAPES = 2  # ppSelectionShapes
_MSO_TEXT_BOX = 17  # msoTextBox


@dataclass
class _TextBoxInfo:
    ref: object
    top: float
    text: str
    font_name: str | None
    font_size: float | None
    bold: bool | None
    color: int | None
    alignment: int | None


class UmekomiProcessor(Processor):
    """Embed overlapping text boxes into the shape underneath them, so the
    text can be edited directly on the shape instead of a separately
    positioned text box.
    """

    name = "umekomi"
    help = "shapeの上に重ねて配置されたテキストボックスをshapeに埋め込む"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="実際には変更せず、埋め込み対象になる組み合わせを表示するだけにする",
        )

    def run(self, args: argparse.Namespace) -> int:
        try:
            app = get_running_powerpoint()
        except PowerPointNotRunningError as exc:
            raise SystemExit(
                "PowerPointでプレゼンテーションを開いた状態で実行してください"
            ) from exc

        try:
            get_active_presentation(app)
        except NoActivePresentationError as exc:
            raise SystemExit(
                "PowerPointでプレゼンテーションを開いた状態で実行してください"
            ) from exc

        try:
            selection = app.ActiveWindow.Selection
        except Exception as exc:
            raise SystemExit(f"選択状態の取得中にエラーが発生しました: {exc}") from exc

        if selection.Type != _SELECTION_SHAPES:
            raise SystemExit("対象を選択してから実行してください（2つ以上選択が必要です）")

        shape_range = selection.ShapeRange
        shapes = [shape_range.Item(i) for i in range(1, shape_range.Count + 1)]

        if len(shapes) < 2:
            raise SystemExit("対象を選択してから実行してください（2つ以上選択が必要です）")

        text_boxes = [s for s in shapes if getattr(s, "Type", None) == _MSO_TEXT_BOX]
        hosts = [
            s
            for s in shapes
            if getattr(s, "Type", None) != _MSO_TEXT_BOX and getattr(s, "HasTextFrame", False)
        ]

        pairs = self._match_text_boxes_to_hosts(text_boxes, hosts)

        if not pairs:
            print("埋め込み対象になる組み合わせが見つかりませんでした")
            return 0

        if args.dry_run:
            self._print_dry_run(pairs)
            return 0

        try:
            app.StartNewUndoEntry()
            embedded_count = 0
            removed_count = 0
            for host, infos in pairs:
                self._embed(host, infos)
                embedded_count += 1
                removed_count += len(infos)
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info(
            "埋め込み先シェイプ数=%d 削除したテキストボックス数=%d", embedded_count, removed_count
        )
        print(f"{embedded_count}個のシェイプにテキストを埋め込みました（{removed_count}個のテキストボックスを削除）")
        return 0

    def _match_text_boxes_to_hosts(
        self, text_boxes: list[object], hosts: list[object]
    ) -> list[tuple[object, list[_TextBoxInfo]]]:
        # 1つのテキストボックスが複数hostの矩形と重なる場合、最も面積が
        # 小さいhost（=より内側に配置された、より具体的な対象）に一意に
        # 割り当てる。割り当てないと同じテキストボックスが2回埋め込まれた
        # 上で二重に削除され、2回目でCOMエラーになる。
        host_by_text_box: dict[int, object] = {}
        for i, tb in enumerate(text_boxes):
            candidates = [h for h in hosts if self._center_inside(tb, h)]
            if not candidates:
                continue
            best = min(candidates, key=lambda h: h.Width * h.Height)  # type: ignore[attr-defined]
            host_by_text_box[i] = best

        grouped: dict[int, list[object]] = {}
        for i, host in host_by_text_box.items():
            grouped.setdefault(id(host), []).append(text_boxes[i])

        pairs: list[tuple[object, list[_TextBoxInfo]]] = []
        for host in hosts:
            tbs = grouped.get(id(host))
            if not tbs:
                continue
            infos = [
                info for info in (self._to_text_box_info(tb) for tb in tbs) if info is not None
            ]
            if infos:
                infos.sort(key=lambda i: i.top)
                pairs.append((host, infos))
        return pairs

    def _center_inside(self, text_box: object, host: object) -> bool:
        center_x = text_box.Left + text_box.Width / 2  # type: ignore[attr-defined]
        center_y = text_box.Top + text_box.Height / 2  # type: ignore[attr-defined]
        return bool(
            host.Left <= center_x <= host.Left + host.Width  # type: ignore[attr-defined]
            and host.Top <= center_y <= host.Top + host.Height  # type: ignore[attr-defined]
        )

    def _to_text_box_info(self, text_box: object) -> _TextBoxInfo | None:
        if not getattr(text_box, "HasTextFrame", False):
            return None
        text_range = text_box.TextFrame.TextRange  # type: ignore[attr-defined]
        text = text_range.Text
        if not text or not text.strip():
            return None

        font = text_range.Font
        try:
            color = font.Color.RGB
        except Exception:
            color = None

        return _TextBoxInfo(
            ref=text_box,
            top=text_box.Top,  # type: ignore[attr-defined]
            text=text,
            font_name=font.Name,
            font_size=font.Size,
            bold=font.Bold,
            color=color,
            alignment=text_range.ParagraphFormat.Alignment,
        )

    def _print_dry_run(self, pairs: list[tuple[object, list[_TextBoxInfo]]]) -> None:
        for i, (_host, infos) in enumerate(pairs, start=1):
            print(f"シェイプ{i}: {len(infos)}個のテキストボックスを埋め込み")
            for info in infos:
                print(f"  Top={info.top:.1f} Text={info.text!r}")

    def _embed(self, host: object, infos: list[_TextBoxInfo]) -> None:
        host_text_range = host.TextFrame.TextRange  # type: ignore[attr-defined]
        existing_text = host_text_range.Text

        lines = [info.text for info in infos]
        if existing_text and existing_text.strip():
            host_top = host.Top  # type: ignore[attr-defined]
            if infos[0].top >= host_top + host.Height / 2:  # type: ignore[attr-defined]
                lines = [existing_text, *lines]
            else:
                lines = [*lines, existing_text]

        host_text_range.Text = "\r".join(lines)

        style = infos[0]
        if style.font_name is not None:
            host_text_range.Font.Name = style.font_name
        if style.font_size is not None:
            host_text_range.Font.Size = style.font_size
        if style.bold is not None:
            host_text_range.Font.Bold = style.bold
        if style.color is not None:
            host_text_range.Font.Color.RGB = style.color
        if style.alignment is not None:
            host_text_range.ParagraphFormat.Alignment = style.alignment

        for info in infos:
            info.ref.Delete()  # type: ignore[attr-defined]
