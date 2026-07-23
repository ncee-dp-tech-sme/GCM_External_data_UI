"""
2026-06-01T23:31:00Z - Initial creation of certificate model
2026-07-25T00:10:00Z - Added missing GCM fields: certificate_validity_period, is_short_lived,
                       san (JSON), is_exception, group_updated_at, gcm_created_at, gcm_updated_at
2026-07-29T00:00:00Z - Added object_type column to store GCM crypto_object_type (Certificate/Key/Protocol)
Certificate database model for GCM certificate inventory
Stores certificate metadata and relationships
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.sql import func
from app.database import Base


class Certificate(Base):
    """
    Certificate model for storing GCM certificate inventory data
    
    This model stores certificate metadata retrieved from GCM API.
    It does not store the actual certificate data (PEM/DER), only metadata.
    """
    __tablename__ = "certificates"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Certificate identifiers
    crypto_id = Column(String(255), unique=True, index=True, nullable=True)
    serial_number = Column(String(255), index=True, nullable=True)
    alias = Column(String(255), index=True, nullable=True)
    
    # Certificate details
    subject = Column(Text, nullable=True)
    issuer = Column(Text, nullable=True)
    subject_cn = Column(String(255), nullable=True)
    issuer_cn = Column(String(255), nullable=True)
    
    # Validity period
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    is_expired = Column(Boolean, default=False)
    days_until_expiry = Column(Integer, nullable=True)
    
    # Cryptographic details
    public_key_algorithm = Column(String(100), nullable=True)
    signature_algorithm = Column(String(100), nullable=True)
    key_size = Column(Integer, nullable=True)
    
    # Crypto object type from GCM (e.g. Certificate, Key, Protocol)
    object_type = Column(String(100), index=True, nullable=True)

    # Relationships
    uri = Column(String(500), index=True, nullable=True)
    asset_type = Column(String(100), nullable=True)
    
    # Additional metadata
    fingerprint_sha256 = Column(String(255), nullable=True)
    version = Column(Integer, nullable=True)
    extensions = Column(Text, nullable=True)  # JSON string
    
    # GCM-specific fields
    certificate_status = Column(String(50), nullable=True)  # Valid, Expired, etc.
    is_ca_certificate = Column(Boolean, nullable=True)
    is_revoked = Column(Boolean, default=False)
    pqc_readiness_flag = Column(String(50), nullable=True)  # PQC_SAFE, PQC_UNSAFE, etc.
    total_violation = Column(Integer, nullable=True)
    total_pqc_violation = Column(Integer, nullable=True)
    exploitability_score = Column(Float, nullable=True)
    object_status = Column(String(50), nullable=True)  # Active, Inactive, etc.
    auto_renewal_status = Column(String(50), nullable=True)
    
    # Certificate validity period string from GCM (e.g. "606 days")
    certificate_validity_period = Column(String(50), nullable=True)

    # Boolean flags from GCM
    is_short_lived = Column(Boolean, nullable=True)
    is_exception = Column(Boolean, nullable=True)

    # Subject Alternative Names – stored as JSON array of {type_id, value}
    san = Column(Text, nullable=True)

    # Discovery and tracking
    discovery_sources = Column(Text, nullable=True)  # JSON array
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)

    # GCM-side created_at / updated_at (distinct from local DB timestamps)
    gcm_created_at = Column(DateTime(timezone=True), nullable=True)
    gcm_updated_at = Column(DateTime(timezone=True), nullable=True)
    group_updated_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # GCM sync metadata
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<Certificate(id={self.id}, alias={self.alias}, serial={self.serial_number})>"

# Made with Bob
