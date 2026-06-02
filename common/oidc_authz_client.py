#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic library: Provides common routines to obtain an OIDC access token from a
refresh_token or password grant and call the Authorization API.

- Configuration is passed as a dictionary (dict) for flexibility and reuse.
- Common functionality for all API calls:
  * URL builders (OIDC/Token, Authorization)
  * Base64URL decode & client_id extraction from refresh_token (azp/client_id)
  * Access token acquisition (refresh_token grant or password grant)
  * Bearer auth header builder
  * Generic GET/POST helpers (relative to app_uri or absolute URL)

Dependencies: requests, urllib3
No environment variables are required.
"""

# This code includes collective AI generated fragments

import requests
import urllib3
import base64
import json

class AuthzClient:
    def __init__(self, config):
        """Expected keys in the config dict:
        - app_uri: str (required)
        - oidc_uri: str (required)
        - realm: str (default 'gcmrealm')
        - verify_ssl: bool (default True)
        - timeout: int/float (default 30)
        - user_agent: str (default 'get-authz-token/2.0')
        """
        self.app_uri = str(config.get('app_uri', '')).rstrip('/')
        self.oidc_uri = str(config.get('oidc_uri', '')).rstrip('/')
        if not self.app_uri or not self.oidc_uri:
            raise ValueError('app_uri and oidc_uri are required')
        self.realm = str(config.get('realm', 'gcmrealm'))
        self.verify_ssl = bool(config.get('verify_ssl', True))
        self.timeout = config.get('timeout', 30)
        self.user_agent = str(config.get('user_agent', 'get-authz-token/2.0'))

        if not self.verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session = requests.Session()

    # --- URL builders ---
    def build_urls(self):
        token_url = f"{self.oidc_uri}/realms/{self.realm}/protocol/openid-connect/token"
        authz_url = f"{self.app_uri}/ibm/usermanagement/api/v2/authorization"
        return token_url, authz_url

    # --- JWT helper ---
    @staticmethod
    def _b64url_decode(segment):
        pad_len = (-len(segment)) % 4
        if pad_len:
            segment += '=' * pad_len
        return base64.urlsafe_b64decode(segment.encode('utf-8'))

    @staticmethod
    def extract_client_id_from_refresh_token(refresh_token):
        """Extract azp or client_id from Keycloak-style refresh_token payload.
        Returns None if it cannot be determined.
        """
        try:
            parts = refresh_token.split('.')
            if len(parts) < 2:
                return None
            payload_raw = AuthzClient._b64url_decode(parts[1])
            payload = json.loads(payload_raw.decode('utf-8'))
            return payload.get('azp') or payload.get('client_id')
        except Exception:
            return None

    # --- Token acquisition ---
    def get_access_token_by_refresh(self, refresh_token):
        """Obtain access token using refresh_token grant.
        
        Args:
            refresh_token: OIDC refresh token
            
        Returns:
            str: Access token
            
        Raises:
            RuntimeError: If token acquisition fails
        """
        token_url, _ = self.build_urls()
        client_id = self.extract_client_id_from_refresh_token(refresh_token)
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }
        if client_id:
            data['client_id'] = client_id
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': self.user_agent,
        }
        resp = self.session.post(token_url, data=data, headers=headers,
                                 verify=self.verify_ssl, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Token refresh failed: HTTP {resp.status_code} - {resp.text}")
        payload = resp.json()
        access_token = payload.get('access_token')
        if not access_token:
            raise RuntimeError('No access_token found in token response')
        return access_token

    def get_access_token_by_password(self, client_id, username, password, client_secret=None, scope='email openid gcm_tenant_creation'):
        """Obtain access token using password grant (Resource Owner Password Credentials).
        
        This method supports both confidential clients (with client_secret) and public clients
        (without client_secret). Public clients like Keycloak's default 'admin-cli' have
        "Client authentication" disabled and only require username/password.
        
        Args:
            client_id: OIDC client ID (e.g., 'admin-cli' for Keycloak admin operations)
            username: GCM user ID
            password: GCM user password
            client_secret: OIDC client secret (optional, None for public clients like admin-cli)
            scope: OAuth scope (default: 'email openid gcm_tenant_creation')
            
        Returns:
            str: Access token
            
        Raises:
            RuntimeError: If token acquisition fails
            
        Examples:
            # Public client (admin-cli with Authorization OFF)
            token = client.get_access_token_by_password('admin-cli', 'admin', 'password')
            
            # Confidential client (with client_secret)
            token = client.get_access_token_by_password('my-client', 'user', 'pass',
                                                        client_secret='secret123')
        """
        token_url, _ = self.build_urls()
        data = {
            'client_id': client_id,
            'username': username,
            'password': password,
            'grant_type': 'password',
            'scope': scope
        }
        # Only include client_secret if provided (for confidential clients)
        if client_secret is not None:
            data['client_secret'] = client_secret
            
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': self.user_agent,
        }
        resp = self.session.post(token_url, data=data, headers=headers,
                                 verify=self.verify_ssl, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(f"Token request failed: HTTP {resp.status_code} - {resp.text}")
        payload = resp.json()
        access_token = payload.get('access_token')
        if not access_token:
            raise RuntimeError('No access_token found in token response')
        return access_token

    # --- Authorization API ---
    def call_authorization_api(self, access_token, tenant_id=''):
        _, authz_url = self.build_urls()
        headers = self._bearer_headers(access_token)
        body = {'tenantId': tenant_id}
        resp = self.session.post(authz_url, headers=headers, json=body,
                                 verify=self.verify_ssl, timeout=self.timeout)
        return resp

    # --- Generic helpers for other APIs ---
    def _bearer_headers(self, access_token, extra=None):
        base = {
            'accept': 'application/json',
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        if extra:
            base.update(extra)
        return base

    def get(self, path_or_url, access_token, headers=None):
        url = path_or_url if path_or_url.startswith('http') else f"{self.app_uri}/{path_or_url.lstrip('/')}"
        hdrs = self._bearer_headers(access_token)
        if headers:
            hdrs.update(headers)
        return self.session.get(url, headers=hdrs, verify=self.verify_ssl, timeout=self.timeout)

    def post(self, path_or_url, access_token, json_body=None, headers=None):
        url = path_or_url if path_or_url.startswith('http') else f"{self.app_uri}/{path_or_url.lstrip('/')}"
        hdrs = self._bearer_headers(access_token)
        if headers:
            hdrs.update(headers)
        return self.session.post(url, headers=hdrs, json=json_body, verify=self.verify_ssl, timeout=self.timeout)
