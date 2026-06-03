#!/usr/bin/env python3
"""
Diagnostic script to identify why assets are fetched but not saved to database.
Simulates the sync process with detailed logging.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.it_asset import ITAsset
from sqlalchemy import func

def check_database_state():
    """Check current database state."""
    db = SessionLocal()
    try:
        total = db.query(func.count(ITAsset.id)).scalar()
        unique_uris = db.query(func.count(func.distinct(ITAsset.uri))).scalar()
        
        print("=" * 60)
        print("CURRENT DATABASE STATE")
        print("=" * 60)
        print(f"Total assets: {total}")
        print(f"Unique URIs: {unique_uris}")
        
        # Check for any NULL or empty URIs
        null_uris = db.query(func.count(ITAsset.id)).filter(
            (ITAsset.uri == None) | (ITAsset.uri == '')
        ).scalar()
        print(f"Assets with NULL/empty URI: {null_uris}")
        
        # Check asset types
        type_counts = db.query(
            ITAsset.asset_type,
            func.count(ITAsset.id)
        ).group_by(ITAsset.asset_type).all()
        
        print("\nAssets by type:")
        for asset_type, count in type_counts:
            print(f"  {asset_type}: {count}")
        
        print("=" * 60)
        
    finally:
        db.close()

def check_for_constraint_violations():
    """Check if there are any constraint violations in the data."""
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("CHECKING FOR POTENTIAL ISSUES")
        print("=" * 60)
        
        # Check for duplicate URIs (should be impossible with UNIQUE constraint)
        duplicates = db.query(
            ITAsset.uri,
            func.count(ITAsset.id).label('count')
        ).group_by(ITAsset.uri).having(func.count(ITAsset.id) > 1).all()
        
        if duplicates:
            print(f"\n⚠️  Found {len(duplicates)} duplicate URIs in database:")
            for uri, count in duplicates[:10]:
                print(f"  {uri}: {count} occurrences")
        else:
            print("\n✅ No duplicate URIs found (UNIQUE constraint working)")
        
        # Check for assets with missing required fields
        missing_uri = db.query(func.count(ITAsset.id)).filter(
            (ITAsset.uri == None) | (ITAsset.uri == '')
        ).scalar()
        
        if missing_uri > 0:
            print(f"\n⚠️  Found {missing_uri} assets with missing URI")
        else:
            print("\n✅ All assets have URIs")
        
        print("=" * 60)
        
    finally:
        db.close()

def analyze_sync_gap():
    """Analyze the gap between expected and actual assets."""
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("SYNC GAP ANALYSIS")
        print("=" * 60)
        
        expected = 651
        actual = db.query(func.count(func.distinct(ITAsset.uri))).scalar()
        gap = expected - actual
        
        print(f"\nExpected assets: {expected}")
        print(f"Actual assets: {actual}")
        print(f"Missing: {gap} ({gap/expected*100:.1f}%)")
        
        if gap > 0:
            print("\n🔍 Possible causes:")
            print("  1. Errors during asset processing (check backend logs)")
            print("  2. Transaction rollback due to exceptions")
            print("  3. Assets failing validation")
            print("  4. Database commit not being called")
            print("  5. Assets being fetched but not added to session")
            
            print("\n💡 Recommendations:")
            print("  1. Check backend logs for ERROR messages during sync")
            print("  2. Look for TRACEBACK output in logs")
            print("  3. Verify all 7 pages were processed")
            print("  4. Check if commit() was called after processing")
        
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    print("\n🔍 SYNC DIAGNOSTIC TOOL\n")
    
    check_database_state()
    check_for_constraint_violations()
    analyze_sync_gap()
    
    print("\n📋 Next Steps:")
    print("  1. Review backend logs for errors during sync")
    print("  2. Check if all 7 pages were processed")
    print("  3. Look for exception tracebacks")
    print("  4. Verify commit() was called")
    print()

# Made with Bob
