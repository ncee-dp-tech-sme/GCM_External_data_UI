"""
Scanner API endpoints for GCM Web UI.
Provides target generation and certificate import from CSV.

Created: 2026-06-02
Last Modified: 2026-06-02
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, Any
import io

from app.database import get_db
from app.schemas.scanner import (
    TargetGenerationRequest,
    TargetGenerationResponse,
    CSVImportRequest,
    CSVImportResponse,
    CSVValidationResult,
    ScannerStats
)
from app.services.scanner_service import ScannerService
from app.services.auth_service import AuthService
from app.services.profile_service import ProfileService

router = APIRouter(tags=["Scanner"])


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
        # Validate inputs
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
        
        # Generate target list
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
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV file"
            )
        
        # Read file content
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        # Validate CSV content
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
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a CSV file"
            )
        
        # Get active profile
        profile = ProfileService.get_active_profile(db)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active profile configured. Please configure a profile first."
            )
        
        # Get auth headers — routes exclusively through the active auth method
        auth_headers = AuthService.get_active_profile_headers(db)

        # Read file content
        content = await file.read()
        csv_content = content.decode('utf-8')

        # Validate CSV first
        total_rows, valid_rows, validation_results = ScannerService.validate_csv_content(
            csv_content
        )

        if valid_rows == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid rows found in CSV. Please check the file format."
            )

        # Import certificates
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
            errors=errors[:10] if errors else []  # Limit to first 10 errors
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


@router.get("/stats", response_model=ScannerStats)
async def get_scanner_stats(
    db: Session = Depends(get_db)
) -> ScannerStats:
    """
    Get scanner statistics.
    
    Returns basic statistics about scanner operations.
    """
    try:
        # For now, return placeholder stats
        # In a full implementation, these would come from a database
        return ScannerStats(
            total_targets_generated=0,
            total_certificates_imported=0,
            last_generation_time=None,
            last_import_time=None
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scanner stats: {str(e)}"
        )


# Made with Bob