"""
Provides functions for safely executing shell commands and parsing output,
based on the CommandExecutorFunctions IDL.
"""

import os
import shlex
import subprocess
import re
from typing import Dict, Any, List, Optional

# Define a reasonable default timeout and output size limit
DEFAULT_TIMEOUT = 5  # seconds
MAX_OUTPUT_SIZE = 10 * 1024  # 10 KB

# Basic safety checks (can be expanded)
UNSAFE_COMMAND_PATTERNS = ["rm ", "sudo ", ">", "|", ";", "&", "`", "$("] # Example patterns
# Safe list commands
SAFE_LIST_COMMANDS = ["ls", "dir", "find"]

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

def parse_file_paths_from_output(output: str, base_dir: Optional[str] = None) -> List[str]:
    """
    Parses file paths from command output, filtering for existing files.

    Implements the contract from src/handler/command_executor_IDL.md.
    Depends on the FileSystem resource implicitly via 'os.path'.

    Args:
        output: A string, typically stdout from a command, expected to
                contain file paths (one per line).
        base_dir: Optional base directory to resolve relative paths against.
                  If None, uses current working directory.

    Returns:
        A list of absolute paths to existing files found in the output.
    """
    existing_files = []
    if not output:
        return existing_files

    # Use provided base_dir or current working directory
    base_directory = base_dir or os.getcwd()
    
    # Split output into lines and process each line
    lines = output.strip().splitlines()
    for line in lines:
        potential_path = line.strip()
        if not potential_path:
            continue
            
        # Skip entries that are likely not file paths (e.g., column headers, permissions)
        # Common in ls -l output
        if potential_path.startswith('total ') or re.match(r'^[drwx-]{10}\s+', potential_path):
            continue
            
        # For ls -l style output, extract just the filename
        if re.match(r'^[drwx-]{10}\s+\d+\s+\w+\s+\w+\s+\d+\s+', potential_path):
            parts = potential_path.split()
            if len(parts) >= 8:  # Typical ls -l format has at least 8 parts
                # The filename is typically the last part or parts
                potential_path = ' '.join(parts[7:])
        
        # Handle paths with spaces that might be quoted
        if (potential_path.startswith('"') and potential_path.endswith('"')) or \
           (potential_path.startswith("'") and potential_path.endswith("'")):
            potential_path = potential_path[1:-1]
            
        # Resolve the path against the base directory
        if os.path.isabs(potential_path):
            absolute_path = potential_path
        else:
            absolute_path = os.path.abspath(os.path.join(base_directory, potential_path))
            
        # Check if the path exists and is a file
        if os.path.isfile(absolute_path):
            existing_files.append(absolute_path)

    return existing_files

def is_safe_list_command(command: str) -> bool:
    """
    Checks if a command is a safe file listing command.
    
    Args:
        command: The command string to check.
        
    Returns:
        True if the command is a safe listing command, False otherwise.
    """
    # Split the command to get the base command
    cmd_parts = shlex.split(command)
    if not cmd_parts:
        return False
        
    base_cmd = cmd_parts[0]
    
    # Check if the base command is in our safe list
    if base_cmd not in SAFE_LIST_COMMANDS:
        return False
        
    # Additional safety checks for specific commands
    if base_cmd == "find":
        # Ensure find command doesn't have -exec or similar dangerous flags
        dangerous_find_flags = ["-exec", "-delete", "-ok"]
        return not any(flag in cmd_parts for flag in dangerous_find_flags)
        
    # For ls and dir, we consider them generally safe
    return True
