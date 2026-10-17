from __future__ import annotations

from bookflow_core.services.dashboard_core import (
    admin_dashboard,
    chart,
    library_profile,
    operation_snapshot,
)
from bookflow_core.services.dashboard_analytics import (
    analytics_overview,
    circulation_analytics,
    collection_health,
    reader_analytics,
    risk_analytics,
)
from bookflow_core.services.dashboard_ai import (
    ai_efficiency,
)

__all__ = [
    "admin_dashboard",
    "analytics_overview",
    "collection_health",
    "circulation_analytics",
    "reader_analytics",
    "risk_analytics",
    "ai_efficiency",
    "chart",
    "library_profile",
    "operation_snapshot",
]
