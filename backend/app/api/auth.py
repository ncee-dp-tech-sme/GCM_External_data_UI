"""
2026-06-01T19:45:00Z - Added OIDC device authorization and GCM authorization endpoints.
2026-06-01T20:26:00Z - Added password grant authentication endpoint.
2026-06-01T21:30:00Z - Added direct token endpoint for form-urlencoded requests.
2026-06-01T22:38:00Z - Added simplified endpoints using active profile.
2026-06-01T22:50:00Z - Removed redundant profile-specific endpoints, kept only active profile flow.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas.auth import (
    PasswordAuthResponse,
    AuthorizationResponse,
)
from app.services.auth_service import AuthService
from app.services.profile_service import ProfileService


router = APIRouter()


@router.post("/login", response_model=PasswordAuthResponse, status_code=status.HTTP_200_OK)
def login(db: Session = Depends(get_db)):
    """
    Authenticate using the active profile's stored credentials.
    Gets access token from OIDC and authorizes to GCM.
    """
    result = AuthService.authenticate_active_profile(db)
    return PasswordAuthResponse(
        access_token=result["access_token"],
        expires_in=result["expires_in"],
        refresh_token=result.get("refresh_token"),
    )


@router.get("/token")
def get_token(db: Session = Depends(get_db)):
    """
    Get a valid access token for the active profile.
    Automatically refreshes if needed using stored refresh token or credentials.
    """
    access_token = AuthService.get_active_profile_token(db)
    return {"access_token": access_token}


@router.post("/authorize", response_model=AuthorizationResponse, status_code=status.HTTP_200_OK)
def authorize(
    tenant_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Authorize against GCM using the active profile.
    Automatically gets/refreshes access token as needed.
    """
    profile = ProfileService.get_active_profile(db)
    result = AuthService.authorize(db, profile, tenant_id)
    return AuthorizationResponse(
        status_code=result["status_code"],
        authorized=result["authorized"],
        payload=result["payload"],
    )

# Made with Bob
