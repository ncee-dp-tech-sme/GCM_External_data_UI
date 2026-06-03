"""
IT Asset service layer for GCM Web UI.
Wraps existing Python modules from it_assets/ directory.

Created: 2026-06-02
Last Modified: 2026-06-03

Changes:
- 2026-06-03 22:44 UTC: Fixed UNIQUE constraint error during sync by maintaining existing_assets_by_uri map across all pages instead of recreating it per page. This prevents duplicate inserts when the same URI appears multiple times in the GCM API response across different pages.
- 2026-06-03 22:54 UTC: Investigation completed - GCM API returns duplicate URIs (178 duplicates out of 646 records). Sync correctly handles this by updating existing assets. Cleaned up debug logging.
- 2026-06-03 23:07 UTC: Fixed critical pagination bug - changed break condition from 'len(assets_list) < page_size' to 'not assets_list' to properly handle the last page which naturally has fewer assets than page_size.
- 2026-06-03 23:17 UTC: CRITICAL FIX - Changed commit strategy from single commit at end to commit after each page. This prevents losing all synced data if an error occurs during processing. Assets are now persisted incrementally, ensuring partial sync success even if later pages fail.
"""

import sys
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

# Add parent directory to path for imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '../../../../'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.oidc_authz_client import AuthzClient
from app.models.it_asset import ITAsset
from app.schemas.it_asset import (
    ITAssetCreate,
    ITAssetUpdate,
    ITAssetFilter,
    ITAssetStats
)


class ITAssetService:
    """Service for managing IT assets with GCM integration."""
    
    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
    
    def get_gcm_client(self, profile_data: Dict[str, Any]) -> AuthzClient:
        """
        Create GCM client from profile data.
        
        Args:
            profile_data: Profile configuration dictionary
            
        Returns:
            Configured AuthzClient instance
        """
        config = {
            "app_uri": profile_data.get("app_uri", "").rstrip("/"),
            "oidc_uri": profile_data.get("oidc_uri", "").rstrip("/"),
            "realm": profile_data.get("realm", "gcmrealm"),
            "verify_ssl": not profile_data.get("insecure", False),
            "timeout": profile_data.get("timeout", 30.0),
            "user_agent": "gcm-webui-asset-service/1.0",
        }
        return AuthzClient(config)
    
    def sync_assets_from_gcm(
        self,
        profile_data: Dict[str, Any],
        access_token: str,
        asset_type: str = "all",
        page_size: int = 100
    ) -> Tuple[int, int, int, List[str]]:
        """
        Sync IT assets from GCM inventory.
        
        Args:
            profile_data: Profile configuration
            access_token: GCM access token
            asset_type: Type of assets to sync (services, applications, databases, or "all" for all types)
            page_size: Number of assets per page
            
        Returns:
            Tuple of (synced_count, created_count, updated_count, errors)
        """
        # If asset_type is "all" or empty, sync all types
        if asset_type == "all" or not asset_type:
            asset_types = ["services", "applications", "databases"]
            total_synced = 0
            total_created = 0
            total_updated = 0
            all_errors = []
            
            for atype in asset_types:
                synced, created, updated, errors = self._sync_single_asset_type(
                    profile_data, access_token, atype, page_size
                )
                total_synced += synced
                total_created += created
                total_updated += updated
                all_errors.extend(errors)
            
            return total_synced, total_created, total_updated, all_errors
        else:
            # Sync single asset type
            return self._sync_single_asset_type(profile_data, access_token, asset_type, page_size)
    
    def _sync_single_asset_type(
        self,
        profile_data: Dict[str, Any],
        access_token: str,
        asset_type: str,
        page_size: int = 100
    ) -> Tuple[int, int, int, List[str]]:
        """
        Sync a single asset type from GCM inventory.
        
        Args:
            profile_data: Profile configuration
            access_token: GCM access token
            asset_type: Type of assets to sync (services, applications, databases)
            page_size: Number of assets per page
            
        Returns:
            Tuple of (synced_count, created_count, updated_count, errors)
        """
        client = self.get_gcm_client(profile_data)
        synced_count = 0
        created_count = 0
        updated_count = 0
        errors = []
        
        # Initialize existing_assets_by_uri map ONCE for the entire sync
        # This map will be updated as new assets are created, preventing duplicates across pages
        existing_assets_by_uri = {}
        
        try:
            # Call authorization API first (required before accessing GCM APIs)
            try:
                auth_resp = client.call_authorization_api(access_token, tenant_id=profile_data.get("tenant_id", ""))
                if not auth_resp.ok:
                    errors.append(f"Authorization API failed: HTTP {auth_resp.status_code}")
                    return synced_count, created_count, updated_count, errors
            except Exception as e:
                errors.append(f"Authorization error: {str(e)}")
                return synced_count, created_count, updated_count, errors
            
            # Fetch assets from GCM
            list_path = f"ibm/assetinventory/api/v1/assets/it_assets/{asset_type}"
            
            page = 1
            total_count = None
            total_pages_calculated = None
            
            while True:
                body = {
                    "columns": ["all"],
                    "page_number": page,
                    "page_size": page_size,
                    "filter": "",
                    "search_by": "",
                    "sort_by": ""
                }
                
                try:
                    resp = client.post(list_path, access_token, json_body=body)
                    if not resp.ok:
                        errors.append(f"GCM API error: HTTP {resp.status_code} - {resp.text}")
                        break
                    
                    data = resp.json()
                    
                    # Get total_count from first page response
                    if page == 1 and total_count is None:
                        total_count = data.get("total_count", 0)
                        if total_count > 0:
                            # Calculate total pages: ceil(total_count / page_size)
                            total_pages_calculated = (total_count + page_size - 1) // page_size
                            print(f"Syncing {asset_type}: {total_count} assets across {total_pages_calculated} pages")
                    
                    assets_list = data.get("it_assets", [])
                    
                    # Break only if the response is empty (no more data)
                    if not assets_list:
                        break
                    
                    print(f"Page {page}: Processing {len(assets_list)} assets")
                    
                    # Update existing_assets_by_uri map with assets from current page
                    # Only query for URIs that are NOT already in the map (to avoid re-querying)
                    asset_uris = [asset.get("uri") for asset in assets_list if asset.get("uri")]
                    
                    # Filter out URIs already in the map
                    new_uris = [uri for uri in asset_uris if uri not in existing_assets_by_uri]
                    
                    if new_uris:
                        existing_assets = self.db.query(ITAsset).filter(ITAsset.uri.in_(new_uris)).all()
                        for asset in existing_assets:
                            existing_assets_by_uri[asset.uri] = asset
                    
                    # Process each asset
                    for asset_data in assets_list:
                        try:
                            uri = asset_data.get('uri', 'unknown')
                            
                            created = self._sync_single_asset(asset_data, existing_assets_by_uri)
                            synced_count += 1
                            if created:
                                created_count += 1
                            else:
                                updated_count += 1
                        except Exception as e:
                            error_msg = f"Error syncing asset {asset_data.get('uri', 'unknown')}: {str(e)}"
                            print(f"ERROR: {error_msg}")
                            import traceback
                            print(f"TRACEBACK: {traceback.format_exc()}")
                            errors.append(error_msg)
                    
                    # Commit after each page to prevent losing all data if an error occurs
                    try:
                        self.db.commit()
                        print(f"Page {page}: Committed {len(assets_list)} assets to database")
                    except Exception as e:
                        error_msg = f"Error committing page {page}: {str(e)}"
                        print(f"ERROR: {error_msg}")
                        import traceback
                        print(f"TRACEBACK: {traceback.format_exc()}")
                        errors.append(error_msg)
                        self.db.rollback()
                        # Continue to next page even if commit fails
                    
                    # Check if we've reached the calculated total pages
                    if total_pages_calculated and page >= total_pages_calculated:
                        print(f"Reached calculated total pages ({total_pages_calculated})")
                        break
                    
                    page += 1
                    
                except Exception as e:
                    errors.append(f"Error fetching page {page}: {str(e)}")
                    break
            
            # Final commit is not needed since we commit after each page
            # But we'll do a final commit to ensure any pending changes are saved
            try:
                self.db.commit()
                print(f"Final commit completed successfully")
            except Exception as e:
                print(f"Final commit error (may be harmless): {str(e)}")
                # Don't add to errors since page commits already succeeded
            
        except Exception as e:
            errors.append(f"Sync error: {str(e)}")
            self.db.rollback()
        
        return synced_count, created_count, updated_count, errors
    
    def _sync_single_asset(
        self,
        asset_data: Dict[str, Any],
        existing_assets_by_uri: Optional[Dict[str, ITAsset]] = None
    ) -> bool:
        """
        Sync a single asset from GCM data.
        
        Args:
            asset_data: Asset data from GCM API
            existing_assets_by_uri: Map of URI to existing ITAsset objects
            
        Returns:
            True if created, False if updated
        """
        uri = asset_data.get("uri")
        if not uri:
            raise ValueError("Asset missing URI")
        
        # Resolve existing asset by URI first.
        existing = None
        if existing_assets_by_uri is not None:
            existing = existing_assets_by_uri.get(uri)
        
        if existing is None:
            existing = self.db.query(ITAsset).filter(ITAsset.uri == uri).first()
        
        # Map GCM fields to database fields
        asset_dict = self._map_gcm_to_db(asset_data)
        asset_dict["last_synced"] = datetime.utcnow()
        
        if existing:
            # Update existing asset matched by unique URI.
            for key, value in asset_dict.items():
                setattr(existing, key, value)
            if existing_assets_by_uri is not None:
                existing_assets_by_uri[uri] = existing
            return False
        
        # Create new asset only when the URI does not exist.
        new_asset = ITAsset(**asset_dict)
        self.db.add(new_asset)
        if existing_assets_by_uri is not None:
            existing_assets_by_uri[uri] = new_asset
        return True
    
    def _map_gcm_to_db(self, gcm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map GCM API fields to database model fields.
        
        Args:
            gcm_data: Data from GCM API
            
        Returns:
            Dictionary with mapped fields
        """
        # Handle tech_contacts - can be string or list
        tech_contacts = gcm_data.get("tech_contacts")
        if isinstance(tech_contacts, str):
            tech_contacts = [c.strip() for c in tech_contacts.split(",") if c.strip()]
        elif not isinstance(tech_contacts, list):
            tech_contacts = None
        
        # Handle extensions/custom attributes
        extensions = gcm_data.get("extensions")
        if extensions and not isinstance(extensions, dict):
            extensions = None
        
        # Handle discovery sources
        discovery_sources = gcm_data.get("discovery_sources")
        if discovery_sources and not isinstance(discovery_sources, list):
            discovery_sources = None
        
        return {
            "asset_id": gcm_data.get("asset_id"),
            "uri": gcm_data.get("uri"),
            "ip": gcm_data.get("ip"),
            "hostname": gcm_data.get("hostname"),
            "port": gcm_data.get("port"),
            "protocol": gcm_data.get("protocol"),
            "asset_type": gcm_data.get("asset_type"),
            "asset_sub_type": gcm_data.get("asset_sub_type"),
            "owner": gcm_data.get("owner"),
            "tech_contacts": tech_contacts,
            "environment": gcm_data.get("environment"),
            "location": gcm_data.get("location"),
            "network": gcm_data.get("network"),
            "mission_criticality": gcm_data.get("mission_criticality"),
            "internet_facing": gcm_data.get("internet_facing"),
            "extensions": extensions,
            "discovery_sources": discovery_sources,
            "first_seen": self._parse_datetime(gcm_data.get("first_seen")),
            "last_seen": self._parse_datetime(gcm_data.get("last_seen")),
            "object_status": gcm_data.get("object_status"),
        }
    
    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string from GCM."""
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception:
            return None
    
    def create_asset(
        self,
        profile_data: Dict[str, Any],
        access_token: str,
        asset_data: ITAssetCreate
    ) -> ITAsset:
        """
        Create a new IT asset in GCM and local database.
        
        Args:
            profile_data: Profile configuration
            access_token: GCM access token
            asset_data: Asset creation data
            
        Returns:
            Created ITAsset instance
        """
        client = self.get_gcm_client(profile_data)
        
        # Prepare asset body for GCM ingest API
        asset_body = {
            "uri": asset_data.uri,
            "ip": asset_data.ip,
            "hostname": asset_data.hostname,
            "port": asset_data.port,
            "asset_type": asset_data.asset_type,
        }
        
        # Add optional fields
        if asset_data.protocol:
            asset_body["protocol"] = asset_data.protocol
        if asset_data.asset_sub_type:
            asset_body["asset_sub_type"] = asset_data.asset_sub_type
        if asset_data.owner:
            asset_body["owner"] = asset_data.owner
        if asset_data.tech_contacts:
            asset_body["tech_contacts"] = asset_data.tech_contacts
        if asset_data.environment:
            asset_body["environment"] = asset_data.environment
        if asset_data.location:
            asset_body["location"] = asset_data.location
        if asset_data.network:
            asset_body["network"] = asset_data.network
        if asset_data.mission_criticality is not None:
            asset_body["mission_criticality"] = asset_data.mission_criticality
        if asset_data.internet_facing:
            # Convert to boolean for ingest API
            asset_body["internet_facing"] = asset_data.internet_facing.upper() == "TRUE"
        if asset_data.extensions:
            asset_body["extensions"] = asset_data.extensions
        
        # Call GCM ingest API
        ingest_path = "ibm/assetinventory/api/v2/assets/ingest/it_assets"
        payload = {"it_assets": [asset_body]}
        
        resp = client.post(ingest_path, access_token, json_body=payload)
        if not resp.ok:
            raise Exception(f"GCM API error: HTTP {resp.status_code} - {resp.text}")
        
        # Create in local database
        db_asset = ITAsset(
            uri=asset_data.uri,
            ip=asset_data.ip,
            hostname=asset_data.hostname,
            port=asset_data.port,
            protocol=asset_data.protocol,
            asset_type=asset_data.asset_type,
            asset_sub_type=asset_data.asset_sub_type,
            owner=asset_data.owner,
            tech_contacts=asset_data.tech_contacts,
            environment=asset_data.environment,
            location=asset_data.location,
            network=asset_data.network,
            mission_criticality=asset_data.mission_criticality,
            internet_facing=asset_data.internet_facing,
            extensions=asset_data.extensions,
            last_synced=datetime.utcnow()
        )
        
        self.db.add(db_asset)
        self.db.commit()
        self.db.refresh(db_asset)
        
        return db_asset
    
    def get_assets(
        self,
        filters: ITAssetFilter
    ) -> Tuple[List[ITAsset], int]:
        """
        Get IT assets with filtering and pagination.
        
        Args:
            filters: Filter criteria
            
        Returns:
            Tuple of (assets list, total count)
        """
        query = self.db.query(ITAsset)
        
        # Apply filters
        if filters.asset_type:
            query = query.filter(ITAsset.asset_type == filters.asset_type)
        if filters.environment:
            query = query.filter(ITAsset.environment == filters.environment)
        if filters.location:
            query = query.filter(ITAsset.location == filters.location)
        if filters.owner:
            query = query.filter(ITAsset.owner == filters.owner)
        if filters.internet_facing:
            query = query.filter(ITAsset.internet_facing == filters.internet_facing)
        
        # Search across multiple fields
        if filters.search:
            search_term = f"%{filters.search}%"
            query = query.filter(
                or_(
                    ITAsset.uri.ilike(search_term),
                    ITAsset.hostname.ilike(search_term),
                    ITAsset.ip.ilike(search_term)
                )
            )
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        if filters.sort_by:
            sort_column = getattr(ITAsset, filters.sort_by, None)
            if sort_column is not None:
                if filters.sort_order == "desc":
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(ITAsset.created_at.desc())
        
        # Apply pagination
        offset = (filters.page - 1) * filters.page_size
        query = query.offset(offset).limit(filters.page_size)
        
        assets = query.all()
        return assets, total
    
    def get_asset_by_id(self, asset_id: int) -> Optional[ITAsset]:
        """Get IT asset by database ID."""
        return self.db.query(ITAsset).filter(ITAsset.id == asset_id).first()
    
    def get_asset_by_uri(self, uri: str) -> Optional[ITAsset]:
        """Get IT asset by URI."""
        return self.db.query(ITAsset).filter(ITAsset.uri == uri).first()
    
    def update_asset(
        self,
        asset_id: int,
        profile_data: Dict[str, Any],
        access_token: str,
        update_data: ITAssetUpdate
    ) -> Optional[ITAsset]:
        """
        Update an IT asset in GCM and local database.
        
        Args:
            asset_id: Database asset ID
            profile_data: Profile configuration
            access_token: GCM access token
            update_data: Update data
            
        Returns:
            Updated ITAsset instance or None if not found
        """
        asset = self.get_asset_by_id(asset_id)
        if not asset:
            return None
        
        client = self.get_gcm_client(profile_data)
        
        # Separate editable and non-editable fields
        editable_fields = {
            "environment", "internet_facing", "location",
            "mission_criticality", "network", "owner",
            "protocol", "tech_contacts"
        }
        
        editable_updates = {}
        ingest_updates = {}
        
        update_dict = update_data.dict(exclude_unset=True)
        for key, value in update_dict.items():
            if key in editable_fields:
                editable_updates[key] = value
            else:
                ingest_updates[key] = value
        
        # Update editable fields via PUT API
        if editable_updates and asset.asset_id:
            put_path = "ibm/assetinventory/api/v1/assets/it_assets"
            payload = {
                "asset_ids": [asset.asset_id],
                "editable_it_asset_attributes": editable_updates
            }
            resp = client.session.put(
                f"{client.app_uri}/{put_path}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json=payload,
                verify=client.verify_ssl,
                timeout=client.timeout
            )
            if not resp.ok:
                raise Exception(f"GCM PUT API error: HTTP {resp.status_code}")
        
        # Update non-editable fields via ingest API
        if ingest_updates:
            ingest_updates["uri"] = asset.uri  # URI is required
            ingest_path = "ibm/assetinventory/api/v2/assets/ingest/it_assets"
            payload = {"it_assets": [ingest_updates]}
            resp = client.post(ingest_path, access_token, json_body=payload)
            if not resp.ok:
                raise Exception(f"GCM ingest API error: HTTP {resp.status_code}")
        
        # Update local database
        for key, value in update_dict.items():
            setattr(asset, key, value)
        
        asset.updated_at = datetime.utcnow()
        asset.last_synced = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(asset)
        
        return asset
    
    def delete_assets(
        self,
        asset_ids: List[int],
        profile_data: Dict[str, Any],
        access_token: str
    ) -> Tuple[int, List[str]]:
        """
        Delete IT assets from GCM and local database.
        
        Args:
            asset_ids: List of database asset IDs
            profile_data: Profile configuration
            access_token: GCM access token
            
        Returns:
            Tuple of (deleted_count, errors)
        """
        client = self.get_gcm_client(profile_data)
        deleted_count = 0
        errors = []
        
        for asset_id in asset_ids:
            try:
                asset = self.get_asset_by_id(asset_id)
                if not asset:
                    errors.append(f"Asset ID {asset_id} not found")
                    continue
                
                # Delete from GCM
                delete_path = "ibm/assetinventory/api/v1/assets/delete/it_assets"
                payload = {
                    "asset_id": [],
                    "uri": [asset.uri]
                }
                
                resp = client.post(delete_path, access_token, json_body=payload)
                if not resp.ok:
                    errors.append(f"GCM delete error for {asset.uri}: HTTP {resp.status_code}")
                    continue
                
                # Delete from local database
                self.db.delete(asset)
                deleted_count += 1
                
            except Exception as e:
                errors.append(f"Error deleting asset ID {asset_id}: {str(e)}")
        
        self.db.commit()
        return deleted_count, errors
    
    def get_stats(self) -> ITAssetStats:
        """
        Get IT asset statistics.
        
        Returns:
            ITAssetStats with aggregated data
        """
        total_assets = self.db.query(func.count(ITAsset.id)).scalar()
        
        # Count by type
        by_type = {}
        type_counts = self.db.query(
            ITAsset.asset_type,
            func.count(ITAsset.id)
        ).group_by(ITAsset.asset_type).all()
        for asset_type, count in type_counts:
            if asset_type:
                by_type[asset_type] = count
        
        # Count by environment
        by_environment = {}
        env_counts = self.db.query(
            ITAsset.environment,
            func.count(ITAsset.id)
        ).group_by(ITAsset.environment).all()
        for environment, count in env_counts:
            if environment:
                by_environment[environment] = count
        
        # Count by location
        by_location = {}
        loc_counts = self.db.query(
            ITAsset.location,
            func.count(ITAsset.id)
        ).group_by(ITAsset.location).all()
        for location, count in loc_counts:
            if location:
                by_location[location] = count
        
        # Internet facing count
        internet_facing_count = self.db.query(func.count(ITAsset.id)).filter(
            ITAsset.internet_facing == "TRUE"
        ).scalar()
        
        # Mission critical count (assuming criticality > 7 is critical)
        mission_critical_count = self.db.query(func.count(ITAsset.id)).filter(
            ITAsset.mission_criticality >= 7
        ).scalar()
        
        return ITAssetStats(
            total_assets=total_assets or 0,
            by_type=by_type,
            by_environment=by_environment,
            by_location=by_location,
            internet_facing_count=internet_facing_count or 0,
            mission_critical_count=mission_critical_count or 0
        )

# Made with Bob
