#!/usr/bin/env python3
"""Test script to check if the API endpoint returns assets."""

import requests
import json

def main():
    base_url = "http://localhost:8000"
    
    # Test the assets list endpoint
    print("Testing GET /api/v1/assets/")
    try:
        response = requests.get(f"{base_url}/api/v1/assets/", params={"page": 1, "page_size": 20})
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse data keys: {data.keys()}")
            print(f"Total assets: {data.get('total', 'N/A')}")
            print(f"Assets returned: {len(data.get('assets', []))}")
            print(f"Page: {data.get('page', 'N/A')}")
            print(f"Page size: {data.get('page_size', 'N/A')}")
            print(f"Total pages: {data.get('total_pages', 'N/A')}")
            
            if data.get('assets'):
                print(f"\nFirst asset:")
                first_asset = data['assets'][0]
                print(json.dumps(first_asset, indent=2))
        else:
            print(f"Error response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the server. Is it running on port 8000?")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == '__main__':
    main()

# Made with Bob
