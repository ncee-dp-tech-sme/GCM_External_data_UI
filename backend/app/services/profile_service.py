"""
Profile service for managing GCM connection profiles
Handles CRUD operations and encryption of sensitive data

2026-07-23: Added api_key encryption/decryption and has_api_key response field.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from fastapi import HTTPException, status

from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileUpdate, ProfileResponse
from app.security import encryption_manager


class ProfileService:
    """Service for managing GCM connection profiles"""
    
    @staticmethod
    def create_profile(db: Session, profile_data: ProfileCreate) -> Profile:
        """
        Create a new profile with encrypted sensitive fields
        
        Args:
            db: Database session
            profile_data: Profile creation data
            
        Returns:
            Created profile
            
        Raises:
            HTTPException: If profile name already exists
        """
        # Check if name already exists
        existing = db.query(Profile).filter(Profile.name == profile_data.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Profile with name '{profile_data.name}' already exists"
            )
        
        # Create profile with encrypted sensitive fields
        profile = Profile(
            name=profile_data.name,
            description=profile_data.description,
            app_uri=profile_data.app_uri,
            oidc_uri=profile_data.oidc_uri,
            realm=profile_data.realm,
            auth_method=profile_data.auth_method,
            client_id=profile_data.client_id,
            client_secret=encryption_manager.encrypt(profile_data.client_secret) if profile_data.client_secret else None,
            username=encryption_manager.encrypt(profile_data.username) if profile_data.username else None,
            password=encryption_manager.encrypt(profile_data.password) if profile_data.password else None,
            api_key=encryption_manager.encrypt(profile_data.api_key) if profile_data.api_key else None,
            timeout=profile_data.timeout,
            insecure=profile_data.insecure,
            tenant_id=profile_data.tenant_id,
            user_agent=profile_data.user_agent
        )
        
        # If this is the first profile, make it active
        if db.query(Profile).count() == 0:
            profile.is_active = True
        
        try:
            db.add(profile)
            db.commit()
            db.refresh(profile)
            return profile
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create profile due to database constraint"
            )
    
    @staticmethod
    def get_profile(db: Session, profile_id: int) -> Profile:
        """
        Get a profile by ID
        
        Args:
            db: Database session
            profile_id: Profile ID
            
        Returns:
            Profile
            
        Raises:
            HTTPException: If profile not found
        """
        profile = db.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Profile with ID {profile_id} not found"
            )
        return profile
    
    @staticmethod
    def get_profile_by_name(db: Session, name: str) -> Optional[Profile]:
        """Get a profile by name"""
        return db.query(Profile).filter(Profile.name == name).first()
    
    @staticmethod
    def get_all_profiles(db: Session) -> List[Profile]:
        """Get all profiles"""
        return db.query(Profile).order_by(Profile.created_at.desc()).all()
    
    @staticmethod
    def get_active_profile(db: Session) -> Optional[Profile]:
        """Get the currently active profile"""
        return db.query(Profile).filter(Profile.is_active == True).first()
    
    @staticmethod
    def update_profile(db: Session, profile_id: int, profile_data: ProfileUpdate) -> Profile:
        """
        Update a profile
        
        Args:
            db: Database session
            profile_id: Profile ID
            profile_data: Profile update data
            
        Returns:
            Updated profile
            
        Raises:
            HTTPException: If profile not found or name conflict
        """
        profile = ProfileService.get_profile(db, profile_id)
        
        # Check for name conflict if name is being changed
        if profile_data.name and profile_data.name != profile.name:
            existing = db.query(Profile).filter(Profile.name == profile_data.name).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Profile with name '{profile_data.name}' already exists"
                )
        
        # Update fields
        update_data = profile_data.model_dump(exclude_unset=True)
        
        # Handle sensitive fields with encryption
        if 'client_secret' in update_data and update_data['client_secret']:
            update_data['client_secret'] = encryption_manager.encrypt(update_data['client_secret'])
        if 'username' in update_data and update_data['username']:
            update_data['username'] = encryption_manager.encrypt(update_data['username'])
        if 'password' in update_data and update_data['password']:
            update_data['password'] = encryption_manager.encrypt(update_data['password'])
        if 'api_key' in update_data and update_data['api_key']:
            update_data['api_key'] = encryption_manager.encrypt(update_data['api_key'])
        
        for key, value in update_data.items():
            setattr(profile, key, value)
        
        db.commit()
        db.refresh(profile)
        return profile
    
    @staticmethod
    def delete_profile(db: Session, profile_id: int) -> None:
        """
        Delete a profile
        
        Args:
            db: Database session
            profile_id: Profile ID
            
        Raises:
            HTTPException: If profile not found or is active
        """
        profile = ProfileService.get_profile(db, profile_id)
        
        if profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete active profile. Activate another profile first."
            )
        
        db.delete(profile)
        db.commit()
    
    @staticmethod
    def set_active_profile(db: Session, profile_id: int) -> Profile:
        """
        Set a profile as active (deactivates all others)
        
        Args:
            db: Database session
            profile_id: Profile ID to activate
            
        Returns:
            Activated profile
            
        Raises:
            HTTPException: If profile not found
        """
        profile = ProfileService.get_profile(db, profile_id)
        
        # Deactivate all profiles
        db.query(Profile).update({Profile.is_active: False})
        
        # Activate the selected profile
        profile.is_active = True
        db.commit()
        db.refresh(profile)
        return profile
    
    @staticmethod
    def to_response(profile: Profile) -> ProfileResponse:
        """
        Convert profile model to response schema
        Excludes sensitive data but indicates if fields are set
        
        Args:
            profile: Profile model
            
        Returns:
            Profile response schema
        """
        return ProfileResponse(
            id=profile.id,
            name=profile.name,
            description=profile.description,
            is_active=profile.is_active,
            app_uri=profile.app_uri,
            oidc_uri=profile.oidc_uri,
            realm=profile.realm,
            auth_method=profile.auth_method,
            client_id=profile.client_id,
            timeout=profile.timeout,
            insecure=profile.insecure,
            tenant_id=profile.tenant_id,
            user_agent=profile.user_agent,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            has_client_secret=bool(profile.client_secret),
            has_refresh_token=bool(profile.refresh_token),
            has_username=bool(profile.username),
            has_password=bool(profile.password),
            has_api_key=bool(profile.api_key),
        )

    @staticmethod
    def store_refresh_token(db: Session, profile: Profile, refresh_token: str) -> Profile:
        """
        Store a refresh token obtained from the OIDC authorization flow
        """
        profile.refresh_token = encryption_manager.encrypt(refresh_token)
        db.commit()
        db.refresh(profile)
        return profile
    
    @staticmethod
    def get_decrypted_refresh_token(profile: Profile) -> str:
        """
        Get the decrypted refresh token for a profile
        """
        if not profile.refresh_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile does not have a stored refresh token. Complete the authorization flow first."
            )
        return encryption_manager.decrypt(profile.refresh_token)
    
    @staticmethod
    def get_decrypted_client_secret(profile: Profile) -> Optional[str]:
        """
        Get the decrypted client secret for a profile
        """
        if not profile.client_secret:
            return None
        return encryption_manager.decrypt(profile.client_secret)
    
    @staticmethod
    def get_decrypted_username(profile: Profile) -> Optional[str]:
        """
        Get the decrypted username for a profile
        """
        if not profile.username:
            return None
        return encryption_manager.decrypt(profile.username)
    
    @staticmethod
    def get_decrypted_password(profile: Profile) -> Optional[str]:
        """
        Get the decrypted password for a profile
        """
        if not profile.password:
            return None
        return encryption_manager.decrypt(profile.password)

    @staticmethod
    def get_decrypted_api_key(profile: Profile) -> Optional[str]:
        """
        Get the decrypted API key for a profile
        """
        if not profile.api_key:
            return None
        return encryption_manager.decrypt(profile.api_key)

    @staticmethod
    def get_active_profile(db: Session) -> Profile:
        """
        Get the currently active profile
        """
        profile = db.query(Profile).filter(Profile.is_active == True).first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active profile found. Please activate a profile first."
            )
        return profile

# Made with Bob
