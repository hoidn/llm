"""
Provides safe access to the file system based on the FileAccessManager IDL.
"""

import os
import logging # Add logging import
from datetime import datetime
from typing import Optional, Dict, Union

# Default max size from IDL description (100KB)
DEFAULT_MAX_FILE_SIZE = 100 * 1024

# Define module-level logger
logger = logging.getLogger(__name__)

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
        # Log the actual base path being used
        logger.info(f"FileAccessManager initialized with base_path: {self.base_path}")
        if not os.path.isdir(self.base_path):
             # IDL doesn't specify error handling here, logging or raising might be options
             # For now, proceed as per IDL, assuming base_path is valid or errors handled later
             logger.warning(f"Base path '{self.base_path}' does not exist or is not a directory.")
             pass


    def _resolve_path(self, file_path: str) -> str:
        """Resolves a potentially relative path against the base path."""
        # Security Note: This basic resolution doesn't prevent path traversal attacks
        # (e.g., "../../../etc/passwd"). A production implementation should add
        # checks to ensure the resolved path stays within the base_path.
        # Sticking strictly to IDL for now.
        # Update: Path safety check is now handled by _is_path_safe
        absolute_req_path = os.path.abspath(os.path.join(self.base_path, file_path))
        return absolute_req_path

    # Add this helper method to the class
    def _is_path_safe(self, resolved_path: str) -> bool:
        """Checks if the resolved path is within the configured base_path."""
        # Use os.path.commonpath to check containment robustly
        # Handles edge cases like identical paths correctly
        try:
            # Ensure both paths are absolute and normalized for reliable comparison
            abs_base = os.path.abspath(self.base_path)
            abs_resolved = os.path.abspath(resolved_path)
            is_safe = os.path.commonpath([abs_base]) == os.path.commonpath([abs_base, abs_resolved])
            if not is_safe:
                logger.error(f"Path safety check failed: '{resolved_path}' is outside base '{self.base_path}'")
            return is_safe
        except ValueError:
            # commonpath raises ValueError if paths are on different drives (Windows)
            logger.error(f"Path safety check failed: '{resolved_path}' and base '{self.base_path}' are on different drives.")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during path safety check for '{resolved_path}': {e}")
            return False


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
            # Add safety check
            if not self._is_path_safe(resolved_path):
                return None # Path safety check failed (error logged in _is_path_safe)

            if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
                logger.warning(f"read_file: File not found or not a file: {resolved_path}")
                return None # File not found or not a file

            file_size = os.path.getsize(resolved_path)
            if file_size > max_size:
                logger.warning(f"read_file: File too large: {resolved_path} (size: {file_size}, limit: {max_size})")
                return f"File too large (size: {file_size} bytes, limit: {max_size} bytes)"

            with open(resolved_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            logger.debug(f"read_file: Successfully read {len(content)} chars from {resolved_path}")
            return content

        except (IOError, OSError, UnicodeDecodeError) as e:
            # IDL implies returning None for generic read errors
            logger.error(f"read_file: Error reading file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"read_file: Unexpected error reading file {file_path}: {e}")
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
            # Add safety check
            if not self._is_path_safe(resolved_path):
                 # Error logged in _is_path_safe
                 return {"error": f"Access denied: Path '{file_path}' is outside the allowed base directory."}


            if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
                 logger.warning(f"get_file_info: File not found or not a regular file: {resolved_path}")
                 return {"error": f"File not found or not a regular file: {file_path}"}

            stat_result = os.stat(resolved_path)
            size_bytes = stat_result.st_size
            modified_timestamp = stat_result.st_mtime
            modified_dt = datetime.fromtimestamp(modified_timestamp)

            # Format size and modified time as strings per IDL examples
            size_str = f"{size_bytes} bytes"
            modified_str = modified_dt.isoformat() # Using ISO format for clarity

            logger.debug(f"get_file_info: Successfully retrieved info for {resolved_path}")
            return {
                "path": resolved_path,
                "size": size_str,
                "modified": modified_str
            }
        except (OSError, FileNotFoundError) as e:
            logger.error(f"get_file_info: Error accessing file info for {file_path}: {e}")
            return {"error": f"Error accessing file info for {file_path}: {e}"}
        except Exception as e: # Catch unexpected errors
             logger.error(f"get_file_info: Unexpected error getting info for {file_path}: {e}")
             return {"error": f"Unexpected error getting info for {file_path}: {e}"}

    def write_file(self, file_path: str, content: str, overwrite: bool = False) -> bool:
        """
        Writes content to a file, optionally overwriting. Constrained by base_path.

        Args:
            file_path: Path to the file (relative to base_path).
            content: The string content to write.
            overwrite: If True, overwrite the file if it exists. Defaults to False.

        Returns:
            True on success, False on failure. Errors are logged internally.
        """
        try:
            resolved_path = self._resolve_path(file_path)
            if not self._is_path_safe(resolved_path):
                return False # Path safety check failed (error logged in _is_path_safe)

            # Check if path exists and handle overwrite logic
            if os.path.exists(resolved_path):
                if os.path.isdir(resolved_path):
                    logger.error(f"write_file: Cannot write to '{resolved_path}', it is a directory.")
                    return False
                if not overwrite:
                    logger.warning(f"write_file: File '{resolved_path}' exists and overwrite is False. Write aborted.")
                    return False
                # If overwrite is True, proceed

            # Ensure parent directory exists
            parent_dir = os.path.dirname(resolved_path)
            if not os.path.exists(parent_dir):
                try:
                    os.makedirs(parent_dir, exist_ok=True)
                    logger.info(f"write_file: Created parent directory '{parent_dir}'.")
                except OSError as e:
                    logger.error(f"write_file: Failed to create parent directory '{parent_dir}': {e}")
                    return False

            # Write the file
            with open(resolved_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"write_file: Successfully wrote {len(content)} chars to '{resolved_path}'.")
            return True

        except (IOError, OSError, PermissionError) as e:
            logger.error(f"write_file: Error writing to file '{file_path}': {e}")
            return False
        except Exception as e:
            logger.error(f"write_file: Unexpected error writing to file '{file_path}': {e}")
            return False

    def insert_content(self, file_path: str, content: str, position: int) -> bool:
        """
        Inserts content into a file at a specific byte offset. Constrained by base_path.

        Args:
            file_path: Path to the file (relative to base_path).
            content: The string content to insert.
            position: The byte offset (0-indexed) where insertion should occur.

        Returns:
            True on success, False on failure. Errors are logged internally.
        """
        try:
            resolved_path = self._resolve_path(file_path)
            if not self._is_path_safe(resolved_path):
                return False # Path safety check failed (error logged in _is_path_safe)

            # Check if file exists and is a file
            if not os.path.exists(resolved_path) or not os.path.isfile(resolved_path):
                logger.error(f"insert_content: File not found or not a file: '{resolved_path}'.")
                return False

            # Read existing content (using binary mode for accurate position handling)
            try:
                with open(resolved_path, 'rb') as f:
                    existing_content_bytes = f.read()
            except (IOError, OSError, PermissionError) as e:
                 logger.error(f"insert_content: Error reading existing file '{resolved_path}': {e}")
                 return False

            # Validate position
            if not (0 <= position <= len(existing_content_bytes)):
                logger.error(f"insert_content: Invalid position {position} for file '{resolved_path}' with size {len(existing_content_bytes)}.")
                return False

            # Prepare content for insertion (encode the new content)
            try:
                content_bytes = content.encode('utf-8')
            except UnicodeEncodeError as e:
                logger.error(f"insert_content: Failed to encode insertion content to UTF-8: {e}")
                return False

            # Construct new content
            new_content_bytes = existing_content_bytes[:position] + content_bytes + existing_content_bytes[position:]

            # Write back the modified content (binary mode)
            try:
                with open(resolved_path, 'wb') as f:
                    f.write(new_content_bytes)
                logger.info(f"insert_content: Successfully inserted {len(content_bytes)} bytes at position {position} in '{resolved_path}'.")
                return True
            except (IOError, OSError, PermissionError) as e:
                logger.error(f"insert_content: Error writing modified content to '{resolved_path}': {e}")
                return False

        except Exception as e:
            logger.error(f"insert_content: Unexpected error inserting content into '{file_path}': {e}")
            return False
