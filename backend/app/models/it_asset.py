"""
IT Asset database model for GCM Web UI.

Created: 2026-06-02
Last Modified: 2026-06-02
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from app.database import Base


class ITAsset(Base):
    """
    IT Asset model representing assets in GCM inventory.
    
    Stores IT asset information including network details, metadata,
    and custom attributes.
    """
    __tablename__ = "it_assets"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # GCM identifiers
    asset_id = Column(String, unique=True, index=True, nullable=True)  # GCM asset ID
    
    # Core asset information (required for creation)
    uri = Column(String, unique=True, index=True, nullable=False)  # Resource URI
    ip = Column(String, index=True, nullable=True)  # IP address
    hostname = Column(String, index=True, nullable=True)  # Hostname
    port = Column(Integer, nullable=True)  # Port number
    protocol = Column(String, nullable=True)  # Protocol (e.g., TLS, TCP)
    
    # Asset classification
    asset_type = Column(String, index=True, nullable=True)  # Database, Service, Application
    asset_sub_type = Column(String, nullable=True)  # e.g., MySQL, PostgreSQL
    
    # Organizational metadata
    owner = Column(String, nullable=True)  # Asset owner
    tech_contacts = Column(JSON, nullable=True)  # Technical contacts (array)
    environment = Column(String, nullable=True)  # Staging, Production, etc.
    location = Column(String, nullable=True)  # Physical/logical location
    network = Column(String, nullable=True)  # Network zone
    
    # Security and compliance
    mission_criticality = Column(Integer, nullable=True)  # Criticality score
    internet_facing = Column(String, nullable=True)  # DEFAULT, UNKNOWN, TRUE, FALSE
    
    # Custom attributes
    extensions = Column(JSON, nullable=True)  # Custom key-value pairs
    
    # Discovery and tracking
    discovery_sources = Column(JSON, nullable=True)  # How asset was discovered
    first_seen = Column(DateTime(timezone=True), nullable=True)  # First discovery
    last_seen = Column(DateTime(timezone=True), nullable=True)  # Last seen
    
    # GCM-specific fields
    object_status = Column(String, nullable=True)  # GCM object status
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_synced = Column(DateTime(timezone=True), nullable=True)  # Last sync from GCM

    def __repr__(self):
        return f"<ITAsset(id={self.id}, uri='{self.uri}', asset_type='{self.asset_type}')>"

# Made with Bob
