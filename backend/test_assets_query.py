#!/usr/bin/env python3
"""Test script to check if assets can be queried from the database."""

from app.database import SessionLocal
from app.services.it_asset_service import ITAssetService
from app.schemas.it_asset import ITAssetFilter

def main():
    db = SessionLocal()
    try:
        service = ITAssetService(db)
        filters = ITAssetFilter(page=1, page_size=20)
        assets, total = service.get_assets(filters)
        
        print(f'Total assets: {total}')
        print(f'Assets returned: {len(assets)}')
        
        if assets:
            print(f'\nFirst asset:')
            print(f'  URI: {assets[0].uri}')
            print(f'  Type: {assets[0].asset_type}')
            print(f'  Hostname: {assets[0].hostname}')
            print(f'  IP: {assets[0].ip}')
            
            # Check if assets have required fields
            print(f'\nChecking first 5 assets for required fields:')
            for i, asset in enumerate(assets[:5]):
                print(f'Asset {i+1}: uri={asset.uri}, type={asset.asset_type}, hostname={asset.hostname}')
        else:
            print('No assets returned!')
            
    finally:
        db.close()

if __name__ == '__main__':
    main()

# Made with Bob
