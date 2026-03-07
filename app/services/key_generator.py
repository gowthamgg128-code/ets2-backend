"""License key generation service."""
import secrets
import string


class KeyGeneratorService:
    """Service for generating secure license keys."""
    
    @staticmethod
    def generate_key(length: int = 32) -> str:
        """
        Generate a secure random license key.
        
        Args:
            length: Length of the key (default: 32)
        
        Returns:
            Random alphanumeric key
        """
        # Use uppercase, lowercase, and digits for better readability
        characters = string.ascii_uppercase + string.ascii_lowercase + string.digits
        
        # Generate random key
        key = ''.join(secrets.choice(characters) for _ in range(length))
        
        return key
    
    @staticmethod
    def format_key(key: str, chunk_size: int = 8) -> str:
        """
        Format key into chunks for display.
        
        Args:
            key: Raw key string
            chunk_size: Size of each chunk (default: 8)
        
        Returns:
            Formatted key with hyphens
        """
        chunks = [key[i:i+chunk_size] for i in range(0, len(key), chunk_size)]
        return '-'.join(chunks)

