#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create a user in a TARGET realm (e.g., gcmrealm) by authenticating to the MASTER realm
with an admin user (e.g., gcmadmin) using Resource Owner Password Credentials (password grant).

Enhancements:
- Suppress InsecureRequestWarning when --insecure is used
- Short options: -u for --admin-username, -w for --admin-password
- Set initial password for the new user with --initial-password and optional --temporary-password

Examples
--------
# Using admin-cli (no secret required) in master realm to create a user in gcmrealm
python create_keycloak_user_admin_password.py \
  --oidc-uri https://<keycloak-host> \
  --admin-realm master \
  --target-realm gcmrealm \
  -u gcmadmin \
  -w '<password>' \
  --username taro.yamada \
  --email taro@example.com \
  --first-name Taro \
  --last-name Yamada \
  --email-verified --enabled \
  --initial-password 'P@ssw0rd!' --temporary-password

Notes
-----
- The admin user (master realm) must have sufficient roles to manage users in the target realm.
- This script uses password grant. Ensure TLS and least-privilege.
- No environment variables; everything is passed as CLI flags.
"""

import argparse
import sys
import requests
import urllib3
from getpass import getpass
from typing import Optional


def build_urls(oidc_uri: str, admin_realm: str, target_realm: str):
    base = oidc_uri.rstrip('/')
    token_url = f"{base}/realms/{admin_realm}/protocol/openid-connect/token"
    users_url = f"{base}/admin/realms/{target_realm}/users"
    return token_url, users_url


def get_access_token_password(token_url: str, client_id: str, client_secret: str,
                              admin_username: str, admin_password: str, verify_ssl: bool) -> str:
    data = {
        'grant_type': 'password',
        'client_id': client_id,
        'username': admin_username,
        'password': admin_password,
        'scope': 'openid'
    }
    if client_secret:
        data['client_secret'] = client_secret

    headers = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'kc-admin-password/1.1'}

    resp = requests.post(token_url, data=data, headers=headers, verify=verify_ssl, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Token request failed: HTTP {resp.status_code} - {resp.text}")
    token = resp.json().get('access_token')
    if not token:
        raise RuntimeError('No access_token in token response')
    return token


def create_user(users_url: str, access_token: str, username: str, email: str,
                first_name: str, last_name: str, enabled: bool, email_verified: bool,
                initial_password: Optional[str], temporary_password: bool,
                verify_ssl: bool):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'kc-admin-password/1.1'
    }
    payload = {
        'username': username,
        'email': email,
        'firstName': first_name,
        'lastName': last_name,
        'enabled': bool(enabled),
        'emailVerified': bool(email_verified),
        'requiredActions': []
    }

    if initial_password is not None:
        payload['credentials'] = [{
            'type': 'password',
            'value': initial_password,
            'temporary': bool(temporary_password)
        }]

    resp = requests.post(users_url, json=payload, headers=headers, verify=verify_ssl, timeout=30)
    if resp.status_code not in (201, 204):
        raise RuntimeError(f"User creation failed: HTTP {resp.status_code} - {resp.text}")
    return resp.headers.get('Location', '')


def parse_args(argv):
    p = argparse.ArgumentParser(description='Create a user in a target realm by authenticating to master realm with admin user (password grant).')
    p.add_argument('--oidc-uri', required=True, help='Base URI for Keycloak, e.g., https://keycloak.example.com')
    p.add_argument('--admin-realm', default='master', help='Realm used for admin authentication (default: master)')
    p.add_argument('--target-realm', required=True, help='Realm where the new user will be created (e.g., gcmrealm)')

    # Client for password grant in admin realm
    p.add_argument('--client-id', default='admin-cli', help='Client ID used for password grant in admin realm (default: admin-cli)')
    p.add_argument('--client-secret', default='', help='Client secret (if using a confidential client); not needed for admin-cli')

    p.add_argument('-u', '--admin-username', required=True, help='Admin username in the admin realm (e.g., gcmadmin)')
    p.add_argument('-w', '--admin-password', required=False, help='Admin password (if omitted, will prompt)')

    # New user info
    p.add_argument('--username', required=True, help='Username to create in target realm')
    p.add_argument('--email', required=True, help='Email of the new user')
    p.add_argument('--first-name', required=True, help='First name')
    p.add_argument('--last-name', required=True, help='Last name')

    p.add_argument('--enabled', action='store_true', help='Create user as enabled')
    p.add_argument('--email-verified', action='store_true', help='Set emailVerified=true')

    # Set new user's password
    p.add_argument('--initial-password', help='Optional: initial password for the new user')
    p.add_argument('--temporary-password', action='store_true', help='Mark the initial password as temporary (user must change at first login)')

    p.add_argument('--insecure', action='store_true', help='Disable TLS certificate verification and suppress warnings (NOT for production)')
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    token_url, users_url = build_urls(args.oidc_uri, args.admin_realm, args.target_realm)

    verify_ssl = not args.insecure
    if not verify_ssl:
        # Suppress only when user explicitly opts out of verification
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    if not args.admin_password:
        args.admin_password = getpass('Admin password (input hidden): ')

    try:
        print('Requesting access token via password grant (master realm)...')
        access_token = get_access_token_password(
            token_url=token_url,
            client_id=args.client_id,
            client_secret=args.client_secret,
            admin_username=args.admin_username,
            admin_password=args.admin_password,
            verify_ssl=verify_ssl,
        )
        print('Access token acquired.')
    except Exception as e:
        print(f'Token acquisition error: {e}')
        return 1

    try:
        print(f'Creating user in realm {args.target_realm}...')
        location = create_user(
            users_url=users_url,
            access_token=access_token,
            username=args.username,
            email=args.email,
            first_name=args.first_name,
            last_name=args.last_name,
            enabled=args.enabled,
            email_verified=args.email_verified,
            initial_password=args.initial_password,
            temporary_password=args.temporary_password,
            verify_ssl=verify_ssl,
        )
        if location:
            print(f'Success: user created. Location: {location}')
        else:
            print('Success: user created.')
        return 0
    except Exception as e:
        print(f'User creation error: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
