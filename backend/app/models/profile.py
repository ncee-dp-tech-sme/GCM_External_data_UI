"""
Profile model for storing GCM connection configurations
Each profile represents a GCM environment (dev, staging, prod, etc.)

2026-07-23: Added auth_method and api_key fields for API key authentication support.
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base

# Supported authentication methods
AUTH_METHOD_OIDC = "oidc"
AUTH_METHOD_API_KEY = "api_key"


class Profile(Base):
    """
    GCM Connection Profile
    Stores configuration for connecting to a GCM instance
    Sensitive fields (passwords, tokens, secrets) are encrypted
    """
    
    __tablename__ = "profiles"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Profile metadata
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500))
    is_active = Column(Boolean, default=False)  # Currently selected profile
    
    # Connection settings
    app_uri = Column(String(255), nullable=False)  # GCM application URI
    oidc_uri = Column(String(255), nullable=True)   # OIDC/Keycloak URI; null when auth_method='api_key'
    realm = Column(String(100), default="gcmrealm")
    
    # Authentication method — mutually exclusive: 'oidc' or 'api_key'
    auth_method = Column(String(20), default=AUTH_METHOD_OIDC, nullable=False)
    
    # OIDC authentication settings (only used when auth_method == 'oidc')
    client_id = Column(String(100))
    client_secret = Column(String(500))  # Encrypted
    refresh_token = Column(String(2000))  # Encrypted
    username = Column(String(100))  # Encrypted (optional)
    password = Column(String(500))  # Encrypted (optional)
    
    # API key authentication settings (only used when auth_method == 'api_key')
    api_key = Column(String(1000))  # Encrypted; transmitted in Authorization header
    
    # HTTP settings
    timeout = Column(Float, default=30.0)
    insecure = Column(Boolean, default=False)  # Skip SSL verification
    
    # Tenant settings
    tenant_id = Column(String(100))
    
    # Advanced settings
    user_agent = Column(String(200), default="gcm-webui/1.0")
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Profile(name='{self.name}', app_uri='{self.app_uri}', auth_method='{self.auth_method}')>"

# Made with Bob
