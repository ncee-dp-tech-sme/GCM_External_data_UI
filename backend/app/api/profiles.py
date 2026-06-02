"""
Profile management API endpoints
Handles CRUD operations for GCM connection profiles
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas.profile import (
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    ProfileListResponse
)
from app.services.profile_service import ProfileService

router = APIRouter()


@router.post("/", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    profile_data: ProfileCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new GCM connection profile
    
    - **name**: Unique profile name
    - **app_uri**: GCM application URI (e.g., https://gcm:31443)
    - **oidc_uri**: OIDC/Keycloak URI (e.g., https://gcm:30443)
    - Sensitive fields (passwords, tokens) are automatically encrypted
    """
    profile = ProfileService.create_profile(db, profile_data)
    return ProfileService.to_response(profile)


@router.get("/", response_model=ProfileListResponse)
def list_profiles(db: Session = Depends(get_db)):
    """
    Get all profiles
    
    Returns list of all profiles with the currently active profile indicated
    """
    profiles = ProfileService.get_all_profiles(db)
    active_profile = ProfileService.get_active_profile(db)
    
    return ProfileListResponse(
        profiles=[ProfileService.to_response(p) for p in profiles],
        total=len(profiles),
        active_profile_id=active_profile.id if active_profile else None
    )


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(
    profile_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific profile by ID
    
    Returns profile details (sensitive fields are not exposed)
    """
    profile = ProfileService.get_profile(db, profile_id)
    return ProfileService.to_response(profile)


@router.put("/{profile_id}", response_model=ProfileResponse)
def update_profile(
    profile_id: int,
    profile_data: ProfileUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a profile
    
    All fields are optional. Only provided fields will be updated.
    Sensitive fields are automatically encrypted.
    """
    profile = ProfileService.update_profile(db, profile_id, profile_data)
    return ProfileService.to_response(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a profile
    
    Cannot delete the currently active profile.
    Activate another profile first.
    """
    ProfileService.delete_profile(db, profile_id)
    return None


@router.post("/{profile_id}/activate", response_model=ProfileResponse)
def activate_profile(
    profile_id: int,
    db: Session = Depends(get_db)
):
    """
    Set a profile as active
    
    Deactivates all other profiles and activates the specified one.
    The active profile is used for GCM API operations.
    """
    profile = ProfileService.set_active_profile(db, profile_id)
    return ProfileService.to_response(profile)


@router.get("/active/current", response_model=ProfileResponse)
def get_active_profile(db: Session = Depends(get_db)):
    """
    Get the currently active profile
    
    Returns the profile that is currently selected for GCM operations
    """
    profile = ProfileService.get_active_profile(db)
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active profile found. Please create and activate a profile."
        )
    return ProfileService.to_response(profile)

# Made with Bob
