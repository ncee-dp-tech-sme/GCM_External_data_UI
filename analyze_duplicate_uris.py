#!/usr/bin/env python3
"""
Analyze dist/assets.json for duplicate URIs in IT assets data.
"""

import json
from collections import Counter
from pathlib import Path

def analyze_duplicate_uris():
    """Analyze the assets.json file for duplicate URIs."""
    
    # Read the JSON file
    json_file = Path(__file__).parent / "assets.json"
    
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Extract basic info
    total_count = data.get('total_count', 0)
    it_assets = data.get('it_assets', [])
    actual_asset_count = len(it_assets)
    
    # Extract all URIs
    uris = []
    for asset in it_assets:
        uri = asset.get('uri')
        if uri:
            uris.append(uri)
    
    # Count URI occurrences
    uri_counter = Counter(uris)
    
    # Find duplicates
    duplicates = {uri: count for uri, count in uri_counter.items() if count > 1}
    unique_uris = len(uri_counter)
    
    # Generate report
    print("=" * 80)
    print("URI DUPLICATE ANALYSIS REPORT")
    print("=" * 80)
    print()
    
    print("SUMMARY:")
    print("-" * 80)
    print(f"Total assets in JSON (total_count field): {total_count}")
    print(f"Actual assets in array: {actual_asset_count}")
    print(f"Assets with URI field: {len(uris)}")
    print(f"Unique URIs found: {unique_uris}")
    print(f"Duplicate URIs: {len(duplicates)}")
    print()
    
    if duplicates:
        print("DUPLICATE URIs FOUND:")
        print("-" * 80)
        # Sort by count (descending) then by URI
        sorted_duplicates = sorted(duplicates.items(), key=lambda x: (-x[1], x[0]))
        
        for uri, count in sorted_duplicates:
            print(f"  {uri}")
            print(f"    Occurrences: {count}")
            
            # Find asset IDs with this URI
            asset_ids = [asset['asset_id'] for asset in it_assets if asset.get('uri') == uri]
            print(f"    Asset IDs: {', '.join(asset_ids[:5])}")
            if len(asset_ids) > 5:
                print(f"               ... and {len(asset_ids) - 5} more")
            print()
    else:
        print("RESULT:")
        print("-" * 80)
        print("✓ No duplicate URIs found!")
        print("  All 651 assets have unique URIs.")
        print()
    
    # Additional statistics
    print("STATISTICS:")
    print("-" * 80)
    print(f"Assets without URI field: {actual_asset_count - len(uris)}")
    print(f"Percentage of unique URIs: {(unique_uris / len(uris) * 100):.2f}%" if uris else "N/A")
    print()
    
    # Sample of URIs (first 10)
    print("SAMPLE URIs (first 10):")
    print("-" * 80)
    for i, uri in enumerate(list(uri_counter.keys())[:10], 1):
        count = uri_counter[uri]
        status = "DUPLICATE" if count > 1 else "unique"
        print(f"  {i}. {uri} ({status}, count: {count})")
    print()
    
    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)
    
    # Return summary for programmatic use
    return {
        'total_count': total_count,
        'actual_assets': actual_asset_count,
        'assets_with_uri': len(uris),
        'unique_uris': unique_uris,
        'duplicate_count': len(duplicates),
        'duplicates': duplicates
    }

if __name__ == "__main__":
    result = analyze_duplicate_uris()
    
    # Exit with appropriate code
    exit(0 if result['duplicate_count'] == 0 else 1)

# Made with Bob
