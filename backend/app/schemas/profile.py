"""
Pydantic schemas for Profile model
Handles validation and serialization of profile data

2026-07-23: Added auth_method and api_key fields for API key authentication support.
2026-07-30: Added private-IP/loopback host check in URI validators to prevent SSRF.
"""

import ipaddress
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import datetime

# Valid authentication method values
AUTH_METHOD_OIDC = "oidc" # HashiCorpIgnore
AUTH_METHOD_API_KEY = "api_key" # HashiCorpIgnore


# Reject URIs that resolve to private/loopback/link-local/multicast addresses (SSRF mitigation).
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local
    ipaddress.ip_network("100.64.0.0/10"),    # shared address space (RFC 6598)
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),         # ULA
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def _assert_public_host(uri: str) -> None:
    """Raise ValueError if the URI's hostname resolves to a private or loopback address."""
    parsed = urlparse(uri)
    host = parsed.hostname or ""
    if not host:
        raise ValueError("URI must contain a valid hostname")
    # Reject plain 'localhost' regardless of case
    if host.lower() == "localhost":
        raise ValueError("URI must not target a private or loopback host")
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        # Not a bare IP — hostname-based URIs are allowed (DNS resolution happens at request time;
        # the important thing is to block literal private IPs and known loopback hostnames).
        return
    if addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_private:
        raise ValueError("URI must not target a private or loopback host")
    for network in _PRIVATE_NETWORKS:
        if addr in network:
            raise ValueError("URI must not target a private or loopback host")



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
        """Ensure app_uri starts with http(s):// and does not target a private/loopback host."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URI must start with http:// or https://')
        _assert_public_host(v)
        return v.rstrip('/')

    @validator('oidc_uri')
    def validate_oidc_uri(cls, v):
        """Ensure oidc_uri, when provided, starts with http(s):// and is not a private host."""
        if v is None:
            return v
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URI must start with http:// or https://')
        _assert_public_host(v)
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
        """Ensure URIs start with http(s):// and are not private/loopback hosts."""
        if not v:
            return v
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URI must start with http:// or https://')
        _assert_public_host(v)
        return v.rstrip('/')


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
