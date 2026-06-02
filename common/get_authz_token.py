#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Keycloak Device Authorization Grant (RFC 8628) – CLI
** "OAuth 2.0 Device Authorization Grant" must be enabled on your Keycloak client Settings.
** "Client authentication" must be turned off (public access)

usage: get_authz_token.py [-h] --oidc-uri OIDC_URI [--realm REALM] -u CLIENT_ID [-o OUTPUT] [--insecure]

Keycloak Device Authorization (RFC 8628) CLI

options:
  -h, --help            show this help message and exit
  --oidc-uri OIDC_URI   OIDC base URI including https:// (e.g., https://host:port)
  --realm REALM         Realm name (default: gcmrealm)
  -u CLIENT_ID, --client-id CLIENT_ID
                        OIDC client_id (required)
  -o OUTPUT, --output OUTPUT
                        Output file to store refresh_token as JSON (default: ./token.json)
  --insecure            Allow self-signed server certificate (TLS verify disabled)
"""

# This code includes collective AI generated fragments

import argparse
import getpass
import json
import os
import sys
import time

import requests
import urllib3

# ------------------------- Fixed scope (kept out of CLI) -------------------------
FIXED_SCOPE = "openid email gcm_tenant_creation offline_access"

# ------------------------- Utilities -------------------------

def _verify_arg(insecure):
    """Return requests 'verify' argument based on --insecure."""
    if insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return False  # TLS verification disabled (development/testing only)
    return True  # Use system CA bundle; for self-signed, prefer a pinned CA file in production


def _ensure_https_base(uri):
    """Validate that the given base uri starts with https:// and does not include /realms."""
    if not uri.lower().startswith("https://"):
        raise ValueError("OIDC base URI must start with 'https://'. Example: https://host:port")
    base = uri.rstrip("/")
    if "/realms/" in base or base.endswith("/realms"):
        raise ValueError("Do not include '/realms' in --oidc-uri. Provide only 'https://host:port'.")
    return base


def _build_realm_base(oidc_base, realm):
    """Build realm base URI: https://host:port/realms/<realm>."""
    return "{}/realms/{}".format(oidc_base, realm)


def _fetch_endpoints(realm_base, verify):
    """Discover device authorization and token endpoints via OIDC well-known at the realm base URI."""
    well_known = "{}/.well-known/openid-configuration".format(realm_base)
    r = requests.get(well_known, timeout=10, verify=verify)
    r.raise_for_status()
    info = r.json()
    device_ep = info.get("device_authorization_endpoint")
    token_ep = info.get("token_endpoint")
    if not device_ep or not token_ep:
        raise RuntimeError("Device/Token endpoints not found in OIDC discovery.")
    return device_ep, token_ep


def _start_device_authorization(device_ep, client_id, verify):
    """Start Device Authorization request."""
    data = {"client_id": client_id, "scope": FIXED_SCOPE}
    print("=== Device Authorization Request ===")
    print("Endpoint  : {}".format(device_ep))
    print("Client ID : {}".format(client_id))
    print("Scope     : {}".format(data["scope"]))
    r = requests.post(device_ep, data=data, timeout=10, verify=verify)
    r.raise_for_status()
    resp = r.json()
    required = ("device_code", "user_code", "verification_uri", "expires_in")
    if not all(k in resp for k in required):
        raise RuntimeError("Invalid device authorization response: {}".format(resp))
    return resp


def _poll_token(token_ep, device_code, client_id, interval, verify):
    """Poll the token endpoint until access token is issued or error."""
    poll_interval = max(int(interval or 5), 5)
    while True:
        print("Polling token endpoint (interval={}s)...".format(poll_interval))
        time.sleep(poll_interval)
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code,
            "client_id": client_id,
        }
        r = requests.post(token_ep, data=data, timeout=10, verify=verify)
        if r.status_code == 200:
            return r.json()
        # RFC 8628-compliant error handling
        err = None
        try:
            err = r.json().get("error")
        except Exception:
            pass
        if err in ("authorization_pending", "slow_down"):
            if err == "slow_down":
                poll_interval += 5
            continue
        elif err in ("access_denied", "expired_token", "invalid_grant"):
            raise RuntimeError("Token polling failed: {}".format(r.text))
        else:
            r.raise_for_status()


# ------------------------- CLI -------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Keycloak Device Authorization (RFC 8628) CLI")
    # --oidc-uri: REQUIRED (base 'https://host:port')
    p.add_argument("--oidc-uri", required=True,
                   help="OIDC base URI including https:// (e.g., https://host:port)")
    # --realm: OPTIONAL (default gcmrealm)
    p.add_argument("--realm", required=False, default="gcmrealm",
                   help="Realm name (default: gcmrealm)")
    # --client-id with short -u
    p.add_argument("-u", "--client-id", required=True,
                   help="OIDC client_id (required)")
    # File output for refresh_token JSON
    p.add_argument("-o", "--output", default="token.json",
                   help="Output file to store refresh_token as JSON (default: ./token.json)")
    # Allow self-signed server certificate
    p.add_argument("--insecure", action="store_true",
                   help="Allow self-signed server certificate (TLS verify disabled)")
    return p.parse_args()


def main():
    args = parse_args()

    # Validate OIDC base and build realm base
    try:
        oidc_base = _ensure_https_base(args.oidc_uri)
    except Exception as e:
        print("[ERROR] {}".format(e))
        return 1
    realm_base = _build_realm_base(oidc_base, args.realm)

    verify = _verify_arg(args.insecure)

    try:
        device_ep, token_ep = _fetch_endpoints(realm_base, verify)
        authz = _start_device_authorization(device_ep, args.client_id, verify)

        # User guidance (console)
        print("\n=== Device Authorization Started ===")
        print("Verification URI : {}".format(authz["verification_uri"]))
        if authz.get("verification_uri_complete"):
            print("(Optional) Verification URI (complete): {}".format(authz["verification_uri_complete"]))
        print("User Code        : {}".format(authz["user_code"]))
        print("Expires in       : {} sec".format(authz["expires_in"]))
        print("Open the Verification URI and enter the User Code to sign in.\n")

        token_resp = _poll_token(token_ep, authz["device_code"], args.client_id, authz.get("interval", 5), verify)

        # Console: access_token / refresh_token / expires_at (access token expiry)
        access_token = token_resp.get("access_token")
        refresh_token = token_resp.get("refresh_token")
        expires_in = int(token_resp.get("expires_in", 300))
        out_obj = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": int(time.time()) + expires_in,
        }
        print("=== Token Response ===")
        print(json.dumps(out_obj, ensure_ascii=False, indent=2))

        # File: write refresh_token as proper JSON
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        except Exception:
            pass  # ok for current dir paths
        file_obj = {"refresh_token": refresh_token}
        with open(args.output, "w") as f:
            json.dump(file_obj, f, ensure_ascii=False, indent=2)
        print("[INFO] refresh_token written to JSON file: {}".format(args.output))

        return 0

    except requests.exceptions.SSLError as e:
        print("[ERROR] TLS verification failed. Use --insecure to allow self-signed certs: {}".format(e))
        return 2
    except requests.exceptions.HTTPError as e:
        print("[ERROR] HTTP error: {}".format(e))
        return 3
    except Exception as e:
        print("[ERROR] {}".format(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
