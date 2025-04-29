"""
Indexes Git repositories to extract file metadata.
Implements the contract defined in src/memory/indexers/git_repository_indexer_IDL.md.
"""

import os
import glob
import logging
from typing import Dict, List, Optional, Tuple

try:
    import git
    from git.exc import GitCommandError
except ImportError:
    logging.warning(
        "GitPython not found. Git-related metadata extraction will be disabled."
    )
    git = None  # type: ignore
    GitCommandError = Exception # type: ignore

# Assuming text_extraction utilities are available in the same directory or path
try:
    from . import text_extraction
except ImportError:
    logging.error("Failed to import text_extraction module. Metadata generation will be limited.")
    # Create a dummy module with dummy functions if import fails
    class DummyTextExtraction:
        def extract_document_summary(self, content: str, max_length: int = 300) -> str:
            return "Summary extraction unavailable."
        def extract_identifiers_by_language(self, content: str, lang: Optional[str] = None) -> List[str]:
            return ["Identifier extraction unavailable."]
    text_extraction = DummyTextExtraction() # type: ignore


# Default configuration values
DEFAULT_MAX_FILE_SIZE = 1 * 1024 * 1024  # 1 MB
DEFAULT_INCLUDE_PATTERNS = ["**/*.py"] # Example: only Python files by default
DEFAULT_EXCLUDE_PATTERNS: List[str] = []
BINARY_EXTENSIONS = {
    '.exe', '.dll', '.so', '.a', '.lib', '.dylib', '.o', '.obj',
    '.jar', '.class', '.war', '.ear',
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.iso', '.dmg',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.ico',
    '.mp3', '.wav', '.ogg', '.flac',
    '.mp4', '.avi', '.mov', '.wmv', '.mkv',
    '.db', '.sqlite', '.mdb',
    '.pyc', '.pyd',
    # Add more known binary extensions as needed
}
BINARY_SIGNATURES = [
    b'\x00', # Presence of null bytes often indicates binary
    b'PK\x03\x04', # ZIP
    b'\x89PNG', # PNG
    b'\xFF\xD8\xFF', # JPEG
    b'GIF8', # GIF
    b'%PDF', # PDF
]

class GitRepositoryIndexer:
    """
    Indexes files within a Git repository, extracts metadata, and updates a MemorySystem.
    """

    def __init__(self, repo_path: str):
        """
        Initializes the indexer for a specific repository path.

        Args:
            repo_path: Path to the local Git repository.

        Raises:
            ValueError: If the repo_path is not a valid directory or not a Git repository.
        """
        if not os.path.isdir(repo_path):
            raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")
        if git and not os.path.isdir(os.path.join(repo_path, ".git")):
             # Check for .git only if GitPython is available
            logging.warning(f"Path exists but may not be a Git repository (no .git directory): {repo_path}")
            # Allow proceeding but Git features will likely fail

        self.repo_path = os.path.abspath(repo_path)
        self.max_file_size: int = DEFAULT_MAX_FILE_SIZE
        self.include_patterns: List[str] = DEFAULT_INCLUDE_PATTERNS[:] # Copy default
        self.exclude_patterns: List[str] = DEFAULT_EXCLUDE_PATTERNS[:] # Copy default
        self._git_repo: Optional[git.Repo] = None

        if git:
            try:
                self._git_repo = git.Repo(self.repo_path)
                logging.info(f"GitRepositoryIndexer initialized for repo: {self.repo_path}")
            except Exception as e:
                logging.warning(f"Failed to initialize git.Repo for {self.repo_path}: {e}. Git features disabled.")
                self._git_repo = None
        else:
             logging.info(f"GitRepositoryIndexer initialized for path (GitPython unavailable): {self.repo_path}")


    def index_repository(self, memory_system: Any) -> Dict[str, str]:
        """
        Indexes the configured Git repository and updates the provided Memory System.

        Args:
            memory_system: The MemorySystem instance to update.

        Returns:
            A dictionary mapping absolute file paths of indexed files to their metadata strings.
        """
        logging.info(f"Starting repository indexing for: {self.repo_path}")
        file_metadata_index: Dict[str, str] = {}
        scanned_files = self.scan_repository()
        indexed_count = 0
        skipped_binary = 0
        skipped_size = 0
        error_count = 0

        logging.info(f"Found {len(scanned_files)} potential files matching patterns.")

        for file_path in scanned_files:
            try:
                # 1. Check file size
                file_size = os.path.getsize(file_path)
                if file_size > self.max_file_size:
                    logging.debug(f"Skipping large file ({file_size} bytes): {file_path}")
                    skipped_size += 1
                    continue

                # 2. Check if text file
                if not self.is_text_file(file_path):
                    logging.debug(f"Skipping binary file: {file_path}")
                    skipped_binary += 1
                    continue

                # 3. Read content
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception as read_err:
                    logging.warning(f"Could not read file {file_path}: {read_err}")
                    error_count += 1
                    continue # Skip to next file

                # 4. Create metadata
                metadata = self.create_metadata(file_path, content)
                file_metadata_index[file_path] = metadata
                indexed_count += 1
                logging.debug(f"Indexed file: {file_path}")

            except Exception as e:
                logging.error(f"Error processing file {file_path}: {e}", exc_info=True)
                error_count += 1

        logging.info(
            f"Indexing complete for {self.repo_path}. "
            f"Indexed: {indexed_count}, Skipped (Binary): {skipped_binary}, "
            f"Skipped (Size): {skipped_size}, Errors: {error_count}"
        )

        # 5. Update Memory System
        if file_metadata_index:
            try:
                memory_system.update_global_index(file_metadata_index)
                logging.info(f"Updated MemorySystem global index with {len(file_metadata_index)} entries.")
            except Exception as update_err:
                logging.error(f"Failed to update MemorySystem index: {update_err}", exc_info=True)
        else:
            logging.info("No new metadata generated to update MemorySystem index.")

        return file_metadata_index

    def scan_repository(self) -> List[str]:
        """
        Scans the repository directory for files matching include/exclude patterns.

        Returns:
            A list of absolute file paths matching the criteria.
        """
        included_files = set()
        excluded_files = set()

        for pattern in self.include_patterns:
            # Use os.path.join to create platform-independent paths
            full_pattern = os.path.join(self.repo_path, pattern)
            try:
                # Use glob with recursive=True to match '**'
                matched = glob.glob(full_pattern, recursive=True)
                # Filter only files (glob can return directories)
                included_files.update(f for f in matched if os.path.isfile(f))
            except Exception as e:
                logging.warning(f"Error during glob matching for include pattern '{pattern}': {e}")


        for pattern in self.exclude_patterns:
            full_pattern = os.path.join(self.repo_path, pattern)
            try:
                matched = glob.glob(full_pattern, recursive=True)
                # Add both files and potential directory matches for exclusion
                excluded_files.update(matched)
            except Exception as e:
                 logging.warning(f"Error during glob matching for exclude pattern '{pattern}': {e}")

        # Refine exclusion: if a directory is excluded, exclude all files within it
        final_excluded = set()
        for excluded_path in excluded_files:
            if os.path.isdir(excluded_path):
                # If it's a directory, find all files under it recursively
                for root, _, files in os.walk(excluded_path):
                    for name in files:
                        final_excluded.add(os.path.abspath(os.path.join(root, name)))
            elif os.path.isfile(excluded_path):
                 final_excluded.add(os.path.abspath(excluded_path))


        # Calculate the final set of files
        final_files = included_files - final_excluded
        logging.debug(f"Scan found {len(included_files)} included, {len(final_excluded)} excluded -> {len(final_files)} final files.")
        return sorted(list(final_files)) # Return sorted list

    def is_text_file(self, file_path: str) -> bool:
        """
        Determines if a file is likely a text file.

        Args:
            file_path: The absolute path to the file.

        Returns:
            True if the file is likely text, False otherwise.
        """
        # 1. Check by extension
        _, ext = os.path.splitext(file_path)
        if ext.lower() in BINARY_EXTENSIONS:
            return False

        # 2. Check content signature (first 1024 bytes)
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)

            # Check for known binary signatures
            for sig in BINARY_SIGNATURES:
                if sig in chunk:
                    return False

            # Try decoding as UTF-8 (common text encoding)
            try:
                chunk.decode('utf-8')
                return True # Decoded successfully, likely text
            except UnicodeDecodeError:
                # Failed UTF-8, try other common encodings if necessary, or assume binary
                try:
                    chunk.decode('latin-1') # Try another common one
                    return True
                except UnicodeDecodeError:
                    return False # Failed multiple decodings, likely binary
        except Exception as e:
            logging.warning(f"Could not read file for text check {file_path}: {e}")
            return False # Treat as binary if read fails

    def create_metadata(self, file_path: str, content: str) -> str:
        """
        Creates a metadata string for a given file and its content.

        Args:
            file_path: The absolute path to the file.
            content: The string content of the file.

        Returns:
            A multi-line string containing structured metadata.
        """
        metadata_lines = []
        try:
            relative_path = os.path.relpath(file_path, self.repo_path)
            filename = os.path.basename(file_path)
            _, extension = os.path.splitext(filename)

            metadata_lines.append(f"File: {relative_path}")
            metadata_lines.append(f"Filename: {filename}")
            metadata_lines.append(f"Extension: {extension}")

            try:
                size = os.path.getsize(file_path)
                metadata_lines.append(f"Size: {size} bytes")
            except OSError as e:
                metadata_lines.append(f"Size: Error getting size ({e})")

            # Text Extraction
            summary = text_extraction.extract_document_summary(content)
            metadata_lines.append(f"Summary: {summary}")

            lang = extension.lstrip('.').lower() # Simple language detection by extension
            identifiers = text_extraction.extract_identifiers_by_language(content, lang=lang)
            if identifiers:
                metadata_lines.append(f"Identifiers: {', '.join(identifiers)}")

            # Git Information (if GitPython available and repo initialized)
            if self._git_repo:
                try:
                    commits = list(self._git_repo.iter_commits(paths=file_path, max_count=1))
                    if commits:
                        last_commit = commits[0]
                        metadata_lines.append(f"Commit: {last_commit.hexsha}")
                        metadata_lines.append(f"Author: {last_commit.author.name}")
                        metadata_lines.append(f"Date: {last_commit.authored_datetime.isoformat()}")
                    else:
                        metadata_lines.append("Commit: No Git history found for this file.")
                except GitCommandError as git_err:
                     metadata_lines.append(f"Commit: Error retrieving Git info ({git_err})")
                except Exception as e:
                    metadata_lines.append(f"Commit: Error retrieving Git info ({type(e).__name__})")
            else:
                 metadata_lines.append("Commit: Git information unavailable (GitPython missing or repo init failed).")


        except Exception as e:
            logging.error(f"Error creating metadata for {file_path}: {e}", exc_info=True)
            metadata_lines.append(f"Metadata Generation Error: {e}")

        return "\n".join(metadata_lines)

    # --- Configuration Methods (Optional but good practice) ---
    def set_max_file_size(self, size_bytes: int):
        if size_bytes > 0:
            self.max_file_size = size_bytes
            logging.info(f"Set max file size to {size_bytes} bytes.")
        else:
            logging.warning("Invalid max_file_size provided, must be positive.")

    def set_include_patterns(self, patterns: List[str]):
        if isinstance(patterns, list):
            self.include_patterns = patterns
            logging.info(f"Set include patterns to: {patterns}")
        else:
            logging.warning("Invalid include_patterns provided, must be a list of strings.")

    def set_exclude_patterns(self, patterns: List[str]):
         if isinstance(patterns, list):
            self.exclude_patterns = patterns
            logging.info(f"Set exclude patterns to: {patterns}")
         else:
            logging.warning("Invalid exclude_patterns provided, must be a list of strings.")
