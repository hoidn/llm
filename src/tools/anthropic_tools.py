"""
Implementation of Anthropic-specific editor tools.

These tools provide functionalities for viewing, creating, and modifying files,
mirroring the tools available with certain Anthropic models.

They rely on the FileAccessManager for safe file operations.
"""

import os
import logging
from typing import Optional, List, Union
from pydantic import BaseModel, Field, ValidationError, field_validator

# Assuming FileAccessManager is importable like this
from src.handler.file_access import FileAccessManager

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_FILE_SIZE = 100 * 1024 # 100 KB, same as FileAccessManager default

# --- Helper Function (Consider moving to a shared utility if used elsewhere) ---

def _normalize_path(base_path: str, relative_path: str) -> str:
    """
    Safely normalizes and resolves a path relative to a base path.

    Args:
        base_path: The absolute base directory.
        relative_path: The path provided by the user/LLM.

    Returns:
        The absolute, normalized path.

    Raises:
        ValueError: If the resolved path attempts to escape the base path
                    or contains potentially unsafe elements.
    """
    if not relative_path:
        raise ValueError("File path cannot be empty")

    # Ensure base_path is absolute and normalized
    abs_base_path = os.path.abspath(base_path)

    # Resolve the combined path
    combined_path = os.path.join(abs_base_path, relative_path)
    abs_resolved_path = os.path.abspath(combined_path)

    # Security Check: Ensure the resolved path is still within the base path
    if not abs_resolved_path.startswith(abs_base_path):
        logger.warning(f"Path traversal attempt detected: '{relative_path}' resolved outside base '{abs_base_path}'")
        raise ValueError("Invalid path: Access denied outside allowed directory.")

    # Additional checks (optional, depending on security needs)
    # e.g., disallow '..' even if it stays within base?
    # if '..' in relative_path.split(os.sep):
    #     raise ValueError("Invalid path: '..' components are not allowed.")

    return abs_resolved_path


# --- Pydantic Input Models ---

class ViewInput(BaseModel):
    file_path: str = Field(..., description="Path to the file or directory to view.")
    start_line: Optional[int] = Field(None, description="Optional 1-based start line number.", ge=1)
    end_line: Optional[int] = Field(None, description="Optional 1-based end line number.", ge=1)
    max_bytes: Optional[int] = Field(DEFAULT_MAX_FILE_SIZE, description="Maximum bytes to read.", gt=0)

    @field_validator('file_path')
    @classmethod
    def path_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("File path cannot be empty")
        return v

class StrReplaceInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to modify.")
    old_string: str = Field(..., description="The exact string to replace.")
    new_string: str = Field(..., description="The string to replace with.")
    count: int = Field(-1, description="Maximum number of replacements (-1 for all).")

    @field_validator('file_path')
    @classmethod
    def path_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("File path cannot be empty")
        return v

    @field_validator('old_string')
    @classmethod
    def old_string_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("Old string cannot be empty")
        return v

class CreateInput(BaseModel):
    file_path: str = Field(..., description="Path for the new file.")
    content: str = Field("", description="Content to write to the new file.")
    overwrite: bool = Field(False, description="Whether to overwrite if the file already exists.")

    @field_validator('file_path')
    @classmethod
    def path_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("File path cannot be empty")
        return v

class InsertInput(BaseModel):
    file_path: str = Field(..., description="Path to the file to modify.")
    content: str = Field(..., description="Content to insert.")
    position: Optional[int] = Field(None, description="0-based byte offset for insertion.", ge=0)
    line: Optional[int] = Field(None, description="1-based line number for insertion (alternative to position).", ge=1)
    after_line: bool = Field(False, description="If using 'line', insert after the specified line instead of before.")

    @field_validator('file_path')
    @classmethod
    def path_must_not_be_empty(cls, v):
        if not v:
            raise ValueError("File path cannot be empty")
        return v

    @field_validator('content')
    @classmethod
    def content_must_not_be_empty(cls, v):
        # Allow empty string insertion? Let's allow it for now.
        # if not v:
        #     raise ValueError("Content to insert cannot be empty")
        return v

# --- Tool Functions ---

def view(
    file_manager: FileAccessManager,
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    max_bytes: Optional[int] = DEFAULT_MAX_FILE_SIZE
) -> str:
    """
    Views the content of a file, optionally limited by line range or size.

    Args:
        file_manager: The FileAccessManager instance.
        file_path: Path to the file.
        start_line: Optional 1-based start line.
        end_line: Optional 1-based end line.
        max_bytes: Maximum bytes to read.

    Returns:
        The file content or an error message.
    """
    try:
        # Validate inputs using Pydantic model
        input_data = ViewInput(file_path=file_path, start_line=start_line, end_line=end_line, max_bytes=max_bytes)

        # Normalize path using FileAccessManager's base path
        abs_path = file_manager._resolve_path(input_data.file_path) # Use internal helper for consistency

        # Check path safety (redundant if _resolve_path does it, but good defense)
        if not file_manager._is_path_safe(abs_path):
             raise ValueError("Invalid path: Access denied.") # Should be caught by _resolve_path

        # Check existence
        if not os.path.exists(abs_path):
            return f"Error: File not found at {abs_path}"
        if not os.path.isfile(abs_path):
            return f"Error: Path is not a file: {abs_path}"

        # Check size limit before reading
        file_size = os.path.getsize(abs_path)
        read_limit = input_data.max_bytes if input_data.max_bytes is not None else DEFAULT_MAX_FILE_SIZE
        if file_size > read_limit:
            return f"Error: File too large ({file_size} bytes). View limit: {read_limit} bytes."

        # Read content using FileAccessManager
        content = file_manager.read_file(input_data.file_path, max_size=read_limit) # Use relative path for FAM

        if content is None:
            # This might happen if FAM encounters an error despite earlier checks
            return f"Error: Could not read file: {abs_path}"

        # Handle line range filtering
        if input_data.start_line is not None or input_data.end_line is not None:
            lines = content.splitlines(keepends=True)
            num_lines = len(lines)

            start_idx = (input_data.start_line - 1) if input_data.start_line is not None else 0
            end_idx = input_data.end_line if input_data.end_line is not None else num_lines

            if input_data.start_line is not None and (input_data.start_line < 1 or input_data.start_line > num_lines):
                 return f"Error: Start line out of range: {input_data.start_line} (File has {num_lines} lines)"
            if input_data.end_line is not None and (input_data.end_line < 1 or input_data.end_line > num_lines):
                 return f"Error: End line out of range: {input_data.end_line} (File has {num_lines} lines)"
            if start_idx >= end_idx:
                 return f"Error: Start line ({input_data.start_line or 1}) must be less than or equal to end line ({input_data.end_line or num_lines})"

            content = "".join(lines[start_idx:end_idx])

        return content

    except ValidationError as e:
        logger.warning(f"Input validation failed for 'view': {e}")
        return f"Error: Invalid input - {e}"
    except ValueError as e: # Catch path normalization errors
        logger.warning(f"Path validation failed for 'view': {e}")
        return f"Error: Invalid path: {e}"
    except Exception as e:
        logger.exception(f"Error during 'view' operation for path '{file_path}': {e}")
        return f"Error: An unexpected error occurred while viewing the file: {e}"


def str_replace(
    file_manager: FileAccessManager,
    file_path: str,
    old_string: str,
    new_string: str,
    count: int = -1
) -> str:
    """
    Replaces occurrences of a string in a file.

    Args:
        file_manager: The FileAccessManager instance.
        file_path: Path to the file.
        old_string: The exact string to replace.
        new_string: The string to replace with.
        count: Maximum number of replacements (-1 for all).

    Returns:
        A status message indicating success or failure.
    """
    try:
        # Validate inputs
        input_data = StrReplaceInput(file_path=file_path, old_string=old_string, new_string=new_string, count=count)

        # Normalize path
        abs_path = file_manager._resolve_path(input_data.file_path)
        if not file_manager._is_path_safe(abs_path):
             raise ValueError("Invalid path: Access denied.")

        # Read current content (use large max_size for replace)
        # Consider adding a specific max_size for safety?
        current_content = file_manager.read_file(input_data.file_path, max_size=None) # Read full file

        if current_content is None:
            return f"Error: File not found or could not be read: {abs_path}"

        # Perform replacement
        replace_count = input_data.count if input_data.count != -1 else None # None means replace all for str.replace
        if replace_count is not None:
             updated_content = current_content.replace(input_data.old_string, input_data.new_string, replace_count)
             actual_replaced = (len(current_content) - len(updated_content)) // (len(input_data.old_string) - len(input_data.new_string)) if len(input_data.old_string) != len(input_data.new_string) else current_content.count(input_data.old_string, 0, len(current_content)) # Estimate count
             # More accurate count for fixed count
             temp_content = current_content
             actual_replaced = 0
             start_index = 0
             for _ in range(replace_count):
                 index = temp_content.find(input_data.old_string, start_index)
                 if index == -1:
                     break
                 actual_replaced += 1
                 start_index = index + 1 # Move past the found occurrence

        else: # Replace all
             updated_content = current_content.replace(input_data.old_string, input_data.new_string)
             actual_replaced = current_content.count(input_data.old_string)


        if actual_replaced == 0:
            return "No matches found for replacement"

        # Write back using FileAccessManager (always overwrite for replace)
        success = file_manager.write_file(input_data.file_path, updated_content, overwrite=True)

        if success:
            return f"Successfully replaced {actual_replaced} occurrence(s)"
        else:
            return f"Error: Failed to write changes to file: {abs_path}"

    except ValidationError as e:
        logger.warning(f"Input validation failed for 'str_replace': {e}")
        return f"Error: Invalid input - {e}"
    except ValueError as e: # Catch path normalization errors
        logger.warning(f"Path validation failed for 'str_replace': {e}")
        return f"Error: Invalid path: {e}"
    except Exception as e:
        logger.exception(f"Error during 'str_replace' operation for path '{file_path}': {e}")
        return f"Error: Error processing file: {e}"


def create(
    file_manager: FileAccessManager,
    file_path: str,
    content: str = "",
    overwrite: bool = False
) -> str:
    """
    Creates a new file with the specified content.

    Args:
        file_manager: The FileAccessManager instance.
        file_path: Path for the new file.
        content: Content to write.
        overwrite: Whether to overwrite if the file exists.

    Returns:
        A status message indicating success or failure.
    """
    try:
        # Validate inputs
        input_data = CreateInput(file_path=file_path, content=content, overwrite=overwrite)

        # Normalize path
        abs_path = file_manager._resolve_path(input_data.file_path)
        if not file_manager._is_path_safe(abs_path):
             raise ValueError("Invalid path: Access denied.")

        # Check existence if not overwriting
        if not input_data.overwrite and os.path.exists(abs_path):
            return f"Error: File already exists at {abs_path}. Use overwrite=True to replace."

        # Create parent directories (FileAccessManager.write_file should handle this)
        # os.makedirs(os.path.dirname(abs_path), exist_ok=True) # FAM handles this

        # Write file using FileAccessManager
        success = file_manager.write_file(input_data.file_path, input_data.content, overwrite=input_data.overwrite)

        if success:
            action = "overwritten" if input_data.overwrite and os.path.exists(abs_path) else "created"
            return f"Successfully {action} file: {abs_path}"
        else:
            # FAM write_file logs errors, return a generic message
            return f"Error: Error creating file {abs_path}. Check logs for details."

    except ValidationError as e:
        logger.warning(f"Input validation failed for 'create': {e}")
        return f"Error: Invalid input - {e}"
    except ValueError as e: # Catch path normalization errors
        logger.warning(f"Path validation failed for 'create': {e}")
        return f"Error: Invalid path: {e}"
    except Exception as e:
        logger.exception(f"Error during 'create' operation for path '{file_path}': {e}")
        return f"Error: An unexpected error occurred while creating the file: {e}"


def insert(
    file_manager: FileAccessManager,
    file_path: str,
    content: str,
    position: Optional[int] = None,
    line: Optional[int] = None,
    after_line: bool = False
) -> str:
    """
    Inserts content into a file at a specific position or line number.

    Args:
        file_manager: The FileAccessManager instance.
        file_path: Path to the file.
        content: Content to insert.
        position: 0-based byte offset for insertion.
        line: 1-based line number for insertion (alternative to position).
        after_line: If using 'line', insert after the specified line.

    Returns:
        A status message indicating success or failure.
    """
    try:
        # Validate inputs
        input_data = InsertInput(file_path=file_path, content=content, position=position, line=line, after_line=after_line)

        # Check mutual exclusivity of position and line
        if input_data.position is not None and input_data.line is not None:
            return "Error: Cannot specify both position and line for insertion."
        if input_data.position is None and input_data.line is None:
            return "Error: Must specify either position or line for insertion."

        # Normalize path
        abs_path = file_manager._resolve_path(input_data.file_path)
        if not file_manager._is_path_safe(abs_path):
             raise ValueError("Invalid path: Access denied.")

        # Check file existence
        if not os.path.exists(abs_path):
            return f"Error: File not found at {abs_path}"
        if not os.path.isfile(abs_path):
            return f"Error: Path is not a file: {abs_path}"

        insert_pos: int = -1
        line_mode_description = ""

        if input_data.position is not None:
            # Validate position against file size
            file_size = os.path.getsize(abs_path)
            if input_data.position > file_size:
                return f"Error: Position {input_data.position} is out of bounds (max: {file_size})"
            insert_pos = input_data.position
            line_mode_description = f"at position {insert_pos}"
        else: # line is not None
            # Read content to determine line position
            current_content = file_manager.read_file(input_data.file_path, max_size=None)
            if current_content is None:
                return f"Error: Could not read file to determine line position: {abs_path}"

            lines = current_content.splitlines(keepends=True)
            num_lines = len(lines)

            target_line_1_based = input_data.line
            if target_line_1_based < 1 or target_line_1_based > num_lines + (1 if input_data.after_line else 0):
                 # Allow inserting after the last line
                 max_line = num_lines + 1 if input_data.after_line else num_lines
                 if target_line_1_based > max_line:
                     return f"Error: Line {target_line_1_based} is out of bounds (File has {num_lines} lines, max allowed: {max_line})"


            # Calculate byte position
            insert_pos = 0
            line_idx_0_based = target_line_1_based - 1

            if input_data.after_line:
                # Position after the target line
                if line_idx_0_based >= num_lines: # After last line
                    insert_pos = len(current_content)
                else:
                    for i in range(line_idx_0_based + 1):
                        insert_pos += len(lines[i])
                line_mode_description = f"after line {target_line_1_based}"
            else:
                # Position before the target line
                for i in range(line_idx_0_based):
                    insert_pos += len(lines[i])
                line_mode_description = f"before line {target_line_1_based}"

        # Ensure content ends with newline if inserting in line mode?
        # Anthropic spec doesn't explicitly say, but it's often desired.
        insert_content = input_data.content
        if input_data.line is not None and not insert_content.endswith('\n'):
             insert_content += '\n'
             logger.debug("Added newline to content for line-based insert.")


        # Perform insertion using FileAccessManager
        success = file_manager.insert_content(input_data.file_path, insert_content, insert_pos)

        if success:
            return f"Successfully inserted content {line_mode_description}"
        else:
            # FAM insert_content logs errors
            return f"Error: Error processing file {abs_path}. Check logs for details."

    except ValidationError as e:
        logger.warning(f"Input validation failed for 'insert': {e}")
        return f"Error: Invalid input - {e}"
    except ValueError as e: # Catch path normalization errors
        logger.warning(f"Path validation failed for 'insert': {e}")
        return f"Error: Invalid path: {e}"
    except Exception as e:
        logger.exception(f"Error during 'insert' operation for path '{file_path}': {e}")
        return f"Error: An unexpected error occurred while inserting content: {e}"


# --- Tool Specifications ---

ANTHROPIC_VIEW_SPEC = {
    "name": "anthropic_view",
    "description": "Views the content of a file, optionally limited by line range or size.",
    "input_schema": ViewInput.model_json_schema()
}

ANTHROPIC_STR_REPLACE_SPEC = {
    "name": "anthropic_str_replace",
    "description": "Replaces occurrences of a string in a file.",
    "input_schema": StrReplaceInput.model_json_schema()
}

ANTHROPIC_CREATE_SPEC = {
    "name": "anthropic_create",
    "description": "Creates a new file with the specified content.",
    "input_schema": CreateInput.model_json_schema()
}

ANTHROPIC_INSERT_SPEC = {
    "name": "anthropic_insert",
    "description": "Inserts content into a file at a specific position or line number.",
    "input_schema": InsertInput.model_json_schema()
}

# List of all tool specifications for easier import
ANTHROPIC_TOOLS = [
    ANTHROPIC_VIEW_SPEC,
    ANTHROPIC_CREATE_SPEC,
    ANTHROPIC_STR_REPLACE_SPEC,
    ANTHROPIC_INSERT_SPEC,
]
