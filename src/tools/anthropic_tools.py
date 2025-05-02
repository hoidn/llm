"""
Tools for Anthropic Claude editor integration.

This module provides functions for file system operations through 
Claude's native editor tools.
"""

import logging
import os
from typing import Optional

from pydantic import BaseModel, Field, ValidationError, validator

logger = logging.getLogger(__name__)

# Maximum read size (default from FileAccessManager)
DEFAULT_MAX_FILE_SIZE = 100 * 1024  # 100 KB

# Tool specification constants
ANTHROPIC_VIEW_SPEC = {
    "name": "anthropic:view",
    "description": "Views the content of a file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to view.",
            },
            "max_bytes": {
                "type": "integer",
                "description": "Optional maximum number of bytes to read.",
            },
        },
        "required": ["file_path"],
    },
}

ANTHROPIC_STR_REPLACE_SPEC = {
    "name": "anthropic:str_replace",
    "description": "Replaces text in a file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to modify.",
            },
            "old_string": {"type": "string", "description": "The text to replace."},
            "new_string": {
                "type": "string",
                "description": "The text to replace it with.",
            },
            "count": {
                "type": "integer",
                "description": "Number of replacements to make. Default is 1, specify -1 for all occurrences.",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    },
}

ANTHROPIC_CREATE_SPEC = {
    "name": "anthropic:create",
    "description": "Creates a new file with the specified content.",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to create.",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file.",
            },
        },
        "required": ["file_path", "content"],
    },
}

ANTHROPIC_INSERT_SPEC = {
    "name": "anthropic:insert",
    "description": "Inserts content at a specific position in a file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path to the file to modify.",
            },
            "position": {
                "type": "integer",
                "description": "The position (character offset) where to insert content.",
            },
            "content": {"type": "string", "description": "The content to insert."},
        },
        "required": ["file_path", "position", "content"],
    },
}

# Collection of all Anthropic tool specifications
ANTHROPIC_TOOLS = [
    ANTHROPIC_VIEW_SPEC,
    ANTHROPIC_STR_REPLACE_SPEC,
    ANTHROPIC_CREATE_SPEC,
    ANTHROPIC_INSERT_SPEC,
]

# Collection of all Anthropic tool names
ANTHROPIC_TOOL_NAMES = [spec["name"] for spec in ANTHROPIC_TOOLS]


def _normalize_path(file_path: str) -> str:
    """
    Normalizes a file path, ensuring it's an absolute path.

    Args:
        file_path: The file path to normalize.

    Returns:
        The normalized absolute path.

    Raises:
        ValueError: If the path is empty or appears unsafe.
    """
    if not file_path or not file_path.strip():
        raise ValueError("File path cannot be empty")

    # Convert to absolute path if it's relative
    norm_path = os.path.abspath(file_path)

    # Basic safety check - prevent paths with unusual patterns
    # This is a very basic check; a production system would need more thorough validation
    if (
        ".." in norm_path.split(os.sep)
        or norm_path.startswith("/dev/")
        or norm_path.startswith("/proc/")
    ):
        raise ValueError(f"Potentially unsafe path: {norm_path}")

    return norm_path


class ViewInput(BaseModel):
    """Input model for the view tool."""

    file_path: str = Field(..., description="The path to the file to view")
    max_bytes: Optional[int] = Field(
        None, description="Maximum number of bytes to read"
    )

    @validator("file_path")
    def validate_file_path(cls, v):
        if not v or not v.strip():
            raise ValueError("File path cannot be empty")
        return v


class StrReplaceInput(BaseModel):
    """Input model for the str_replace tool."""

    file_path: str = Field(..., description="The path to the file to modify")
    old_string: str = Field(..., description="The text to replace")
    new_string: str = Field(..., description="The text to replace it with")
    count: Optional[int] = Field(
        1,
        description="Number of replacements to make. Default is 1, specify -1 for all occurrences.",
    )

    @validator("file_path")
    def validate_file_path(cls, v):
        if not v or not v.strip():
            raise ValueError("File path cannot be empty")
        return v

    @validator("old_string")
    def validate_old_string(cls, v):
        if v == "":
            raise ValueError("Old string cannot be empty for replacement")
        return v


class CreateInput(BaseModel):
    """Input model for the create tool."""

    file_path: str = Field(..., description="The path to the file to create")
    content: str = Field(..., description="The content to write to the file")

    @validator("file_path")
    def validate_file_path(cls, v):
        if not v or not v.strip():
            raise ValueError("File path cannot be empty")
        return v


class InsertInput(BaseModel):
    """Input model for the insert tool."""

    file_path: str = Field(..., description="The path to the file to modify")
    position: int = Field(
        ..., description="The position (character offset) where to insert content"
    )
    content: str = Field(..., description="The content to insert")

    @validator("file_path")
    def validate_file_path(cls, v):
        if not v or not v.strip():
            raise ValueError("File path cannot be empty")
        return v

    @validator("position")
    def validate_position(cls, v):
        if v < 0:
            raise ValueError("Position cannot be negative")
        return v

    @validator("content")
    def validate_content(cls, v):
        if v == "":
            raise ValueError("Insert content cannot be empty")
        return v


def view(
    file_path: str,
    max_bytes: Optional[int] = None,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """
    Reads the content of a file, with optional range-based viewing.

    Args:
        file_path: The path to the file to read.
        max_bytes: Optional maximum number of bytes to read.
        start_line: Optional line number to start reading from (1-based indexing).
        end_line: Optional line number to end reading at (1-based indexing, inclusive).

    Returns:
        A string containing the file content or error message.
    """
    try:
        # Create input model for validation
        input_data = {"file_path": file_path}
        if max_bytes is not None:
            input_data["max_bytes"] = max_bytes

        # Validate input
        input_model = ViewInput(**input_data)

        # Normalize path
        try:
            normalized_path = _normalize_path(input_model.file_path)
        except ValueError as e:
            return f"Error: Invalid path: {e}"

        # Check if file exists
        if not os.path.exists(normalized_path):
            return f"Error: File not found: {normalized_path}"

        if not os.path.isfile(normalized_path):
            return f"Error: Not a file: {normalized_path}"

        # Check file size
        file_size = os.path.getsize(normalized_path)
        max_size = input_model.max_bytes or DEFAULT_MAX_FILE_SIZE

        if file_size > max_size:
            return f"Error: File too large: {file_size} bytes (limit: {max_size} bytes)"

        # Read file
        try:
            if start_line is not None or end_line is not None:
                # Line-based reading
                with open(
                    normalized_path, encoding="utf-8", errors="replace"
                ) as f:
                    all_lines = f.readlines()

                # Validate line ranges
                if start_line is not None and (
                    start_line < 1 or start_line > len(all_lines)
                ):
                    return f"Error: Start line out of range: {start_line} (file has {len(all_lines)} lines)"

                if end_line is not None and (end_line < 1 or end_line > len(all_lines)):
                    return f"Error: End line out of range: {end_line} (file has {len(all_lines)} lines)"

                # Apply defaults if needed
                actual_start = (start_line or 1) - 1  # Convert to 0-based indexing
                actual_end = end_line if end_line is not None else len(all_lines)

                # Ensure correct ordering
                if actual_start > actual_end - 1:
                    return f"Error: Start line ({start_line}) must be less than or equal to end line ({end_line})"

                # Join selected lines
                content = "".join(all_lines[actual_start:actual_end])
            else:
                # Full file reading
                with open(
                    normalized_path, encoding="utf-8", errors="replace"
                ) as f:
                    content = f.read()

            return content
        except Exception as e:
            return f"Error: Error reading file: {e}"

    except ValidationError as e:
        return f"Error: Invalid input: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in view tool: {e}")
        return f"Error: Unexpected error: {e}"


def str_replace(
    file_path: str, old_string: str, new_string: str, count: Optional[int] = 1
) -> str:
    """
    Replaces occurrences of a string in a file.

    Args:
        file_path: The path to the file to modify.
        old_string: The text to replace.
        new_string: The text to replace it with.
        count: Number of replacements to make. Default is 1, specify -1 for all occurrences.

    Returns:
        A string describing the result or error message.
    """
    try:
        # Check if old_string is empty
        if not old_string:
            return "Error: Old string cannot be empty for replacement"

        # Create input model for validation
        input_data = {
            "file_path": file_path,
            "old_string": old_string,
            "new_string": new_string,
        }
        if count is not None:
            input_data["count"] = count

        # Validate input
        input_model = StrReplaceInput(**input_data)

        # Normalize path
        try:
            normalized_path = _normalize_path(input_model.file_path)
        except ValueError as e:
            return f"Error: Invalid path: {e}"

        # Check if file exists
        if not os.path.exists(normalized_path):
            return f"Error: File not found: {normalized_path}"

        if not os.path.isfile(normalized_path):
            return f"Error: Not a file: {normalized_path}"

        # Read file
        try:
            with open(normalized_path, encoding="utf-8", errors="replace") as f:
                content = f.read()

            # Perform replacement
            effective_count = input_model.count if input_model.count is not None else 1
            new_content, replacements = content, 0

            if effective_count == -1:  # Replace all occurrences
                new_content = content.replace(
                    input_model.old_string, input_model.new_string
                )
                replacements = content.count(input_model.old_string)
            else:
                new_content = content.replace(
                    input_model.old_string, input_model.new_string, effective_count
                )
                replacements = min(
                    content.count(input_model.old_string), effective_count
                )

            # Write back if changes were made
            if replacements > 0:
                with open(normalized_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                return f"Successfully replaced {replacements} occurrence(s)"
            else:
                return "No matches found for replacement"

        except Exception as e:
            return f"Error: Error processing file: {e}"

    except ValidationError as e:
        return f"Error: Invalid input: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in str_replace tool: {e}")
        return f"Error: Unexpected error: {e}"


def create(file_path: str, content: str, overwrite: bool = False) -> str:
    """
    Creates a new file with the specified content.

    Args:
        file_path: The path to the file to create.
        content: The content to write to the file.
        overwrite: Whether to overwrite the file if it already exists.

    Returns:
        A string describing the result or error message.
    """
    try:
        # Create input model for validation
        input_data = {"file_path": file_path, "content": content}

        # Validate input
        input_model = CreateInput(**input_data)

        # Normalize path
        try:
            normalized_path = _normalize_path(input_model.file_path)
        except ValueError as e:
            return f"Error: Invalid path: {e}"

        # Check if file already exists and handle overwrite flag
        if os.path.exists(normalized_path):
            if not overwrite:
                return f"Error: File already exists: {normalized_path}. Use overwrite=True to replace it."
            # If overwrite is True, we'll continue and overwrite the file

        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(normalized_path)
        if parent_dir and not os.path.exists(parent_dir):
            try:
                os.makedirs(parent_dir, exist_ok=True)
            except Exception as e:
                return f"Error: Failed to create parent directory: {e}"

        # Create file
        try:
            mode = "w" if not os.path.exists(normalized_path) or overwrite else "x"
            with open(normalized_path, mode, encoding="utf-8") as f:
                f.write(input_model.content)

            action = (
                "Created"
                if not os.path.exists(normalized_path) or not overwrite
                else "Overwritten"
            )
            return f"Successfully {action.lower()} file: {normalized_path}"
        except Exception as e:
            return f"Error: Error creating file: {e}"

    except ValidationError as e:
        return f"Error: Invalid input: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in create tool: {e}")
        return f"Error: Unexpected error: {e}"


def insert(
    file_path: str,
    content: str,
    position: Optional[int] = None,
    line: Optional[int] = None,
    after_line: bool = False,
) -> str:
    """
    Inserts content at a specific position in a file.

    Args:
        file_path: The path to the file to modify.
        content: The content to insert.
        position: The character position (offset) where to insert content. Mutually exclusive with line.
        line: The line number where to insert content (1-based indexing). Mutually exclusive with position.
        after_line: If True and using line parameter, insert after the specified line instead of before it.

    Returns:
        A string describing the result or error message.
    """
    try:
        # Validate basic input data
        if position is not None and line is not None:
            return "Error: Cannot specify both position and line parameters"

        if position is None and line is None:
            return "Error: Must specify either position or line parameter"

        # Create input model for validation
        input_data = {
            "file_path": file_path,
            "content": content,
            "position": (
                position if position is not None else 0
            ),  # Temporary value if using line
        }

        # Validate file path and content through model
        # (We'll set the real position after line calculation if needed)
        input_model = InsertInput(**input_data)

        # Normalize path
        try:
            normalized_path = _normalize_path(input_model.file_path)
        except ValueError as e:
            return f"Error: Invalid path: {e}"

        # Check if file exists
        if not os.path.exists(normalized_path):
            return f"Error: File not found: {normalized_path}"

        if not os.path.isfile(normalized_path):
            return f"Error: Not a file: {normalized_path}"

        # Read file
        try:
            with open(normalized_path, encoding="utf-8", errors="replace") as f:
                if line is not None:
                    # Line-based approach
                    lines = f.readlines()

                    # Validate line number
                    if (
                        line < 1 or line > len(lines) + 1
                    ):  # +1 to allow appending at the end
                        return f"Error: Line {line} is out of bounds (file has {len(lines)} lines)"

                    if line == len(lines) + 1:
                        # Special case: append to end of file
                        position = len("".join(lines))
                    # Calculate character position from line number
                    elif after_line:
                        # Insert after the specified line
                        position = sum(len(lines[i]) for i in range(line))
                    else:
                        # Insert before the specified line
                        position = sum(len(lines[i]) for i in range(line - 1))

                    content_to_insert = input_model.content
                    # Ensure content ends with newline if inserting after line
                    if after_line and not content_to_insert.endswith("\n"):
                        content_to_insert += "\n"

                    # Reread as a single string to use the position-based logic
                    f.seek(0)
                    file_content = f.read()
                else:
                    # Position-based approach (as before)
                    file_content = f.read()
                    content_to_insert = input_model.content

            # Check position bounds for position-based insertion
            if position > len(file_content):
                return f"Error: Position {position} is out of bounds (max: {len(file_content)})"

            # Insert content
            new_content = (
                file_content[:position] + content_to_insert + file_content[position:]
            )

            # Write modified content
            with open(normalized_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            if line is not None:
                insert_mode = "after" if after_line else "before"
                return f"Successfully inserted content {insert_mode} line {line}"
            else:
                return f"Successfully inserted content at position {position}"

        except Exception as e:
            return f"Error: Error processing file: {e}"

    except ValidationError as e:
        return f"Error: Invalid input: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in insert tool: {e}")
        return f"Error: Unexpected error: {e}"
