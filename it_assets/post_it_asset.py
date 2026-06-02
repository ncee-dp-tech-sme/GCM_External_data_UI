#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
usage: post_it_asset.py [-h] [-f CONFIG_FILE] --app-uri APP_URI --oidc-uri OIDC_URI [--realm REALM]
                        [-t REFRESH_TOKEN | -u USERNAME [-w PASSWORD]]
                        [--client-id CLIENT_ID] [--client-secret CLIENT_SECRET]
                        [--tenant-id TENANT_ID] [--timeout TIMEOUT] [--insecure]
                        {create,update} ...

Obtain an access token, call the Authorization API, then create/update an IT asset.
Supports two authentication methods: refresh token or username/password.
Update uses PUT /api/v1/assets/it_assets for specific editable attributes and continues to use ingest API (v2) for other attributes.

positional arguments:
  {create,update}
    create              Create new asset (uri/ip/hostname/port/asset-type required)
    update              Update asset (uri required)

options:
  -h, --help            show this help message and exit
  --app-uri APP_URI     Base URI for the application (e.g., https://gcmapp.apps.example.com)
  --oidc-uri OIDC_URI   Base URI for OIDC (Keycloak) (e.g., https://oidc.apps.example.com)
  --realm REALM         OIDC realm (default: gcmrealm)
  -t REFRESH_TOKEN, --refresh-token REFRESH_TOKEN
                        OIDC/Keycloak refresh token; prompts if omitted (when not using username/password)
  -u USERNAME, --username USERNAME
                        GCM username for password authentication (alternative to refresh token)
  -w PASSWORD, --password PASSWORD
                        GCM password; prompts if omitted (when using username)
  --client-id CLIENT_ID
                        OIDC client ID (default: gcmapiclient for refresh token, gcmclient for password)
  --client-secret CLIENT_SECRET
                        OIDC client secret (optional, for confidential clients)
  --tenant-id TENANT_ID
                        Tenant ID to include in Authorization API body (optional)
  --timeout TIMEOUT     HTTP timeout seconds (default: 30)
  --insecure            Disable SSL certificate verification (NOT recommended for production)


usage: post_it_asset.py create [-h] --uri URI --ip IP --hostname HOSTNAME [--protocol PROTOCOL] --port PORT --asset-type ASSET_TYPE
                               [--asset-sub-type ASSET_SUB_TYPE] [--mission-criticality MISSION_CRITICALITY] [--internet-facing INTERNET_FACING]
                               [--owner OWNER] [--tech-contacts TECH_CONTACTS] [--network NETWORK] [--environment ENVIRONMENT]
                               [--location LOCATION] [--custom-attr CUSTOM_ATTR]

options:
  -h, --help            show this help message and exit
  --uri URI             URI
  --ip IP               IP
  --hostname HOSTNAME   Hostname
  --protocol PROTOCOL   Protocol (e.g., TLS, TCP)
  --port PORT           Port (integer)
  --asset-type ASSET_TYPE
                        Asset type (e.g., Database, Service, Application)
  --asset-sub-type ASSET_SUB_TYPE
                        Asset sub type (e.g., MySQL)
  --mission-criticality MISSION_CRITICALITY
                        Mission criticality (integer; optional)
  --internet-facing INTERNET_FACING
                        Internet facing: for create (ingest v2) expects boolean; for update (PUT v1) expects DEFAULT/UNKNOWN/TRUE/FALSE or
                        truthy/falsy inputs
  --owner OWNER         Owner
  --tech-contacts TECH_CONTACTS
                        Tech contacts comma-separated (e.g., 'user1,admin2')
  --network NETWORK     Network (e.g., zone-1)
  --environment ENVIRONMENT
                        Environment (e.g., Staging, Production)
  --location LOCATION   Location (e.g., 'Helsinki, Finland')
  --custom-attr CUSTOM_ATTR
                        Repeatable; KEY=VALUE (e.g., --custom-attr os=linux)


usage: post_it_asset.py update [-h] --uri URI [--ip IP] [--hostname HOSTNAME] [--protocol PROTOCOL] [--port PORT] [--asset-type ASSET_TYPE]
                               [--asset-sub-type ASSET_SUB_TYPE] [--mission-criticality MISSION_CRITICALITY] [--internet-facing INTERNET_FACING]
                               [--owner OWNER] [--tech-contacts TECH_CONTACTS] [--network NETWORK] [--environment ENVIRONMENT]
                               [--location LOCATION] [--custom-attr CUSTOM_ATTR]

options:
  -h, --help            show this help message and exit
  --uri URI             URI
  --ip IP               IP
  --hostname HOSTNAME   Hostname
  --protocol PROTOCOL   Protocol (e.g., TLS, TCP)
  --port PORT           Port (integer)
  --asset-type ASSET_TYPE
                        Asset type (e.g., Database, Service, Application)
  --asset-sub-type ASSET_SUB_TYPE
                        Asset sub type (e.g., MySQL)
  --mission-criticality MISSION_CRITICALITY
                        Mission criticality (integer; optional)
  --internet-facing INTERNET_FACING
                        Internet facing: for create (ingest v2) expects boolean; for update (PUT v1) expects DEFAULT/UNKNOWN/TRUE/FALSE or
                        truthy/falsy inputs
  --owner OWNER         Owner
  --tech-contacts TECH_CONTACTS
                        Tech contacts comma-separated (e.g., 'user1,admin2')
  --network NETWORK     Network (e.g., zone-1)
  --environment ENVIRONMENT
                        Environment (e.g., Staging, Production)
  --location LOCATION   Location (e.g., 'Helsinki, Finland')
  --custom-attr CUSTOM_ATTR
                        Repeatable; KEY=VALUE (e.g., --custom-attr os=linux)
"""

# This file includes AI-generated code - Review and modify as needed

import argparse
import sys
import getpass
import os

# --- import AuthzClient from ../common/oidc_authz_client.py ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)
from common.oidc_authz_client import AuthzClient  # noqa: E402
from common.config_loader import load_config, add_config_argument, apply_config_defaults  # noqa: E402

EDITABLE_FIELDS = {
    "environment",
    "internet_facing",
    "location",
    "mission_criticality",
    "network",
    "owner",
    "protocol",
    "tech_contacts",
}

SEARCH_ORDER = ["services", "applications", "databases"]
ASSET_CATEGORY = "it_assets"
UNSET = object()


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Obtain an access token, call the Authorization API, "
            "then create/update an IT asset.\n"
            "Supports two authentication methods: refresh token or username/password.\n"
            "Configuration can be loaded from config.toml file.\n"
            "Update uses PUT /api/v1/assets/it_assets for "
            "specific editable attributes and continues to use ingest API (v2) for other attributes."
        )
    )
    
    # Config file argument
    add_config_argument(parser)

    parser.add_argument("--app-uri",
                        help="Base URI for the application (e.g., https://gcmapp.apps.example.com)")
    parser.add_argument("--oidc-uri",
                        help="Base URI for OIDC (Keycloak) (e.g., https://oidc.apps.example.com)")
    parser.add_argument("--realm", default="gcmrealm", help="OIDC realm (default: gcmrealm)")
    
    # Authentication: mutually exclusive group for refresh token vs username/password
    auth_group = parser.add_mutually_exclusive_group(required=False)
    auth_group.add_argument("-t", "--refresh-token", required=False,
                            help="OIDC/Keycloak refresh token; prompts if omitted (when not using username/password)")
    auth_group.add_argument("-u", "--username", required=False,
                            help="GCM username for password authentication (alternative to refresh token)")
    
    parser.add_argument("-w", "--password", required=False,
                        help="GCM password; prompts if omitted (when using username)")
    parser.add_argument("--client-id", default="",
                        help="OIDC client ID (default: gcmapiclient for refresh token, gcmclient for password)")
    parser.add_argument("--client-secret", default="",
                        help="OIDC client secret (optional, for confidential clients)")
    
    parser.add_argument("--tenant-id", default="",
                        help="Tenant ID to include in Authorization API body (optional)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="HTTP timeout seconds (default: 30)")
    parser.add_argument("--insecure", action="store_true",
                        help="Disable SSL certificate verification (NOT recommended for production)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_asset_options(subp, required_keys=None):
        req = set(required_keys or [])
        def reqd(name):
            return name in req
        subp.add_argument("--uri", required=reqd("uri"), default=None, help="URI")
        subp.add_argument("--ip", required=reqd("ip"), default=None, help="IP")
        subp.add_argument("--hostname", required=reqd("hostname"), default=None, help="Hostname")
        subp.add_argument("--protocol", default=None, help="Protocol (e.g., TLS, TCP)")
        subp.add_argument("--port", type=int, required=reqd("port"), default=None, help="Port (integer)")
        subp.add_argument("--asset-type", required=reqd("asset_type"), default=None,
                          help="Asset type (e.g., Database, Service, Application)")
        subp.add_argument("--asset-sub-type", default=None, help="Asset sub type (e.g., MySQL)")
        subp.add_argument("--mission-criticality", type=int, default=None,
                          help="Mission criticality (integer; optional)")
        subp.add_argument("--internet-facing", default=None,
                          help="Internet facing: for create (ingest v2) expects boolean; for update (PUT v1) expects DEFAULT/UNKNOWN/TRUE/FALSE or truthy/falsy inputs")
        subp.add_argument("--owner", default=None, help="Owner")
        subp.add_argument("--tech-contacts", default=UNSET,
                          help="Tech contacts comma-separated (e.g., 'user1,admin2')")
        subp.add_argument("--network", default=None, help="Network (e.g., zone-1)")
        subp.add_argument("--environment", default=None, help="Environment (e.g., Staging, Production)")
        subp.add_argument("--location", default=None, help="Location (e.g., 'Helsinki, Finland')")
        subp.add_argument("--custom-attr", action="append", default=[],
                          help="Repeatable; KEY=VALUE (e.g., --custom-attr os=linux)")

    create_parser = subparsers.add_parser("create", help="Create new asset (uri/ip/hostname/port/asset-type required)")
    add_asset_options(create_parser, required_keys={"uri", "ip", "hostname", "port", "asset_type"})

    update_parser = subparsers.add_parser("update", help="Update asset (uri required)")
    add_asset_options(update_parser, required_keys={"uri"})

    return parser


def parse_bool_to_bool(value):
    v = (value or "").strip().lower()
    if v in {"true", "t", "yes", "y", "1"}:
        return True
    if v in {"false", "f", "no", "n", "0"}:
        return False
    return None


def normalize_internet_facing_for_put(value):
    if value is None:
        return None
    b = parse_bool_to_bool(value)
    if b is True:
        return "TRUE"
    if b is False:
        return "FALSE"
    s_up = str(value).strip().upper()
    if s_up in {"DEFAULT", "UNKNOWN", "TRUE", "FALSE"}:
        return s_up
    print("Warning: internet_facing value is invalid for PUT; expected DEFAULT/UNKNOWN/TRUE/FALSE.")
    return None


def normalize_internet_facing_for_ingest(value):
    if value is None:
        return None
    b = parse_bool_to_bool(value)
    if b is not None:
        return b
    s_up = str(value).strip().upper()
    if s_up == "TRUE":
        return True
    if s_up == "FALSE":
        return False
    if s_up in {"DEFAULT", "UNKNOWN"}:
        print("Info: internet_facing '{}' has no boolean meaning for ingest; omitting.".format(s_up))
        return None
    print("Warning: internet_facing value is invalid for ingest; expected boolean or TRUE/FALSE.")
    return None


def parse_contacts_to_list(text):
    return [s.strip() for s in text.split(",") if s.strip()]


def normalize_contacts_arg(raw):
    if raw is UNSET:
        return (None, False)
    if isinstance(raw, str):
        s = raw.strip()
        if s == "" or s.upper() == "NULL":
            return (["NULL"], True)
        return (parse_contacts_to_list(s), True)
    return (None, False)


def parse_custom_attrs(pairs):
    bucket = {}
    for p in pairs or []:
        if '=' not in p:
            print("Warning: --custom-attr '{}' is invalid (expected KEY=VALUE); ignored.".format(p))
            continue
        k, v = p.split('=', 1)
        k = k.strip()
        v = v.strip()
        if not k:
            print("Warning: --custom-attr '{}' has empty key; ignored.".format(p))
            continue
        bucket.setdefault(k, []).append(v)
    extensions = {}
    for k, values in bucket.items():
        if len(values) > 1:
            print("Warning: attribute '{}' has multiple values; using the last one: '{}'".format(k, values[-1]))
        extensions[k] = values[-1]
    return extensions


def build_asset_dict(args):
    asset = {}

    def put_if_present(key, value):
        # EDITABLE vs NON-EDITABLE empty-string policy
        if value is None:
            return
        if isinstance(value, str) and value == "":
            if key in EDITABLE_FIELDS:
                asset[key] = "NULL"  # deletion token for editable
            else:
                asset[key] = ""      # keep empty string for non-editable
            return
        if isinstance(value, list) and len(value) == 0:
            return
        asset[key] = value

    put_if_present("uri", args.uri)
    put_if_present("ip", args.ip)
    put_if_present("hostname", args.hostname)
    put_if_present("protocol", args.protocol)
    put_if_present("port", args.port)
    put_if_present("asset_type", args.asset_type)
    put_if_present("asset_sub_type", args.asset_sub_type)
    put_if_present("owner", args.owner)
    put_if_present("network", args.network)
    put_if_present("environment", args.environment)
    put_if_present("location", args.location)

    # tech_contacts (UNSET / ["NULL"] / list)
    raw_contacts = getattr(args, "tech_contacts", UNSET)
    contacts_value, contacts_provided = normalize_contacts_arg(raw_contacts)
    if contacts_provided:
        asset["tech_contacts"] = contacts_value

    if args.mission_criticality is not None:
        asset["mission_criticality"] = args.mission_criticality

    # Store raw internet_facing for path-specific normalization
    if getattr(args, "internet_facing", None) is not None:
        asset["internet_facing"] = args.internet_facing

    user_extensions = parse_custom_attrs(getattr(args, "custom_attr", []))
    if user_extensions:
        asset["extensions"] = user_extensions

    return asset


def find_asset_id_by_uri(client, access_token, uri):
    print("Searching asset_id by URI across services, applications, and databases...")
    body = {
        "columns": ["asset_id", "uri"],
        "search_by": uri,
        "page_number": 1,
        "page_size": 1,
    }
    headers = make_headers(client, access_token)
    for asset_type in SEARCH_ORDER:
        list_path = "ibm/assetinventory/api/v1/assets/{}/{}".format(ASSET_CATEGORY, asset_type)
        url = "{}/{}".format(client.app_uri, list_path)
        resp = do_request(client.session, "post", url, headers, body, client.verify_ssl, client.timeout,
                          label="Assets list ({})".format(asset_type))
        if resp is None or not getattr(resp, 'ok', False):
            continue
        try:
            payload = resp.json()
        except Exception:
            payload = None
        if isinstance(payload, dict) and "it_assets" in payload:
            it_assets = payload.get("it_assets")
            if isinstance(it_assets, list) and it_assets:
                item = it_assets[0]
                asset_id = item.get("asset_id")
                print("[MATCH] asset_type={}, asset_id={}, uri={}".format(asset_type, asset_id, item.get("uri")))
                return asset_id
        print("[INFO] No match found in '{}'.".format(asset_type))
    print("[RESULT] No asset matched the specified URI in applications/databases/services.")
    print(" uri: {}".format(uri))
    return None


def make_headers(client, access_token):
    return {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": "Bearer {}".format(access_token),
        "User-Agent": client.user_agent,
    }


def do_request(session, method, url, headers, payload, verify, timeout, label):
    try:
        resp = getattr(session, method)(url, headers=headers, json=payload, verify=verify, timeout=timeout)
        print("{} Response: HTTP {}".format(label, resp.status_code))
        try:
            print(resp.json())
        except Exception:
            print("{} response is not JSON; raw text:".format(label))
            print(resp.text)
        return resp
    except Exception as e:
        print("{} error: {}".format(label, e))
        return None


def call_put_editable_attributes(client, access_token, asset_id, editable):
    # Normalize internet_facing for PUT (enum string)
    if "internet_facing" in editable:
        norm_enum = normalize_internet_facing_for_put(editable["internet_facing"])
        if norm_enum is None:
            editable.pop("internet_facing", None)
        else:
            editable["internet_facing"] = norm_enum

    path = "ibm/assetinventory/api/v1/assets/it_assets"
    url = "{}/{}".format(client.app_uri, path)
    payload = {
        "asset_ids": [asset_id],
        "editable_it_asset_attributes": editable,
    }
    headers = make_headers(client, access_token)
    resp = do_request(client.session, "put", url, headers, payload, client.verify_ssl, client.timeout,
                      label="Editable update")
    return bool(resp and resp.ok)


def call_ingest_v2(client, access_token, asset_body):
    # Normalize internet_facing to boolean for ingest
    if "internet_facing" in asset_body:
        norm_bool = normalize_internet_facing_for_ingest(asset_body["internet_facing"])
        if norm_bool is None:
            asset_body.pop("internet_facing", None)
        else:
            asset_body["internet_facing"] = norm_bool

    ingest_path = "ibm/assetinventory/api/v2/assets/ingest/it_assets"
    ingest_url = "{}/{}".format(client.app_uri, ingest_path)
    payload = {"it_assets": [asset_body]}
    headers = make_headers(client, access_token)
    resp = do_request(client.session, "post", ingest_url, headers, payload, client.verify_ssl, client.timeout,
                      label="Ingest v2")
    return bool(resp and resp.ok)


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

    config = {
        "app_uri": args.app_uri.rstrip("/"),
        "oidc_uri": args.oidc_uri.rstrip("/"),
        "realm": args.realm,
        "verify_ssl": not args.insecure,
        "timeout": args.timeout,
        "user_agent": "post-it-asset/5.5",
    }

    try:
        client = AuthzClient(config)
    except Exception as e:
        print("Client initialization error: {}".format(e))
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
        print("Token acquisition error: {}".format(e))
        return 2

    try:
        print("\nCalling authorization API (v2)...")
        auth_resp = client.call_authorization_api(access_token, tenant_id=args.tenant_id)
        print("Authorization API Response: HTTP {}".format(auth_resp.status_code))
        try:
            print(auth_resp.json())
        except Exception:
            print("Authorization response is not JSON; printing raw text:")
            print(auth_resp.text)
        if not auth_resp.ok:
            print("Authorization API failed; aborting subsequent calls.")
            return 3
    except Exception as e:
        print("Authorization API error: {}".format(e))
        return 3

    asset = build_asset_dict(args)

    if args.command == "create":
        ok = call_ingest_v2(client, access_token, asset)
        return 0 if ok else 4

    # update path
    if not asset.get("uri"):
        print("Update requires --uri; missing.")
        return 5

    # Build editable from normalized inputs
    editable = {}
    for k in EDITABLE_FIELDS:
        if k in asset:
            editable[k] = asset[k]

    # Ingest body excludes editable fields
    ingest_body = dict((k, v) for (k, v) in asset.items() if k not in EDITABLE_FIELDS)

    ok_put = True
    if editable:
        asset_id = find_asset_id_by_uri(client, access_token, asset["uri"])
        if not asset_id:
            print("Failed to resolve asset_id from URI; cannot call PUT /api/v1/assets/it_assets.")
            ok_put = False
        else:
            ok_put = call_put_editable_attributes(client, access_token, asset_id, editable)

    ok_ingest = True
    if ingest_body and any(k != "uri" for k in ingest_body.keys()):
        ok_ingest = call_ingest_v2(client, access_token, ingest_body)

    if editable and not ok_put:
        return 6
    if ingest_body and any(k != "uri" for k in ingest_body.keys()) and not ok_ingest:
        return 7

    print("Update completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
