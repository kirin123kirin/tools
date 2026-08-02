from __future__ import annotations

import argparse
import logging

from workpytools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from workpytools.common.theme_colors import ACCENT_HEX_COLORS, hex_to_ppt_rgb
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_MSO_GROUP = 6  # msoGroup
_MSO_COLOR_TYPE_SCHEME = 2  # msoColorTypeSchemeColor
_MSO_SHAPE_RECTANGLE = 1  # msoShapeRectangle
_MSO_CONNECTOR_STRAIGHT = 1  # msoConnectorStraight
_MSO_TRUE = -1  # msoTrue
_MSO_FALSE = 0  # msoFalse
_PP_AUTO_SIZE_NONE = 0  # ppAutoSizeNone
_PP_AUTO_SIZE_SHAPE_TO_FIT_TEXT = 1  # ppAutoSizeShapeToFitText
_DEFAULT_FONT = "メイリオ"

# サンプル図形を画面外に作る際のオフセット（ポイント）。作成直後に
# 削除するため見た目には影響しないが、万一削除に失敗しても画面上の
# 既存コンテンツと重ならないようにする。
_OFFSCREEN_LEFT = -2000
_OFFSCREEN_TOP = -2000

# CommandBars経由で「既定の図形として設定」を呼び出すためのコントロールID。
# Microsoft公式ドキュメントには載っておらず、実機で有効だったIDを暫定的に
# 使う。環境によって無効な場合があるため、失敗しても処理は継続する。
_SET_AS_DEFAULT_SHAPE_CONTROL_ID = 2969


class IroProcessor(Processor):
    """Unify presentation colors around a house palette in three steps:
    (1) freeze any theme-referencing colors on existing slides to their
    current RGB values so the theme change in step 2 doesn't alter them,
    (2) set the theme's accent1-6 colors to the new palette, and (3) try
    to make a rectangle/connector/textbox with the desired formatting the
    session-only default shape via the "Set as Default Shape" command.
    """

    name = "iro"
    help = "既存スライドを独自色化した上でテーマカラーと既定図形の書式を統一する"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        pass

    def run(self, args: argparse.Namespace) -> int:
        try:
            app = get_running_powerpoint()
        except PowerPointNotRunningError as exc:
            raise SystemExit(
                "PowerPointでプレゼンテーションを開いた状態で実行してください"
            ) from exc

        try:
            presentation = get_active_presentation(app)
        except NoActivePresentationError as exc:
            raise SystemExit(
                "PowerPointでプレゼンテーションを開いた状態で実行してください"
            ) from exc

        try:
            app.StartNewUndoEntry()
            logger.info("ステップ1開始: 既存スライドの独自色化")
            frozen_count = self._freeze_theme_colors_in_slides(presentation)
            logger.info("ステップ1完了: %d件", frozen_count)
            logger.info("ステップ2開始: テーマカラーの変更")
            design_count = self._apply_theme_colors(presentation)
            logger.info("ステップ2完了: デザイン%d件", design_count)
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: "
                f"{type(exc).__name__}: {exc!r}"
            ) from exc

        default_shape_warning = self._apply_default_shape_formats(app, presentation)

        logger.info(
            "独自色化=%d件 テーマ変更デザイン数=%d 既定書式警告=%s",
            frozen_count,
            design_count,
            default_shape_warning,
        )
        message = (
            f"既存スライドの色を{frozen_count}件独自色化し、"
            f"テーマカラーを新配色に変更しました（デザイン{design_count}件）。"
        )
        if default_shape_warning is None:
            message += (
                "シェイプ・矢印・テキストボックスの既定書式を一時適用しました"
                "（このセッション限り、PowerPoint再起動で失われます）"
            )
        else:
            message += f"\n{default_shape_warning}"
        print(message)
        return 0

    # --- ステップ1: 既存スライドの独自色化 -----------------------------

    def _freeze_theme_colors_in_slides(self, presentation: object) -> int:
        count = 0
        slides = presentation.Slides  # type: ignore[attr-defined]
        for i in range(1, slides.Count + 1):
            count += self._freeze_shapes(slides.Item(i).Shapes)
        return count

    def _freeze_shapes(self, shapes: object) -> int:
        count = 0
        for i in range(1, shapes.Count + 1):  # type: ignore[attr-defined]
            shape = shapes.Item(i)  # type: ignore[attr-defined]
            count += self._freeze_shape(shape)
        return count

    def _freeze_shape(self, shape: object) -> int:
        if getattr(shape, "Type", None) == _MSO_GROUP:
            return self._freeze_shapes(shape.GroupItems)  # type: ignore[attr-defined]

        count = 0
        count += self._freeze_fill_color(shape)
        count += self._freeze_line_color(shape)
        count += self._freeze_font_color(shape)
        return count

    def _freeze_fill_color(self, shape: object) -> int:
        # 表（msoTable）シェイプはFill/Lineプロパティへのアクセス自体が
        # COMレベルの例外（pywintypes.com_error、AttributeErrorではない）
        # になることが実機で確認されている。getattr()の既定値フォール
        # バックはAttributeErrorしか吸収しないため、com_error等も含めて
        # 広く捕捉し「読み取れないシェイプは独自色化の対象外」として
        # スキップする。
        try:
            fill = getattr(shape, "Fill", None)
            if fill is None or not fill.Visible:
                return 0
            fore_color = fill.ForeColor
        except Exception:
            return 0
        return self._freeze_color(fore_color)

    def _freeze_line_color(self, shape: object) -> int:
        try:
            line = getattr(shape, "Line", None)
            if line is None or not line.Visible:
                return 0
            fore_color = line.ForeColor
        except Exception:
            return 0
        return self._freeze_color(fore_color)

    def _freeze_font_color(self, shape: object) -> int:
        if not getattr(shape, "HasTextFrame", False):
            return 0
        text_range = shape.TextFrame.TextRange  # type: ignore[attr-defined]
        if not text_range.Text:
            return 0
        return self._freeze_color(text_range.Font.Color)

    def _freeze_color(self, color_format: object) -> int:
        if getattr(color_format, "Type", None) != _MSO_COLOR_TYPE_SCHEME:
            return 0
        current_rgb = color_format.RGB  # type: ignore[attr-defined]
        color_format.RGB = current_rgb  # type: ignore[attr-defined]
        return 1

    # --- ステップ2: テーマカラーの変更 -----------------------------------

    def _apply_theme_colors(self, presentation: object) -> int:
        designs = presentation.Designs  # type: ignore[attr-defined]
        for i in range(1, designs.Count + 1):
            color_scheme = designs.Item(i).SlideMaster.Theme.ThemeColorScheme
            for index, hex_color in ACCENT_HEX_COLORS.items():
                # ThemeColorSchemeはpywin32のダイナミックディスパッチ経由だと
                # .Item(index)という明示メソッド呼び出しの形が解決できず
                # AttributeErrorになる（型情報が実行時に完全解決されない）。
                # COMの既定メンバー呼び出し color_scheme(index) であれば
                # 動作するため、そちらを使う。
                color_scheme(index).RGB = hex_to_ppt_rgb(hex_color)
        return int(designs.Count)

    # --- ステップ3: 既定書式の一時適用 -----------------------------------

    def _apply_default_shape_formats(self, app: object, presentation: object) -> str | None:
        slide = self._first_slide(presentation)
        if slide is None:
            return "スライドが存在しないため、既定書式の一時適用をスキップしました"

        created_shapes: list[object] = []
        try:
            rectangle = self._create_formatted_rectangle(slide)
            created_shapes.append(rectangle)
            connector = self._create_formatted_connector(slide)
            created_shapes.append(connector)
            textbox = self._create_formatted_textbox(slide)
            created_shapes.append(textbox)

            for shape in created_shapes:
                self._try_set_as_default_shape(app, shape)
        except Exception as exc:
            return (
                "既定書式の一時適用に失敗しました。手動で図形を選択し、"
                f"右クリック→『既定の図形として設定』を行ってください（詳細: {exc}）"
            )
        finally:
            for shape in created_shapes:
                try:
                    shape.Delete()  # type: ignore[attr-defined]
                except Exception:
                    pass  # 削除失敗は致命的ではないため無視する

        return None

    def _first_slide(self, presentation: object) -> object | None:
        slides = presentation.Slides  # type: ignore[attr-defined]
        if slides.Count == 0:
            return None
        return slides.Item(1)  # type: ignore[no-any-return]

    def _create_formatted_rectangle(self, slide: object) -> object:
        shape = slide.Shapes.AddShape(  # type: ignore[attr-defined]
            _MSO_SHAPE_RECTANGLE, _OFFSCREEN_LEFT, _OFFSCREEN_TOP, 100, 60
        )
        shape.Line.ForeColor.RGB = hex_to_ppt_rgb("#000000")
        shape.Line.Weight = 1
        shape.TextFrame.WordWrap = _MSO_TRUE
        shape.TextFrame.AutoSize = _PP_AUTO_SIZE_NONE
        shape.TextFrame.TextRange.Font.Name = _DEFAULT_FONT
        shape.TextFrame.TextRange.Font.NameFarEast = _DEFAULT_FONT
        return shape

    def _create_formatted_connector(self, slide: object) -> object:
        shape = slide.Shapes.AddConnector(  # type: ignore[attr-defined]
            _MSO_CONNECTOR_STRAIGHT,
            _OFFSCREEN_LEFT,
            _OFFSCREEN_TOP,
            _OFFSCREEN_LEFT + 100,
            _OFFSCREEN_TOP,
        )
        shape.Line.ForeColor.RGB = hex_to_ppt_rgb("#000000")
        shape.Line.Weight = 2
        return shape

    def _create_formatted_textbox(self, slide: object) -> object:
        shape = slide.Shapes.AddTextbox(  # type: ignore[attr-defined]
            1, _OFFSCREEN_LEFT, _OFFSCREEN_TOP, 100, 30  # 1 = msoTextOrientationHorizontal
        )
        shape.TextFrame.WordWrap = _MSO_FALSE
        shape.TextFrame.AutoSize = _PP_AUTO_SIZE_SHAPE_TO_FIT_TEXT
        text_range = shape.TextFrame.TextRange
        text_range.Font.Name = _DEFAULT_FONT
        text_range.Font.NameFarEast = _DEFAULT_FONT
        text_range.Font.Size = 12
        text_range.Font.Color.RGB = hex_to_ppt_rgb("#000000")
        return shape

    def _try_set_as_default_shape(self, app: object, shape: object) -> None:
        shape.Select()  # type: ignore[attr-defined]
        control = app.CommandBars.FindControl(  # type: ignore[attr-defined]
            Id=_SET_AS_DEFAULT_SHAPE_CONTROL_ID
        )
        control.Execute()
