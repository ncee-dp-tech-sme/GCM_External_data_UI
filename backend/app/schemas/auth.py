"""
2026-06-01T19:44:00Z - Added device authorization and GCM authorization schemas.
2026-06-01T22:52:00Z - Removed unused device authorization schemas, kept only active profile schemas.
2026-07-23T00:00:00Z - Added ApiKeyAuthInfo response for API key authentication status.
"""

from pydantic import BaseModel
from typing import Optional


class PasswordAuthResponse(BaseModel):
    """Response schema for password authentication (OIDC only)"""
    access_token: str
    expires_in: int
    refresh_token: Optional[str] = None


class ApiKeyAuthInfo(BaseModel):
    """
    Informational response when the active profile uses API key authentication.
    No token is issued; the api_key is transmitted directly in the Authorization header
    with token_type: api_key on every request.
    """
    auth_method: str = "api_key"
    message: str = (
        "API key authentication is active. No OIDC token is required. "
        "Requests include Authorization: <api_key> and token_type: api_key headers."
    )


class AuthorizationResponse(BaseModel):
    """Response schema for GCM authorization"""
    status_code: int
    authorized: bool
    payload: dict

# Made with Bob
