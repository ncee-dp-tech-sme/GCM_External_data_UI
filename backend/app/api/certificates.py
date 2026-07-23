"""
2026-06-01T23:33:00Z - Initial creation of certificate API endpoints
Certificate management API endpoints
Handles CRUD operations for GCM certificate inventory
2026-07-25T00:04:00Z - Added /debug-gcm probe endpoint for diagnosing GCM connectivity and filter issues.
2026-07-25T12:30:00Z - Added /sync/all endpoint that paginates GCM until exhausted.
2026-07-29T00:00:00Z - Added object_type query parameter to list_certificates endpoint.
"""

from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import math
import json

from app.database import get_db
from app.schemas.certificate import (
    CertificateUpload,
    CertificateResponse,
    CertificateListResponse,
    CertificateFilter,
    CertificateStats,
    CertificateDelete,
    CertificateDetailsResponse
)
from app.services.certificate_service import CertificateService

router = APIRouter()


@router.post("/sync", status_code=status.HTTP_200_OK)
def sync_certificates(
    page_number: int = Query(1, ge=1, description="Page number to sync"),
    page_size: int = Query(100, ge=1, le=1000, description="Certificates per page"),
    db: Session = Depends(get_db)
):
    """
    Sync certificates from GCM API to local database
    
    This endpoint fetches certificates from GCM and stores them locally
    for faster querying and offline access.
    
    - **page_number**: Page number to fetch (default: 1)
    - **page_size**: Number of certificates per page (default: 100, max: 1000)
    """
    result = CertificateService.sync_certificates_from_gcm(db, page_number, page_size)
    return result


@router.post("/sync/all", status_code=status.HTTP_200_OK)
def sync_all_certificates(
    page_size: int = Query(100, ge=1, le=500, description="Certificates per GCM page"),
    db: Session = Depends(get_db)
):
    """
    Sync ALL certificates from GCM by iterating pages until none remain.
    The caller does not need to know the total count in advance.
    """
    result = CertificateService.sync_all_certificates_from_gcm(db, page_size)
    return result


@router.get("/debug-gcm", status_code=status.HTTP_200_OK)
def debug_gcm_probe(db: Session = Depends(get_db)):
    """
    Diagnostic probe: fires one request using the same auth path as sync,
    captures exact wire headers, and returns the GCM response.
    Remove before deploying to production.
    """
    from app.services.certificate_service import CertificateService
    import requests as _requests

    # Build client + headers exactly as sync does
    client, auth_headers = CertificateService._get_gcm_client_and_headers(db)

    # Intercept the single outgoing request to record its exact wire headers
    captured: dict = {}

    class CapturingSession(_requests.Session):
        def send(self, request, **kwargs):
            captured.update(dict(request.headers))
            return super().send(request, **kwargs)

    client.session = CapturingSession()

    bare_body = {"page_number": 1, "page_size": 5, "filter": "", "sort_by": "", "search_by": ""}
    resp = CertificateService._gcm_post(client, auth_headers, "ibm/assetinventory/api/v1/assets/crypto_objects/all", bare_body)
    try:
        resp_body = resp.json()
    except Exception:
        resp_body = resp.text[:500]

    # Redact Authorization to first 20 chars
    redacted = {
        k: (v[:20] + "...") if k.lower() == "authorization" and len(v) > 20 else v
        for k, v in captured.items()
    }

    return {
        "exact_wire_headers": redacted,
        "gcm_status": resp.status_code,
        "gcm_response": resp_body,
    }


@router.get("/", response_model=CertificateListResponse)
def list_certificates(
    search: Optional[str] = Query(None, description="Search by alias, URI, or serial number"),
    uri: Optional[str] = Query(None, description="Filter by URI"),
    issuer_cn: Optional[str] = Query(None, description="Filter by issuer CN"),
    is_expired: Optional[bool] = Query(None, description="Filter by expiry status"),
    expiring_days: Optional[int] = Query(None, ge=0, description="Filter certificates expiring within N days"),
    object_type: Optional[str] = Query(None, description="Filter by crypto object type (Certificate, Key, Protocol)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    db: Session = Depends(get_db)
):
    """
    List certificates with filtering and pagination
    
    Returns a paginated list of certificates from the local database.
    Use the /sync endpoint first to fetch certificates from GCM.
    
    **Filters:**
    - **search**: Search across alias, URI, serial number, and subject CN
    - **uri**: Filter by specific URI
    - **issuer_cn**: Filter by issuer common name
    - **is_expired**: Filter by expiry status (true/false)
    - **expiring_days**: Show certificates expiring within N days
    
    **Pagination:**
    - **page**: Page number (starts at 1)
    - **page_size**: Items per page (max 100)
    
    **Sorting:**
    - **sort_by**: Field to sort by (default: created_at)
    - **sort_order**: asc or desc (default: desc)
    """
    filters = CertificateFilter(
        search=search,
        uri=uri,
        issuer_cn=issuer_cn,
        is_expired=is_expired,
        expiring_days=expiring_days,
        object_type=object_type,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    certificates, total = CertificateService.list_certificates(db, filters)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return CertificateListResponse(
        certificates=[CertificateResponse.model_validate(cert) for cert in certificates],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{certificate_id}", response_model=CertificateDetailsResponse)
def get_certificate(
    certificate_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific certificate
    
    Returns complete certificate details including extensions and metadata.
    
    - **certificate_id**: Database ID (integer) or crypto_id (UUID string)
    """
    cert = CertificateService.get_certificate_by_id_or_crypto_id(db, certificate_id)
    return CertificateDetailsResponse.model_validate(cert)


@router.post("/", response_model=CertificateResponse, status_code=status.HTTP_201_CREATED)
def upload_certificate(
    cert_upload: CertificateUpload,
    db: Session = Depends(get_db)
):
    """
    Upload a certificate to GCM
    
    Uploads a certificate file (PEM or DER format) to GCM and associates it
    with the specified URI.
    
    - **cert_file_base64**: Base64-encoded certificate file content
    - **uri**: URI where the certificate is used (e.g., 'https://example.com:443')
    - **alias**: Optional alias (auto-generated if not provided)
    """
    cert = CertificateService.upload_certificate(db, cert_upload)
    return CertificateResponse.model_validate(cert)


@router.delete("/", status_code=status.HTTP_200_OK)
def delete_certificates(
    delete_request: CertificateDelete,
    db: Session = Depends(get_db)
):
    """
    Delete certificates from GCM and local database
    
    Deletes certificates by ID, serial number, or crypto ID.
    At least one deletion criteria must be provided.
    
    - **certificate_ids**: List of database certificate IDs
    - **serial_numbers**: List of certificate serial numbers
    - **crypto_ids**: List of GCM crypto object IDs
    """
    result = CertificateService.delete_certificates(db, delete_request)
    return result


@router.get("/stats/summary", response_model=CertificateStats)
def get_certificate_statistics(db: Session = Depends(get_db)):
    """
    Get certificate statistics for dashboard
    
    Returns aggregated statistics including:
    - Total certificate count
    - Expired certificates count
    - Certificates expiring soon (within 30 days)
    - Distribution by issuer
    - Distribution by algorithm
    - Expiry timeline for next 12 months
    """
    stats = CertificateService.get_statistics(db)
    return stats


# Made with Bob