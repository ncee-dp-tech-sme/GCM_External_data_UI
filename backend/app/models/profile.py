"""
Profile model for storing GCM connection configurations
Each profile represents a GCM environment (dev, staging, prod, etc.)
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from sqlalchemy.sql import func
from app.database import Base


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
    oidc_uri = Column(String(255), nullable=False)  # OIDC/Keycloak URI
    realm = Column(String(100), default="gcmrealm")
    
    # Authentication settings
    client_id = Column(String(100))
    client_secret = Column(String(500))  # Encrypted
    refresh_token = Column(String(2000))  # Encrypted
    username = Column(String(100))  # Encrypted (optional)
    password = Column(String(500))  # Encrypted (optional)
    
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
        return f"<Profile(name='{self.name}', app_uri='{self.app_uri}')>"

# Made with Bob
