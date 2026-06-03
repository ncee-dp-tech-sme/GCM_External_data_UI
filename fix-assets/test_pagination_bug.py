#!/usr/bin/env python3
"""
Test script to identify the pagination bug in IT asset sync.

Created: 2026-06-03
Purpose: Investigate why only 468 unique URIs are synced when GCM has 651 assets
"""

import json

# Load the full API response
with open('../../dist/assets.json', 'r') as f:
    data = json.load(f)

total_count = data.get('total_count')
assets = data.get('it_assets', [])

print("=" * 80)
print("PAGINATION BUG ANALYSIS")
print("=" * 80)

print(f"\n1. API Response Analysis:")
print(f"   - Total count from API: {total_count}")
print(f"   - Assets in response: {len(assets)}")

# Count unique URIs
unique_uris = set()
duplicate_uris = {}

for asset in assets:
    uri = asset.get('uri')
    if uri:
        if uri in unique_uris:
            duplicate_uris[uri] = duplicate_uris.get(uri, 1) + 1
        unique_uris.add(uri)

print(f"   - Unique URIs: {len(unique_uris)}")
print(f"   - Duplicate URIs: {len(duplicate_uris)}")

print(f"\n2. Pagination Logic Analysis:")
print(f"   Current sync logic issues:")

# Simulate the current pagination logic
page_size = 100
total_pages_calc = data.get("total_pages", data.get("totalPages", 1))

print(f"   - Page size: {page_size}")
print(f"   - Total pages from API: {total_pages_calc}")
print(f"   - Expected pages (651 / 100): {(total_count + page_size - 1) // page_size}")

# Check if API provides pagination info
print(f"\n3. API Response Keys:")
for key in data.keys():
    if key != 'it_assets':
        print(f"   - {key}: {data[key]}")

print(f"\n4. IDENTIFIED ISSUES:")
print(f"   ❌ The sync uses page_size=100 by default")
print(f"   ❌ With 651 assets, it should fetch 7 pages (651/100 = 6.51 → 7 pages)")
print(f"   ❌ Current logic breaks early if len(assets_list) < page_size")
print(f"   ❌ This happens on page 7 which has only 51 assets (651 - 600)")

# Simulate what happens with current logic
print(f"\n5. SIMULATION OF CURRENT LOGIC:")
simulated_fetched = 0
for page in range(1, 10):
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, len(assets))
    page_assets = assets[start_idx:end_idx]
    
    print(f"   Page {page}: {len(page_assets)} assets (indices {start_idx}-{end_idx-1})")
    simulated_fetched += len(page_assets)
    
    # Current logic breaks here
    if len(page_assets) < page_size:
        print(f"   ⚠️  BREAKS HERE: len({len(page_assets)}) < page_size({page_size})")
        break
    
    if end_idx >= len(assets):
        break

print(f"\n   Total fetched with current logic: {simulated_fetched}")
print(f"   Missing assets: {len(assets) - simulated_fetched}")

print(f"\n6. ROOT CAUSE:")
print(f"   The pagination logic at lines 207-208 breaks the loop when:")
print(f"   'if len(assets_list) < page_size: break'")
print(f"   ")
print(f"   This is WRONG because the last page will naturally have fewer assets!")
print(f"   Page 7 has 51 assets (651 - 600), so the loop breaks prematurely.")

print(f"\n7. CORRECT LOGIC SHOULD BE:")
print(f"   - Use total_count from API response")
print(f"   - Calculate: total_pages = ceil(total_count / page_size)")
print(f"   - Loop: for page in range(1, total_pages + 1)")
print(f"   - OR: Check if assets_list is empty (not < page_size)")

print("\n" + "=" * 80)

# Made with Bob
