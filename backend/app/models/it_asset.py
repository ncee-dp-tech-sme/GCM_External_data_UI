"""
IT Asset database model for GCM Web UI.

Created: 2026-06-02
Last Modified: 2026-06-02
Changes:
- 2026-07-25: Added GCM security fields: total_violation, pqc_readiness_flag,
  exploitability_score, is_exception, contains_classified_data, is_encrypted, total_pqc_violation.
- 2026-07-25: Replaced speculative fields with confirmed GCM columns payload:
  added protocol_version, servicename, databasename, databasetype, version,
  application_id, patch. Removed contains_classified_data, is_encrypted,
  total_pqc_violation (not in confirmed GCM columns list).
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Float
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
    asset_id = Column(String, unique=True, index=True, nullable=True)  # GCM asset UUID

    # Core asset information
    uri = Column(String, unique=True, index=True, nullable=False)
    ip = Column(String, index=True, nullable=True)
    hostname = Column(String, index=True, nullable=True)
    port = Column(Integer, nullable=True)
    protocol = Column(String, nullable=True)         # e.g. TLS, TCP
    protocol_version = Column(JSON, nullable=True)   # list of version strings e.g. ["TLSv1.3","TLSv1.2"]

    # Asset classification
    asset_type = Column(String, index=True, nullable=True)  # Database, Service, Application
    asset_sub_type = Column(String, nullable=True)

    # Service / application / database specific
    servicename = Column(String, nullable=True)
    databasename = Column(String, nullable=True)
    databasetype = Column(String, nullable=True)
    version = Column(String, nullable=True)         # software version
    application_id = Column(String, nullable=True)  # GCM applicationID
    patch = Column(String, nullable=True)           # patch level

    # Organizational metadata
    owner = Column(String, nullable=True)
    tech_contacts = Column(JSON, nullable=True)     # array of contact strings
    environment = Column(String, nullable=True)
    location = Column(String, nullable=True)
    network = Column(String, nullable=True)

    # Security and compliance
    mission_criticality = Column(Integer, nullable=True)
    internet_facing = Column(String, nullable=True)  # DEFAULT, UNKNOWN, TRUE, FALSE
    total_violation = Column(Integer, nullable=True)
    pqc_readiness_flag = Column(String, nullable=True)  # PQC_SAFE, PQC_UNSAFE, etc.
    exploitability_score = Column(Float, nullable=True)
    is_exception = Column(String, nullable=True)        # TRUE/FALSE

    # Custom attributes
    extensions = Column(JSON, nullable=True)

    # Discovery and tracking
    discovery_sources = Column(JSON, nullable=True)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    # GCM object status
    object_status = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_synced = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<ITAsset(id={self.id}, uri='{self.uri}', asset_type='{self.asset_type}')>"

# Made with Bob
