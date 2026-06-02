"""
2026-06-01T19:45:00Z - Added GCM user registration schemas.
"""

from pydantic import BaseModel, Field
from typing import List


class GCMUserRegistrationRequest(BaseModel):
    """Request schema for registering an existing OIDC user in GCM"""
    email: str = Field(..., min_length=1, description="Email address of the existing OIDC user")
    distinguished_name: str = Field(..., min_length=1, description="Distinguished name for the user")
    display_name: str = Field(..., min_length=1, description="Display name for the user")
    roles: List[str] = Field(..., min_length=1, description="GCM role names to assign")


class GCMUserRegistrationResponse(BaseModel):
    """Response schema for GCM user registration"""
    status_code: int
    success: bool
    payload: dict

# Made with Bob
