"""
Provides functions for safely executing shell commands and parsing output,
based on the CommandExecutorFunctions IDL.
"""

import os
import shlex
import subprocess
from typing import Dict, Any, List, Optional

# Define a reasonable default timeout and output size limit
DEFAULT_TIMEOUT = 5  # seconds
MAX_OUTPUT_SIZE = 10 * 1024  # 10 KB

# Basic safety checks (can be expanded)
UNSAFE_COMMAND_PATTERNS = ["rm ", "sudo ", ">", "|", ";", "&", "`", "$("] # Example patterns

def execute_command_safely(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = DEFAULT_TIMEOUT
) -> Dict[str, Any]:
    """
    Executes a shell command safely with resource limits.

    Implements the contract from src/handler/command_executor_IDL.md.
    Depends on the Shell resource implicitly via 'subprocess'.

    Args:
        command: The command string to execute.
        cwd: Optional working directory. Defaults to current directory.
        timeout: Optional execution timeout in seconds. Defaults to 5.

    Returns:
        A dictionary containing:
            'success': bool - True if exit code is 0.
            'output': str - Captured stdout (truncated).
            'error': str - Captured stderr (truncated).
            'exit_code': int - The command's exit code, or None if execution failed.
    """
    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    result = {
        "success": False,
        "output": "",
        "error": "",
        "exit_code": None,
    }

    # Basic safety check
    for pattern in UNSAFE_COMMAND_PATTERNS:
        if pattern in command:
            result["error"] = f"UnsafeCommandDetected: Command contains potentially unsafe pattern '{pattern}'."
            return result

    try:
        # Use shlex.split for basic command parsing safety against injection
        # Note: This is not foolproof for complex shell syntax but handles simple cases.
        cmd_parts = shlex.split(command)

        process = subprocess.run(
            cmd_parts,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,  # Don't raise CalledProcessError, check exit code manually
            encoding='utf-8',
            errors='replace'
        )

        result["output"] = process.stdout[:MAX_OUTPUT_SIZE]
        result["error"] = process.stderr[:MAX_OUTPUT_SIZE]
        result["exit_code"] = process.returncode
        result["success"] = (process.returncode == 0)

    except subprocess.TimeoutExpired:
        result["error"] = f"TimeoutExpired: Command exceeded {timeout} seconds limit."
        # exit_code remains None
    except FileNotFoundError:
        # Often means the command itself wasn't found in PATH
        result["error"] = f"ExecutionException: Command not found: '{cmd_parts[0]}'."
        # exit_code remains None
    except Exception as e:
        # Catch other potential exceptions during execution
        result["error"] = f"ExecutionException: An unexpected error occurred: {e}"
        # exit_code remains None

    return result

def parse_file_paths_from_output(output: str) -> List[str]:
    """
    Parses file paths from command output, filtering for existing files.

    Implements the contract from src/handler/command_executor_IDL.md.
    Depends on the FileSystem resource implicitly via 'os.path'.

    Args:
        output: A string, typically stdout from a command, expected to
                contain file paths (one per line).

    Returns:
        A list of absolute paths to existing files found in the output.
    """
    existing_files = []
    if not output:
        return existing_files

    lines = output.strip().splitlines()
    for line in lines:
        potential_path = line.strip()
        if not potential_path:
            continue

        # Check if the path exists and is a file
        # Note: This uses the current working directory context unless
        # the path is already absolute. If paths are relative to the
        # command's cwd, that context might be needed.
        # For simplicity matching IDL, we check existence directly.
        absolute_path = os.path.abspath(potential_path)
        if os.path.isfile(absolute_path):
            existing_files.append(absolute_path)

    return existing_files
