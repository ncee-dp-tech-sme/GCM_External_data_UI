"""
Scanner API endpoints for GCM Web UI.
Provides target generation and certificate import from CSV.

Created: 2026-06-02
Last Modified: 2026-06-02
Last Modified: 2026-07-25 - Added /run-scan endpoint that fetches SSL certificates from a target list.
Last Modified: 2026-07-25 - Added /run-scan-stream SSE endpoint with real-time progress and stop support.
                           - Added /stop-scan/{scan_id} endpoint to cancel a running stream scan.
Last Modified: 2026-07-25 - Added /ingest-scan-results endpoint for SSH key and TLS protocol ingest.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import io
import json
import asyncio

from app.database import get_db
from app.schemas.scanner import (
    TargetGenerationRequest,
    TargetGenerationResponse,
    CSVImportRequest,
    CSVImportResponse,
    CSVValidationResult,
    ScannerStats,
    ScanRequest,
    ScanResponse,
    ScanResult,
    StreamScanRequest,
    IngestScanResultsRequest,
    IngestScanResultsResponse,
)
from app.services.scanner_service import ScannerService
from app.services.auth_service import AuthService
from app.services.profile_service import ProfileService

router = APIRouter(tags=["Scanner"])

# In-memory stop-flag registry: scan_id -> {"stopped": bool}
# Only lives for the duration of the scan; keys are removed when done.
_scan_jobs: Dict[str, Dict[str, bool]] = {}


@router.post("/generate-targets", response_model=TargetGenerationResponse)
async def generate_targets(
    request: TargetGenerationRequest,
    db: Session = Depends(get_db)
) -> TargetGenerationResponse:
    """
    Generate scan target list as CSV.

    Expands IP ranges and port ranges into individual targets.
    Returns CSV content ready for download.
    """
    try:
        if not request.ip_ranges and not request.hosts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either ip_ranges or hosts must be provided"
            )

        if not request.ports:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ports must be provided"
            )

        target_count, csv_content, filename = ScannerService.generate_target_list(
            ip_ranges=request.ip_ranges,
            hosts=request.hosts,
            ports=request.ports,
            alias_prefix=request.alias_prefix or ""
        )

        return TargetGenerationResponse(
            target_count=target_count,
            csv_content=csv_content,
            filename=filename
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate targets: {str(e)}"
        )


@router.post("/validate-csv", response_model=Dict[str, Any])
async def validate_csv(
    file: UploadFile = File(..., description="CSV file to validate"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Validate CSV file for certificate import.

    Upload a CSV file to check for required fields and format issues.
    Returns validation results without importing.

    **File Format:**
    - Required columns: Alias, Certdata
    - Optional column: URI (optional)
    - Certdata should be base64-encoded certificate
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV file"
            )

        content = await file.read()
        csv_content = content.decode('utf-8')

        total_rows, valid_rows, validation_results = ScannerService.validate_csv_content(
            csv_content
        )

        return {
            "filename": file.filename,
            "total_rows": total_rows,
            "valid_rows": valid_rows,
            "invalid_rows": total_rows - valid_rows,
            "validation_results": validation_results
        }

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate CSV: {str(e)}"
        )


@router.post("/import-csv", response_model=CSVImportResponse)
async def import_csv(
    file: UploadFile = File(..., description="CSV file containing certificates to import"),
    db: Session = Depends(get_db)
) -> CSVImportResponse:
    """
    Import certificates from CSV file to GCM.

    Upload a CSV file to validate and import certificates into GCM.
    Uses the active profile for GCM connection.

    **File Format:**
    - Required columns: Alias, Certdata
    - Optional column: URI (optional)
    - Certdata should be base64-encoded certificate

    **Prerequisites:**
    - Active profile must be configured
    - User must be authenticated
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV file"
            )

        profile = ProfileService.get_active_profile(db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active profile configured. Please configure a profile first."
            )

        auth_headers = AuthService.get_active_profile_headers(db)

        content = await file.read()
        csv_content = content.decode('utf-8')

        total_rows, valid_rows, validation_results = ScannerService.validate_csv_content(
            csv_content
        )

        if valid_rows == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid rows found in CSV. Please check the file format."
            )

        profile_data = {
            "app_uri": profile.app_uri,
            "oidc_uri": profile.oidc_uri,
            "realm": profile.realm,
            "tenant_id": profile.tenant_id,
            "insecure": profile.insecure,
            "timeout": profile.timeout,
        }

        imported_count, failed_count, errors = ScannerService.import_certificates_from_csv(
            csv_content=csv_content,
            profile_data=profile_data,
            auth_headers=auth_headers,
        )

        return CSVImportResponse(
            total_rows=total_rows,
            valid_rows=valid_rows,
            invalid_rows=total_rows - valid_rows,
            imported_count=imported_count,
            failed_count=failed_count,
            errors=errors[:10] if errors else []
        )

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import certificates: {str(e)}"
        )


@router.post("/run-scan", response_model=ScanResponse)
async def run_scan(
    request: ScanRequest,
    db: Session = Depends(get_db)
) -> ScanResponse:
    """
    Scan a list of targets and retrieve their SSL certificates / service info.

    Accepts the CSV produced by /generate-targets (Alias, URI columns).
    Returns a certificates CSV ready to be passed to /import-csv.
    """
    try:
        if not request.targets_csv.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="targets_csv must not be empty"
            )

        total, scanned, failed, certs_csv, filename, raw_results = ScannerService.scan_targets(
            targets_csv=request.targets_csv,
            timeout=request.timeout or 5.0,
            insecure=request.insecure or False,
        )

        results = [
            ScanResult(
                alias=r["alias"],
                uri=r["uri"],
                success=r["success"],
                cert_b64=r.get("cert_b64"),
                tls_version=r.get("tls_version"),
                cipher_suite=r.get("cipher_suite"),
                cert_subject=r.get("cert_subject"),
                cert_issuer=r.get("cert_issuer"),
                cert_not_after=r.get("cert_not_after"),
                service=r.get("service"),
                service_banner=r.get("service_banner"),
                ssh_host_key_type=r.get("ssh_host_key_type"),
                ssh_host_key_fingerprint=r.get("ssh_host_key_fingerprint"),
                findings=r.get("findings") or [],
                error=r.get("error"),
            )
            for r in raw_results
        ]

        return ScanResponse(
            total_targets=total,
            scanned=scanned,
            failed=failed,
            certificates_csv=certs_csv,
            filename=filename,
            results=results,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {str(e)}"
        )


@router.post("/run-scan-stream")
async def run_scan_stream(request: StreamScanRequest):
    """
    Stream scan progress as Server-Sent Events.

    The client should open this with an EventSource (or fetch + ReadableStream).
    Events emitted:
      - scanning  : { type, index, total, alias, host, port }        — about to probe
      - progress  : { type, index, total, alias, host, port, result } — probe done
      - done      : { type, total, scanned, failed, stopped,
                      certificates_csv, filename, results }

    Pass a scan_id in the request body; use DELETE /stop-scan/{scan_id} to stop.
    """
    if not request.targets_csv.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="targets_csv must not be empty"
        )

    scan_id = request.scan_id
    stop_flag: Dict[str, bool] = {"stopped": False}
    _scan_jobs[scan_id] = stop_flag

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            gen = ScannerService.scan_targets_stream(
                targets_csv=request.targets_csv,
                timeout=request.timeout or 5.0,
                insecure=request.insecure or False,
                stop_flag=stop_flag,
            )
            # Run the synchronous generator in the thread pool so it doesn't
            # block the event loop between targets.
            while True:
                event = await loop.run_in_executor(None, next, gen, None)
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    break
                # Yield control back to the event loop between targets
                await asyncio.sleep(0)
        finally:
            _scan_jobs.pop(scan_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ingest-scan-results", response_model=IngestScanResultsResponse)
async def ingest_scan_results(
    request: IngestScanResultsRequest,
    db: Session = Depends(get_db)
) -> IngestScanResultsResponse:
    """
    Ingest SSH host keys and TLS protocol metadata from a completed scan into GCM.

    Accepts the raw results list produced by the streaming scan endpoint.
    Calls:
      - /v2/assets/ingest/crypto_objects/keys     (SSH host keys)
      - /v2/assets/ingest/crypto_objects/protocols (TLS version + ciphers)
    """
    profile = ProfileService.get_active_profile(db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active profile configured. Please configure a profile first."
        )

    auth_headers = AuthService.get_active_profile_headers(db)

    profile_data = {
        "app_uri": profile.app_uri,
        "oidc_uri": profile.oidc_uri,
        "realm": profile.realm,
        "tenant_id": profile.tenant_id,
        "insecure": profile.insecure,
        "timeout": profile.timeout,
    }

    results = [r.dict() for r in request.results]

    keys_imported, keys_failed, keys_errors = ScannerService.ingest_keys_from_results(
        results, profile_data, auth_headers
    )
    protocols_imported, protocols_failed, protocols_errors = ScannerService.ingest_protocols_from_results(
        results, profile_data, auth_headers
    )

    all_errors = keys_errors + protocols_errors

    return IngestScanResultsResponse(
        keys_imported=keys_imported,
        keys_failed=keys_failed,
        protocols_imported=protocols_imported,
        protocols_failed=protocols_failed,
        errors=all_errors,
    )


@router.delete("/stop-scan/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def stop_scan(scan_id: str):
    """
    Signal a running stream scan to stop after the current target.

    Returns 204 whether or not the scan_id is known (idempotent).
    """
    if scan_id in _scan_jobs:
        _scan_jobs[scan_id]["stopped"] = True


@router.get("/stats", response_model=ScannerStats)
async def get_scanner_stats(
    db: Session = Depends(get_db)
) -> ScannerStats:
    """
    Get scanner statistics.

    Returns basic statistics about scanner operations.
    """
    try:
        return ScannerStats(
            total_targets_generated=0,
            total_certificates_imported=0,
            last_generation_date=None,
            last_import_date=None
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scanner stats: {str(e)}"
        )


# Made with Bob
