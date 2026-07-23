"""
2026-06-01T23:32:00Z - Initial creation of certificate service
2026-06-02T01:27:00Z - Modified upload_certificate to sync from GCM instead of creating local entry
2026-06-02T17:36:00Z - Fixed delete_certificates to use OR condition for serial_numbers and crypto_ids filters
2026-07-23T00:00:00Z - Added API key authentication support via AuthService.get_active_profile_headers().
                       _get_gcm_client_and_headers() replaces _get_authz_client() as the internal
                       entry point; it routes exclusively through either OIDC or API key auth.
2026-07-24T00:00:00Z - Fixed NoneType crash: guard oidc_uri with (or "") before rstrip() so api_key
                       profiles (where oidc_uri is None) no longer cause a 500 on sync.
2026-07-25T00:00:00Z - Moved logger to module level; added DEBUG logging around GCM requests/responses.
2026-07-25T00:01:00Z - Treat GCM HTTP 400 + error_code "0x00000000" as an empty result (GCM quirk).
2026-07-25T00:02:00Z - Fixed sync endpoint: use /crypto_objects/all with Certificate filter instead of
                       /crypto_objects/certificates (which does not exist). Added crypto_objects key
                       to response fallback chain.
2026-07-25T00:03:00Z - Replaced columns:["all"] with specific field list that GCM accepts.
2026-07-25T00:05:00Z - Fixed response key: /crypto_objects/all returns 'all_crypto_objects', not 'crypto_objects'.
2026-07-25T00:10:00Z - Extended sync body columns list and _sync_certificate_to_db to capture all GCM
                       fields: certificate_validity_period, is_short_lived, san, is_exception,
                       group_updated_at, gcm_created_at, gcm_updated_at.
2026-07-25T12:00:00Z - Removed columns list and Certificate filter from sync body: GCM returns error 13
                       when either is present; omitting them (as debug-gcm probe does) fixes the issue.
2026-07-25T12:30:00Z - Added sync_all_certificates_from_gcm() that paginates until GCM returns fewer
                       records than page_size so the user does not need to know the total up front.
Certificate service for managing GCM certificate inventory
Wraps existing Python modules and provides database operations
"""

import sys
import os
import json
import logging
import base64
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from fastapi import HTTPException, status

# Add parent directory to path for importing GCM modules
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models.certificate import Certificate
from app.schemas.certificate import (
    CertificateUpload,
    CertificateResponse,
    CertificateFilter,
    CertificateStats,
    CertificateDelete
)
from app.services.profile_service import ProfileService
from app.services.auth_service import AuthService
from app.models.profile import AUTH_METHOD_API_KEY

# Import GCM modules
from common.oidc_authz_client import AuthzClient

logger = logging.getLogger(__name__)


class CertificateService:
    """Service for managing GCM certificate inventory"""

    @staticmethod
    def _get_gcm_client_and_headers(db: Session) -> Tuple[AuthzClient, dict]:
        """
        Get an AuthzClient and the ready-to-use auth headers for the active profile.

        Branches exclusively on auth_method:
          - 'oidc':    obtains an OIDC access token, calls the GCM authorization API,
                       returns Bearer headers.
          - 'api_key': validates the API key and returns Authorization + token_type headers.
                       The GCM authorization API call is skipped entirely.

        Returns:
            Tuple of (AuthzClient, auth_headers dict)
        """
        profile = ProfileService.get_active_profile(db)

        app_uri = profile.app_uri.rstrip("/")
        # oidc_uri is None for api_key profiles; AuthzClient requires a non-empty value
        # so fall back to app_uri as a placeholder (it is never used in the api_key path).
        oidc_uri = (profile.oidc_uri or app_uri).rstrip("/")

        config = {
            "app_uri": app_uri,
            "oidc_uri": oidc_uri,
            "realm": profile.realm,
            "verify_ssl": not profile.insecure,
            "timeout": profile.timeout,
            "user_agent": profile.user_agent,
        }
        client = AuthzClient(config)

        if profile.auth_method == AUTH_METHOD_API_KEY:
            # API key path — no OIDC token exchange, no authorization API call
            auth_headers = AuthService.build_api_key_headers(profile)
            return client, auth_headers

        # OIDC path — no API key code runs
        access_token = AuthService.get_active_profile_token(db)
        tenant_id = profile.tenant_id or ""
        auth_resp = client.call_authorization_api(access_token, tenant_id=tenant_id)
        logger.debug("GCM authz API — status: %s  body: %.300s", auth_resp.status_code, auth_resp.text)
        if not auth_resp.ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"GCM authorization failed: {auth_resp.text}",
            )
        return client, {"Authorization": f"Bearer {access_token}"}
    
    @staticmethod
    def _gcm_post(client: AuthzClient, auth_headers: dict, path: str, body: dict):
        """
        POST to a GCM API path with the pre-built auth_headers.

        Uses client.session directly so that the correct Authorization header
        (either 'Bearer <token>' for OIDC or raw api_key for API key auth)
        is sent verbatim without any overriding by AuthzClient internals.
        """
        url = f"{client.app_uri}/{path.lstrip('/')}"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
        }
        headers.update(auth_headers)
        return client.session.post(
            url,
            headers=headers,
            json=body,
            verify=client.verify_ssl,
            timeout=client.timeout,
        )

    @staticmethod
    def sync_certificates_from_gcm(
        db: Session,
        page_number: int = 1,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Sync certificates from GCM API to local database
        
        Args:
            db: Database session
            page_number: Page number to fetch
            page_size: Number of certificates per page
            
        Returns:
            Dict with sync statistics
        """
        client, auth_headers = CertificateService._get_gcm_client_and_headers(db)

        # Build request body — omit columns and filter; GCM returns error 13 when
        # either is present (confirmed: debug-gcm probe with bare body succeeds).
        body = {
            "page_number": page_number,
            "page_size": page_size,
            "filter": "",
            "search_by": "",
            "sort_by": "",
        }

        # Call GCM API — /all endpoint with filter is the correct path
        list_path = "ibm/assetinventory/api/v1/assets/crypto_objects/all"
        logger.debug("GCM sync request — URL: %s/%s  body: %s", client.app_uri, list_path, json.dumps(body))
        logger.debug("GCM sync request auth header present: %s", "Authorization" in auth_headers)
        resp = CertificateService._gcm_post(client, auth_headers, list_path, body)
        logger.debug("GCM sync response — status: %s  body: %.500s", resp.status_code, resp.text)
        
        if not resp.ok:
            # GCM returns HTTP 400 with error_code "0x00000000" to signal an empty
            # result set ("HPDBA0521I Successful completion").  Treat it as zero
            # certificates rather than a gateway error.
            try:
                err = resp.json()
            except Exception:
                err = {}
            if resp.status_code == 400 and err.get("error_code") == "0x00000000":
                logger.debug("GCM returned 400/0x00000000 (empty result) — treating as no certificates")
                return {
                    "total_fetched": 0,
                    "synced": 0,
                    "updated": 0,
                    "errors": [],
                    "page": page_number,
                    "page_size": page_size,
                    "gcm_response_keys": list(err.keys()),
                    "gcm_total_count": 0,
                    "debug_info": {"gcm_message": err.get("error_message", "")},
                }
            logger.error("GCM cert sync failed — status: %s  body: %s", resp.status_code, resp.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch certificates from GCM: {resp.text}"
            )
        
        data = resp.json()
        logger.debug("GCM API response keys: %s", list(data.keys()))
        
        # /crypto_objects/all returns 'all_crypto_objects'
        certificates = data.get("all_crypto_objects", [])
        if not certificates:
            certificates = data.get("crypto_objects", [])
        if not certificates:
            certificates = data.get("crypto_certificates", [])
        if not certificates:
            certificates = data.get("data", [])
        if not certificates:
            certificates = data.get("certificates", [])
        if not certificates:
            certificates = data.get("results", [])
        
        # Sync to database
        synced = 0
        updated = 0
        errors = []
        
        for cert_data in certificates:
            try:
                cert = CertificateService._sync_certificate_to_db(db, cert_data)
                if cert:
                    synced += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append({
                    "crypto_id": cert_data.get("crypto_id"),
                    "error": str(e)
                })
        
        db.commit()
        
        return {
            "total_fetched": len(certificates),
            "synced": synced,
            "updated": updated,
            "errors": errors,
            "page": page_number,
            "page_size": page_size,
            "gcm_response_keys": list(data.keys()),
            "gcm_total_count": data.get("total_count", data.get("total", 0)),
            "debug_info": {
                "has_data_key": "data" in data,
                "has_certificates_key": "certificates" in data,
                "has_results_key": "results" in data,
                "response_sample": str(data)[:200]
            }
        }
    
    @staticmethod
    def sync_all_certificates_from_gcm(
        db: Session,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Sync all certificates from GCM by iterating pages until exhausted.
        Stops when a page returns fewer records than page_size.
        """
        client, auth_headers = CertificateService._get_gcm_client_and_headers(db)
        list_path = "ibm/assetinventory/api/v1/assets/crypto_objects/all"

        total_fetched = 0
        total_synced = 0
        total_updated = 0
        all_errors: list = []
        page = 1

        while True:
            body = {
                "page_number": page,
                "page_size": page_size,
                "filter": "",
                "search_by": "",
                "sort_by": "",
            }
            logger.debug("GCM sync-all page %d — %s", page, list_path)
            resp = CertificateService._gcm_post(client, auth_headers, list_path, body)
            logger.debug("GCM sync-all page %d — status: %s  body: %.300s", page, resp.status_code, resp.text)

            if not resp.ok:
                try:
                    err = resp.json()
                except Exception:
                    err = {}
                # GCM signals an empty page with 400 + error_code 0x00000000
                if resp.status_code == 400 and err.get("error_code") == "0x00000000":
                    logger.debug("GCM returned 400/0x00000000 on page %d — treating as end of results", page)
                    break
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to fetch certificates from GCM (page {page}): {resp.text}",
                )

            data = resp.json()
            certificates = (
                data.get("all_crypto_objects")
                or data.get("crypto_objects")
                or data.get("crypto_certificates")
                or data.get("data")
                or data.get("certificates")
                or data.get("results")
                or []
            )

            for cert_data in certificates:
                try:
                    cert = CertificateService._sync_certificate_to_db(db, cert_data)
                    if cert:
                        total_synced += 1
                    else:
                        total_updated += 1
                except Exception as e:
                    all_errors.append({"crypto_id": cert_data.get("crypto_id"), "error": str(e)})

            db.commit()
            total_fetched += len(certificates)
            logger.debug("GCM sync-all page %d — fetched %d, running total %d", page, len(certificates), total_fetched)

            # Stop when this page was not full — no more pages left
            if len(certificates) < page_size:
                break

            page += 1

        return {
            "total_fetched": total_fetched,
            "synced": total_synced,
            "updated": total_updated,
            "errors": all_errors,
            "pages": page,
        }

    @staticmethod
    def _parse_bool(value: Any) -> bool:
        """
        Parse boolean value from GCM API
        GCM returns booleans as strings ('TRUE', 'FALSE') or actual booleans
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.upper() in ('TRUE', '1', 'YES')
        return bool(value)
    
    @staticmethod
    def _sync_certificate_to_db(db: Session, cert_data: Dict[str, Any]) -> Optional[Certificate]:
        """
        Sync a single certificate to database
        Maps GCM API fields to database model
        
        Returns:
            Certificate if newly created, None if updated
        """
        crypto_id = cert_data.get("crypto_id")
        if not crypto_id:
            return None
        
        # Check if certificate exists
        cert = db.query(Certificate).filter(Certificate.crypto_id == crypto_id).first()
        is_new = cert is None
        
        if is_new:
            cert = Certificate()
        
        # Map GCM API fields to database fields
        cert.crypto_id = crypto_id
        
        # Alias - GCM uses 'crypto_object_name'
        cert.alias = cert_data.get("crypto_object_name") or cert_data.get("alias")
        
        # Serial number - GCM uses 'certificate_serial_number'
        cert.serial_number = cert_data.get("certificate_serial_number") or cert_data.get("serial_number")
        
        # Subject and Issuer
        cert.subject = cert_data.get("subject")
        cert.issuer = cert_data.get("issuer")
        
        # Extract CN from subject/issuer if available
        if cert.subject and "CN=" in cert.subject:
            try:
                cert.subject_cn = cert.subject.split("CN=")[1].split(",")[0]
            except:
                pass
        
        if cert.issuer and "CN=" in cert.issuer:
            try:
                cert.issuer_cn = cert.issuer.split("CN=")[1].split(",")[0]
            except:
                pass
        
        # Parse dates - GCM uses 'not_before' and 'not_after'
        not_before = cert_data.get("not_before") or cert_data.get("valid_from")
        if not_before:
            try:
                cert.valid_from = datetime.fromisoformat(not_before.replace("Z", "+00:00"))
            except:
                pass
        
        not_after = cert_data.get("not_after") or cert_data.get("valid_to")
        if not_after:
            try:
                cert.valid_to = datetime.fromisoformat(not_after.replace("Z", "+00:00"))
                # Calculate expiry
                now = datetime.now(cert.valid_to.tzinfo)
                cert.is_expired = cert.valid_to < now
                cert.days_until_expiry = (cert.valid_to - now).days
            except:
                pass
        
        # Cryptographic details - GCM uses different field names
        cert.public_key_algorithm = cert_data.get("key_algorithm") or cert_data.get("public_key_algorithm")
        cert.signature_algorithm = cert_data.get("hashing_algorithm") or cert_data.get("signature_algorithm")
        cert.key_size = cert_data.get("key_length") or cert_data.get("key_size")
        
        # Fingerprint and version
        cert.fingerprint_sha256 = cert_data.get("fingerprint_sha256")
        cert.version = cert_data.get("format_version") or cert_data.get("version")
        
        # Handle relationships
        relationships = cert_data.get("relationships", [])
        if relationships:
            first_rel = relationships[0]
            asset_ids = first_rel.get("asset_identifiers", {})
            cert.uri = asset_ids.get("uri")
            cert.asset_type = first_rel.get("asset_type")
        
        # Store extensions as JSON
        if cert_data.get("extensions"):
            cert.extensions = json.dumps(cert_data["extensions"])
        
        # GCM-specific fields
        cert.certificate_status = cert_data.get("certificate_status")
        cert.is_ca_certificate = CertificateService._parse_bool(cert_data.get("is_ca_certificate"))
        cert.is_revoked = CertificateService._parse_bool(cert_data.get("is_revoked"))
        cert.pqc_readiness_flag = cert_data.get("pqc_readiness_flag")
        cert.total_violation = cert_data.get("total_violation")
        cert.total_pqc_violation = cert_data.get("total_pqc_violation")
        cert.exploitability_score = cert_data.get("exploitability_score")
        cert.object_status = cert_data.get("object_status")
        cert.auto_renewal_status = cert_data.get("auto_renewal_status")

        # Additional boolean flags
        cert.is_short_lived = CertificateService._parse_bool(cert_data.get("is_short_lived")) if cert_data.get("is_short_lived") is not None else None
        cert.is_exception = CertificateService._parse_bool(cert_data.get("is_exception")) if cert_data.get("is_exception") is not None else None

        # Validity period string
        cert.certificate_validity_period = cert_data.get("certificate_validity_period")

        # Subject Alternative Names — store as JSON
        san = cert_data.get("san")
        if san is not None:
            cert.san = json.dumps(san)

        # Discovery and tracking
        if cert_data.get("discovery_sources"):
            cert.discovery_sources = json.dumps(cert_data["discovery_sources"])

        # Parse first_seen and last_seen dates
        first_seen = cert_data.get("first_seen")
        if first_seen:
            try:
                cert.first_seen = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
            except:
                pass

        last_seen = cert_data.get("last_seen")
        if last_seen:
            try:
                cert.last_seen = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            except:
                pass

        # GCM-side created_at / updated_at / group_updated_at
        for attr, key in [
            ("gcm_created_at", "created_at"),
            ("gcm_updated_at", "updated_at"),
            ("group_updated_at", "group_updated_at"),
        ]:
            raw = cert_data.get(key)
            if raw:
                try:
                    setattr(cert, attr, datetime.fromisoformat(raw.replace("Z", "+00:00")))
                except:
                    pass

        cert.last_synced_at = datetime.utcnow()
        
        if is_new:
            db.add(cert)
        
        return cert if is_new else None
    
    @staticmethod
    def list_certificates(
        db: Session,
        filters: CertificateFilter
    ) -> Tuple[List[Certificate], int]:
        """
        List certificates with filtering and pagination
        
        Returns:
            Tuple of (certificates, total_count)
        """
        query = db.query(Certificate)
        
        # Apply filters
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Certificate.alias.ilike(search_term),
                    Certificate.uri.ilike(search_term),
                    Certificate.serial_number.ilike(search_term),
                    Certificate.subject_cn.ilike(search_term),
                    Certificate.crypto_id.ilike(search_term),
                    Certificate.public_key_algorithm.ilike(search_term),
                    Certificate.signature_algorithm.ilike(search_term),
                    Certificate.pqc_readiness_flag.ilike(search_term),
                    Certificate.issuer_cn.ilike(search_term),
                    Certificate.subject.ilike(search_term),
                    Certificate.issuer.ilike(search_term)
                )
            )
        
        if filters.uri:
            query = query.filter(Certificate.uri.ilike(f"%{filters.uri}%"))
        
        if filters.issuer_cn:
            query = query.filter(Certificate.issuer_cn.ilike(f"%{filters.issuer_cn}%"))
        
        if filters.is_expired is not None:
            query = query.filter(Certificate.is_expired == filters.is_expired)
        
        if filters.expiring_days:
            query = query.filter(
                and_(
                    Certificate.is_expired == False,
                    Certificate.days_until_expiry <= filters.expiring_days,
                    Certificate.days_until_expiry >= 0
                )
            )
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        sort_field = getattr(Certificate, filters.sort_by, Certificate.created_at)
        if filters.sort_order == "asc":
            query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(sort_field.desc())
        
        # Apply pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)
        
        certificates = query.all()
        
        return certificates, total
    
    @staticmethod
    def get_certificate(db: Session, cert_id: int) -> Certificate:
        """Get a certificate by database ID"""
        cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
        if not cert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Certificate with ID {cert_id} not found"
            )
        return cert
    
    @staticmethod
    def get_certificate_by_id_or_crypto_id(db: Session, identifier: str) -> Certificate:
        """
        Get a certificate by database ID or crypto_id
        
        Args:
            db: Database session
            identifier: Either database ID (integer as string) or crypto_id (UUID string)
            
        Returns:
            Certificate
        """
        # Try to parse as integer (database ID)
        try:
            cert_id = int(identifier)
            cert = db.query(Certificate).filter(Certificate.id == cert_id).first()
            if cert:
                return cert
        except ValueError:
            # Not an integer, treat as crypto_id
            pass
        
        # Try as crypto_id (UUID string)
        cert = db.query(Certificate).filter(Certificate.crypto_id == identifier).first()
        if not cert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Certificate with ID or crypto_id '{identifier}' not found"
            )
        return cert
    
    @staticmethod
    def upload_certificate(
        db: Session,
        cert_upload: CertificateUpload
    ) -> Certificate:
        """
        Upload a certificate to GCM and sync back to database
        
        This method:
        1. Uploads the certificate to GCM API
        2. Syncs the certificate back from GCM to get complete data
        3. Returns the synced certificate from local database
        
        Args:
            db: Database session
            cert_upload: Certificate upload data
            
        Returns:
            Synced certificate from database
        """
        client, auth_headers = CertificateService._get_gcm_client_and_headers(db)

        # Parse URI
        uri = cert_upload.uri.strip()
        alias = cert_upload.alias or CertificateService._generate_alias(uri)

        # Build ingest body
        body = {
            "crypto_object_certs": {
                "cert_data": cert_upload.cert_file_base64,
                "crypto_object_alias": alias,
                "relationships": [
                    {
                        "asset_identifiers": {"uri": uri},
                        "asset_type": "IT_ASSET",
                    }
                ],
                "tag_ids": [],
            }
        }

        # POST to GCM
        ingest_path = "ibm/assetinventory/api/v1/assets/ingest/crypto_objects/certificate_from_file"
        resp = CertificateService._gcm_post(client, auth_headers, ingest_path, body)
        
        if not resp.ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to upload certificate to GCM: {resp.text}"
            )
        
        # Parse response to get crypto_id or serial number for syncing
        try:
            resp_data = resp.json()
        except:
            resp_data = {}
        
        # Sync certificates from GCM to get the uploaded certificate with full data
        # We'll sync the first page which should contain the newly uploaded certificate
        sync_result = CertificateService.sync_certificates_from_gcm(db, page_number=1, page_size=100)
        
        # Try to find the certificate by alias or URI
        cert = db.query(Certificate).filter(
            or_(
                Certificate.alias == alias,
                Certificate.uri == uri
            )
        ).order_by(Certificate.created_at.desc()).first()
        
        if not cert:
            # Fallback: create a minimal entry if sync didn't capture it yet
            cert = Certificate(
                alias=alias,
                uri=uri,
                asset_type="IT_ASSET",
                last_synced_at=datetime.utcnow()
            )
            db.add(cert)
            db.commit()
            db.refresh(cert)
        
        return cert
    
    @staticmethod
    def _generate_alias(uri: str) -> str:
        """Generate a default alias from URI"""
        # Remove scheme if present
        uri_clean = uri.replace("https://", "").replace("http://", "")
        # Replace special characters
        alias = uri_clean.replace(":", "_").replace("/", "_").replace("[", "").replace("]", "")
        return alias
    
    @staticmethod
    def delete_certificates(
        db: Session,
        delete_request: CertificateDelete
    ) -> Dict[str, Any]:
        """
        Delete certificates from GCM and database
        
        Returns:
            Dict with deletion statistics
        """
        client, auth_headers = CertificateService._get_gcm_client_and_headers(db)

        # Collect serial numbers and crypto IDs
        serial_numbers = delete_request.serial_numbers or []
        crypto_ids = delete_request.crypto_ids or []
        
        # If certificate IDs provided, get their serial numbers/crypto IDs
        if delete_request.certificate_ids:
            certs = db.query(Certificate).filter(
                Certificate.id.in_(delete_request.certificate_ids)
            ).all()
            
            for cert in certs:
                if cert.serial_number:
                    serial_numbers.append(cert.serial_number)
                if cert.crypto_id:
                    crypto_ids.append(cert.crypto_id)
        
        if not serial_numbers and not crypto_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No certificates specified for deletion"
            )
        
        # Build delete body
        body = {
            "certificate_serial_numbers": serial_numbers,
            "crypto_ids": crypto_ids,
        }
        
        # Call GCM delete API
        delete_path = "ibm/assetinventory/api/v1/assets/delete/crypto_objects/certificates"
        resp = CertificateService._gcm_post(client, auth_headers, delete_path, body)
        
        if not resp.ok:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to delete certificates from GCM: {resp.text}"
            )
        
        # Delete from database
        deleted_count = 0
        if delete_request.certificate_ids:
            deleted_count = db.query(Certificate).filter(
                Certificate.id.in_(delete_request.certificate_ids)
            ).delete(synchronize_session=False)
        elif serial_numbers or crypto_ids:
            # Delete by serial number or crypto ID using OR condition
            filters = []
            if serial_numbers:
                filters.append(Certificate.serial_number.in_(serial_numbers))
            if crypto_ids:
                filters.append(Certificate.crypto_id.in_(crypto_ids))
            
            deleted_count = db.query(Certificate).filter(
                or_(*filters)
            ).delete(synchronize_session=False)
        
        db.commit()
        
        return {
            "deleted_from_gcm": len(serial_numbers) + len(crypto_ids),
            "deleted_from_db": deleted_count,
            "serial_numbers": serial_numbers,
            "crypto_ids": crypto_ids
        }
    
    @staticmethod
    def get_statistics(db: Session) -> CertificateStats:
        """Get certificate statistics for dashboard"""
        total = db.query(Certificate).count()
        expired = db.query(Certificate).filter(Certificate.is_expired == True).count()
        expiring_soon = db.query(Certificate).filter(
            and_(
                Certificate.is_expired == False,
                Certificate.days_until_expiry <= 30,
                Certificate.days_until_expiry >= 0
            )
        ).count()
        
        # By issuer
        by_issuer = {}
        issuer_results = db.query(
            Certificate.issuer_cn,
            func.count(Certificate.id)
        ).group_by(Certificate.issuer_cn).all()
        
        for issuer_cn, count in issuer_results:
            by_issuer[issuer_cn or "Unknown"] = count
        
        # By algorithm
        by_algorithm = {}
        algo_results = db.query(
            Certificate.signature_algorithm,
            func.count(Certificate.id)
        ).group_by(Certificate.signature_algorithm).all()
        
        for algo, count in algo_results:
            by_algorithm[algo or "Unknown"] = count
        
        # Expiry timeline (next 12 months)
        expiry_timeline = []
        now = datetime.utcnow()
        for i in range(12):
            month_start = now + timedelta(days=30 * i)
            month_end = now + timedelta(days=30 * (i + 1))
            
            count = db.query(Certificate).filter(
                and_(
                    Certificate.valid_to >= month_start,
                    Certificate.valid_to < month_end
                )
            ).count()
            
            expiry_timeline.append({
                "month": month_start.strftime("%Y-%m"),
                "count": count
            })
        
        return CertificateStats(
            total_certificates=total,
            expired_certificates=expired,
            expiring_soon=expiring_soon,
            by_issuer=by_issuer,
            by_algorithm=by_algorithm,
            expiry_timeline=expiry_timeline
        )

# Made with Bob
