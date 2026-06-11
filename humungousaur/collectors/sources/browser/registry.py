from __future__ import annotations

from typing import Any

from .brave import BRAVE_BROWSER_COLLECTOR
from .chrome import CHROME_BROWSER_COLLECTOR
from .edge import EDGE_BROWSER_COLLECTOR
from .firefox import FIREFOX_BROWSER_COLLECTOR
from .safari import SAFARI_BROWSER_COLLECTOR


BROWSER_APP_COLLECTORS: tuple[Any, ...] = (
    CHROME_BROWSER_COLLECTOR,
    EDGE_BROWSER_COLLECTOR,
    BRAVE_BROWSER_COLLECTOR,
    FIREFOX_BROWSER_COLLECTOR,
    SAFARI_BROWSER_COLLECTOR,
)


def browser_collector_status_records() -> list[dict[str, Any]]:
    return [collector.status_record() for collector in BROWSER_APP_COLLECTORS]


__all__ = ["BROWSER_APP_COLLECTORS", "browser_collector_status_records"]
