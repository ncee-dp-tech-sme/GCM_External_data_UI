"""
2026-06-01T19:44:00Z - Added device authorization and GCM authorization schemas.
2026-06-01T22:52:00Z - Removed unused device authorization schemas, kept only active profile schemas.
"""

from pydantic import BaseModel
from typing import Optional


class PasswordAuthResponse(BaseModel):
    """Response schema for password authentication"""
    access_token: str
    expires_in: int
    refresh_token: Optional[str] = None


class AuthorizationResponse(BaseModel):
    """Response schema for GCM authorization"""
    status_code: int
    authorized: bool
    payload: dict

# Made with Bob
