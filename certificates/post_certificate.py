#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: post_certificate.py [-h] [-f CONFIG_FILE] [--app-uri APP_URI] [--oidc-uri OIDC_URI] [--realm REALM]
                           [-t REFRESH_TOKEN | -u USERNAME [-w PASSWORD]]
                           [--client-id CLIENT_ID] [--client-secret CLIENT_SECRET]
                           [--tenant-id TENANT_ID] [--timeout TIMEOUT] [--insecure]
                           -i CERT_FILE --uri URI [--alias ALIAS]

Import a single certificate using the crypto_objects ingest API (JSON).
Supports two authentication methods: refresh token or username/password.
Configuration can be loaded from config.toml file.

options:
  -h, --help            show this help message and exit
  --app-uri APP_URI     Base URI for the application host, e.g., https://gcmapp.apps.example.com
  --oidc-uri OIDC_URI   Base URI for the OIDC host (Keycloak), e.g., https://oidc.apps.example.com
  --realm REALM         OIDC realm (default: gcmrealm)
  -t REFRESH_TOKEN, --refresh-token REFRESH_TOKEN
                        Refresh token obtained from OIDC/Keycloak; prompts if omitted (when not using username/password)
  -u USERNAME, --username USERNAME
                        GCM username for password authentication (alternative to refresh token)
  -w PASSWORD, --password PASSWORD
                        GCM password; prompts if omitted (when using username)
  --client-id CLIENT_ID
                        OIDC client ID (default: gcmapiclient for refresh token, gcmclient for password)
  --client-secret CLIENT_SECRET
                        OIDC client secret (optional, for confidential clients)
  --tenant-id TENANT_ID
                        Tenant ID to include in the authorization API body (optional)
  --timeout TIMEOUT     HTTP timeout seconds (default: 30)
  --insecure            Disable SSL certificate verification (NOT recommended in production)
  -i CERT_FILE, --cert-file CERT_FILE
                        Path to a certificate file (PEM or DER)
  --uri URI             Endpoint in 'https://host_or_ip:port' or 'host_or_ip:port' form (no path)
  --alias ALIAS         Optional alias; default is 'ip_port' (or 'host_port' when no IP is provided)
"""

# This file includes AI-generated code - Review and modify as needed

import argparse
import sys
import base64
import getpass
import re
import os
from urllib.parse import urlparse

# --- import AuthzClient from ../common/oidc_authz_client.py ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from common.oidc_authz_client import AuthzClient  # noqa: E402
from common.config_loader import load_config, add_config_argument, apply_config_defaults  # noqa: E402


def build_arg_parser():
    """Create the single-command parser (certificate-only)."""
    parser = argparse.ArgumentParser(
        description=(
            "Import a single certificate using the crypto_objects ingest API (JSON).\n"
            "Supports two authentication methods: refresh token or username/password.\n"
            "Configuration can be loaded from config.toml file."
        )
    )
    
    # Config file argument
    add_config_argument(parser)
    
    # OIDC / connection settings
    parser.add_argument("--app-uri",
                        help="Base URI for the application host, e.g., https://gcmapp.apps.example.com")
    parser.add_argument("--oidc-uri",
                        help="Base URI for the OIDC host (Keycloak), e.g., https://oidc.apps.example.com")
    parser.add_argument("--realm", default="gcmrealm", help="OIDC realm (default: gcmrealm)")
    
    # Authentication: mutually exclusive group for refresh token vs username/password
    auth_group = parser.add_mutually_exclusive_group(required=False)
    auth_group.add_argument("-t", "--refresh-token", required=False,
                            help="Refresh token obtained from OIDC/Keycloak; prompts if omitted (when not using username/password)")
    auth_group.add_argument("-u", "--username", required=False,
                            help="GCM username for password authentication (alternative to refresh token)")
    
    parser.add_argument("-w", "--password", required=False,
                        help="GCM password; prompts if omitted (when using username)")
    parser.add_argument("--client-id", default="",
                        help="OIDC client ID (default: gcmapiclient for refresh token, gcmclient for password)")
    parser.add_argument("--client-secret", default="",
                        help="OIDC client secret (optional, for confidential clients)")
    
    parser.add_argument("--tenant-id", default="",
                        help="Tenant ID to include in the authorization API body (optional)")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds (default: 30)")
    parser.add_argument("--insecure", action="store_true",
                        help="Disable SSL certificate verification (NOT recommended in production)")

    # Certificate inputs
    parser.add_argument("-i", "--cert-file", required=True, help="Path to a certificate file (PEM or DER)")
    parser.add_argument("--uri", required=True,
                        help="Endpoint in 'https://host_or_ip:port' or 'host_or_ip:port' form (no path)")
    parser.add_argument("--alias", default="",
                        help="Optional alias; default is 'ip_port' (or 'host_port' when no IP is provided)")
    return parser


def normalize_flexible_uri(uri):
    """
    Normalize user input and return:
    - api_uri_https: always 'https://host:port' (for potential HTTPS calls)
    - relationship_uri:
        * if input had scheme (https://), keep scheme (e.g., 'https://host:port')
        * if input had no scheme, keep scheme-less ('host:port' or '[IPv6]:port')
    - host, port: parsed host and port (port is int)
    Accepts:
    - 'https://host:port'
    - 'host:port' (no scheme)
    IPv6:
    - Prefer bracketed form: [2001:db8::1]:443
    """
    raw = uri.strip()

    # Case 1: Scheme present -> preserve it in relationship_uri
    if raw.lower().startswith("https://"):
        p = urlparse(raw)
        if p.scheme.lower() != "https":
            raise ValueError("URI scheme must be https if provided.")
        if not p.hostname or not p.port:
            raise ValueError("URI must include host/IP and port (e.g., 'https://host_or_ip:443').")
        host = p.hostname
        port = p.port
        api_uri_https = f"https://{host}:{port}"
        relationship_uri = api_uri_https  # preserve scheme for relationships
        return api_uri_https, relationship_uri, host, port

    # Case 2: No scheme, bracketed IPv6 '[...]:port'
    bracket_ipv6 = re.match(r"^\[(?P<host>.+)\]:(?P<port>\d+)$", raw)
    if bracket_ipv6:
        host = bracket_ipv6.group("host")
        port = int(bracket_ipv6.group("port"))
        api_uri_https = f"https://{host}:{port}"
        relationship_uri = f"[{host}]:{port}"  # scheme-less but keep bracketed form
        return api_uri_https, relationship_uri, host, port

    # Case 3: No scheme, unbracketed host:port
    if ":" not in raw:
        raise ValueError("URI without scheme must be 'host:port' (e.g., 'example.com:443').")
    host, port_str = raw.rsplit(":", 1)
    host = host.strip()
    port_str = port_str.strip()
    if not host or not port_str.isdigit():
        raise ValueError("Invalid 'host:port' format. Example: 'example.com:443' or '[2001:db8::1]:443'.")
    port = int(port_str)
    api_uri_https = f"https://{host}:{port}"
    relationship_uri = f"{host}:{port}"  # scheme-less
    return api_uri_https, relationship_uri, host, port


def read_file_as_base64(path):
    """
    Read the entire input file (PEM or DER) and Base64-encode it.
    No header/footer stripping or validation; output has no newlines.
    """
    with open(path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode("ascii")


def make_default_alias(host, port):
    """
    Produce a default alias in 'ip_port' style when host is an IP (IPv4/IPv6),
    otherwise 'host_port'. Brackets are removed and ':' in IPv6 is replaced by '_'.
    """
    host_clean = host.strip()
    # Remove IPv6 brackets if any
    host_clean = host_clean.strip("[]")
    # Heuristic: treat as IP if it contains only digits, '.' or ':' (IPv4/IPv6)
    is_ip_like = bool(re.fullmatch(r"[0-9.:]+", host_clean))
    if ":" in host_clean:  # IPv6 -> replace ':' with '_'
        host_clean = host_clean.replace(":", "_")
    alias = f"{host_clean}_{port}"
    return alias if is_ip_like else alias  # same shape; when IP provided it equals 'ip_port'


def main(argv):
    parser = build_arg_parser()
    
    # Load config file and apply defaults
    config = load_config()
    apply_config_defaults(parser, config)
    
    args = parser.parse_args(argv)
    
    # Validate required arguments (after config defaults applied)
    if not args.app_uri:
        parser.error("--app-uri is required (either via command-line or config file)")
    if not args.oidc_uri:
        parser.error("--oidc-uri is required (either via command-line or config file)")

    # Determine authentication method
    use_password_auth = args.username is not None
    
    # Set default client_id based on authentication method if not specified
    if not args.client_id:
        args.client_id = "gcmclient" if use_password_auth else "gcmapiclient"

    # Prompt for credentials if not provided
    if use_password_auth:
        # Password authentication
        if not args.password:
            args.password = getpass.getpass(prompt="Enter password (input hidden): ")
    else:
        # Refresh token authentication
        if not args.refresh_token:
            args.refresh_token = getpass.getpass(prompt="Enter refresh_token (input hidden): ")

    # Build config dict passed to the AuthzClient (no environment variables)
    config = {
        "app_uri": args.app_uri.rstrip("/"),
        "oidc_uri": args.oidc_uri.rstrip("/"),
        "realm": args.realm,
        "verify_ssl": not args.insecure,
        "timeout": args.timeout,
        "user_agent": "post-cert-ingest/2.0",
    }

    # Initialize client
    try:
        client = AuthzClient(config)
    except Exception as e:
        print(f"Client initialization error: {e}")
        return 1

    # Acquire access_token
    try:
        if use_password_auth:
            print("Obtaining access_token via password grant...")
            access_token = client.get_access_token_by_password(
                client_id=args.client_id,
                username=args.username,
                password=args.password,
                client_secret=args.client_secret if args.client_secret else None
            )
        else:
            print("Obtaining access_token from refresh_token...")
            access_token = client.get_access_token_by_refresh(args.refresh_token)
        print("Access token acquired.")
    except Exception as e:
        print(f"Token acquisition error: {e}")
        return 2

    # Authorization API (v2)
    try:
        print("\nCalling authorization API (v2)...")
        auth_resp = client.call_authorization_api(access_token, tenant_id=args.tenant_id)
        print(f"Authorization API Response: HTTP {auth_resp.status_code}")
        try:
            print(auth_resp.json())
        except Exception:
            print("Authorization response is not JSON; printing raw text:")
            print(auth_resp.text)
        if not auth_resp.ok:
            print("Authorization API failed; aborting subsequent calls.")
            return 3
    except Exception as e:
        print(f"Authorization API error: {e}")
        return 3

    # Normalize URI & derive alias
    try:
        api_uri_https, relationship_uri, host, port = normalize_flexible_uri(args.uri)
    except ValueError as e:
        print(f"Invalid URI: {str(e)}")
        return 1

    alias = (args.alias.strip() or make_default_alias(host, port))
    print(f"Using alias: {alias}")
    print(f"Relationships URI: {relationship_uri}")

    # Read entire file and Base64-encode (no validation/stripping)
    try:
        cert_b64 = read_file_as_base64(args.cert_file)
    except Exception as e:
        print(f"Failed to read and base64-encode the input file: {str(e)}")
        return 1

    # Build ingest body (JSON)
    body = {
        "crypto_object_certs": {
            "cert_data": cert_b64,
            "crypto_object_alias": alias,
            "relationships": [
                {
                    "asset_identifiers": {"uri": relationship_uri},
                    "asset_type": "IT_ASSET",
                }
            ],
            "tag_ids": [],
        }
    }

    # POST to ingest API
    ingest_path = "ibm/assetinventory/api/v1/assets/ingest/crypto_objects/certificate_from_file"
    try:
        print("\nPosting to Asset Inventory ingest API (crypto_objects/certificate_from_file)...")
        resp = client.post(ingest_path, access_token, json_body=body)
        print(f"Ingest API Response: HTTP {resp.status_code}")
        if resp.headers.get("Content-Type", "").startswith("application/json"):
            try:
                print(resp.json())
            except Exception:
                print("Failed to parse JSON response.")
        else:
            print(resp.text)
    except Exception as e:
        print(f"Ingest API error: {e}")
        return 4

    return 0 if resp.ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
