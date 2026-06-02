#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: get_asset_id_by_uri.py [-h] [-f CONFIG_FILE] --app-uri APP_URI --oidc-uri OIDC_URI [--realm REALM]
                              [-t REFRESH_TOKEN | -u USERNAME [-w PASSWORD]]
                              [--client-id CLIENT_ID] [--client-secret CLIENT_SECRET]
                              [--tenant-id TENANT_ID] [--timeout TIMEOUT] [--insecure] --uri URI

Search an IT asset by URI across applications, databases, and services, printing the first match (asset_id and uri) to stdout.
Supports two authentication methods: refresh token or username/password.

options:
  -h, --help            show this help message and exit
  --app-uri APP_URI     Base URI of the application host, e.g., https://<GCM_HOST>:<PORT>
  --oidc-uri OIDC_URI   Base URI of the OIDC (Keycloak) host, e.g., https://oidc.apps.example.com
  --realm REALM         OIDC realm (default: gcmrealm)
  -t REFRESH_TOKEN, --refresh-token REFRESH_TOKEN
                        Refresh token obtained from OIDC; prompts if omitted (when not using username/password)
  -u USERNAME, --username USERNAME
                        GCM username for password authentication (alternative to refresh token)
  -w PASSWORD, --password PASSWORD
                        GCM password; prompts if omitted (when using username)
  --client-id CLIENT_ID
                        OIDC client ID (default: gcmapiclient for refresh token, gcmclient for password)
  --client-secret CLIENT_SECRET
                        OIDC client secret (optional, for confidential clients)
  --tenant-id TENANT_ID
                        Tenant ID to include in the Authorization API body (optional)
  --timeout TIMEOUT     HTTP timeout seconds (default: 30)
  --insecure            Disable SSL certificate verification (NOT recommended in production)
  --uri URI             Target URI to match exactly. Filter will be uri=="<input value>".
"""

# This file includes AI-generated code - Review and modify as needed

import argparse
import getpass
import os
import sys

# --- Import AuthzClient from ../common/oidc_authz_client.py ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from common.oidc_authz_client import AuthzClient  # noqa: E402
from common.config_loader import load_config, add_config_argument, apply_config_defaults  # noqa: E402


ASSET_CATEGORY = "it_assets"
SEARCH_ORDER = ["services", "applications", "databases"]  # Search order


def build_arg_parser():
    """Build CLI argument parser."""
    p = argparse.ArgumentParser(
        description=(
            "Search an IT asset by URI across applications, databases, and services, "
            "printing the first match (asset_id and uri) to stdout.\n"
            "Supports two authentication methods: refresh token or username/password."
        )
    )
    # Connection / OIDC
    p.add_argument("--app-uri", required=True,
                   help="Base URI of the application host, e.g., https://<GCM_HOST>:<PORT>")
    p.add_argument("--oidc-uri", required=True,
                   help="Base URI of the OIDC (Keycloak) host, e.g., https://oidc.apps.example.com")
    p.add_argument("--realm", default="gcmrealm", help="OIDC realm (default: gcmrealm)")
    
    # Authentication: mutually exclusive group for refresh token vs username/password
    auth_group = p.add_mutually_exclusive_group(required=False)
    auth_group.add_argument("-t", "--refresh-token", required=False,
                            help="Refresh token obtained from OIDC; prompts if omitted (when not using username/password)")
    auth_group.add_argument("-u", "--username", required=False,
                            help="GCM username for password authentication (alternative to refresh token)")
    
    p.add_argument("-w", "--password", required=False,
                   help="GCM password; prompts if omitted (when using username)")
    p.add_argument("--client-id", default="",
                   help="OIDC client ID (default: gcmapiclient for refresh token, gcmclient for password)")
    p.add_argument("--client-secret", default="",
                   help="OIDC client secret (optional, for confidential clients)")
    
    p.add_argument("--tenant-id", default="",
                   help="Tenant ID to include in the Authorization API body (optional)")
    p.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds (default: 30)")
    p.add_argument("--insecure", action="store_true",
                   help="Disable SSL certificate verification (NOT recommended in production)")
    # Search condition
    p.add_argument("--uri", required=True,
                   help='Target URI to match exactly. Filter will be uri=="<input value>".')
    return p


def build_request_body(uri: str):
    """Build POST body per requirements (columns limited to asset_id and uri, page_size=1)."""
    return {
        "columns": ["asset_id", "uri"],
        "search_by": uri,
        "page_number": 1,
        "page_size": 1
    }


def extract_first_item(payload):
    """
    Extract the first matching item from the API response.

    Primary format supported:
      {
        "total_count": <int>,
        "it_assets": [
          {"asset_id": "...", "uri": "..."},
          ...
        ]
      }
    """
    if payload is None:
        return None

    # Primary: response with "it_assets" array
    if isinstance(payload, dict) and "it_assets" in payload:
        it_assets = payload.get("it_assets")
        if isinstance(it_assets, list) and it_assets:
            return it_assets[0]

    return None


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

    # Initialize AuthzClient (no environment variables)
    config = {
        "app_uri": args.app_uri.rstrip("/"),
        "oidc_uri": args.oidc_uri.rstrip("/"),
        "realm": args.realm,
        "verify_ssl": not args.insecure,
        "timeout": args.timeout,
        "user_agent": "search-asset-by-uri/1.1",
    }
    try:
        client = AuthzClient(config)
    except Exception as e:
        print(f"[ERROR] Client initialization error: {e}")
        return 1

    # Acquire access_token
    try:
        if use_password_auth:
            access_token = client.get_access_token_by_password(
                client_id=args.client_id,
                username=args.username,
                password=args.password,
                client_secret=args.client_secret if args.client_secret else None
            )
        else:
            access_token = client.get_access_token_by_refresh(args.refresh_token)
    except Exception as e:
        print(f"[ERROR] Token acquisition error: {e}")
        return 2

    # Call Authorization API (v2) before asset search
    try:
        auth_resp = client.call_authorization_api(access_token, tenant_id=args.tenant_id)
        if not auth_resp.ok:
            print(f"[ERROR] Authorization API failed: HTTP {auth_resp.status_code}")
            return 3
    except Exception as e:
        print(f"[ERROR] Authorization API error: {e}")
        return 3

    # Search across asset types in required order
    body = build_request_body(args.uri)

    for asset_type in SEARCH_ORDER:
        list_path = f"ibm/assetinventory/api/v1/assets/{ASSET_CATEGORY}/{asset_type}"
        try:
            resp = client.post(list_path, access_token, json_body=body)
        except Exception as e:
            print(f"[WARN] Assets API error ({asset_type}): {e}")
            continue

        if not resp.ok:
            print(f"[INFO] No match in '{asset_type}' or request failed: HTTP {resp.status_code}")
            continue

        try:
            payload = resp.json()
        except Exception:
            payload = None

        item = extract_first_item(payload)
        if item and ("asset_id" in item or "uri" in item):
            # Print the first match and exit
            print("[MATCH]")
            print(f"  asset_type: {asset_type}")
            print(f"  asset_id : {item.get('asset_id')}")
            print(f"  uri      : {item.get('uri')}")
            return 0

        print(f"[INFO] No match found in '{asset_type}'.")

    # No match in all asset types
    print("[RESULT] No asset matched the specified URI in applications/databases/services.")
    print(f"  uri: {args.uri}")
    return 4


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
