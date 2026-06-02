"""
Pydantic schemas for Profile model
Handles validation and serialization of profile data
"""

from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class ProfileBase(BaseModel):
    """Base profile schema with common fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Profile name")
    description: Optional[str] = Field(None, max_length=500, description="Profile description")
    app_uri: str = Field(..., description="GCM application URI (e.g., https://gcm:31443)")
    oidc_uri: str = Field(..., description="OIDC/Keycloak URI (e.g., https://gcm:30443)")
    realm: str = Field(default="gcmrealm", description="Keycloak realm")
    client_id: Optional[str] = Field(None, max_length=100, description="OIDC client ID")
    timeout: float = Field(default=30.0, ge=1.0, le=300.0, description="HTTP timeout in seconds")
    insecure: bool = Field(default=False, description="Skip SSL verification (not recommended)")
    tenant_id: Optional[str] = Field(None, max_length=100, description="GCM tenant ID")
    user_agent: str = Field(default="gcm-webui/1.0", description="HTTP User-Agent header")
    
    @validator('app_uri', 'oidc_uri')
    def validate_uri(cls, v):
        """Ensure URIs start with http:// or https://"""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URI must start with http:// or https://')
        return v.rstrip('/')  # Remove trailing slash


class ProfileCreate(ProfileBase):
    """Schema for creating a new profile"""
    client_secret: Optional[str] = Field(None, description="OIDC client secret (will be encrypted)")
    username: Optional[str] = Field(None, description="Username for password grant (will be encrypted)")
    password: Optional[str] = Field(None, description="Password for password grant (will be encrypted)")
    
    @validator('client_secret', 'username', 'password')
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
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: Optional[float] = Field(None, ge=1.0, le=300.0)
    insecure: Optional[bool] = None
    tenant_id: Optional[str] = None
    user_agent: Optional[str] = None
    
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
    
    class Config:
        from_attributes = True


class ProfileListResponse(BaseModel):
    """Schema for list of profiles"""
    profiles: list[ProfileResponse]
    total: int
    active_profile_id: Optional[int] = None

# Made with Bob
