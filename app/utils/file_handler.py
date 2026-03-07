"""File handling utility."""
from pathlib import Path
import os


class FileHandler:
    """Safe file handling utility."""
    
    @staticmethod
    def ensure_directory(path: str) -> Path:
        """
        Ensure directory exists, creating if necessary.
        
        Args:
            path: Directory path
        
        Returns:
            Path object
        """
        dir_path = Path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path
    
    @staticmethod
    def save_file(file_path: str, content: bytes) -> None:
        """
        Save binary content to file.
        
        Args:
            file_path: Path to save file
            content: Binary content
        """
        path = Path(file_path)
        FileHandler.ensure_directory(path.parent)
        
        with open(path, 'wb') as f:
            f.write(content)
    
    @staticmethod
    def read_file(file_path: str) -> bytes:
        """
        Read binary content from file.
        
        Args:
            file_path: Path to read file
        
        Returns:
            Binary content
        """
        with open(file_path, 'rb') as f:
            return f.read()
    
    @staticmethod
    def delete_file(file_path: str) -> bool:
        """
        Delete a file if it exists.
        
        Args:
            file_path: Path to delete
        
        Returns:
            True if deleted, False if not found
        """
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Check if file exists."""
        return Path(file_path).exists()

