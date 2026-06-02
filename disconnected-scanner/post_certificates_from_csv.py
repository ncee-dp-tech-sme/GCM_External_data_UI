#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: post_certificates_from_csv.py [-h] [-f CONFIG_FILE] --app-uri APP_URI --oidc-uri OIDC_URI [--realm REALM]
                                     [-t REFRESH_TOKEN | -u USERNAME [-w PASSWORD]]
                                     [--client-id CLIENT_ID] [--client-secret CLIENT_SECRET]
                                     [--tenant-id TENANT_ID] [--timeout TIMEOUT] [--insecure]
                                     -f CSV_FILE [--filename FILENAME] [--content-type CONTENT_TYPE]

Send an existing certificate CSV to the API (OIDC -> Authorization -> Import CSV).
Supports two authentication methods: refresh token or username/password.

options:
  -h, --help            show this help message and exit
  --app-uri APP_URI     Base URI for the app (e.g., https://gcmapp.apps.example.com)
  --oidc-uri OIDC_URI   Base URI for OIDC/Keycloak (e.g., https://oidc.apps.example.com)
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
                        tenantId included in Authorization API body (optional)
  --timeout TIMEOUT     HTTP timeout seconds (default: 30)
  --insecure            Disable SSL certificate verification (NOT recommended)
  -f CSV_FILE, --csv-file CSV_FILE
                        Path to the certificate CSV (Import-certificate-template.csv format)
  --filename FILENAME   multipart/form-data file part name (default: Import-certificate-template.csv)
  --content-type CONTENT_TYPE
                        Content-Type for the file part (e.g., text/csv, application/vnd.ms-excel)
"""

# This file includes AI-generated code - Review and modify as needed

import argparse
import getpass
import os
import sys
import json

# --- Import AuthzClient (supports package or plain module in ../common) ---
try:
    from common.oidc_authz_client import AuthzClient  # package form (common/__init__.py exists)
    from common.config_loader import load_config, add_config_argument, apply_config_defaults
except Exception:
    COMMON_DIR = os.path.join(os.path.dirname(__file__), '..', 'common')
    if COMMON_DIR not in sys.path:
        sys.path.append(COMMON_DIR)
    from oidc_authz_client import AuthzClient  # module form
    from config_loader import load_config, add_config_argument, apply_config_defaults

# Fixed import API path
IMPORT_PATH = 'ibm/assetinventory/api/v1/assets/csv/import/certificates'


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            'Send an existing certificate CSV to the API (OIDC -> Authorization -> Import CSV).\n'
            'Supports two authentication methods: refresh token or username/password.\n'
            'Configuration can be loaded from config.toml file.'
        )
    )
    
    # Config file argument (no short option due to conflict with -f/--csv-file)
    parser.add_argument(
        '--config-file',
        help='Path to TOML configuration file (default: config.toml in current or parent directory, or GCM_CONFIG env var)'
    )
    
    parser.add_argument('--app-uri',
                        help='Base URI for the app (e.g., https://gcmapp.apps.example.com)')
    parser.add_argument('--oidc-uri',
                        help='Base URI for OIDC/Keycloak (e.g., https://oidc.apps.example.com)')
    parser.add_argument('--realm', default='gcmrealm', help='OIDC realm (default: gcmrealm)')
    
    # Authentication: mutually exclusive group for refresh token vs username/password
    auth_group = parser.add_mutually_exclusive_group(required=False)
    auth_group.add_argument('-t', '--refresh-token', required=False,
                            help='Refresh token obtained from OIDC/Keycloak; prompts if omitted (when not using username/password)')
    auth_group.add_argument('-u', '--username', required=False,
                            help='GCM username for password authentication (alternative to refresh token)')
    
    parser.add_argument('-w', '--password', required=False,
                        help='GCM password; prompts if omitted (when using username)')
    parser.add_argument('--client-id', default='',
                        help='OIDC client ID (default: gcmapiclient for refresh token, gcmclient for password)')
    parser.add_argument('--client-secret', default='',
                        help='OIDC client secret (optional, for confidential clients)')
    
    parser.add_argument('--tenant-id', default='',
                        help='tenantId included in Authorization API body (optional)')
    parser.add_argument('--timeout', type=float, default=30.0,
                        help='HTTP timeout seconds (default: 30)')
    parser.add_argument('--insecure', action='store_true',
                        help='Disable SSL certificate verification (NOT recommended)')
    parser.add_argument('-f', '--csv-file', required=True,
                        help='Path to the certificate CSV (Import-certificate-template.csv format)')
    parser.add_argument('--filename', default='Import-certificate-template.csv',
        help='multipart/form-data file part name (default: Import-certificate-template.csv)')
    parser.add_argument('--content-type', default='text/csv',
        help='Content-Type for the file part (e.g., text/csv, application/vnd.ms-excel)')
    return parser


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
        args.client_id = 'gcmclient' if use_password_auth else 'gcmapiclient'

    # Prompt for credentials if not provided
    if use_password_auth:
        # Password authentication
        if not args.password:
            args.password = getpass.getpass(prompt='Enter password (input hidden): ')
    else:
        # Refresh token authentication
        if not args.refresh_token:
            args.refresh_token = getpass.getpass(prompt='Enter refresh_token (input hidden): ')

    # Build config for the client
    config = {
        'app_uri': args.app_uri,
        'oidc_uri': args.oidc_uri,
        'realm': args.realm,
        'verify_ssl': not args.insecure,
        'timeout': args.timeout,
        'user_agent': 'post-certificates-from-csv/2.0',
    }

    try:
        client = AuthzClient(config)
    except Exception as e:
        print(f'Client initialization error: {e}')
        return 1

    # Acquire access_token
    try:
        if use_password_auth:
            print('Obtaining access_token via password grant...')
            access_token = client.get_access_token_by_password(
                client_id=args.client_id,
                username=args.username,
                password=args.password,
                client_secret=args.client_secret if args.client_secret else None
            )
        else:
            print('Obtaining access_token from refresh_token...')
            access_token = client.get_access_token_by_refresh(args.refresh_token)
    except Exception as e:
        print(f'Token acquisition error: {e}')
        return 2

    # Call Authorization API
    try:
        print('Calling Authorization API (v2)...')
        authz_resp = client.call_authorization_api(access_token, tenant_id=args.tenant_id)
        print(f'Authorization Response: HTTP {authz_resp.status_code}')
        try:
            print(json.dumps(authz_resp.json(), ensure_ascii=False, indent=2))
        except Exception:
            print('Response is not JSON; printing raw text:')
            print(authz_resp.text)
        if not authz_resp.ok:
            print('Authorization API failed; aborting import.')
            return 2
    except Exception as e:
        print(f'Authorization API error: {e}')
        return 2

    # Read CSV bytes
    try:
        with open(args.csv_file, 'rb') as f:
            csv_bytes = f.read()
    except Exception as e:
        print(f'Failed to read CSV file: {e}')
        return 1

    # Build import URL
    import_url = f"{client.app_uri}/{IMPORT_PATH}"

    # POST multipart/form-data
    try:
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
            # Let requests set Content-Type with boundary automatically
        }
        files = {
            'file': (args.filename, csv_bytes, args.content_type),
        }
        print('Posting CSV to Asset Inventory import API (certificates)...')
        resp = client.session.post(
            import_url,
            headers=headers,
            files=files,
            verify=client.verify_ssl,
            timeout=client.timeout,
        )
        print(f'Import API Response: HTTP {resp.status_code}')
        try:
            print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
        except Exception:
            print('Import response is not JSON; printing raw text:')
            print(resp.text)
        return 0 if resp.ok else 3
    except Exception as e:
        print(f'Import API error: {e}')
        return 3


if __name__ == '__main__':
    import sys as _sys
    _sys.exit(main(_sys.argv[1:]))
