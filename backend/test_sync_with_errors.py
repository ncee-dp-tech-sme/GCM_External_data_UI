#!/usr/bin/env python3
"""
Test sync and capture all errors to identify why 178 assets are not being saved.

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
from app.services.it_asset_service import ITAssetService

# Database setup
DATABASE_URL = "sqlite:///./gcm_webui.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def test_sync_with_error_tracking():
    """Run sync and track all errors."""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("SYNC TEST WITH ERROR TRACKING")
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
        
        # Check database count before sync
        db_count_before = db.query(func.count(ITAsset.id)).scalar()
        print(f"\nDatabase count BEFORE sync: {db_count_before}")
        
        # Run sync
        print("\n" + "=" * 80)
        print("RUNNING SYNC...")
        print("=" * 80)
        
        service = ITAssetService(db)
        
        synced, created, updated, errors = service.sync_assets_from_gcm(
            profile_data=profile_data,
            access_token=access_token,
            asset_type="all",
            page_size=100
        )
        
        # Check database count after sync
        db_count_after = db.query(func.count(ITAsset.id)).scalar()
        
        print("\n" + "=" * 80)
        print("SYNC RESULTS")
        print("=" * 80)
        print(f"Synced: {synced}")
        print(f"Created: {created}")
        print(f"Updated: {updated}")
        print(f"Errors: {len(errors)}")
        print(f"\nDatabase count BEFORE: {db_count_before}")
        print(f"Database count AFTER: {db_count_after}")
        print(f"Database increase: {db_count_after - db_count_before}")
        
        if errors:
            print("\n" + "=" * 80)
            print(f"ERRORS ({len(errors)} total)")
            print("=" * 80)
            
            # Group errors by type
            error_types = {}
            for error in errors:
                error_type = error.split(':')[0] if ':' in error else 'Unknown'
                if error_type not in error_types:
                    error_types[error_type] = []
                error_types[error_type].append(error)
            
            for error_type, error_list in error_types.items():
                print(f"\n{error_type} ({len(error_list)} occurrences):")
                # Show first 5 examples
                for error in error_list[:5]:
                    print(f"  - {error}")
                if len(error_list) > 5:
                    print(f"  ... and {len(error_list) - 5} more")
        
        # Calculate discrepancy
        expected_increase = created
        actual_increase = db_count_after - db_count_before
        discrepancy = expected_increase - actual_increase
        
        if discrepancy > 0:
            print("\n" + "=" * 80)
            print("⚠️  DISCREPANCY DETECTED")
            print("=" * 80)
            print(f"Expected new assets: {expected_increase}")
            print(f"Actual new assets: {actual_increase}")
            print(f"Missing assets: {discrepancy}")
            print(f"\nThis means {discrepancy} assets were reported as 'created' but not saved to DB!")
            print("Possible causes:")
            print("  - Database commit failed")
            print("  - Duplicate URI constraint violations")
            print("  - Assets added to session but not flushed")
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_sync_with_error_tracking()

# Made with Bob
