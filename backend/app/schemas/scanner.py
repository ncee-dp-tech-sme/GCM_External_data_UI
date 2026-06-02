"""
Disconnected Scanner schemas for GCM Web UI.
Simplified implementation for target generation and CSV import.

Created: 2026-06-02
Last Modified: 2026-06-02
"""

from typing import Optional, List
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


class ScannerStats(BaseModel):
    """Statistics for scanner operations."""
    
    total_targets_generated: int = 0
    total_certificates_imported: int = 0
    last_generation_date: Optional[str] = None
    last_import_date: Optional[str] = None


# Made with Bob