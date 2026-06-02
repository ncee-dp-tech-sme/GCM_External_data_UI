"""
2026-06-01T23:32:00Z - Added certificate schemas
2026-06-02T01:36:00Z - Added IT asset schemas
2026-06-02T02:20:00Z - Added scanner schemas
Pydantic schemas for request/response validation
"""

from app.schemas.profile import (
    ProfileBase,
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    ProfileListResponse
)
from app.schemas.auth import (
    PasswordAuthResponse,
    AuthorizationResponse
)
from app.schemas.user_management import (
    GCMUserRegistrationRequest,
    GCMUserRegistrationResponse
)
from app.schemas.certificate import (
    CertificateBase,
    CertificateUpload,
    CertificateResponse,
    CertificateListResponse,
    CertificateFilter,
    CertificateStats,
    BulkImportRequest as CertBulkImportRequest,
    BulkImportResponse as CertBulkImportResponse,
    CertificateDelete,
    CertificateDetailsResponse
)
from app.schemas.it_asset import (
    ITAssetBase,
    ITAssetCreate,
    ITAssetUpdate,
    ITAssetResponse,
    ITAssetListResponse,
    ITAssetFilter,
    ITAssetStats,
    BulkImportRequest as AssetBulkImportRequest,
    BulkImportResponse as AssetBulkImportResponse,
    SyncAssetsRequest,
    SyncAssetsResponse
)
from app.schemas.scanner import (
    TargetGenerationRequest,
    TargetGenerationResponse,
    CSVImportRequest,
    CSVValidationResult,
    CSVImportResponse,
    ScannerStats
)

__all__ = [
    "ProfileBase",
    "ProfileCreate",
    "ProfileUpdate",
    "ProfileResponse",
    "ProfileListResponse",
    "PasswordAuthResponse",
    "AuthorizationResponse",
    "GCMUserRegistrationRequest",
    "GCMUserRegistrationResponse",
    "CertificateBase",
    "CertificateUpload",
    "CertificateResponse",
    "CertificateListResponse",
    "CertificateFilter",
    "CertificateStats",
    "CertBulkImportRequest",
    "CertBulkImportResponse",
    "CertificateDelete",
    "CertificateDetailsResponse",
    "ITAssetBase",
    "ITAssetCreate",
    "ITAssetUpdate",
    "ITAssetResponse",
    "ITAssetListResponse",
    "ITAssetFilter",
    "ITAssetStats",
    "AssetBulkImportRequest",
    "AssetBulkImportResponse",
    "SyncAssetsRequest",
    "SyncAssetsResponse",
    "TargetGenerationRequest",
    "TargetGenerationResponse",
    "CSVImportRequest",
    "CSVValidationResult",
    "CSVImportResponse",
    "ScannerStats",
]

# Made with Bob
