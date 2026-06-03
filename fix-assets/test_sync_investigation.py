#!/usr/bin/env python3
"""
Investigation script for IT Asset sync discrepancy.
Tests why only 468 assets are synced when GCM reports 651.

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
import json

# Database setup - use the same database as the app
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
        "user_agent": "gcm-webui-sync-investigation/1.0",
    }
    return AuthzClient(config)

def investigate_sync():
    """Investigate the sync discrepancy."""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("IT ASSET SYNC INVESTIGATION")
        print("=" * 80)
        
        # Get active profile and token
        profile = ProfileService.get_active_profile(db)
        if not profile:
            print("ERROR: No active profile found")
            return
        
        print(f"\n✓ Active Profile: {profile.name}")
        
        access_token = AuthService.get_active_profile_token(db)
        if not access_token:
            print("ERROR: No access token available")
            return
        
        print("✓ Access token obtained")
        
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
        print("\n" + "=" * 80)
        print("STEP 1: Authorization")
        print("=" * 80)
        auth_resp = client.call_authorization_api(access_token, tenant_id=profile_data.get("tenant_id", ""))
        if not auth_resp.ok:
            print(f"ERROR: Authorization failed: HTTP {auth_resp.status_code}")
            return
        print("✓ Authorization successful")
        
        # Check database counts BEFORE sync
        print("\n" + "=" * 80)
        print("STEP 2: Current Database State")
        print("=" * 80)
        
        db_total = db.query(func.count(ITAsset.id)).scalar()
        print(f"Total assets in database: {db_total}")
        
        # Count by type
        type_counts = db.query(
            ITAsset.asset_type,
            func.count(ITAsset.id)
        ).group_by(ITAsset.asset_type).all()
        
        print("\nAssets by type in database:")
        for asset_type, count in type_counts:
            print(f"  - {asset_type or 'NULL'}: {count}")
        
        # Investigate each asset type from GCM
        asset_types = ["services", "applications", "databases"]
        page_size = 100
        
        gcm_totals = {}
        gcm_details = {}
        
        for asset_type in asset_types:
            print("\n" + "=" * 80)
            print(f"STEP 3: Investigating GCM Asset Type: {asset_type.upper()}")
            print("=" * 80)
            
            # Initialize gcm_details for this asset type
            gcm_details[asset_type] = {
                "total_pages": 0,
                "total_count": 0,
                "first_page_size": 0
            }
            
            list_path = f"ibm/assetinventory/api/v1/assets/it_assets/{asset_type}"
            
            page = 1
            total_fetched = 0
            pages_fetched = 0
            
            while True:
                body = {
                    "columns": ["all"],
                    "page_number": page,
                    "page_size": page_size,
                    "filter": "",
                    "search_by": "",
                    "sort_by": ""
                }
                
                print(f"\nFetching page {page}...")
                resp = client.post(list_path, access_token, json_body=body)
                
                if not resp.ok:
                    print(f"ERROR: HTTP {resp.status_code} - {resp.text}")
                    break
                
                data = resp.json()
                assets_list = data.get("it_assets", [])
                
                if not assets_list:
                    print(f"  No assets on page {page}")
                    break
                
                pages_fetched += 1
                total_fetched += len(assets_list)
                
                # Get pagination info
                total_pages = data.get("total_pages", data.get("totalPages", "unknown"))
                total_count = data.get("total_count", data.get("totalCount", "unknown"))
                current_page = data.get("page_number", data.get("pageNumber", page))
                
                print(f"  ✓ Page {page}: {len(assets_list)} assets")
                print(f"    - total_pages from API: {total_pages}")
                print(f"    - total_count from API: {total_count}")
                print(f"    - current_page from API: {current_page}")
                
                # Store first page response for analysis
                if page == 1:
                    gcm_details[asset_type] = {
                        "total_pages": total_pages,
                        "total_count": total_count,
                        "first_page_size": len(assets_list)
                    }
                
                # Also store for empty results
                if not assets_list and page == 1:
                    gcm_details[asset_type] = {
                        "total_pages": 0,
                        "total_count": 0,
                        "first_page_size": 0
                    }
                
                # Check pagination logic
                if len(assets_list) < page_size:
                    print(f"  → Stopping: Got {len(assets_list)} assets (less than page_size {page_size})")
                    break
                
                if total_pages != "unknown" and total_pages > 1 and page >= total_pages:
                    print(f"  → Stopping: Reached last page ({page} >= {total_pages})")
                    break
                
                page += 1
            
            gcm_totals[asset_type] = total_fetched
            
            print(f"\n{asset_type.upper()} SUMMARY:")
            print(f"  - Pages fetched: {pages_fetched}")
            print(f"  - Total assets fetched: {total_fetched}")
            print(f"  - GCM reported total: {gcm_details[asset_type].get('total_count', 'unknown')}")
        
        # Final comparison
        print("\n" + "=" * 80)
        print("STEP 4: FINAL COMPARISON")
        print("=" * 80)
        
        gcm_grand_total = sum(gcm_totals.values())
        
        print(f"\nGCM Assets Fetched:")
        for asset_type, count in gcm_totals.items():
            print(f"  - {asset_type}: {count}")
        print(f"  TOTAL: {gcm_grand_total}")
        
        print(f"\nDatabase Assets:")
        print(f"  TOTAL: {db_total}")
        
        print(f"\nDISCREPANCY: {gcm_grand_total - db_total} assets")
        
        # Detailed analysis
        print("\n" + "=" * 80)
        print("STEP 5: DETAILED ANALYSIS")
        print("=" * 80)
        
        for asset_type in asset_types:
            gcm_reported = gcm_details[asset_type].get('total_count', 'unknown')
            gcm_fetched = gcm_totals[asset_type]
            
            print(f"\n{asset_type.upper()}:")
            print(f"  - GCM reported total: {gcm_reported}")
            print(f"  - Actually fetched: {gcm_fetched}")
            
            if gcm_reported != "unknown" and gcm_reported != gcm_fetched:
                print(f"  ⚠️  MISMATCH: {gcm_reported - gcm_fetched} assets not fetched!")
                print(f"     Possible causes:")
                print(f"     - Pagination stopping too early")
                print(f"     - Page size too small")
                print(f"     - API returning incomplete data")
        
        print("\n" + "=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        
        if gcm_grand_total > db_total:
            print(f"\n⚠️  {gcm_grand_total - db_total} assets were fetched but not saved to database!")
            print("   Possible causes:")
            print("   - Errors during asset processing (check logs)")
            print("   - Duplicate URI conflicts")
            print("   - Database constraints")
        
        if any(gcm_details[t].get('total_count', 0) != gcm_totals[t] for t in asset_types if gcm_details[t].get('total_count') != 'unknown'):
            print("\n⚠️  Not all pages were fetched from GCM API!")
            print("   Possible causes:")
            print("   - Pagination logic stopping too early")
            print("   - Page size too small (current: 100)")
            print("   - total_pages field incorrect or missing")
            print("\n   SOLUTION: Increase page_size or fix pagination logic")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    investigate_sync()

# Made with Bob
