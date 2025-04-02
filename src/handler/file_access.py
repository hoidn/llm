"""
File access module for reading file contents.
"""
import os
from typing import Dict, Optional

class FileAccessManager:
    """
    Manager for file access operations.
    
    Handles reading file contents for inclusion in context.
    """
    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize FileAccessManager with optional base path.
        
        Args:
            base_path: Optional base path for relative file paths
        """
        self.base_path = base_path or os.getcwd()
    
    def read_file(self, file_path: str, max_size: int = 100 * 1024) -> Optional[str]:
        """
        Read file contents safely.
        
        Args:
            file_path: Path to file
            max_size: Maximum file size in bytes
            
        Returns:
            File contents or None if file cannot be read
        """
        try:
            # Resolve path
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.base_path, file_path)
            
            # Check if file exists
            if not os.path.isfile(file_path):
                print(f"File not found: {file_path}")
                return None
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > max_size:
                print(f"File too large: {file_path} ({file_size} bytes)")
                return f"File too large: {file_path} ({file_size} bytes)"
            
            # Read file
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
            return None
    
    def get_file_info(self, file_path: str) -> Dict[str, str]:
        """
        Get file information.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary with file information
        """
        try:
            # Resolve path
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.base_path, file_path)
            
            # Check if file exists
            if not os.path.isfile(file_path):
                return {"error": f"File not found: {file_path}"}
            
            # Get file info
            stat = os.stat(file_path)
            return {
                "path": file_path,
                "size": str(stat.st_size),
                "modified": str(stat.st_mtime)
            }
        except Exception as e:
            return {"error": f"Error getting file info: {str(e)}"}
