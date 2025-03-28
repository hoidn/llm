"""Git repository indexer for Memory System."""
from typing import Dict, List, Optional, Set, Tuple
import os
import glob
from pathlib import Path
import re

class GitRepositoryIndexer:
    """Indexes a Git repository for use with Memory System.
    
    This component scans a git repository, extracts metadata from text files,
    and updates the global index in the Memory System.
    """
    
    # Common binary file extensions to skip
    BINARY_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',  # Images
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # Documents
        '.zip', '.tar', '.gz', '.rar', '.7z',  # Archives
        '.exe', '.dll', '.so', '.dylib',  # Binaries
        '.pyc', '.pyo', '.pyd',  # Python cache files
        '.o', '.obj', '.a', '.lib',  # Compiled objects
    }
    
    # Content patterns that indicate binary data
    BINARY_CONTENT_PATTERNS = [
        b'\x00',  # Null byte
        b'\xff\xd8\xff',  # JPEG SOI marker
        b'\x89PNG',  # PNG signature
        b'PK\x03\x04',  # ZIP signature
    ]
    
    def __init__(self, repo_path: str):
        """Initialize the indexer with a repository path.
        
        Args:
            repo_path: Path to the git repository to index
        """
        self.repo_path = repo_path
        self.max_file_size = 1_000_000  # Default 1MB max file size
        self.include_patterns = ["**/*"]  # Default include all files
        self.exclude_patterns = []  # Default exclude none
    
    def index_repository(self, memory_system) -> Dict[str, str]:
        """Index the repository and update the Memory System.
        
        Scans the repository, extracts metadata from text files, and
        returns a dictionary mapping file paths to their metadata.
        
        Args:
            memory_system: The Memory System instance to update
            
        Returns:
            Dict mapping file paths to their metadata
        """
        print(f"Indexing repository: {self.repo_path}")
        
        # Get all files matching patterns
        file_paths = self.scan_repository()
        print(f"Found {len(file_paths)} files matching patterns")
        
        # Process each file and create metadata
        file_metadata = {}
        skipped_files = 0
        
        for file_path in file_paths:
            # Skip files exceeding max size
            if os.path.getsize(file_path) > self.max_file_size:
                skipped_files += 1
                continue
                
            # Skip binary files
            if not self.is_text_file(file_path):
                skipped_files += 1
                continue
            
            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Create metadata
                metadata = self.create_metadata(file_path, content)
                file_metadata[file_path] = metadata
            except Exception as e:
                print(f"Error processing file {file_path}: {e}")
                skipped_files += 1
        
        print(f"Indexed {len(file_metadata)} files, skipped {skipped_files} files")
        return file_metadata
    
    def scan_repository(self) -> List[str]:
        """Scan the repository for files matching patterns.
        
        Returns:
            List of file paths that match include/exclude patterns
        """
        included_files = set()
        
        # Process include patterns
        for pattern in self.include_patterns:
            pattern_path = os.path.join(self.repo_path, pattern)
            matched_files = glob.glob(pattern_path, recursive=True)
            included_files.update(matched_files)
        
        # Process exclude patterns
        excluded_files = set()
        for pattern in self.exclude_patterns:
            pattern_path = os.path.join(self.repo_path, pattern)
            matched_files = glob.glob(pattern_path, recursive=True)
            excluded_files.update(matched_files)
        
        # Remove excluded files from included files
        result_files = list(included_files - excluded_files)
        
        # Filter out directories, keep only files
        return [f for f in result_files if os.path.isfile(f)]
    
    def is_text_file(self, file_path: str) -> bool:
        """Determine if a file is a text file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file is a text file, False otherwise
        """
        # Check by extension first
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in self.BINARY_EXTENSIONS:
            return False
        
        # Check content for binary data
        try:
            # Read first 1024 bytes
            with open(file_path, 'rb') as f:
                data = f.read(1024)
            
            # Check for null bytes and other binary signatures
            for pattern in self.BINARY_CONTENT_PATTERNS:
                if pattern in data:
                    return False
            
            # Try decoding as utf-8
            try:
                data.decode('utf-8')
                return True
            except UnicodeDecodeError:
                return False
        except Exception:
            # If there's any error, assume it's not a text file
            return False
