"""
2026-06-01T19:45:00Z - Added GCM user registration endpoint.
"""

import requests
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.user_management import (
    GCMUserRegistrationRequest,
    GCMUserRegistrationResponse,
)
from app.services.auth_service import AuthService
from app.services.profile_service import ProfileService


router = APIRouter()


# Register an existing OIDC user in GCM.
@router.post("/profiles/{profile_id}/users", response_model=GCMUserRegistrationResponse, status_code=status.HTTP_200_OK)
def register_oidc_user(
    profile_id: int,
    request: GCMUserRegistrationRequest,
    db: Session = Depends(get_db),
):
    """Register an existing OIDC user in GCM"""
    profile = ProfileService.get_profile(db, profile_id)
    auth_result = AuthService.authorize(db, profile, profile.tenant_id)
    access_token = auth_result["access_token"]

    response = requests.post(
        f"{profile.app_uri}/ibm/usermanagement/api/v1/users",
        json={
            "email": request.email,
            "distinguishedName": request.distinguished_name,
            "displayName": request.display_name,
            "assignRolesList": request.roles,
        },
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": profile.user_agent,
        },
        timeout=profile.timeout,
        verify=not profile.insecure,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    return GCMUserRegistrationResponse(
        status_code=response.status_code,
        success=response.ok,
        payload=payload,
    )

# Made with Bob
