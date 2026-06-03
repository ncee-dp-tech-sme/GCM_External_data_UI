#!/usr/bin/env python3
"""
Import missing assets from dist/assets.json directly into the database.
This bypasses the GCM API pagination issue.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.it_asset import ITAsset
from sqlalchemy import func

def import_missing_assets():
    """Import assets from JSON that are missing from database."""
    
    # Load JSON file
    json_path = Path(__file__).parent.parent.parent / "dist" / "assets.json"
    
    if not json_path.exists():
        print(f"❌ JSON file not found: {json_path}")
        return
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    json_assets = data.get("it_assets", [])
    
    print("=" * 60)
    print("IMPORTING MISSING ASSETS FROM JSON")
    print("=" * 60)
    print(f"\nTotal assets in JSON: {len(json_assets)}")
    
    db = SessionLocal()
    try:
        # Get existing URIs
        existing_uris = set(uri for (uri,) in db.query(ITAsset.uri).all() if uri)
        print(f"Existing assets in DB: {len(existing_uris)}")
        
        # Find missing assets
        missing_assets = [a for a in json_assets if a.get("uri") and a.get("uri") not in existing_uris]
        print(f"Missing assets to import: {len(missing_assets)}")
        
        if not missing_assets:
            print("\n✅ No missing assets - database is complete!")
            return
        
        # Import missing assets
        imported = 0
        errors = []
        
        print(f"\n📥 Importing {len(missing_assets)} missing assets...")
        
        for asset_data in missing_assets:
            try:
                # Parse tech_contacts
                tech_contacts = asset_data.get("tech_contacts")
                if isinstance(tech_contacts, str):
                    tech_contacts = [c.strip() for c in tech_contacts.split(",") if c.strip()]
                elif not isinstance(tech_contacts, list):
                    tech_contacts = None
                
                # Parse datetime fields
                def parse_dt(dt_str):
                    if not dt_str:
                        return None
                    try:
                        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                    except:
                        return None
                
                # Create asset
                new_asset = ITAsset(
                    asset_id=asset_data.get("asset_id"),
                    uri=asset_data.get("uri"),
                    ip=asset_data.get("ip"),
                    hostname=asset_data.get("hostname"),
                    port=asset_data.get("port"),
                    protocol=asset_data.get("protocol"),
                    asset_type=asset_data.get("asset_type"),
                    asset_sub_type=asset_data.get("asset_sub_type"),
                    owner=asset_data.get("owner"),
                    tech_contacts=tech_contacts,
                    environment=asset_data.get("environment"),
                    location=asset_data.get("location"),
                    network=asset_data.get("network"),
                    mission_criticality=asset_data.get("mission_criticality"),
                    internet_facing=asset_data.get("internet_facing"),
                    extensions=asset_data.get("extensions") if isinstance(asset_data.get("extensions"), dict) else None,
                    discovery_sources=asset_data.get("discovery_sources") if isinstance(asset_data.get("discovery_sources"), list) else None,
                    first_seen=parse_dt(asset_data.get("first_seen")),
                    last_seen=parse_dt(asset_data.get("last_seen")),
                    object_status=asset_data.get("object_status"),
                    last_synced=datetime.utcnow()
                )
                
                db.add(new_asset)
                imported += 1
                
                # Commit every 100 assets
                if imported % 100 == 0:
                    db.commit()
                    print(f"   Imported {imported}/{len(missing_assets)}...")
                
            except Exception as e:
                errors.append(f"Error importing {asset_data.get('uri', 'unknown')}: {str(e)}")
        
        # Final commit
        db.commit()
        
        print(f"\n✅ Import complete!")
        print(f"   Successfully imported: {imported}")
        print(f"   Errors: {len(errors)}")
        
        if errors:
            print(f"\n❌ Errors (first 10):")
            for error in errors[:10]:
                print(f"   {error}")
        
        # Verify final count
        final_count = db.query(func.count(func.distinct(ITAsset.uri))).scalar()
        print(f"\n📊 Final database count: {final_count} unique URIs")
        
        if final_count == 651:
            print("🎉 SUCCESS: All 651 assets are now in the database!")
        else:
            print(f"⚠️  Expected 651, got {final_count} (missing {651 - final_count})")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Import failed: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    import_missing_assets()

# Made with Bob
