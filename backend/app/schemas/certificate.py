"""
2026-06-01T23:31:00Z - Initial creation of certificate schemas
2026-07-25T00:10:00Z - Added new fields to CertificateResponse: certificate_validity_period,
2026-07-29T00:00:00Z - Added object_type to CertificateResponse and CertificateFilter
                       is_short_lived, is_exception, san, gcm_created_at, gcm_updated_at,
                       group_updated_at
Certificate Pydantic schemas for API request/response validation
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class CertificateBase(BaseModel):
    """Base certificate schema with common fields"""
    alias: Optional[str] = None
    uri: Optional[str] = None
    serial_number: Optional[str] = None
    subject: Optional[str] = None
    issuer: Optional[str] = None
    subject_cn: Optional[str] = None
    issuer_cn: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    public_key_algorithm: Optional[str] = None
    signature_algorithm: Optional[str] = None
    key_size: Optional[int] = None
    fingerprint_sha256: Optional[str] = None


class CertificateUpload(BaseModel):
    """Schema for uploading a certificate"""
    cert_file_base64: str = Field(..., description="Base64-encoded certificate file (PEM or DER)")
    uri: str = Field(..., description="URI where certificate is used (e.g., https://example.com:443)")
    alias: Optional[str] = Field(None, description="Optional alias for the certificate")
    
    @field_validator('uri')
    @classmethod
    def validate_uri(cls, v: str) -> str:
        """Validate URI format"""
        v = v.strip()
        if not v:
            raise ValueError("URI cannot be empty")
        # Basic validation - should contain host:port
        if ':' not in v and not v.startswith('https://'):
            raise ValueError("URI must include port (e.g., 'host:443' or 'https://host:443')")
        return v


class CertificateResponse(CertificateBase):
    """Schema for certificate response"""
    id: int
    crypto_id: Optional[str] = None
    is_expired: bool = False
    days_until_expiry: Optional[int] = None
    asset_type: Optional[str] = None
    version: Optional[int] = None
    
    # Crypto object type (Certificate, Key, Protocol)
    object_type: Optional[str] = None

    # GCM-specific fields
    certificate_status: Optional[str] = None
    is_ca_certificate: Optional[bool] = None
    is_revoked: Optional[bool] = None
    pqc_readiness_flag: Optional[str] = None
    total_violation: Optional[int] = None
    total_pqc_violation: Optional[int] = None
    exploitability_score: Optional[float] = None
    object_status: Optional[str] = None
    auto_renewal_status: Optional[str] = None
    
    # Additional GCM boolean flags
    is_short_lived: Optional[bool] = None
    is_exception: Optional[bool] = None

    # Certificate validity period string (e.g. "606 days")
    certificate_validity_period: Optional[str] = None

    # Subject Alternative Names (JSON string of list of {type_id, value})
    san: Optional[str] = None

    # Discovery and tracking
    discovery_sources: Optional[str] = None  # JSON string
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    # GCM-side timestamps
    gcm_created_at: Optional[datetime] = None
    gcm_updated_at: Optional[datetime] = None
    group_updated_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class CertificateListResponse(BaseModel):
    """Schema for paginated certificate list response"""
    certificates: List[CertificateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CertificateFilter(BaseModel):
    """Schema for certificate filtering"""
    search: Optional[str] = Field(None, description="Search by alias, URI, or serial number")
    uri: Optional[str] = Field(None, description="Filter by URI")
    issuer_cn: Optional[str] = Field(None, description="Filter by issuer CN")
    is_expired: Optional[bool] = Field(None, description="Filter by expiry status")
    expiring_days: Optional[int] = Field(None, description="Filter certificates expiring within N days")
    object_type: Optional[str] = Field(None, description="Filter by crypto object type (Certificate, Key, Protocol)")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field("created_at", description="Sort field")
    sort_order: Optional[str] = Field("desc", description="Sort order (asc/desc)")


class CertificateStats(BaseModel):
    """Schema for certificate statistics"""
    total_certificates: int
    expired_certificates: int
    expiring_soon: int  # Expiring within 30 days
    by_issuer: Dict[str, int]
    by_algorithm: Dict[str, int]
    expiry_timeline: List[Dict[str, Any]]  # For chart data


class BulkImportRequest(BaseModel):
    """Schema for bulk certificate import from CSV"""
    csv_data: str = Field(..., description="CSV data as string")
    skip_errors: bool = Field(True, description="Continue import on errors")


class BulkImportResponse(BaseModel):
    """Schema for bulk import response"""
    total_rows: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]]
    job_id: Optional[str] = None


class CertificateDelete(BaseModel):
    """Schema for certificate deletion"""
    certificate_ids: Optional[List[int]] = Field(None, description="List of certificate IDs to delete")
    serial_numbers: Optional[List[str]] = Field(None, description="List of serial numbers to delete")
    crypto_ids: Optional[List[str]] = Field(None, description="List of crypto IDs to delete")
    
    @field_validator('certificate_ids', 'serial_numbers', 'crypto_ids')
    @classmethod
    def validate_at_least_one(cls, v, info):
        """Ensure at least one deletion criteria is provided"""
        # This will be called for each field, so we check in the model_validator instead
        return v


class CertificateDetailsResponse(CertificateResponse):
    """Extended certificate details with additional information"""
    extensions: Optional[str] = None  # JSON string of certificate extensions
    raw_subject: Optional[str] = None
    raw_issuer: Optional[str] = None

# Made with Bob
