from .health import router as health_router
from .auth import router as auth_router
from .public import router as public_router
from .reader_auth import router as reader_auth_router
from .reader_portal import router as reader_portal_router
from .reader_ai import router as reader_ai_router
from .admin_portal import router as admin_portal_router
from .library import router as library_router
from .locations import router as locations_router
from .catalog import router as catalog_router
from .circulation import router as circulation_router
from .dashboard import router as dashboard_router
from .ai import router as ai_router
from .ai_kernel import router as ai_kernel_router
from .readers import router as readers_router
from .rules import router as rules_router
from .notifications import router as notifications_router
from .tasks import router as tasks_router
from .super_admin import router as super_admin_router

routers = [
    health_router, auth_router, public_router, reader_auth_router, reader_portal_router, reader_ai_router,
    admin_portal_router,
    library_router, locations_router, catalog_router, circulation_router,
    readers_router, rules_router, notifications_router, tasks_router,
    dashboard_router, ai_router, ai_kernel_router, super_admin_router,
]
