"""
Application configuration management
Loads settings from environment variables
"""

from pydantic_settings import BaseSettings
from typing import List
import sys
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    app_name: str = "GCM Web UI"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Database
    database_url: str = "sqlite:///./gcm_webui.db"
    
    # Security
    encryption_key: str
    session_expire_minutes: int = 480
    
    # CORS
    cors_origins: str = "http://localhost:3000"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


def load_settings() -> Settings:
    """
    Load settings with helpful error messages
    """
    try:
        return Settings()
    except Exception as e:
        error_msg = str(e)
        
        # Check if .env file exists
        env_file = Path(".env")
        if not env_file.exists():
            print("\n" + "="*60)
            print("ERROR: Configuration file not found")
            print("="*60)
            print("\nThe .env file is missing. Please run the setup script:")
            print("\n  cd webui/backend")
            print("  ./setup.sh")
            print("\nOr manually create .env from .env.example:")
            print("\n  cp .env.example .env")
            print("\nThen generate keys:")
            print("\n  python -m app.security")
            print("\nAnd update .env with the generated keys.")
            print("="*60 + "\n")
            sys.exit(1)
        
        # Check for missing required fields
        if "secret_key" in error_msg.lower() or "encryption_key" in error_msg.lower():
            print("\n" + "="*60)
            print("ERROR: Missing required configuration")
            print("="*60)
            print("\nYour .env file is missing required keys.")
            print("\nGenerate encryption key:")
            print("\n  python -m app.security")
            print("\nGenerate secret key:")
            print("\n  python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
            print("\nThen update your .env file with these values.")
            print("="*60 + "\n")
            sys.exit(1)
        
        # Generic error
        print(f"\nConfiguration error: {error_msg}\n")
        sys.exit(1)


# Global settings instance
settings = load_settings()

# Made with Bob
