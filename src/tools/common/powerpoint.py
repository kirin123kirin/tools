from __future__ import annotations

from typing import Any

import win32com.client


class PowerPointNotRunningError(RuntimeError):
    """Raised when no running PowerPoint instance can be attached to."""


class NoActivePresentationError(RuntimeError):
    """Raised when PowerPoint is running but has no active window
    (e.g. Presentations.Count == 0)."""


def get_running_powerpoint() -> Any:
    """Attach to an already-running PowerPoint Application via COM.

    Never launches a new instance -- deciding whether to start one is left
    to the caller, since that's a per-command policy (outline does; ikko
    and mokuji don't).
    """
    try:
        return win32com.client.GetActiveObject("PowerPoint.Application")
    except Exception as exc:
        raise PowerPointNotRunningError(
            "PowerPointが起動していません"
        ) from exc


def get_active_presentation(app: Any) -> Any:
    """Return the presentation behind the focused window.

    Uses ActiveWindow.Presentation rather than ActivePresentation so that,
    with multiple PowerPoint windows open, the one currently focused wins.
    """
    try:
        return app.ActiveWindow.Presentation
    except Exception as exc:
        raise NoActivePresentationError(
            "PowerPointでプレゼンテーションが開かれていません"
        ) from exc
