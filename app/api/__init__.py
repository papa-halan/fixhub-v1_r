from app.api.admin import router as admin_router
from app.api.common import router as common_router
from app.api.contractor import router as contractor_router
from app.api.jobs import router as jobs_router
from app.api.resident import router as resident_router

__all__ = [
    "admin_router",
    "common_router",
    "contractor_router",
    "jobs_router",
    "resident_router",
]
