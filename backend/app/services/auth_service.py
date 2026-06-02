"""
2026-06-01T19:45:00Z - Added OIDC device authorization and GCM authorization service.
2026-06-01T20:26:00Z - Added password grant authentication method.
2026-06-01T22:37:00Z - Added active profile authentication and automatic token refresh.
2026-06-01T22:50:00Z - Removed unused device authorization methods, simplified to active profile flow only.
"""

from typing import Optional
from sqlalchemy.orm import Session
import requests
import urllib3
from fastapi import HTTPException, status

from app.models.profile import Profile
from app.services.profile_service import ProfileService


class AuthService:
    """Service for OIDC and GCM authorization flows using active profile"""

    # Build token endpoint URL.
    @staticmethod
    def _token_endpoint(profile: Profile) -> str:
        return f"{profile.oidc_uri}/realms/{profile.realm}/protocol/openid-connect/token"

    # Build GCM authorization endpoint URL.
    @staticmethod
    def _authorization_endpoint(profile: Profile) -> str:
        return f"{profile.app_uri}/ibm/usermanagement/api/v2/authorization"

    # Build requests verify flag.
    @staticmethod
    def _verify_ssl(profile: Profile) -> bool:
        verify_ssl = not profile.insecure
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return verify_ssl

    # Build common request headers.
    @staticmethod
    def _headers(profile: Profile, content_type: str = "application/x-www-form-urlencoded") -> dict:
        return {
            "Content-Type": content_type,
            "User-Agent": profile.user_agent,
            "Accept": "application/json",
        }

    # Authenticate using password grant and get access token directly.
    @staticmethod
    def authenticate_with_password(profile: Profile, username: str, password: str, client_id_override: str = None) -> dict:
        """Authenticate using password grant (Resource Owner Password Credentials).
        
        Args:
            profile: Profile with OIDC configuration
            username: GCM username
            password: GCM password
            client_id_override: Optional client_id to use instead of profile's client_id
            
        Returns:
            dict with access_token, refresh_token (optional), and expires_in
        """
        client_id = client_id_override or profile.client_id
        client_secret = ProfileService.get_decrypted_client_secret(profile)
        
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
            "scope": "openid",
        }
        
        if client_id:
            data["client_id"] = client_id
        if client_secret:
            data["client_secret"] = client_secret
        
        response = requests.post(
            AuthService._token_endpoint(profile),
            data=data,
            headers=AuthService._headers(profile),
            timeout=profile.timeout,
            verify=AuthService._verify_ssl(profile),
        )
        
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {response.text}",
            ) from exc
        
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OIDC token response did not include an access token.",
            )
        
        return {
            "access_token": access_token,
            "refresh_token": payload.get("refresh_token"),
            "expires_in": payload.get("expires_in", 300),
        }

    # Exchange refresh token for access token.
    @staticmethod
    def get_access_token(db: Session, profile: Profile) -> str:
        """Get access token using refresh token."""
        refresh_token = ProfileService.get_decrypted_refresh_token(profile)
        client_secret = ProfileService.get_decrypted_client_secret(profile)

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if profile.client_id:
            data["client_id"] = profile.client_id
        if client_secret:
            data["client_secret"] = client_secret

        response = requests.post(
            AuthService._token_endpoint(profile),
            data=data,
            headers=AuthService._headers(profile),
            timeout=profile.timeout,
            verify=AuthService._verify_ssl(profile),
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to exchange refresh token for access token: {response.text}",
            ) from exc

        payload = response.json()
        access_token = payload.get("access_token")
        rotated_refresh_token = payload.get("refresh_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="OIDC token response did not include an access token.",
            )
        if rotated_refresh_token:
            ProfileService.store_refresh_token(db, profile, rotated_refresh_token)
        return access_token

    # Authenticate using active profile's stored credentials.
    @staticmethod
    def authenticate_active_profile(db: Session) -> dict:
        """
        Authenticate using the active profile's stored username and password.
        Gets access token from OIDC.
        
        Returns:
            dict with access_token, refresh_token, and expires_in
        """
        profile = ProfileService.get_active_profile(db)
        
        # Get credentials from profile
        username = ProfileService.get_decrypted_username(profile)
        password = ProfileService.get_decrypted_password(profile)
        
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Active profile does not have username/password configured. Please update the profile."
            )
        
        # Authenticate
        result = AuthService.authenticate_with_password(profile, username, password)
        
        # Store refresh token
        if result.get("refresh_token"):
            ProfileService.store_refresh_token(db, profile, result["refresh_token"])
        
        return result
    
    # Get a valid access token for the active profile (refresh if needed).
    @staticmethod
    def get_active_profile_token(db: Session) -> str:
        """
        Get a valid access token for the active profile.
        If a refresh token exists, use it. Otherwise, authenticate with username/password.
        
        Returns:
            str: Valid access token
        """
        profile = ProfileService.get_active_profile(db)
        
        # Try to use refresh token first
        if profile.refresh_token:
            try:
                return AuthService.get_access_token(db, profile)
            except HTTPException:
                # Refresh token expired or invalid, fall back to password auth
                pass
        
        # Fall back to password authentication
        username = ProfileService.get_decrypted_username(profile)
        password = ProfileService.get_decrypted_password(profile)
        
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid authentication method available. Profile needs username/password or refresh token."
            )
        
        result = AuthService.authenticate_with_password(profile, username, password)
        
        # Store refresh token for future use
        if result.get("refresh_token"):
            ProfileService.store_refresh_token(db, profile, result["refresh_token"])
        
        return result["access_token"]

    # Call GCM authorization API.
    @staticmethod
    def authorize(db: Session, profile: Profile, tenant_id: Optional[str] = None) -> dict:
        """Authorize to GCM using access token."""
        access_token = AuthService.get_access_token(db, profile)
        response = requests.post(
            AuthService._authorization_endpoint(profile),
            json={"tenantId": tenant_id if tenant_id is not None else (profile.tenant_id or "")},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": profile.user_agent,
            },
            timeout=profile.timeout,
            verify=AuthService._verify_ssl(profile),
        )

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}

        return {
            "status_code": response.status_code,
            "authorized": response.ok,
            "payload": payload,
            "access_token": access_token,
        }

# Made with Bob
