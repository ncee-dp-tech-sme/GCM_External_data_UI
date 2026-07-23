"""
Pydantic schemas for Profile model
Handles validation and serialization of profile data

2026-07-23: Added auth_method and api_key fields for API key authentication support.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import datetime

# Valid authentication method values
AUTH_METHOD_OIDC = "oidc"
AUTH_METHOD_API_KEY = "api_key"


class ProfileBase(BaseModel):
    """Base profile schema with common fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Profile name")
    description: Optional[str] = Field(None, max_length=500, description="Profile description")
    app_uri: str = Field(..., description="GCM application URI (e.g., https://gcm:31443)")
    oidc_uri: Optional[str] = Field(None, description="OIDC/Keycloak URI (e.g., https://gcm:30443) — required when auth_method='oidc'")
    realm: str = Field(default="gcmrealm", description="Keycloak realm")
    # Authentication method: 'oidc' or 'api_key' — mutually exclusive
    auth_method: str = Field(
        default=AUTH_METHOD_OIDC,
        description="Authentication method: 'oidc' (default) or 'api_key'",
    )
    client_id: Optional[str] = Field(None, max_length=100, description="OIDC client ID")
    timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="HTTP timeout in seconds")
    insecure: bool = Field(default=False, description="Skip SSL verification (not recommended)")
    tenant_id: Optional[str] = Field(None, max_length=100, description="GCM tenant ID")
    user_agent: str = Field(default="gcm-webui/1.0", description="HTTP User-Agent header")

    @validator('auth_method')
    def validate_auth_method(cls, v):
        """Ensure auth_method is one of the supported values."""
        allowed = {AUTH_METHOD_OIDC, AUTH_METHOD_API_KEY}
        if v not in allowed:
            raise ValueError(f"auth_method must be one of: {', '.join(sorted(allowed))}")
        return v

    @validator('app_uri')
    def validate_app_uri(cls, v):
        """Ensure app_uri starts with http:// or https://"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URI must start with http:// or https://')
        return v.rstrip('/')

    @validator('oidc_uri')
    def validate_oidc_uri(cls, v):
        """Ensure oidc_uri, when provided, starts with http:// or https://"""
        if v is None:
            return v
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URI must start with http:// or https://')
        return v.rstrip('/')


class ProfileCreate(ProfileBase):
    """Schema for creating a new profile"""
    client_secret: Optional[str] = Field(None, description="OIDC client secret (will be encrypted)")
    username: Optional[str] = Field(None, description="Username for password grant (will be encrypted)")
    password: Optional[str] = Field(None, description="Password for password grant (will be encrypted)")
    # API key for api_key auth method (will be encrypted)
    api_key: Optional[str] = Field(None, description="API key for api_key auth method (will be encrypted)")

    @validator('client_secret', 'username', 'password', 'api_key')
    def validate_sensitive_fields(cls, v):
        """Ensure sensitive fields are not empty strings"""
        if v == "":
            return None
        return v


class ProfileUpdate(BaseModel):
    """Schema for updating an existing profile (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    app_uri: Optional[str] = None
    oidc_uri: Optional[str] = None
    realm: Optional[str] = None
    auth_method: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[float] = Field(None, ge=1.0, le=300.0)
    insecure: Optional[bool] = None
    tenant_id: Optional[str] = None
    user_agent: Optional[str] = None

    @validator('auth_method')
    def validate_auth_method(cls, v):
        """Ensure auth_method is one of the supported values."""
        if v is None:
            return v
        allowed = {AUTH_METHOD_OIDC, AUTH_METHOD_API_KEY}
        if v not in allowed:
            raise ValueError(f"auth_method must be one of: {', '.join(sorted(allowed))}")
        return v

    @validator('app_uri', 'oidc_uri')
    def validate_uri(cls, v):
        """Ensure URIs start with http:// or https://"""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError('URI must start with http:// or https://')
        return v.rstrip('/') if v else v


class ProfileResponse(ProfileBase):
    """Schema for profile responses (excludes sensitive data)"""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    # Indicate if sensitive fields are set (without exposing values)
    has_client_secret: bool = False
    has_refresh_token: bool = False
    has_username: bool = False
    has_password: bool = False
    has_api_key: bool = False

    class Config:
        from_attributes = True


class ProfileListResponse(BaseModel):
    """Schema for list of profiles"""
    profiles: list[ProfileResponse]
    total: int
    active_profile_id: Optional[int] = None

# Made with Bob
