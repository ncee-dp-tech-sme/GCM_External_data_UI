#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: show_version_info.py [-h] [-f CONFIG_FILE] --app-uri APP_URI --oidc-uri OIDC_URI [--realm REALM]
                            [-t REFRESH_TOKEN | -u USERNAME [-w PASSWORD]]
                            [--client-id CLIENT_ID] [--client-secret CLIENT_SECRET]
                            [--tenant-id TENANT_ID] [--timeout TIMEOUT] [--insecure]

Run Authorization API and then fetch/print version info.
Supports two authentication methods: refresh token or username/password.

options:
  -h, --help            show this help message and exit
  --app-uri APP_URI     Base URI for the app, e.g., https://gcmapp.apps.example.com
  --oidc-uri OIDC_URI   Base URI for OIDC (Keycloak), e.g., https://oidc.apps.example.com
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
                        tenantId included in Authorization API body (default: empty)
  --timeout TIMEOUT     HTTP timeout seconds (default: 30)
  --insecure            Disable SSL certificate verification (NOT recommended)
"""

# This file includes AI-generated code - Review and modify as needed

import argparse
import getpass
import sys

from oidc_authz_client import AuthzClient
from config_loader import load_config, add_config_argument, apply_config_defaults


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            'Run Authorization API and then fetch/print version info.\n'
            'Supports two authentication methods: refresh token or username/password.\n'
            'Configuration can be loaded from config.toml file.'
        )
    )
    
    # Config file argument
    add_config_argument(parser)
    
    parser.add_argument('--app-uri', help='Base URI for the app, e.g., https://gcmapp.apps.example.com')
    parser.add_argument('--oidc-uri', help='Base URI for OIDC (Keycloak), e.g., https://oidc.apps.example.com')
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
    
    parser.add_argument('--tenant-id', default='', help='tenantId included in Authorization API body (default: empty)')
    parser.add_argument('--timeout', type=float, default=30.0, help='HTTP timeout seconds (default: 30)')
    parser.add_argument('--insecure', action='store_true', help='Disable SSL certificate verification (NOT recommended)')
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

    # Build config dict passed to the library
    config = {
        'app_uri': args.app_uri,
        'oidc_uri': args.oidc_uri,
        'realm': args.realm,
        'verify_ssl': not args.insecure,
        'timeout': args.timeout,
        'user_agent': 'get-authz-token/2.0',
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
        print('Access Token:')
        print(access_token)
    except Exception as e:
        print(f'Token acquisition error: {e}')
        return 2

    # Call Authorization API
    try:
        print('Calling Authorization API (v2)...')
        resp = client.call_authorization_api(access_token, tenant_id=args.tenant_id)
        print(f'Authorization Response: HTTP {resp.status_code}')
        try:
            print(resp.json())
        except Exception:
            print('Response is not JSON; printing raw text:')
            print(resp.text)
    except Exception as e:
        print(f'Authorization API error: {e}')
        return 3

    # Fetch Version Info
    try:
        print('Fetching version info (v1/system/version-info)...')
        vi_resp = client.get('/ibm/usermanagement/api/v1/system/version-info', access_token)
        print('Version Info Response:')
        print(vi_resp.status_code)
        try:
            print(vi_resp.json())
        except Exception as e:
            print('JSON decode error:', e)
            print(vi_resp.text)
    except Exception as e:
        print(f'Version info API error: {e}')
        return 4

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
