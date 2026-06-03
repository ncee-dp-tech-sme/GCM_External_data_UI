#!/usr/bin/env python3
"""
Analyze URIs to understand the discrepancy.

Created: 2026-06-03
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models.it_asset import ITAsset
from app.services.profile_service import ProfileService
from app.services.auth_service import AuthService
from common.oidc_authz_client import AuthzClient

# Database setup
DATABASE_URL = "sqlite:///./gcm_webui.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_gcm_client(profile_data):
    """Create GCM client from profile data."""
    config = {
        "app_uri": profile_data.get("app_uri", "").rstrip("/"),
        "oidc_uri": profile_data.get("oidc_uri", "").rstrip("/"),
        "realm": profile_data.get("realm", "gcmrealm"),
        "verify_ssl": not profile_data.get("insecure", False),
        "timeout": profile_data.get("timeout", 30.0),
        "user_agent": "gcm-webui-uri-analysis/1.0",
    }
    return AuthzClient(config)

def analyze_uris():
    """Analyze URIs from GCM vs database."""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("URI ANALYSIS")
        print("=" * 80)
        
        # Get active profile and token
        profile = ProfileService.get_active_profile(db)
        if not profile:
            print("ERROR: No active profile found")
            return
        
        access_token = AuthService.get_active_profile_token(db)
        if not access_token:
            print("ERROR: No access token available")
            return
        
        profile_data = {
            "app_uri": profile.app_uri,
            "oidc_uri": profile.oidc_uri,
            "realm": profile.realm,
            "insecure": profile.insecure,
            "timeout": profile.timeout,
            "tenant_id": getattr(profile, 'tenant_id', '')
        }
        
        client = get_gcm_client(profile_data)
        
        # Call authorization API
        auth_resp = client.call_authorization_api(access_token, tenant_id=profile_data.get("tenant_id", ""))
        if not auth_resp.ok:
            print(f"ERROR: Authorization failed")
            return
        
        # Fetch all service URIs from GCM
        print("\nFetching all service URIs from GCM...")
        list_path = "ibm/assetinventory/api/v1/assets/it_assets/services"
        
        gcm_uris = set()
        gcm_uri_list = []  # Keep order to detect duplicates
        page = 1
        page_size = 100
        
        while True:
            body = {
                "columns": ["all"],
                "page_number": page,
                "page_size": page_size,
                "filter": "",
                "search_by": "",
                "sort_by": ""
            }
            
            resp = client.post(list_path, access_token, json_body=body)
            if not resp.ok:
                break
            
            data = resp.json()
            assets_list = data.get("it_assets", [])
            
            if not assets_list:
                break
            
            for asset in assets_list:
                uri = asset.get("uri")
                if uri:
                    gcm_uri_list.append(uri)
                    gcm_uris.add(uri)
            
            if len(assets_list) < page_size:
                break
            
            page += 1
        
        print(f"✓ Fetched {len(gcm_uri_list)} service records from GCM")
        print(f"✓ Unique URIs in GCM: {len(gcm_uris)}")
        
        # Check for duplicates
        duplicates = len(gcm_uri_list) - len(gcm_uris)
        if duplicates > 0:
            print(f"⚠️  Found {duplicates} duplicate URI entries in GCM response!")
            
            # Find which URIs are duplicated
            from collections import Counter
            uri_counts = Counter(gcm_uri_list)
            dup_uris = {uri: count for uri, count in uri_counts.items() if count > 1}
            print(f"\nDuplicated URIs ({len(dup_uris)} unique URIs with duplicates):")
            for uri, count in sorted(dup_uris.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  - {uri}: appears {count} times")
            if len(dup_uris) > 10:
                print(f"  ... and {len(dup_uris) - 10} more")
        
        # Get all service URIs from database
        print("\nFetching all service URIs from database...")
        db_services = db.query(ITAsset).filter(ITAsset.asset_type == "Service").all()
        db_uris = set(asset.uri for asset in db_services)
        print(f"✓ Found {len(db_uris)} unique service URIs in database")
        
        # Compare
        print("\n" + "=" * 80)
        print("COMPARISON")
        print("=" * 80)
        
        in_gcm_not_db = gcm_uris - db_uris
        in_db_not_gcm = db_uris - gcm_uris
        
        print(f"\nURIs in GCM but NOT in database: {len(in_gcm_not_db)}")
        if in_gcm_not_db:
            print("\nFirst 10 missing URIs:")
            for uri in list(in_gcm_not_db)[:10]:
                print(f"  - {uri}")
        
        print(f"\nURIs in database but NOT in GCM: {len(in_db_not_gcm)}")
        if in_db_not_gcm:
            print("\nFirst 10 extra URIs:")
            for uri in list(in_db_not_gcm)[:10]:
                print(f"  - {uri}")
        
        print("\n" + "=" * 80)
        print("CONCLUSION")
        print("=" * 80)
        
        if duplicates > 0:
            print(f"\n⚠️  GCM API returns {duplicates} duplicate entries!")
            print(f"   This explains why sync reports {len(gcm_uri_list)} synced")
            print(f"   but only {len(gcm_uris)} unique assets exist.")
        
        if len(in_gcm_not_db) > 0:
            print(f"\n⚠️  {len(in_gcm_not_db)} assets from GCM are missing in database!")
            print("   These should have been created during sync.")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    analyze_uris()

# Made with Bob
