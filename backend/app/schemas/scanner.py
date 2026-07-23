"""
Disconnected Scanner schemas for GCM Web UI.
Simplified implementation for target generation and CSV import.

Created: 2026-06-02
Last Modified: 2026-06-02
Last Modified: 2026-07-25 - Added ScanRequest / ScanResponse schemas for the run-scan endpoint
Last Modified: 2026-07-25 - Added StreamScanRequest, enriched ScanResult with service/protocol/SSH fields, ScanJobStatus
Last Modified: 2026-07-25 - Added findings field to ScanResult for crypto-weakness reporting
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class TargetGenerationRequest(BaseModel):
    """Request schema for generating scan targets."""
    
    ip_ranges: Optional[str] = Field(
        None,
        description="Comma-separated IP ranges in CIDR or wildcard format (e.g., 192.168.1.0/24,10.0.0.*)"
    )
    hosts: Optional[str] = Field(
        None,
        description="Comma-separated list of FQDNs (e.g., example.com,another.com)"
    )
    ports: str = Field(
        ...,
        description="Port range or list (e.g., 443-8443 or 443,8443)"
    )
    alias_prefix: Optional[str] = Field(
        "",
        description="Optional prefix for alias names"
    )
    
    @validator('ip_ranges', 'hosts')
    def at_least_one_target(cls, v, values):
        """Ensure at least one of ip_ranges or hosts is provided."""
        if not v and not values.get('ip_ranges') and not values.get('hosts'):
            raise ValueError('Either ip_ranges or hosts must be provided')
        return v


class TargetGenerationResponse(BaseModel):
    """Response schema for target generation."""
    
    target_count: int = Field(..., description="Number of targets generated")
    csv_content: str = Field(..., description="CSV content as string")
    filename: str = Field(..., description="Suggested filename")


class CSVImportRequest(BaseModel):
    """Request schema for importing certificates from CSV."""
    
    csv_content: str = Field(..., description="CSV file content as string")
    filename: str = Field(..., description="Original filename")
    validate_only: bool = Field(
        False,
        description="If true, only validate without importing"
    )


class CSVValidationResult(BaseModel):
    """Validation result for a single CSV row."""
    
    row_number: int
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    data: dict = {}


class CSVImportResponse(BaseModel):
    """Response schema for CSV import operation."""
    
    total_rows: int
    valid_rows: int
    invalid_rows: int
    imported_count: int = 0
    failed_count: int = 0
    validation_results: List[CSVValidationResult] = []
    errors: List[str] = []


class ScanRequest(BaseModel):
    """Request schema for scanning a list of targets to retrieve SSL certificates."""

    targets_csv: str = Field(
        ...,
        description="CSV content (Alias, URI) produced by generate-targets"
    )
    timeout: Optional[float] = Field(
        5.0,
        description="Per-target socket timeout in seconds"
    )
    insecure: Optional[bool] = Field(
        False,
        description="Allow self-signed / untrusted certificates on targets"
    )


class ScanResult(BaseModel):
    """Result for a single scanned target — enriched with service/protocol details."""

    alias: str
    uri: str
    success: bool
    # SSL/TLS fields
    cert_b64: Optional[str] = None
    tls_version: Optional[str] = None
    cipher_suite: Optional[str] = None
    cert_subject: Optional[str] = None
    cert_issuer: Optional[str] = None
    cert_not_after: Optional[str] = None
    # Service detection
    service: Optional[str] = None        # e.g. "tls", "ssh", "ftp", "smtp", "http", "unknown"
    service_banner: Optional[str] = None
    # SSH host key fields
    ssh_host_key_type: Optional[str] = None
    ssh_host_key_fingerprint: Optional[str] = None
    # Crypto-weakness findings
    findings: List[str] = []
    # Generic error
    error: Optional[str] = None


class ScanResponse(BaseModel):
    """Response schema for the run-scan endpoint."""

    total_targets: int
    scanned: int
    failed: int
    certificates_csv: str = Field(
        ...,
        description="Certificates CSV (Alias, Certdata, URI) ready for the import step"
    )
    filename: str
    results: List[ScanResult] = []


class StreamScanRequest(BaseModel):
    """Request for the SSE streaming scan endpoint."""

    targets_csv: str = Field(..., description="CSV content (Alias, URI)")
    timeout: Optional[float] = Field(5.0, description="Per-target socket timeout in seconds")
    insecure: Optional[bool] = Field(False, description="Allow self-signed certificates")
    scan_id: str = Field(..., description="Client-generated UUID used to cancel the scan")


class ScanJobStatus(BaseModel):
    """Tracks whether a running scan should be stopped."""

    stopped: bool = False


class ScannerStats(BaseModel):
    """Statistics for scanner operations."""

    total_targets_generated: int = 0
    total_certificates_imported: int = 0
    last_generation_date: Optional[str] = None
    last_import_date: Optional[str] = None


# Made with Bob