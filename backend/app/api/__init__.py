"""
2026-06-01T23:33:00Z - Added certificate routes
2026-06-02T01:40:00Z - Added IT asset routes
2026-06-02T02:27:00Z - Added scanner routes
API routes package
"""

from fastapi import APIRouter
from app.api import profiles, auth, user_management, certificates, it_assets, scanner

api_router = APIRouter()

# Include profile routes
api_router.include_router(profiles.router, prefix="/profiles", tags=["profiles"])

# Include authentication routes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Include user management routes
api_router.include_router(user_management.router, prefix="/user-management", tags=["user-management"])

# Include certificate routes
api_router.include_router(certificates.router, prefix="/certificates", tags=["certificates"])

# Include IT asset routes
api_router.include_router(it_assets.router, prefix="/assets", tags=["it-assets"])

# Include scanner routes
api_router.include_router(scanner.router, prefix="/scanner")

__all__ = ["api_router"]

# Made with Bob
