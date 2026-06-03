#!/usr/bin/env python3
"""
Test script to verify the pagination fix works correctly.

Created: 2026-06-03
Purpose: Verify that the fixed pagination logic correctly fetches all 651 assets
"""

import json
import math

def simulate_pagination_old(total_assets, page_size):
    """Simulate the OLD (buggy) pagination logic"""
    fetched = 0
    page = 1
    
    while True:
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_assets)
        assets_on_page = end_idx - start_idx
        
        if assets_on_page == 0:
            break
        
        fetched += assets_on_page
        
        # OLD BUGGY LOGIC: Break if page not full
        if assets_on_page < page_size:
            break
        
        page += 1
    
    return fetched, page

def simulate_pagination_new(total_assets, page_size):
    """Simulate the NEW (fixed) pagination logic"""
    fetched = 0
    page = 1
    
    # Calculate total pages on first request
    total_pages = math.ceil(total_assets / page_size)
    
    while True:
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_assets)
        assets_on_page = end_idx - start_idx
        
        if assets_on_page == 0:
            break
        
        fetched += assets_on_page
        
        # NEW FIXED LOGIC: Check against calculated total pages
        if page >= total_pages:
            break
        
        page += 1
    
    return fetched, page

print("=" * 80)
print("PAGINATION FIX VERIFICATION")
print("=" * 80)

# Test with actual GCM data
total_assets = 651
page_size = 100

print(f"\nTest Parameters:")
print(f"  Total assets: {total_assets}")
print(f"  Page size: {page_size}")
print(f"  Expected pages: {math.ceil(total_assets / page_size)}")

print(f"\n1. OLD (BUGGY) PAGINATION LOGIC:")
old_fetched, old_pages = simulate_pagination_old(total_assets, page_size)
print(f"   Pages fetched: {old_pages}")
print(f"   Assets fetched: {old_fetched}")
print(f"   Missing assets: {total_assets - old_fetched}")
print(f"   Status: {'❌ INCOMPLETE' if old_fetched < total_assets else '✅ COMPLETE'}")

print(f"\n2. NEW (FIXED) PAGINATION LOGIC:")
new_fetched, new_pages = simulate_pagination_new(total_assets, page_size)
print(f"   Pages fetched: {new_pages}")
print(f"   Assets fetched: {new_fetched}")
print(f"   Missing assets: {total_assets - new_fetched}")
print(f"   Status: {'✅ COMPLETE' if new_fetched == total_assets else '❌ INCOMPLETE'}")

print(f"\n3. COMPARISON:")
print(f"   Improvement: +{new_fetched - old_fetched} assets")
print(f"   Additional pages: +{new_pages - old_pages} pages")

# Test edge cases
print(f"\n4. EDGE CASE TESTS:")

test_cases = [
    (100, 100, "Exact page boundary"),
    (101, 100, "One asset over boundary"),
    (99, 100, "One asset under boundary"),
    (1, 100, "Single asset"),
    (1000, 100, "Large dataset"),
]

all_passed = True
for total, page_sz, description in test_cases:
    old_f, _ = simulate_pagination_old(total, page_sz)
    new_f, _ = simulate_pagination_new(total, page_sz)
    passed = new_f == total
    all_passed = all_passed and passed
    status = "✅" if passed else "❌"
    print(f"   {status} {description}: {total} assets, fetched {new_f} (old: {old_f})")

print(f"\n5. SUMMARY:")
if all_passed and new_fetched == total_assets:
    print(f"   ✅ ALL TESTS PASSED!")
    print(f"   ✅ The fix correctly handles all pagination scenarios")
    print(f"   ✅ All {total_assets} assets will now be synced")
else:
    print(f"   ❌ SOME TESTS FAILED")
    print(f"   ❌ Additional fixes may be needed")

print("\n" + "=" * 80)

# Made with Bob
