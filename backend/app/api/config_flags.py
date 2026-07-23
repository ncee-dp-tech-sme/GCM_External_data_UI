"""
2026-07-30T00:00:00Z - Created feature-flags endpoint so the frontend can read ENABLE_ASSET_SYNC
Config flags API — exposes runtime feature toggles to the frontend
"""

from fastapi import APIRouter
from app.config import settings

router = APIRouter()


# Return current feature-flag values so the browser UI can adapt without a rebuild
@router.get("/features")
async def get_feature_flags():
    """Return server-side feature flags consumed by the frontend."""
    return {
        "enable_asset_sync": settings.enable_asset_sync,
    }

# Made with Bob
