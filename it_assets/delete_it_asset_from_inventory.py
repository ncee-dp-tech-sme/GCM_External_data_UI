#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: delete_it_asset_from_inventory.py [-h] [-f CONFIG_FILE] --app-uri APP_URI --oidc-uri OIDC_URI [--realm REALM]
                                         [-t REFRESH_TOKEN | -u USERNAME [-w PASSWORD]]
                                         [--client-id CLIENT_ID] [--client-secret CLIENT_SECRET]
                                         [--tenant-id TENANT_ID] [--timeout TIMEOUT] [--insecure]
                                         (--asset-id ASSET_ID | --uri URI)

Delete IT assets from Asset Inventory by asset-id or URI (either one is required).
Supports two authentication methods: refresh token or username/password.

options:
  -h, --help            show this help message and exit
  --app-uri APP_URI     Base URI for the application host, e.g., https://<GCM_HOST>:<PORT>
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
  --insecure            Disable SSL certificate verification (NOT recommended)
  --asset-id ASSET_ID   IT asset identifier to delete (single value)
  --uri URI             IT asset URI to delete (single value)
"""

# This file includes AI-generated code - Review and modify as needed

import argparse
import json
import getpass
import os
import sys

# --- import AuthzClient from ../common/oidc_authz_client.py ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

from common.oidc_authz_client import AuthzClient  # noqa: E402
from common.config_loader import load_config, add_config_argument, apply_config_defaults  # noqa: E402


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Delete IT assets from Asset Inventory by asset-id or URI (either one is required).\n"
            "Supports two authentication methods: refresh token or username/password.\n"
            "Configuration can be loaded from config.toml file."
        )
    )
    
    # Config file argument
    add_config_argument(parser)
    
    # Connection / OIDC
    parser.add_argument(
        "--app-uri",
        help="Base URI for the application host, e.g., https://<GCM_HOST>:<PORT>"
    )
    parser.add_argument(
        "--oidc-uri",
        help="Base URI for the OIDC host (Keycloak), e.g., https://oidc.apps.example.com"
    )
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
    
    parser.add_argument("--tenant-id", default="", help="Tenant ID to include in the authorization API body (optional)")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds (default: 30)")
    parser.add_argument("--insecure", action="store_true", help="Disable SSL certificate verification (NOT recommended)")

    # Deletion inputs: require either --asset-id or --uri
    mex = parser.add_mutually_exclusive_group(required=True)
    mex.add_argument("--asset-id", help="IT asset identifier to delete (single value)")
    mex.add_argument("--uri", help="IT asset URI to delete (single value)")
    return parser


def build_delete_body(asset_id, uri):
    """
    Build the deletion POST body. At least one of asset_id or uri must be provided.
    The API expects arrays for 'asset_id' and 'uri' even for single values.
    """
    asset_id = (asset_id or "").strip()
    uri = (uri or "").strip()
    if not asset_id and not uri:
        # Argparse enforces one-of requirement; this is an extra guard.
        raise ValueError("Either --asset-id or --uri must be provided.")
    body = {
        "asset_id": [asset_id] if asset_id else [],
        "uri": [uri] if uri else [],
    }
    return body


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

    # Build deletion body (argparse already enforces one-of requirement)
    body = build_delete_body(args.asset_id, args.uri)

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
        "user_agent": "delete-it-assets/2.0",
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

    # Call Authorization API (v2)
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

    # Call delete API
    delete_path = "ibm/assetinventory/api/v1/assets/delete/it_assets"
    try:
        print("\nPosting to IT assets delete API...")
        resp = client.post(delete_path, access_token, json_body=body)
        print(f"Delete API Response: HTTP {resp.status_code}")
    except Exception as e:
        print(f"Delete API error: {e}")
        return 4

    # Print JSON (or raw text if not JSON)
    try:
        payload = resp.json()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        print("Response is not JSON; printing raw text:")
        print(resp.text)

    return 0 if resp.ok else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
