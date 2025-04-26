"""
Provides safe access to the file system based on the FileAccessManager IDL.
"""

import os
from datetime import datetime
from typing import Optional, Dict, Union

# Default max size from IDL description (100KB)
DEFAULT_MAX_FILE_SIZE = 100 * 1024

class FileAccessManager:
    """
    Manages safe reading and metadata retrieval for files within a specified base path.

    Implements the contract defined in src/handler/file_access_IDL.md.
    Depends on the FileSystem resource implicitly via the 'os' module.
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initializes the FileAccessManager.

        Args:
            base_path: Optional base directory for resolving relative paths.
                       Defaults to the current working directory.
        """
        if base_path is None:
            self.base_path = os.path.abspath(os.getcwd())
        else:
            self.base_path = os.path.abspath(base_path)
        # Ensure base_path exists and is a directory (optional safety check)
        if not os.path.isdir(self.base_path):
             # IDL doesn't specify error handling here, logging or raising might be options
             # For now, proceed as per IDL, assuming base_path is valid or errors handled later
             pass


    def _resolve_path(self, file_path: str) -> str:
        """Resolves a potentially relative path against the base path."""
        # Security Note: This basic resolution doesn't prevent path traversal attacks
        # (e.g., "../../../etc/passwd"). A production implementation should add
        # checks to ensure the resolved path stays within the base_path.
        # Sticking strictly to IDL for now.
        absolute_req_path = os.path.abspath(os.path.join(self.base_path, file_path))
        return absolute_req_path

    def read_file(self, file_path: str, max_size: Optional[int] = DEFAULT_MAX_FILE_SIZE) -> Optional[str]:
        """
        Reads the content of a specified file safely.

        Args:
            file_path: Path to the file (can be relative to base_path).
            max_size: Maximum file size in bytes. Defaults to 100KB.

        Returns:
            The file content as a string if successful and within limits,
            a specific error string if the file is too large, or None if
            the file is not found or another read error occurs.
        """
        if max_size is None:
            max_size = DEFAULT_MAX_FILE_SIZE

        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
                return None # File not found or not a file

            file_size = os.path.getsize(resolved_path)
            if file_size > max_size:
                return f"File too large (size: {file_size} bytes, limit: {max_size} bytes)"

            with open(resolved_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            return content

        except (IOError, OSError, UnicodeDecodeError):
            # IDL implies returning None for generic read errors
            return None

    def get_file_info(self, file_path: str) -> Dict[str, str]:
        """
        Retrieves metadata information about a specified file.

        Args:
            file_path: Path to the file (can be relative to base_path).

        Returns:
            A dictionary with 'path', 'size', 'modified' on success,
            or a dictionary with 'error' on failure.
        """
        try:
            resolved_path = self._resolve_path(file_path)

            if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
                 return {"error": f"File not found or not a regular file: {file_path}"}

            stat_result = os.stat(resolved_path)
            size_bytes = stat_result.st_size
            modified_timestamp = stat_result.st_mtime
            modified_dt = datetime.fromtimestamp(modified_timestamp)

            # Format size and modified time as strings per IDL examples
            size_str = f"{size_bytes} bytes"
            modified_str = modified_dt.isoformat() # Using ISO format for clarity

            return {
                "path": resolved_path,
                "size": size_str,
                "modified": modified_str
            }
        except (OSError, FileNotFoundError) as e:
            return {"error": f"Error accessing file info for {file_path}: {e}"}
        except Exception as e: # Catch unexpected errors
             return {"error": f"Unexpected error getting info for {file_path}: {e}"}
