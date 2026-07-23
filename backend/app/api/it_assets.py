"""
IT Asset API endpoints for GCM Web UI.

Created: 2026-06-02
Last Modified: 2026-06-02
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.profile_service import ProfileService
from app.services.auth_service import AuthService
from app.services.it_asset_service import ITAssetService
from app.schemas.it_asset import (
    ITAssetCreate,
    ITAssetUpdate,
    ITAssetResponse,
    ITAssetListResponse,
    ITAssetFilter,
    ITAssetStats,
    SyncAssetsRequest,
    SyncAssetsResponse
)

router = APIRouter()


def get_active_profile_and_headers(db: Session) -> tuple:
    """
    Get active profile data and ready-to-use auth headers.

    Supports both OIDC and API key authentication methods transparently.
    The auth_method on the active profile determines which path is taken;
    no mixing of methods occurs.

    Returns:
        Tuple of (profile_data dict, auth_headers dict)

    Raises:
        HTTPException: If no active profile or credential retrieval fails
    """
    profile = ProfileService.get_active_profile(db)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active profile configured",
        )

    # Single call — branches exclusively on profile.auth_method
    try:
        auth_headers = AuthService.get_active_profile_headers(db)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}",
        )

    profile_data = {
        "app_uri": profile.app_uri,
        "oidc_uri": profile.oidc_uri,
        "realm": profile.realm,
        "insecure": profile.insecure,
        "timeout": profile.timeout,
        "tenant_id": profile.tenant_id,
        "auth_method": profile.auth_method,
    }

    return profile_data, auth_headers


@router.post("/sync", response_model=SyncAssetsResponse)
def sync_assets(
    request: SyncAssetsRequest,
    db: Session = Depends(get_db)
):
    """
    Sync IT assets from GCM inventory.
    
    Fetches assets from GCM and updates local database.
    """
    profile_data, auth_headers = get_active_profile_and_headers(db)
    
    service = ITAssetService(db)
    
    try:
        synced, created, updated, errors = service.sync_assets_from_gcm(
            profile_data=profile_data,
            auth_headers=auth_headers,
            asset_type=request.asset_type,
            page_size=request.page_size
        )
        
        return SyncAssetsResponse(
            synced_count=synced,
            created_count=created,
            updated_count=updated,
            error_count=len(errors),
            errors=errors
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )


@router.get("/", response_model=ITAssetListResponse)
def list_assets(
    asset_type: str = None,
    environment: str = None,
    location: str = None,
    owner: str = None,
    internet_facing: str = None,
    search: str = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = None,
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """
    List IT assets with filtering and pagination.
    
    Query parameters:
    - asset_type: Filter by asset type
    - environment: Filter by environment
    - location: Filter by location
    - owner: Filter by owner
    - internet_facing: Filter by internet facing status
    - search: Search in URI, hostname, or IP
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - sort_by: Field to sort by
    - sort_order: Sort order (asc/desc)
    """
    service = ITAssetService(db)
    
    # Create filter object
    filters = ITAssetFilter(
        asset_type=asset_type,
        environment=environment,
        location=location,
        owner=owner,
        internet_facing=internet_facing,
        search=search,
        page=page,
        page_size=min(page_size, 100),  # Cap at 100
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    try:
        assets, total = service.get_assets(filters)
        
        total_pages = (total + filters.page_size - 1) // filters.page_size
        
        return ITAssetListResponse(
            assets=assets,
            total=total,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list assets: {str(e)}"
        )


@router.get("/stats", response_model=ITAssetStats)
def get_asset_stats(db: Session = Depends(get_db)):
    """
    Get IT asset statistics.
    
    Returns aggregated statistics including counts by type, environment, location, etc.
    """
    service = ITAssetService(db)
    
    try:
        return service.get_stats()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.get("/{asset_id}", response_model=ITAssetResponse)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    """
    Get IT asset by ID.
    
    Returns detailed information about a specific asset.
    """
    service = ITAssetService(db)
    
    asset = service.get_asset_by_id(asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID {asset_id} not found"
        )
    
    return asset


@router.post("/", response_model=ITAssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    asset_data: ITAssetCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new IT asset.
    
    Creates the asset in both GCM and local database.
    """
    profile_data, auth_headers = get_active_profile_and_headers(db)
    
    service = ITAssetService(db)
    
    # Check if asset with same URI already exists
    existing = service.get_asset_by_uri(asset_data.uri)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Asset with URI '{asset_data.uri}' already exists"
        )
    
    try:
        asset = service.create_asset(
            profile_data=profile_data,
            auth_headers=auth_headers,
            asset_data=asset_data
        )
        return asset
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create asset: {str(e)}"
        )


@router.put("/{asset_id}", response_model=ITAssetResponse)
def update_asset(
    asset_id: int,
    update_data: ITAssetUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an IT asset.
    
    Updates the asset in both GCM and local database.
    """
    profile_data, auth_headers = get_active_profile_and_headers(db)
    
    service = ITAssetService(db)
    
    try:
        asset = service.update_asset(
            asset_id=asset_id,
            profile_data=profile_data,
            auth_headers=auth_headers,
            update_data=update_data
        )
        
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Asset with ID {asset_id} not found"
            )
        
        return asset
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update asset: {str(e)}"
        )


@router.delete("/")
def delete_assets(
    asset_ids: List[int],
    db: Session = Depends(get_db)
):
    """
    Delete IT assets.
    
    Deletes assets from both GCM and local database.
    Accepts a list of asset IDs.
    """
    if not asset_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No asset IDs provided"
        )
    
    profile_data, auth_headers = get_active_profile_and_headers(db)
    
    service = ITAssetService(db)
    
    try:
        deleted_count, errors = service.delete_assets(
            asset_ids=asset_ids,
            profile_data=profile_data,
            auth_headers=auth_headers,
        )
        
        return {
            "deleted_count": deleted_count,
            "error_count": len(errors),
            "errors": errors
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete assets: {str(e)}"
        )


@router.get("/types/list")
def list_asset_types(db: Session = Depends(get_db)):
    """
    Get list of available asset types.
    
    Returns distinct asset types from the database.
    """
    from app.models.it_asset import ITAsset
    
    try:
        # Query distinct asset types
        types = db.query(ITAsset.asset_type).distinct().all()
        asset_types = [t[0] for t in types if t[0]]
        
        # Add common types if not present
        common_types = ["Service", "Application", "Database", "Server"]
        for ct in common_types:
            if ct not in asset_types:
                asset_types.append(ct)
        
        return {"asset_types": sorted(asset_types)}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list asset types: {str(e)}"
        )

# Made with Bob
