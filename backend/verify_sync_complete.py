#!/usr/bin/env python3
"""
Verification script to check if all 651 IT assets from GCM are synced to the database.
Run this after performing a sync from the Web UI.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.it_asset import ITAsset
from sqlalchemy import func

def verify_sync():
    """Verify that all 651 unique assets are in the database."""
    db = SessionLocal()
    try:
        # Count total assets
        total_assets = db.query(func.count(ITAsset.id)).scalar()
        
        # Count unique URIs
        unique_uris = db.query(func.count(func.distinct(ITAsset.uri))).scalar()
        
        # Get asset type breakdown
        type_counts = db.query(
            ITAsset.asset_type,
            func.count(ITAsset.id)
        ).group_by(ITAsset.asset_type).all()
        
        print("=" * 60)
        print("IT ASSET SYNC VERIFICATION")
        print("=" * 60)
        print(f"\n📊 Database Statistics:")
        print(f"   Total assets in database: {total_assets}")
        print(f"   Unique URIs: {unique_uris}")
        print(f"\n📋 Assets by Type:")
        for asset_type, count in sorted(type_counts, key=lambda x: x[1], reverse=True):
            print(f"   {asset_type}: {count}")
        
        print("\n" + "=" * 60)
        
        # Verification
        expected_count = 651
        if unique_uris == expected_count:
            print(f"✅ SUCCESS: All {expected_count} unique assets synced!")
            print("=" * 60)
            return True
        else:
            print(f"❌ INCOMPLETE: Expected {expected_count}, found {unique_uris}")
            print(f"   Missing: {expected_count - unique_uris} assets")
            print("=" * 60)
            return False
            
    finally:
        db.close()

if __name__ == "__main__":
    success = verify_sync()
    sys.exit(0 if success else 1)

# Made with Bob
