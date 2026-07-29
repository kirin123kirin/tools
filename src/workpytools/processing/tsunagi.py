from __future__ import annotations

import argparse
import logging

from workpytools.common.connector_sites import (
    SiteShape,
    nearest_site,
    nearest_site_pair,
)
from workpytools.common.powerpoint import (
    NoActivePresentationError,
    PowerPointNotRunningError,
    get_active_presentation,
    get_running_powerpoint,
)
from workpytools.processing.base import Processor

logger = logging.getLogger(__name__)

_SELECTION_SHAPES = 2  # ppSelectionShapes
_MSO_CONNECTOR_STRAIGHT = 1  # msoConnectorStraight
_MSO_TRUE = -1  # msoTrue
_CONNECTOR_LINE_WEIGHT = 2  # iroコマンドで定めた矢印の既定書式に合わせる
_BLACK_RGB = 0x000000


class TsunagiProcessor(Processor):
    """Snap connectors to the nearest connection sites of nearby shapes,
    so they don't have to be dragged onto the handles by hand. The mode is
    inferred from the current selection:

    - selection contains connectors and 2+ other shapes -> snap both ends
      of every selected connector to the nearest site among those shapes
    - no connectors and exactly 2 shapes -> create a straight connector
      between them
    - anything else -> error, see run()
    """

    name = "tsunagi"
    help = "コネクタの端点を最寄りのシェイプの接続点に吸着させる（2つ選択で新規作成）"

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
            raise SystemExit(
                "コネクタとシェイプ、または繋ぎたいシェイプを2つ選択してから実行してください"
            )

        shape_range = selection.ShapeRange
        selected = [shape_range.Item(i) for i in range(1, shape_range.Count + 1)]

        connectors = [s for s in selected if self._is_connector(s)]
        shapes = [s for s in selected if not self._is_connector(s)]

        if connectors:
            return self._run_snap(app, connectors, shapes)
        return self._run_create(app, shapes)

    def _is_connector(self, shape: object) -> bool:
        # Shape.TypeがmsoLineでもConnectorが偽なら単なる直線で接続できないため、
        # Connectorプロパティで判定する
        return getattr(shape, "Connector", 0) == _MSO_TRUE

    # --- 吸着モード（既存コネクタの再接続） -----------------------------

    def _run_snap(self, app: object, connectors: list[object], shapes: list[object]) -> int:
        if len(shapes) < 2:
            raise SystemExit("接続先のシェイプを2つ以上選択してください")

        site_shapes = [self._to_site_shape(s) for s in shapes]

        try:
            app.StartNewUndoEntry()  # type: ignore[attr-defined]
            for connector in connectors:
                self._snap_connector(connector, site_shapes)
        except SystemExit:
            raise
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info("%d本のコネクタを吸着しました", len(connectors))
        print(f"{len(connectors)}本のコネクタを最寄りのシェイプに接続しました")
        return 0

    def _snap_connector(self, connector: object, site_shapes: list[SiteShape]) -> None:
        begin_point, end_point = self._connector_endpoints(connector)

        begin_pick = nearest_site(begin_point, site_shapes)
        end_pick = nearest_site(end_point, site_shapes)
        if begin_pick is None or end_pick is None:
            raise SystemExit("接続先のシェイプに接続点がありません")

        if begin_pick.shape.ref is end_pick.shape.ref:
            raise SystemExit(
                "コネクタの両端が同じシェイプに最も近いため、接続先を判断できません"
            )

        connector_format = connector.ConnectorFormat  # type: ignore[attr-defined]
        connector_format.BeginConnect(begin_pick.shape.ref, begin_pick.site_index)
        connector_format.EndConnect(end_pick.shape.ref, end_pick.site_index)
        logger.info(
            "コネクタを接続しました: 始点site=%d 終点site=%d",
            begin_pick.site_index,
            end_pick.site_index,
        )

    def _connector_endpoints(
        self, connector: object
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """The connector's two visible endpoints, derived from its bounding
        box plus the flip flags (COM exposes no direct start/end coordinates).
        HorizontalFlip/VerticalFlip tell us which diagonal of the box the
        line actually runs along."""
        left = connector.Left  # type: ignore[attr-defined]
        top = connector.Top  # type: ignore[attr-defined]
        right = left + connector.Width  # type: ignore[attr-defined]
        bottom = top + connector.Height  # type: ignore[attr-defined]

        flipped_h = getattr(connector, "HorizontalFlip", 0) == _MSO_TRUE
        flipped_v = getattr(connector, "VerticalFlip", 0) == _MSO_TRUE

        begin_x = right if flipped_h else left
        end_x = left if flipped_h else right
        begin_y = bottom if flipped_v else top
        end_y = top if flipped_v else bottom

        return (begin_x, begin_y), (end_x, end_y)

    # --- 新規作成モード（シェイプ2つを繋ぐ） -----------------------------

    def _run_create(self, app: object, shapes: list[object]) -> int:
        if len(shapes) != 2:
            raise SystemExit(
                "繋ぎたいシェイプをちょうど2つ選択してください"
                "（コネクタを選択すればその両端を吸着させます）"
            )

        begin_shape, end_shape = shapes
        begin_site = self._to_site_shape(begin_shape)
        end_site = self._to_site_shape(end_shape)
        begin_index, end_index = nearest_site_pair(begin_site, end_site)

        try:
            app.StartNewUndoEntry()  # type: ignore[attr-defined]
            slide = app.ActiveWindow.View.Slide  # type: ignore[attr-defined]
            connector = slide.Shapes.AddConnector(_MSO_CONNECTOR_STRAIGHT, 0, 0, 0, 0)
            connector_format = connector.ConnectorFormat
            connector_format.BeginConnect(begin_shape, begin_index)
            connector_format.EndConnect(end_shape, end_index)
            connector.Line.ForeColor.RGB = _BLACK_RGB
            connector.Line.Weight = _CONNECTOR_LINE_WEIGHT
        except Exception as exc:
            raise SystemExit(
                f"PowerPointの操作中にエラーが発生しました（Ctrl+Zで開始前の状態に戻せます）: {exc}"
            ) from exc

        logger.info(
            "コネクタを新規作成しました: 始点site=%d 終点site=%d", begin_index, end_index
        )
        print("1本のコネクタを作成して接続しました")
        return 0

    # --- 共通 -----------------------------------------------------------

    def _to_site_shape(self, shape: object) -> SiteShape:
        return SiteShape(
            left=shape.Left,  # type: ignore[attr-defined]
            top=shape.Top,  # type: ignore[attr-defined]
            width=shape.Width,  # type: ignore[attr-defined]
            height=shape.Height,  # type: ignore[attr-defined]
            site_count=int(getattr(shape, "ConnectionSiteCount", 4)),
            ref=shape,
        )
