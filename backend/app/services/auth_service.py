"""
2026-06-01T19:45:00Z - Added OIDC device authorization and GCM authorization service.
2026-06-01T20:26:00Z - Added password grant authentication method.
2026-06-01T22:37:00Z - Added active profile authentication and automatic token refresh.
2026-06-01T22:50:00Z - Removed unused device authorization methods, simplified to active profile flow only.
2026-07-23T00:00:00Z - Added API key authentication as a mutually exclusive auth method.
                       get_active_profile_token() is the single decision point: it checks
                       auth_method and branches to either OIDC or API key logic exclusively.
                       build_api_key_headers() produces the Authorization header for API key requests.
2026-07-25T00:04:00Z - Fixed API key header: removed token_type header; the stored api_key value
                       already includes the 'Bearer ' prefix so it is sent as-is in Authorization.
"""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session
import requests
import urllib3
from fastapi import HTTPException, status

from app.models.profile import Profile, AUTH_METHOD_OIDC, AUTH_METHOD_API_KEY
from app.services.profile_service import ProfileService


@dataclass(frozen=True)
class ApiKeyCredential:
    """
    Immutable value object representing a validated API key credential.
    Carries exactly the two headers required for API key authentication:
      - Authorization: <api_key>
      - token_type: api_key
    Instantiation validates that the key is present and non-empty.
    """
    api_key: str

    def __post_init__(self):
        if not self.api_key or not self.api_key.strip():
            raise ValueError("api_key must be a non-empty string")

    def to_headers(self) -> dict:
        """Return the Authorization and token_type headers for API key authentication.
        The stored api_key already includes the 'Bearer ' prefix.
        token_type: api_key is mandatory for GCM to recognise API key auth."""
        return {
            "Authorization": self.api_key,
            "token_type": "api_key",
        }


class AuthService:
    """Service for OIDC and GCM authorization flows using active profile.

    Authentication method is determined exclusively by `profile.auth_method`.
    The single decision point is `get_active_profile_token()` / `build_request_headers()`.
    When auth_method == 'api_key', no OIDC code is invoked. When auth_method == 'oidc',
    no API key code is invoked.
    """

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

    # Build common OIDC request headers.
    @staticmethod
    def _headers(profile: Profile, content_type: str = "application/x-www-form-urlencoded") -> dict:
        return {
            "Content-Type": content_type,
            "User-Agent": profile.user_agent,
            "Accept": "application/json",
        }

    # --- API key authentication ---

    @staticmethod
    def get_api_key_credential(profile: Profile) -> ApiKeyCredential:
        """
        Build and validate the ApiKeyCredential from the active profile.

        Raises:
            HTTPException 400 if the profile has no api_key configured.
            HTTPException 422 if the stored api_key value is malformed.
        """
        raw = ProfileService.get_decrypted_api_key(profile)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Profile auth_method is 'api_key' but no api_key is configured. "
                    "Please update the profile with a valid API key."
                ),
            )
        try:
            return ApiKeyCredential(api_key=raw)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Stored api_key is malformed: {exc}",
            ) from exc

    @staticmethod
    def build_api_key_headers(profile: Profile) -> dict:
        """
        Return the Authorization and token_type headers for an API key request.

        The caller must include these headers verbatim in every outgoing request.
        Raises HTTPException if the profile is missing or has a malformed api_key.
        """
        credential = AuthService.get_api_key_credential(profile)
        return credential.to_headers()

    # --- OIDC authentication ---

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
        Authenticate using the active profile's stored username and password (OIDC only).
        Raises HTTPException 400 if the active profile uses API key auth — the /login
        endpoint is not applicable in that case.

        Returns:
            dict with access_token, refresh_token, and expires_in
        """
        profile = ProfileService.get_active_profile(db)

        if profile.auth_method == AUTH_METHOD_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The active profile uses API key authentication. "
                    "The /auth/login endpoint is for OIDC profiles only. "
                    "API key credentials do not require a login step."
                ),
            )

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

    # --- Single decision point for token/credential resolution ---

    @staticmethod
    def get_active_profile_token(db: Session) -> str:
        """
        Get a valid access token (OIDC) for the active profile.

        THIS IS THE SINGLE DECISION POINT FOR AUTH METHOD SELECTION.
        Raises HTTPException 400 if the active profile uses API key auth — callers
        that need to support both methods should use get_active_profile_headers()
        instead, which handles both methods and returns ready-to-use headers.

        Returns:
            str: Valid OIDC access token
        """
        profile = ProfileService.get_active_profile(db)

        if profile.auth_method == AUTH_METHOD_API_KEY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "The active profile uses API key authentication. "
                    "Call get_active_profile_headers() to obtain pre-built request headers."
                ),
            )

        # OIDC path: try refresh token first, then fall back to password auth
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

    @staticmethod
    def get_active_profile_headers(db: Session) -> dict:
        """
        Return ready-to-use Authorization headers for the active profile.

        THIS IS THE RECOMMENDED ENTRY POINT FOR SERVICE LAYERS that need to make
        authenticated requests. It branches exclusively on auth_method:

          - auth_method == 'api_key':  {"Authorization": "<key>", "token_type": "api_key"}
          - auth_method == 'oidc':     {"Authorization": "Bearer <token>"}

        No OIDC code runs when auth_method is 'api_key'.
        No API key code runs when auth_method is 'oidc'.

        Raises:
            HTTPException 400/401/502: if credential retrieval fails for the active method.
        """
        profile = ProfileService.get_active_profile(db)

        if profile.auth_method == AUTH_METHOD_API_KEY:
            # API key path — OIDC is completely bypassed
            return AuthService.build_api_key_headers(profile)

        # OIDC path — API key code is completely bypassed
        access_token = AuthService.get_active_profile_token(db)
        return {"Authorization": f"Bearer {access_token}"}

    # Call GCM authorization API.
    @staticmethod
    def authorize(db: Session, profile: Profile, tenant_id: Optional[str] = None) -> dict:
        """Authorize to GCM using access token (OIDC only)."""
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
