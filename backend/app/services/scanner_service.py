"""
Scanner service layer for GCM Web UI.
Wraps existing Python modules from disconnected-scanner/ directory.

Created: 2026-06-02
Last Modified: 2026-06-02 17:18 UTC - Fixed CSV validation to handle case-insensitive headers (Alias, Certdata, URI)
Last Modified: 2026-06-02 17:30 UTC - Fixed certificate import to use correct API endpoint and request format
"""

import sys
import os
import csv
import io
import ipaddress
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Add parent directory to path for imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '../../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.oidc_authz_client import AuthzClient


class ScannerService:
    """Service for disconnected scanner operations."""
    
    @staticmethod
    def expand_ips(ip_pattern: str) -> List[str]:
        """
        Expand IP pattern to list of IPs.
        
        Args:
            ip_pattern: IP in CIDR, wildcard, or single IP format
            
        Returns:
            List of IP addresses
        """
        ips = []
        if '*' in ip_pattern:
            # Handle wildcard: e.g., 192.168.1.*
            base = ip_pattern.split('*')[0]
            for i in range(256):
                ips.append(f"{base}{i}")
        else:
            # Handle CIDR: e.g., 192.168.1.0/24
            try:
                network = ipaddress.ip_network(ip_pattern, strict=False)
                ips = [str(ip) for ip in network.hosts()]
            except ValueError:
                # Single IP
                ips = [ip_pattern]
        return ips
    
    @staticmethod
    def expand_ports(port_pattern: str) -> List[int]:
        """
        Expand port pattern to list of ports.
        
        Args:
            port_pattern: Port range or list (e.g., "443-8443" or "443,8443")
            
        Returns:
            List of port numbers
        """
        ports = []
        for part in port_pattern.split(','):
            part = part.strip()
            if '-' in part:
                start, end = map(int, part.split('-'))
                ports.extend(range(start, end + 1))
            else:
                ports.append(int(part))
        return ports
    
    @staticmethod
    def generate_target_list(
        ip_ranges: str = None,
        hosts: str = None,
        ports: str = "",
        alias_prefix: str = ""
    ) -> Tuple[int, str, str]:
        """
        Generate scan target list as CSV.
        
        Args:
            ip_ranges: Comma-separated IP ranges in CIDR or wildcard format
            hosts: Comma-separated list of FQDNs
            ports: Port range or list
            alias_prefix: Optional prefix for alias names
            
        Returns:
            Tuple of (target_count, csv_content, filename)
        """
        # Collect all targets (IPs and hosts)
        targets = []
        
        if ip_ranges:
            for ip_range in ip_ranges.split(','):
                ip_range = ip_range.strip()
                if ip_range:
                    targets.extend(ScannerService.expand_ips(ip_range))
        
        if hosts:
            targets.extend([host.strip() for host in hosts.split(',') if host.strip()])
        
        # Expand ports
        port_list = ScannerService.expand_ports(ports)
        
        # Generate CSV rows
        rows = []
        for target in targets:
            for port in port_list:
                uri = f"https://{target}:{port}"
                alias = f"{alias_prefix}{target}_{port}"
                rows.append([alias, uri])
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Alias", "URI"])
        writer.writerows(rows)
        csv_content = output.getvalue()
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scan_targets_{timestamp}.csv"
        
        return len(rows), csv_content, filename
    
    @staticmethod
    def _normalize_certificate_csv_row(row: Dict[str, str]) -> Dict[str, str]:
        """
        Normalize certificate CSV headers to internal field names.
        Handles case-insensitive matching for flexibility.
        """
        normalized_row = {}
        
        # Map supported CSV headers to internal field names (case-insensitive)
        header_mapping = {
            'alias': 'alias',
            'certdata': 'certificate',
            'uri': 'uri',
            'uri (optional)': 'uri',
            'certificate': 'certificate',
        }
        
        for key, value in row.items():
            # Normalize the key to lowercase for case-insensitive matching
            key_lower = key.strip().lower()
            normalized_key = header_mapping.get(key_lower, key)
            normalized_row[normalized_key] = value
        
        return normalized_row
    
    @staticmethod
    def validate_csv_row(row: Dict[str, str], row_number: int) -> Dict[str, Any]:
        """
        Validate a single CSV row for certificate import.
        
        Args:
            row: Dictionary of CSV row data
            row_number: Row number for error reporting
            
        Returns:
            Dictionary with validation results
        """
        normalized_row = ScannerService._normalize_certificate_csv_row(row)
        errors = []
        warnings = []
        
        # Required fields for GCM certificate import
        required_fields = ['certificate']
        
        for field in required_fields:
            if field not in normalized_row or not normalized_row[field]:
                errors.append(f"Missing required field: {field}")
        
        # Validate URI format
        if 'uri' in normalized_row and normalized_row['uri']:
            uri = normalized_row['uri'].strip()
            if not uri.startswith(('https://', 'http://')):
                warnings.append(f"URI should start with https:// or http://")
        
        # Validate certificate format (basic check)
        if 'certificate' in normalized_row and normalized_row['certificate']:
            cert = normalized_row['certificate'].strip()
            if not (cert.startswith('-----BEGIN CERTIFICATE-----') or
                    cert.startswith('MII')):  # DER format starts with MII
                errors.append("Certificate must be in PEM or DER format")
        
        is_valid = len(errors) == 0
        
        return {
            'row_number': row_number,
            'is_valid': is_valid,
            'errors': errors,
            'warnings': warnings,
            'data': normalized_row
        }
    
    @staticmethod
    def validate_csv_content(csv_content: str) -> Tuple[int, int, List[Dict]]:
        """
        Validate CSV content for certificate import.
        
        Args:
            csv_content: CSV file content as string
            
        Returns:
            Tuple of (total_rows, valid_rows, validation_results)
        """
        validation_results = []
        total_rows = 0
        valid_rows = 0
        
        try:
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            for idx, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                total_rows += 1
                result = ScannerService.validate_csv_row(row, idx)
                validation_results.append(result)
                if result['is_valid']:
                    valid_rows += 1
                    
        except Exception as e:
            validation_results.append({
                'row_number': 0,
                'is_valid': False,
                'errors': [f"CSV parsing error: {str(e)}"],
                'warnings': [],
                'data': {}
            })
        
        return total_rows, valid_rows, validation_results
    
    @staticmethod
    def import_certificates_from_csv(
        csv_content: str,
        profile_data: Dict[str, Any],
        access_token: str
    ) -> Tuple[int, int, List[str]]:
        """
        Import certificates from CSV to GCM.
        
        Args:
            csv_content: CSV file content as string
            profile_data: Profile configuration
            access_token: GCM access token
            
        Returns:
            Tuple of (imported_count, failed_count, errors)
        """
        imported_count = 0
        failed_count = 0
        errors = []
        
        # Create GCM client
        config = {
            "app_uri": profile_data.get("app_uri", "").rstrip("/"),
            "oidc_uri": profile_data.get("oidc_uri", "").rstrip("/"),
            "realm": profile_data.get("realm", "gcmrealm"),
            "verify_ssl": not profile_data.get("insecure", False),
            "timeout": profile_data.get("timeout", 30.0),
            "user_agent": "gcm-webui-scanner-service/1.0",
        }
        
        try:
            client = AuthzClient(config)
            
            # Call authorization API
            auth_resp = client.call_authorization_api(access_token, tenant_id=profile_data.get("tenant_id", ""))
            if not auth_resp.ok:
                errors.append(f"Authorization API failed: HTTP {auth_resp.status_code}")
                return imported_count, failed_count, errors
            
            # Parse CSV
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            # Import each certificate
            for idx, row in enumerate(reader, start=2):
                try:
                    normalized_row = ScannerService._normalize_certificate_csv_row(row)
                    
                    # Prepare certificate data in GCM API format
                    uri = normalized_row.get('uri', '').strip()
                    certificate = normalized_row.get('certificate', '').strip()
                    alias = normalized_row.get('alias', '').strip()
                    
                    # Generate default alias if not provided
                    if not alias and uri:
                        # Remove scheme and special chars to create alias
                        alias = uri.replace("https://", "").replace("http://", "").replace(":", "_").replace("/", "_")
                    
                    # Build request body matching GCM API format (same as post_certificate.py)
                    cert_data = {
                        "crypto_object_certs": {
                            "cert_data": certificate,
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
                    
                    # POST to GCM certificate ingest API (correct endpoint)
                    ingest_path = "ibm/assetinventory/api/v1/assets/ingest/crypto_objects/certificate_from_file"
                    resp = client.post(ingest_path, access_token, json_body=cert_data)
                    
                    if resp.ok:
                        imported_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"Row {idx}: HTTP {resp.status_code} - {resp.text[:100]}")
                        
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Row {idx}: {str(e)}")
            
        except Exception as e:
            errors.append(f"Import error: {str(e)}")
        
        return imported_count, failed_count, errors


# Made with Bob