#!/usr/bin/env python3
"""
Compare assets in dist/assets.json with database to find missing URIs.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.it_asset import ITAsset

def find_missing_assets():
    """Find assets in JSON that are not in database."""
    
    # Load JSON file
    json_path = Path(__file__).parent.parent.parent / "dist" / "assets.json"
    
    if not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        return
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    json_assets = data.get("it_assets", [])
    json_uris = set(asset.get("uri") for asset in json_assets if asset.get("uri"))
    
    print("=" * 60)
    print("MISSING ASSETS ANALYSIS")
    print("=" * 60)
    print(f"\nAssets in JSON file: {len(json_uris)}")
    
    # Get URIs from database
    db = SessionLocal()
    try:
        db_assets = db.query(ITAsset.uri).all()
        db_uris = set(uri for (uri,) in db_assets if uri)
        
        print(f"Assets in database: {len(db_uris)}")
        
        # Find missing URIs
        missing_uris = json_uris - db_uris
        extra_uris = db_uris - json_uris
        
        print(f"\n📊 Comparison:")
        print(f"   Missing from DB: {len(missing_uris)}")
        print(f"   Extra in DB (not in JSON): {len(extra_uris)}")
        
        if missing_uris:
            print(f"\n❌ Missing URIs (first 20):")
            for uri in sorted(list(missing_uris))[:20]:
                # Find the asset in JSON to get more details
                asset = next((a for a in json_assets if a.get("uri") == uri), None)
                if asset:
                    asset_type = asset.get("asset_type", "unknown")
                    print(f"   {uri} ({asset_type})")
        
        if extra_uris:
            print(f"\n⚠️  Extra URIs in DB (first 10):")
            for uri in sorted(list(extra_uris))[:10]:
                print(f"   {uri}")
        
        # Analyze missing assets by type
        if missing_uris:
            missing_by_type = {}
            for uri in missing_uris:
                asset = next((a for a in json_assets if a.get("uri") == uri), None)
                if asset:
                    asset_type = asset.get("asset_type", "unknown")
                    missing_by_type[asset_type] = missing_by_type.get(asset_type, 0) + 1
            
            print(f"\n📋 Missing assets by type:")
            for asset_type, count in sorted(missing_by_type.items(), key=lambda x: x[1], reverse=True):
                print(f"   {asset_type}: {count}")
        
        print("=" * 60)
        
    finally:
        db.close()

if __name__ == "__main__":
    find_missing_assets()

# Made with Bob
