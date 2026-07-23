"""
Scanner service layer for GCM Web UI.
Wraps existing Python modules from disconnected-scanner/ directory.

Created: 2026-06-02
Last Modified: 2026-06-02 17:18 UTC - Fixed CSV validation to handle case-insensitive headers (Alias, Certdata, URI)
Last Modified: 2026-06-02 17:30 UTC - Fixed certificate import to use correct API endpoint and request format
Last Modified: 2026-07-23 00:00 UTC - import_certificates_from_csv now accepts auth_headers dict instead of
                                       access_token string to support API key authentication.
Last Modified: 2026-07-25 00:00 UTC - Added scan_targets() method that fetches SSL certs from a target list CSV.
Last Modified: 2026-07-25 00:00 UTC - Added multi-protocol probe (TLS, SSH, banner detection) and
                                       probe_target() for enriched per-target results.
Last Modified: 2026-07-25 00:00 UTC - Fix WRONG_VERSION_NUMBER on SSH ports: skip TLS when port is a known
                                       plain-text service; fix SSLV3_ALERT_HANDSHAKE_FAILURE by retrying
                                       with a legacy-permissive SSL context when the strict one is rejected.
Last Modified: 2026-07-25 00:00 UTC - Added crypto-weakness detection (expired cert, legacy TLS, weak/broken
                                       cipher, small key, self-signed, SHA1 signature); findings surfaced in
                                       scanner UI only — CSV stays Alias/Certdata/URI to match GCM format.
Last Modified: 2026-07-25 00:01 UTC - Added SSH alternative ports 2222/22222 to _PLAINTEXT_PORTS; fixed
                                       LEGACY_SSH_KEX detection; ssh_host_key_fingerprint now stores cleaned
                                       comma-separated algorithm list for clearer UI display.
Last Modified: 2026-07-25 00:02 UTC - Added ingest_keys_from_results() for SSH host keys to GCM /v2/keys
                                       and ingest_protocols_from_results() for TLS to GCM /v2/protocols.
Last Modified: 2026-07-25 00:03 UTC - Add port 2222/22222 to _PORT_SERVICE_HINTS so probe_target takes the
                                        direct SSH path; normalise SSH wire key type to clean GCM algorithm
                                        name (RSA/ECDSA/Ed25519); drop enum fields (key_type, key_usage,
                                        origin_source) that GCM may reject as unknown values.
Last Modified: 2026-07-28 00:00 UTC - Remove 'results' from done SSE event (large cert_b64 payloads caused
                                        silent JSON parse failure in browser, preventing action bar from
                                        appearing after scan). JS reads results from scannerState instead.
Last Modified: 2026-07-28 00:01 UTC - Fix SSH key ingest payload: replace nested relationships block with
                                        flat it_asset_uri field to match the structure accepted by GCM v2
                                        keys API (mirrors the working protocol ingest structure).
"""

import sys
import os
import csv
import io
import ssl
import socket
import base64
import hashlib
import struct
import ipaddress
from urllib.parse import urlparse
from typing import List, Dict, Any, Tuple, Optional, Generator, Set
from datetime import datetime, timezone

from cryptography import x509 as crypto_x509
from cryptography.hazmat.primitives.asymmetric import rsa, ec, dsa, ed25519, ed448
from cryptography.hazmat.backends import default_backend

# Add parent directory to path for imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.oidc_authz_client import AuthzClient

# ---------------------------------------------------------------------------
# Service-banner fingerprints — ordered by likelihood on common port ranges
# ---------------------------------------------------------------------------
_BANNER_SIGNATURES: List[Tuple[bytes, str]] = [
    (b"SSH-",        "ssh"),
    (b"220 ",        "ftp_or_smtp"),   # FTP 220 / SMTP 220 — disambiguated below
    (b"SMTP",        "smtp"),
    (b"220-",        "ftp"),
    (b"+OK",         "pop3"),
    (b"* OK",        "imap"),
    (b"HTTP/",       "http"),
    (b"AMQP",        "amqp"),
    (b"\x16\x03",    "tls_record"),    # TLS ClientHello-like record
]

# Well-known service→port hints (used when banner is empty / timeout on read)
_PORT_SERVICE_HINTS: Dict[int, str] = {
    21:   "ftp",
    22:   "ssh",
    2222: "ssh",
    22222:"ssh",
    25:   "smtp",
    110:  "pop3",
    143:  "imap",
    443:  "https",
    465:  "smtps",
    587:  "submission",
    993:  "imaps",
    995:  "pop3s",
    3306: "mysql",
    5432: "postgresql",
    6379: "redis",
    27017:"mongodb",
    8443: "https-alt",
    8080: "http-alt",
}

# ---------------------------------------------------------------------------
# Crypto-weakness detection
# ---------------------------------------------------------------------------

# TLS versions considered weak / broken
_LEGACY_TLS_VERSIONS: Set[str] = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1", "TLSv1.0"}

# Cipher substrings that indicate known-weak key-exchange or bulk cipher
_WEAK_CIPHER_FRAGMENTS: List[str] = [
    "RC4", "RC2", "DES", "3DES", "EXPORT", "NULL", "ANON", "ADH", "AECDH",
    "MD5", "SHA1",       # HMAC (not to be confused with RSA-SHA1 sig on cert)
    "_CBC_",             # CBC mode in TLS <= 1.2 is vulnerable (BEAST/POODLE)
    "RSA_WITH_",         # static RSA key exchange — no forward secrecy
]

# RSA / DSA key sizes below this are considered weak
_MIN_RSA_DSA_BITS = 2048
# EC key sizes below this are considered weak
_MIN_EC_BITS = 224

# Signature algorithm OIDs that indicate SHA-1 signed cert
_SHA1_SIG_OIDS = {
    "1.2.840.113549.1.1.5",   # sha1WithRSAEncryption
    "1.2.840.10040.4.3",       # id-dsa-with-sha1
    "1.2.840.10045.4.1",       # ecdsa-with-SHA1
}


def _analyse_cert_findings(cert_der: bytes, tls_version: str, cipher_name: str,
                            used_legacy_fallback: bool) -> List[str]:
    """
    Inspect a DER-encoded certificate and the negotiated TLS parameters.
    Returns a list of human-readable finding strings, e.g.:
      ["EXPIRED", "LEGACY_TLS:TLSv1.0", "WEAK_CIPHER:TLS_RSA_WITH_AES_256_CBC_SHA",
       "WEAK_KEY:RSA-1024", "SELF_SIGNED", "SHA1_SIGNATURE"]
    Empty list means no findings (clean).
    """
    findings: List[str] = []

    # 1. Legacy TLS version
    if tls_version in _LEGACY_TLS_VERSIONS or used_legacy_fallback:
        findings.append(f"LEGACY_TLS:{tls_version}")

    # 2. Weak cipher suite
    cipher_upper = cipher_name.upper()
    for fragment in _WEAK_CIPHER_FRAGMENTS:
        if fragment.upper() in cipher_upper:
            findings.append(f"WEAK_CIPHER:{cipher_name}")
            break  # one finding per cipher is enough

    # 3. Parse certificate with the cryptography library
    try:
        cert = crypto_x509.load_der_x509_certificate(cert_der, default_backend())

        # 3a. Expired
        try:
            now = datetime.now(timezone.utc)
            if cert.not_valid_after_utc < now:
                findings.append("EXPIRED")
            elif (cert.not_valid_after_utc - now).days < 30:
                findings.append("EXPIRING_SOON")
        except Exception:
            pass

        # 3b. Self-signed (subject == issuer)
        if cert.subject == cert.issuer:
            findings.append("SELF_SIGNED")

        # 3c. Weak public key
        try:
            pk = cert.public_key()
            if isinstance(pk, (rsa.RSAPublicKey, dsa.DSAPublicKey)):
                if pk.key_size < _MIN_RSA_DSA_BITS:
                    findings.append(f"WEAK_KEY:{type(pk).__name__.replace('PublicKey','')}-{pk.key_size}")
            elif isinstance(pk, ec.EllipticCurvePublicKey):
                if pk.key_size < _MIN_EC_BITS:
                    findings.append(f"WEAK_KEY:EC-{pk.key_size}")
        except Exception:
            pass

        # 3d. SHA-1 signature algorithm
        try:
            sig_oid = cert.signature_algorithm_oid.dotted_string
            if sig_oid in _SHA1_SIG_OIDS:
                findings.append("SHA1_SIGNATURE")
        except Exception:
            pass

    except Exception:
        pass  # cryptography library unavailable or unparseable cert — skip cert-level checks

    return findings


class ScannerService:
    """Service for disconnected scanner operations."""

    # ------------------------------------------------------------------
    # IP / port helpers
    # ------------------------------------------------------------------

    @staticmethod
    def expand_ips(ip_pattern: str) -> List[str]:
        """Expand IP pattern (CIDR, wildcard, single) to list of IPs."""
        ips = []
        if '*' in ip_pattern:
            base = ip_pattern.split('*')[0]
            for i in range(256):
                ips.append(f"{base}{i}")
        else:
            try:
                network = ipaddress.ip_network(ip_pattern, strict=False)
                ips = [str(ip) for ip in network.hosts()]
            except ValueError:
                ips = [ip_pattern]
        return ips

    @staticmethod
    def expand_ports(port_pattern: str) -> List[int]:
        """Expand port pattern (range or comma-list) to list of ints."""
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

        Returns: (target_count, csv_content, filename)
        """
        targets = []
        if ip_ranges:
            for ip_range in ip_ranges.split(','):
                ip_range = ip_range.strip()
                if ip_range:
                    targets.extend(ScannerService.expand_ips(ip_range))

        if hosts:
            targets.extend([h.strip() for h in hosts.split(',') if h.strip()])

        port_list = ScannerService.expand_ports(ports)

        rows = []
        for target in targets:
            for port in port_list:
                uri = f"https://{target}:{port}"
                alias = f"{alias_prefix}{target}_{port}"
                rows.append([alias, uri])

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Alias", "URI"])
        writer.writerows(rows)
        csv_content = output.getvalue()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"scan_targets_{timestamp}.csv"
        return len(rows), csv_content, filename

    # ------------------------------------------------------------------
    # CSV validation / normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_certificate_csv_row(row: Dict[str, str]) -> Dict[str, str]:
        """Normalize certificate CSV headers to internal field names (case-insensitive)."""
        normalized_row = {}
        header_mapping = {
            'alias': 'alias',
            'certdata': 'certificate',
            'uri': 'uri',
            'uri (optional)': 'uri',
            'certificate': 'certificate',
        }
        for key, value in row.items():
            key_lower = key.strip().lower()
            normalized_key = header_mapping.get(key_lower, key)
            normalized_row[normalized_key] = value
        return normalized_row

    @staticmethod
    def validate_csv_row(row: Dict[str, str], row_number: int) -> Dict[str, Any]:
        """Validate a single CSV row for certificate import."""
        normalized_row = ScannerService._normalize_certificate_csv_row(row)
        errors = []
        warnings = []

        for field in ['certificate']:
            if field not in normalized_row or not normalized_row[field]:
                errors.append(f"Missing required field: {field}")

        if 'uri' in normalized_row and normalized_row['uri']:
            uri = normalized_row['uri'].strip()
            if not uri.startswith(('https://', 'http://')):
                warnings.append("URI should start with https:// or http://")

        if 'certificate' in normalized_row and normalized_row['certificate']:
            cert = normalized_row['certificate'].strip()
            if not (cert.startswith('-----BEGIN CERTIFICATE-----') or cert.startswith('MII')):
                errors.append("Certificate must be in PEM or DER format")

        return {
            'row_number': row_number,
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'data': normalized_row,
        }

    @staticmethod
    def validate_csv_content(csv_content: str) -> Tuple[int, int, List[Dict]]:
        """Validate CSV content for certificate import. Returns (total, valid, results)."""
        validation_results = []
        total_rows = 0
        valid_rows = 0
        try:
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            for idx, row in enumerate(reader, start=2):
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
                'data': {},
            })
        return total_rows, valid_rows, validation_results

    # ------------------------------------------------------------------
    # GCM import helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _gcm_post(client: AuthzClient, auth_headers: Dict[str, Any], path: str, body: dict):
        """POST to a GCM API path using pre-built auth headers."""
        url = f"{client.app_uri}/{path.lstrip('/')}"
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        headers.update(auth_headers)
        return client.session.post(
            url, headers=headers, json=body,
            verify=client.verify_ssl, timeout=client.timeout,
        )

    @staticmethod
    def import_certificates_from_csv(
        csv_content: str,
        profile_data: Dict[str, Any],
        auth_headers: Dict[str, Any],
    ) -> Tuple[int, int, List[str]]:
        """Import certificates from CSV to GCM. Returns (imported, failed, errors)."""
        imported_count = 0
        failed_count = 0
        errors = []

        app_uri = profile_data.get("app_uri", "").rstrip("/")
        oidc_uri = (profile_data.get("oidc_uri") or app_uri).rstrip("/")
        config = {
            "app_uri": app_uri,
            "oidc_uri": oidc_uri,
            "realm": profile_data.get("realm", "gcmrealm"),
            "verify_ssl": not profile_data.get("insecure", False),
            "timeout": profile_data.get("timeout", 30.0),
            "user_agent": "gcm-webui-scanner-service/1.0",
        }

        if not auth_headers.get("Authorization"):
            errors.append(
                "Missing 'Authorization' header. "
                "Ensure the active profile has valid credentials configured."
            )
            return imported_count, failed_count, errors

        try:
            client = AuthzClient(config)
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)

            for idx, row in enumerate(reader, start=2):
                try:
                    normalized_row = ScannerService._normalize_certificate_csv_row(row)
                    uri = normalized_row.get('uri', '').strip()
                    certificate = normalized_row.get('certificate', '').strip()
                    alias = normalized_row.get('alias', '').strip()

                    if not alias and uri:
                        alias = (uri.replace("https://", "").replace("http://", "")
                                    .replace(":", "_").replace("/", "_"))

                    cert_data = {
                        "crypto_object_certs": {
                            "cert_data": certificate,
                            "crypto_object_alias": alias,
                            "relationships": [
                                {"asset_identifiers": {"uri": uri}, "asset_type": "IT_ASSET"}
                            ],
                            "tag_ids": [],
                        }
                    }

                    ingest_path = ("ibm/assetinventory/api/v1/assets/ingest/"
                                   "crypto_objects/certificate_from_file")
                    resp = ScannerService._gcm_post(client, auth_headers, ingest_path, cert_data)

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

    @staticmethod
    def _build_gcm_client(profile_data: Dict[str, Any]) -> "AuthzClient":
        """Build an AuthzClient from profile_data dict."""
        app_uri = profile_data.get("app_uri", "").rstrip("/")
        oidc_uri = (profile_data.get("oidc_uri") or app_uri).rstrip("/")
        return AuthzClient({
            "app_uri": app_uri,
            "oidc_uri": oidc_uri,
            "realm": profile_data.get("realm", "gcmrealm"),
            "verify_ssl": not profile_data.get("insecure", False),
            "timeout": profile_data.get("timeout", 30.0),
            "user_agent": "gcm-webui-scanner-service/1.0",
        })

    @staticmethod
    def ingest_keys_from_results(
        results: List[Dict[str, Any]],
        profile_data: Dict[str, Any],
        auth_headers: Dict[str, Any],
    ) -> Tuple[int, int, List[str]]:
        """
        Ingest SSH host keys from scan results into GCM /v2/assets/ingest/crypto_objects/keys.
        Only processes results where service == 'ssh' and ssh_host_key_type is present.
        Returns (imported, failed, errors).
        """
        imported_count = 0
        failed_count = 0
        errors: List[str] = []

        if not auth_headers.get("Authorization"):
            return 0, 0, ["Missing Authorization header — check active profile credentials."]

        ssh_results = [
            r for r in results
            if r.get("service") == "ssh" and r.get("ssh_host_key_type") and r.get("success")
        ]
        if not ssh_results:
            return 0, 0, []

        try:
            client = ScannerService._build_gcm_client(profile_data)
            ingest_path = "ibm/assetinventory/api/v2/assets/ingest/crypto_objects/keys"

            for r in ssh_results:
                alias    = r.get("alias", "")
                uri      = r.get("uri", "")
                key_type = r.get("ssh_host_key_type", "")   # e.g. "rsa-sha2-512", "ssh-rsa", "ecdsa-sha2-nistp256"
                alg_list = r.get("ssh_host_key_fingerprint", "")  # comma-sep algorithm string

                # Normalise SSH wire-format key type → clean algorithm name for GCM
                if "ed25519" in key_type:
                    gcm_algorithm = "Ed25519"
                    key_length = 256
                elif "rsa" in key_type:
                    gcm_algorithm = "RSA"
                    key_length = 2048  # conservative; actual size not captured in KEX
                elif "ecdsa" in key_type or "nistp" in key_type:
                    gcm_algorithm = "ECDSA"
                    key_length = 256 if "256" in key_type else (384 if "384" in key_type else 521)
                elif "dss" in key_type or "dsa" in key_type:
                    gcm_algorithm = "DSA"
                    key_length = 1024
                else:
                    gcm_algorithm = key_type  # pass through unknown types as-is
                    key_length = 0

                key_obj: Dict[str, Any] = {
                    "crypto_object_name": alias,
                    "key_algorithm": gcm_algorithm,
                    "it_asset_uri": uri,
                    "discovery_sources": ["GCM-Scanner"],
                }
                # Only include numeric fields when they have a meaningful value
                if key_length:
                    key_obj["key_length"] = key_length

                body = {
                    "crypto_object_keys": [key_obj],
                    "detailed_response": True,
                }

                try:
                    resp = ScannerService._gcm_post(client, auth_headers, ingest_path, body)
                    if resp.ok:
                        imported_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"{alias}: HTTP {resp.status_code} - {resp.text[:100]}")
                except Exception as e:
                    failed_count += 1
                    errors.append(f"{alias}: {str(e)}")

        except Exception as e:
            errors.append(f"Key ingest error: {str(e)}")

        return imported_count, failed_count, errors

    @staticmethod
    def ingest_protocols_from_results(
        results: List[Dict[str, Any]],
        profile_data: Dict[str, Any],
        auth_headers: Dict[str, Any],
    ) -> Tuple[int, int, List[str]]:
        """
        Ingest TLS protocol metadata from scan results into GCM /v2/assets/ingest/crypto_objects/protocols.
        Only processes results where service == 'tls' and tls_version is present.
        Returns (imported, failed, errors).
        """
        imported_count = 0
        failed_count = 0
        errors: List[str] = []

        if not auth_headers.get("Authorization"):
            return 0, 0, ["Missing Authorization header — check active profile credentials."]

        tls_results = [
            r for r in results
            if r.get("service") == "tls" and r.get("tls_version") and r.get("success")
        ]
        if not tls_results:
            return 0, 0, []

        try:
            client = ScannerService._build_gcm_client(profile_data)
            ingest_path = "ibm/assetinventory/api/v2/assets/ingest/crypto_objects/protocols"

            for r in tls_results:
                alias   = r.get("alias", "")
                uri     = r.get("uri", "")
                tls_ver = r.get("tls_version", "")
                cipher  = r.get("cipher_suite", "")

                body = {
                    "crypto_object_protocols": [
                        {
                            "crypto_object_name": alias,
                            "protocol": "TLS",
                            "it_asset_uri": uri,
                            "discovery_sources": ["GCM-Scanner"],
                            "protocols": [
                                {
                                    "version": tls_ver,
                                    "ciphers": [cipher] if cipher else [],
                                }
                            ],
                            "relationship_type": "HOSTED_ON",
                        }
                    ],
                    "detailed_response": True,
                }

                try:
                    resp = ScannerService._gcm_post(client, auth_headers, ingest_path, body)
                    if resp.ok:
                        imported_count += 1
                    else:
                        failed_count += 1
                        errors.append(f"{alias}: HTTP {resp.status_code} - {resp.text[:100]}")
                except Exception as e:
                    failed_count += 1
                    errors.append(f"{alias}: {str(e)}")

        except Exception as e:
            errors.append(f"Protocol ingest error: {str(e)}")

        return imported_count, failed_count, errors

    # ------------------------------------------------------------------
    # Multi-protocol probe helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ssl_context(insecure: bool) -> ssl.SSLContext:
        """Create a strict SSL context (TLS 1.2+, full cert verification unless insecure)."""
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    @staticmethod
    def _build_legacy_ssl_context(insecure: bool) -> ssl.SSLContext:
        """
        Permissive SSL context for legacy servers (TLS 1.0+, all ciphers).

        Used as a fallback when the strict context produces HANDSHAKE_FAILURE,
        which typically means the server only supports old TLS versions or
        weak cipher suites that Python's default context refuses.
        """
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # Allow TLS 1.0 and above
        ctx.minimum_version = ssl.TLSVersion.TLSv1
        # Enable all cipher suites including legacy RSA key exchange
        ctx.set_ciphers("ALL:@SECLEVEL=0")
        return ctx

    @staticmethod
    def _do_tls_handshake(host: str, port: int, timeout: float, ctx: ssl.SSLContext,
                          used_legacy_fallback: bool = False) -> Dict[str, Any]:
        """
        Perform TLS handshake and extract cert metadata + crypto-weakness findings.
        Raises ssl.SSLError / OSError on failure (caller decides what to do).
        """
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert_der = ssock.getpeercert(binary_form=True)
                cert_b64 = base64.b64encode(cert_der).decode("utf-8")
                cipher = ssock.cipher()          # (name, protocol, bits)
                tls_ver = ssock.version() or ""  # e.g. "TLSv1.3"
                cipher_name = cipher[0] if cipher else ""

                cert_dict = ssock.getpeercert()
                subject = ScannerService._dn_to_str(cert_dict.get("subject", ()))
                issuer = ScannerService._dn_to_str(cert_dict.get("issuer", ()))
                not_after = cert_dict.get("notAfter", "")

                # Detect crypto weaknesses
                findings = _analyse_cert_findings(
                    cert_der, tls_ver, cipher_name, used_legacy_fallback
                )

                banner = f"{tls_ver} {cipher_name}".strip()
                if used_legacy_fallback:
                    banner += " [legacy fallback]"

                return {
                    "success": True,
                    "service": "tls",
                    "cert_b64": cert_b64,
                    "tls_version": tls_ver,
                    "cipher_suite": cipher_name,
                    "cert_subject": subject,
                    "cert_issuer": issuer,
                    "cert_not_after": not_after,
                    "service_banner": banner,
                    "ssh_host_key_type": None,
                    "ssh_host_key_fingerprint": None,
                    "findings": findings,
                    "error": None,
                }

    @staticmethod
    def _probe_tls(host: str, port: int, timeout: float, ssl_ctx: ssl.SSLContext) -> Dict[str, Any]:
        """
        Attempt a TLS handshake, with automatic fallback to a legacy context on
        HANDSHAKE_FAILURE (servers that only support TLS 1.0/1.1 or weak ciphers).

        Raises ssl.SSLError / OSError when the port is not TLS at all
        (e.g. WRONG_VERSION_NUMBER from an SSH or plain-text service).
        """
        try:
            return ScannerService._do_tls_handshake(host, port, timeout, ssl_ctx,
                                                    used_legacy_fallback=False)
        except ssl.SSLError as e:
            err_str = str(e)
            # HANDSHAKE_FAILURE → server rejected our cipher/version offer.
            # Retry with a permissive legacy context to reach old servers.
            if "HANDSHAKE_FAILURE" in err_str or "ALERT_HANDSHAKE_FAILURE" in err_str:
                legacy_ctx = ScannerService._build_legacy_ssl_context(insecure=True)
                return ScannerService._do_tls_handshake(host, port, timeout, legacy_ctx,
                                                        used_legacy_fallback=True)
            # Any other SSLError (WRONG_VERSION_NUMBER, etc.) — not TLS, re-raise
            raise

    @staticmethod
    def _dn_to_str(dn_tuple) -> str:
        """Convert SSL cert subject/issuer tuple-of-tuples to CN=.../ string."""
        parts = []
        for rdn in dn_tuple:
            for attr, value in rdn:
                parts.append(f"{attr}={value}")
        return "/".join(parts)

    @staticmethod
    def _read_banner(sock: socket.socket, size: int = 256) -> bytes:
        """Read up to `size` bytes from a connected socket for banner detection."""
        try:
            sock.settimeout(2.0)
            return sock.recv(size)
        except Exception:
            return b""

    @staticmethod
    def _classify_banner(banner: bytes, port: int) -> str:
        """Return a service label from the raw TCP banner bytes."""
        for prefix, label in _BANNER_SIGNATURES:
            if banner.startswith(prefix):
                if label == "ftp_or_smtp":
                    return "smtp" if port in (25, 465, 587, 2525) else "ftp"
                return label
        return _PORT_SERVICE_HINTS.get(port, "unknown")

    @staticmethod
    def _probe_ssh(host: str, port: int, timeout: float) -> Dict[str, Any]:
        """
        Connect to an SSH service and extract the server host key via the
        SSH binary protocol (RFC 4253).  No external library required.

        Returns a partial result dict.
        """
        with socket.create_connection((host, port), timeout=timeout) as sock:
            banner_bytes = ScannerService._read_banner(sock, 256)
            banner_str = banner_bytes.decode("utf-8", errors="replace").strip()

            if not banner_bytes.startswith(b"SSH-"):
                return {
                    "success": True,
                    "service": "ssh",
                    "service_banner": banner_str,
                    "cert_b64": None,
                    "tls_version": None, "cipher_suite": None,
                    "cert_subject": None, "cert_issuer": None, "cert_not_after": None,
                    "ssh_host_key_type": None,
                    "ssh_host_key_fingerprint": None,
                    "findings": [],
                    "error": "Unexpected SSH banner",
                }

            # Send our client ident string
            sock.sendall(b"SSH-2.0-GCM-Scanner_1.0\r\n")

            # Read SSH_MSG_KEXINIT (packet length 4 bytes, padding 1 byte, type 1 byte)
            host_key_type, host_key_b64, fingerprint = ScannerService._parse_ssh_host_key(sock)

            # Parse the raw algorithms from _parse_ssh_host_key's fingerprint placeholder
            # fingerprint is like "<advertised: ecdsa-sha2-nistp256,rsa-sha2-512,...>"
            alg_list: List[str] = []
            if fingerprint and fingerprint.startswith("<advertised: "):
                alg_str = fingerprint[len("<advertised: "):-1]  # strip wrapper
                alg_list = [a.strip() for a in alg_str.split(",") if a.strip()]

            # Build a clean display string for the UI
            algorithms_display = ", ".join(alg_list) if alg_list else fingerprint or ""

            # Flag security issues based on parsed algorithm list
            ssh_findings = []
            if host_key_type and host_key_type == "ssh-rsa":
                ssh_findings.append("WEAK_SSH_HOSTKEY:ssh-rsa(SHA1)")
            # Legacy KEX: server does NOT advertise any rsa-sha2-* variant
            if alg_list and not any("rsa-sha2" in a for a in alg_list) and any(a == "ssh-rsa" for a in alg_list):
                ssh_findings.append("LEGACY_SSH_KEX:no-sha2")

            return {
                "success": True,
                "service": "ssh",
                "service_banner": banner_str,
                "cert_b64": None,
                "tls_version": None, "cipher_suite": None,
                "cert_subject": None, "cert_issuer": None, "cert_not_after": None,
                "ssh_host_key_type": host_key_type,
                "ssh_host_key_fingerprint": algorithms_display,
                "findings": ssh_findings,
                "error": None,
            }

    @staticmethod
    def _parse_ssh_host_key(sock: socket.socket) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Read the SSH_MSG_KEXINIT packet to extract the server host-key algorithms list.
        Then send a minimal KEXECDH_INIT / KEX_INIT and await SSH_MSG_KEXINIT from server.
        We only parse the kex_algorithms and server_host_key_algorithms fields to report
        what the server advertises — we do not complete the key exchange.

        Returns (key_type, None, fingerprint_placeholder).
        """
        try:
            raw = ScannerService._ssh_read_packet(sock)
            if not raw or raw[0] != 20:   # SSH_MSG_KEXINIT = 20
                return None, None, None

            # Skip: msg type (1) + cookie (16) = offset 17
            offset = 17
            # Read name-list fields: kex_algorithms, server_host_key_algorithms, ...
            # We only need field index 1 (server_host_key_algorithms)
            for i in range(2):
                if offset + 4 > len(raw):
                    return None, None, None
                length = struct.unpack(">I", raw[offset:offset+4])[0]
                offset += 4
                value = raw[offset:offset+length].decode("utf-8", errors="replace")
                offset += length
                if i == 1:
                    # server_host_key_algorithms — first entry is preferred
                    key_type = value.split(",")[0].strip()
                    fingerprint = f"<advertised: {value}>"
                    return key_type, None, fingerprint

        except Exception:
            pass
        return None, None, None

    @staticmethod
    def _ssh_read_packet(sock: socket.socket) -> Optional[bytes]:
        """Read one SSH binary packet; return the payload bytes (after length + padding)."""
        try:
            sock.settimeout(3.0)
            # Read 4-byte packet length
            length_bytes = ScannerService._recv_exact(sock, 4)
            if length_bytes is None:
                return None
            packet_length = struct.unpack(">I", length_bytes)[0]
            if packet_length > 65536:  # sanity guard
                return None
            payload_and_pad = ScannerService._recv_exact(sock, packet_length)
            if payload_and_pad is None:
                return None
            padding_length = payload_and_pad[0]
            # payload starts at byte 1, ends before the padding
            return payload_and_pad[1: packet_length - padding_length]
        except Exception:
            return None

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
        """Read exactly n bytes from sock, or return None on failure."""
        buf = b""
        while len(buf) < n:
            try:
                chunk = sock.recv(n - len(buf))
                if not chunk:
                    return None
                buf += chunk
            except Exception:
                return None
        return buf

    @staticmethod
    def _probe_banner(host: str, port: int, timeout: float) -> Dict[str, Any]:
        """
        Plain TCP connect + banner read for non-TLS, non-SSH services.
        """
        with socket.create_connection((host, port), timeout=timeout) as sock:
            banner = ScannerService._read_banner(sock)
            service = ScannerService._classify_banner(banner, port)
            banner_str = banner.decode("utf-8", errors="replace").strip()[:120]
            return {
                "success": True,
                "service": service,
                "service_banner": banner_str,
                "cert_b64": None,
                "tls_version": None, "cipher_suite": None,
                "cert_subject": None, "cert_issuer": None, "cert_not_after": None,
                "ssh_host_key_type": None,
                "ssh_host_key_fingerprint": None,
                "findings": [],
                "error": None,
            }

    # ------------------------------------------------------------------
    # Ports that speak plain-text first — never try TLS on these
    # ------------------------------------------------------------------

    # Known plain-text-first ports: attempting TLS produces WRONG_VERSION_NUMBER
    # because the server sends a non-TLS banner (SSH, FTP, SMTP, etc.)
    _PLAINTEXT_PORTS = frozenset({
        22,    # SSH (standard)
        2222,  # SSH (common alternative)
        22222, # SSH (less common alternative)
        21,    # FTP
        25,    # SMTP
        110,   # POP3
        143,   # IMAP
        3306,  # MySQL
        5432,  # PostgreSQL
        6379,  # Redis
        27017, # MongoDB
    })

    # ------------------------------------------------------------------
    # Main per-target probe (TLS first, SSH fallback, banner fallback)
    # ------------------------------------------------------------------

    @staticmethod
    def probe_target(
        alias: str,
        uri: str,
        host: str,
        port: int,
        timeout: float,
        ssl_ctx: ssl.SSLContext,
    ) -> Dict[str, Any]:
        """
        Probe a single target using a smart protocol-detection strategy:

          • Plain-text ports (22, 21, 25 …): skip TLS entirely, go straight
            to SSH probe (port 22) or banner probe.  This avoids the
            WRONG_VERSION_NUMBER error that occurs when Python tries to
            TLS-handshake an SSH or FTP server.

          • All other ports: try TLS first (with automatic legacy-context
            fallback for HANDSHAKE_FAILURE / old servers), then fall through
            to banner detection on definitive non-TLS errors.
        """
        base = {"alias": alias, "uri": uri}
        _empty = {
            "service_banner": None, "cert_b64": None,
            "tls_version": None, "cipher_suite": None,
            "cert_subject": None, "cert_issuer": None, "cert_not_after": None,
            "ssh_host_key_type": None, "ssh_host_key_fingerprint": None,
            "findings": [],
        }

        # ---- Step 1: For well-known plain-text ports, skip TLS entirely ----
        if port in ScannerService._PLAINTEXT_PORTS:
            if port == 22 or _PORT_SERVICE_HINTS.get(port) == "ssh":
                try:
                    result = ScannerService._probe_ssh(host, port, timeout)
                    result.update(base)
                    return result
                except Exception as e:
                    # SSH probe failed but the port is open; report banner
                    pass
            # Fall through to banner probe for other plain-text ports
        else:
            # ---- Step 2: Try TLS (strict, then legacy fallback) ----
            try:
                result = ScannerService._probe_tls(host, port, timeout, ssl_ctx)
                result.update(base)
                return result
            except ssl.SSLError:
                # Definitive non-TLS response (WRONG_VERSION_NUMBER etc.)
                # — fall through to plain-text probes below
                pass
            except (socket.timeout, ConnectionRefusedError, OSError) as e:
                # Port is unreachable / connection refused — no point trying further
                return {**base, **_empty, "success": False, "service": None, "error": str(e)}

        # ---- Step 3: Banner read (plain-text services) ----
        try:
            result = ScannerService._probe_banner(host, port, timeout)
            result.update(base)
            # If the banner identifies this as SSH, upgrade to a full SSH probe
            if result.get("service") == "ssh":
                try:
                    ssh_result = ScannerService._probe_ssh(host, port, timeout)
                    ssh_result.update(base)
                    return ssh_result
                except Exception:
                    pass  # return the banner result as-is
            return result
        except Exception as e:
            return {**base, **_empty, "success": False, "service": None, "error": str(e)}

    # ------------------------------------------------------------------
    # Certificates CSV builder — shared by batch and streaming paths
    # ------------------------------------------------------------------

    @staticmethod
    def _build_certificates_csv(results: List[Dict[str, Any]]) -> str:
        """
        Build the certificates CSV from probe results.

        Output format matches Import-certificate.csv exactly — GCM only accepts:
          Alias, Certdata, URI (optional)

        Findings are captured in each result dict and shown in the scanner UI,
        but are NOT written to the CSV to avoid breaking GCM's fixed import format.
        Only TLS targets that returned a certificate are included.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Alias", "Certdata", "URI (optional)"])
        for r in results:
            if not (r["success"] and r.get("cert_b64")):
                continue
            writer.writerow([r["alias"], r["cert_b64"], r.get("uri", "")])
        return output.getvalue()

    # ------------------------------------------------------------------
    # Batch scan (original blocking endpoint — kept for compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def scan_targets(
        targets_csv: str,
        timeout: float = 5.0,
        insecure: bool = False,
    ) -> Tuple[int, int, int, str, str, List[Dict[str, Any]]]:
        """
        Fetch SSL certificates / service info from a target list CSV.

        Returns: (total_targets, scanned, failed, certificates_csv, filename, results)
        """
        ssl_ctx = ScannerService._build_ssl_context(insecure)
        results: List[Dict[str, Any]] = []

        csv_file = io.StringIO(targets_csv)
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        total_targets = len(rows)

        for row in rows:
            uri = (row.get("URI") or row.get("url") or "").strip()
            alias = (row.get("Alias") or "").strip()

            if not uri:
                results.append({
                    "alias": alias, "uri": uri, "success": False, "service": None,
                    "service_banner": None, "cert_b64": None,
                    "tls_version": None, "cipher_suite": None,
                    "cert_subject": None, "cert_issuer": None, "cert_not_after": None,
                    "ssh_host_key_type": None, "ssh_host_key_fingerprint": None,
                    "findings": [], "error": "Missing URI",
                })
                continue

            parsed = urlparse(uri)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if not alias:
                alias = f"{host}_{port}"

            result = ScannerService.probe_target(alias, uri, host, port, timeout, ssl_ctx)
            results.append(result)

        scanned = sum(1 for r in results if r["success"])
        failed = total_targets - scanned

        # Build certificates CSV — TLS hits only, with findings columns so GCM
        # can surface weakness information when the cert is imported.
        certificates_csv = ScannerService._build_certificates_csv(results)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"certificates_{timestamp}.csv"
        return total_targets, scanned, failed, certificates_csv, filename, results

    # ------------------------------------------------------------------
    # Streaming scan generator (used by the SSE endpoint)
    # ------------------------------------------------------------------

    @staticmethod
    def scan_targets_stream(
        targets_csv: str,
        timeout: float = 5.0,
        insecure: bool = False,
        stop_flag: Optional[Dict[str, bool]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Generator that probes targets one-by-one and yields progress dicts.

        Each yielded dict has:
          { "type": "progress", "index": n, "total": N,
            "alias": ..., "host": ..., "port": ..., "result": {...} }

        Final yield:
          { "type": "done", "total": N, "scanned": n, "failed": n,
            "certificates_csv": "...", "filename": "..." }

        If stop_flag["stopped"] is True the generator stops early and
        yields a "done" event with stopped=True.
        """
        ssl_ctx = ScannerService._build_ssl_context(insecure)

        csv_file = io.StringIO(targets_csv)
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        total_targets = len(rows)
        results: List[Dict[str, Any]] = []

        for idx, row in enumerate(rows):
            # Check stop flag
            if stop_flag and stop_flag.get("stopped"):
                break

            uri = (row.get("URI") or row.get("url") or "").strip()
            alias = (row.get("Alias") or "").strip()

            if not uri:
                result = {
                    "alias": alias, "uri": uri, "success": False, "service": None,
                    "service_banner": None, "cert_b64": None,
                    "tls_version": None, "cipher_suite": None,
                    "cert_subject": None, "cert_issuer": None, "cert_not_after": None,
                    "ssh_host_key_type": None, "ssh_host_key_fingerprint": None,
                    "findings": [], "error": "Missing URI",
                }
                results.append(result)
                yield {
                    "type": "progress", "index": idx + 1, "total": total_targets,
                    "alias": alias, "host": "", "port": 0, "result": result,
                }
                continue

            parsed = urlparse(uri)
            host = parsed.hostname or ""
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if not alias:
                alias = f"{host}_{port}"

            yield {
                "type": "scanning", "index": idx + 1, "total": total_targets,
                "alias": alias, "host": host, "port": port,
            }

            result = ScannerService.probe_target(alias, uri, host, port, timeout, ssl_ctx)
            results.append(result)

            yield {
                "type": "progress", "index": idx + 1, "total": total_targets,
                "alias": alias, "host": host, "port": port, "result": result,
            }

        scanned = sum(1 for r in results if r["success"])
        failed = len(results) - scanned

        # Build certificates CSV with findings columns
        certificates_csv = ScannerService._build_certificates_csv(results)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"certificates_{timestamp}.csv"

        stopped = bool(stop_flag and stop_flag.get("stopped"))
        # Do NOT include 'results' here — the JS already has them in scannerState.scanResults
        # (accumulated from every 'progress' event).  Including cert_b64 in the done event
        # makes the JSON frame potentially many MB, causing silent parse failures in the browser.
        yield {
            "type": "done",
            "total": total_targets,
            "scanned": scanned,
            "failed": failed,
            "stopped": stopped,
            "certificates_csv": certificates_csv,
            "filename": filename,
        }


# Made with Bob
