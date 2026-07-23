"""
IT Asset Pydantic schemas for request/response validation.

Created: 2026-06-02
Last Modified: 2026-06-02
Changes:
- 2026-07-25: Added new GCM security fields to ITAssetResponse: total_violation,
  pqc_readiness_flag, exploitability_score, is_exception.
- 2026-07-25: Added confirmed GCM column fields to all schemas: protocol_version,
  servicename, databasename, databasetype, version, application_id, patch.
  Removed contains_classified_data, is_encrypted, total_pqc_violation (not in GCM payload).
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ITAssetBase(BaseModel):
    """Base schema for IT Asset with common fields."""
    uri: str = Field(..., description="Resource URI (required)")
    ip: Optional[str] = Field(None, description="IP address")
    hostname: Optional[str] = Field(None, description="Hostname")
    port: Optional[int] = Field(None, description="Port number")
    protocol: Optional[str] = Field(None, description="Protocol (e.g., TLS, TCP)")
    protocol_version: Optional[List[str]] = Field(None, description="Protocol versions (e.g., ['TLSv1.3', 'TLSv1.2'])")
    asset_type: Optional[str] = Field(None, description="Asset type (Database, Service, Application)")
    asset_sub_type: Optional[str] = Field(None, description="Asset sub-type (e.g., MySQL)")
    servicename: Optional[str] = Field(None, description="Service name")
    databasename: Optional[str] = Field(None, description="Database name")
    databasetype: Optional[str] = Field(None, description="Database type")
    version: Optional[str] = Field(None, description="Software version")
    application_id: Optional[str] = Field(None, description="GCM application ID")
    patch: Optional[str] = Field(None, description="Patch level")
    owner: Optional[str] = Field(None, description="Asset owner")
    tech_contacts: Optional[List[str]] = Field(None, description="Technical contacts")
    environment: Optional[str] = Field(None, description="Environment (Staging, Production)")
    location: Optional[str] = Field(None, description="Physical/logical location")
    network: Optional[str] = Field(None, description="Network zone")
    mission_criticality: Optional[int] = Field(None, description="Mission criticality score")
    internet_facing: Optional[str] = Field(None, description="Internet facing (DEFAULT, UNKNOWN, TRUE, FALSE)")
    total_violation: Optional[int] = Field(None, description="Total violations")
    pqc_readiness_flag: Optional[str] = Field(None, description="PQC readiness (PQC_SAFE, PQC_UNSAFE)")
    exploitability_score: Optional[float] = Field(None, description="Exploitability score")
    is_exception: Optional[str] = Field(None, description="Exception flag (TRUE/FALSE)")
    extensions: Optional[Dict[str, Any]] = Field(None, description="Custom attributes")


class ITAssetCreate(ITAssetBase):
    """Schema for creating a new IT asset."""
    ip: str = Field(..., description="IP address (required for creation)")
    hostname: str = Field(..., description="Hostname (required for creation)")
    port: int = Field(..., description="Port number (required for creation)")
    asset_type: str = Field(..., description="Asset type (required for creation)")


class ITAssetUpdate(BaseModel):
    """Schema for updating an existing IT asset (all fields optional)."""
    uri: Optional[str] = None
    ip: Optional[str] = None
    hostname: Optional[str] = None
    port: Optional[int] = None
    protocol: Optional[str] = None
    protocol_version: Optional[str] = None
    asset_type: Optional[str] = None
    asset_sub_type: Optional[str] = None
    servicename: Optional[str] = None
    databasename: Optional[str] = None
    databasetype: Optional[str] = None
    version: Optional[str] = None
    application_id: Optional[str] = None
    patch: Optional[str] = None
    owner: Optional[str] = None
    tech_contacts: Optional[List[str]] = None
    environment: Optional[str] = None
    location: Optional[str] = None
    network: Optional[str] = None
    mission_criticality: Optional[int] = None
    internet_facing: Optional[str] = None
    total_violation: Optional[int] = None
    pqc_readiness_flag: Optional[str] = None
    exploitability_score: Optional[float] = None
    is_exception: Optional[str] = None
    extensions: Optional[Dict[str, Any]] = None


class ITAssetResponse(ITAssetBase):
    """Schema for IT asset response."""
    id: int
    asset_id: Optional[str] = None
    discovery_sources: Optional[List[str]] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    object_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_synced: Optional[datetime] = None

    class Config:
        from_attributes = True


class ITAssetListResponse(BaseModel):
    """Schema for paginated IT asset list response."""
    assets: List[ITAssetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ITAssetFilter(BaseModel):
    """Schema for filtering IT assets."""
    asset_type: Optional[str] = None
    environment: Optional[str] = None
    location: Optional[str] = None
    owner: Optional[str] = None
    internet_facing: Optional[str] = None
    search: Optional[str] = Field(None, description="Search by URI, hostname, or IP")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: Optional[str] = Field("asc", description="Sort order (asc/desc)")


class ITAssetStats(BaseModel):
    """Schema for IT asset statistics."""
    total_assets: int
    by_type: Dict[str, int]
    by_environment: Dict[str, int]
    by_location: Dict[str, int]
    internet_facing_count: int
    mission_critical_count: int


class BulkImportRequest(BaseModel):
    """Schema for bulk import request."""
    assets: List[ITAssetCreate]


class BulkImportResponse(BaseModel):
    """Schema for bulk import response."""
    success_count: int
    error_count: int
    errors: List[Dict[str, Any]]


class SyncAssetsRequest(BaseModel):
    """Schema for sync assets request."""
    asset_type: Optional[str] = Field("services", description="Asset type to sync (services, applications, databases)")
    page_size: int = Field(100, ge=1, le=1000, description="Page size for sync")


class SyncAssetsResponse(BaseModel):
    """Schema for sync assets response."""
    synced_count: int
    created_count: int
    updated_count: int
    error_count: int
    errors: List[str]

# Made with Bob
