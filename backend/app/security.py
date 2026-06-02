"""
Security utilities for encryption and credential management
Uses Fernet symmetric encryption for sensitive data
"""

from cryptography.fernet import Fernet
from app.config import settings
import base64


class EncryptionManager:
    """Manages encryption and decryption of sensitive data"""
    
    def __init__(self):
        """Initialize with encryption key from settings"""
        self._cipher = None
    
    @property
    def cipher(self):
        """Lazy-load cipher to avoid initialization errors at import time"""
        if self._cipher is None:
            self._cipher = Fernet(settings.encryption_key.encode())
        return self._cipher
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt a string value
        
        Args:
            data: Plain text string to encrypt
            
        Returns:
            Base64 encoded encrypted string
        """
        if not data:
            return ""
        encrypted = self.cipher.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt an encrypted string
        
        Args:
            encrypted_data: Base64 encoded encrypted string
            
        Returns:
            Decrypted plain text string
        """
        if not encrypted_data:
            return ""
        decoded = base64.b64decode(encrypted_data.encode())
        decrypted = self.cipher.decrypt(decoded)
        return decrypted.decode()


# Global encryption manager instance
encryption_manager = EncryptionManager()


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key
    Use this to generate a key for the ENCRYPTION_KEY environment variable
    
    Returns:
        Base64 encoded Fernet key
    """
    return Fernet.generate_key().decode()


if __name__ == "__main__":
    # Generate a new key when run directly
    print("Generated Encryption Key:")
    print(generate_encryption_key())
    print("\nAdd this to your .env file as ENCRYPTION_KEY")

# Made with Bob
