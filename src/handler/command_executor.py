"""Secure command execution utilities."""
import subprocess
import os
import shlex
from typing import List, Dict, Optional, Any

# Maximum execution time in seconds
DEFAULT_TIMEOUT = 5

# Maximum output size in bytes
MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MB

def execute_command_safely(command: str, 
                          cwd: Optional[str] = None,
                          timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """Execute a command safely with resource limits.
    
    Args:
        command: Command to execute
        cwd: Working directory for command execution
        timeout: Maximum execution time in seconds
        
    Returns:
        Dictionary with execution results:
        {
            "success": bool,
            "output": str,
            "error": str,
            "exit_code": int
        }
    """
    try:
        # Parse the command to catch obvious injection attempts
        args = shlex.split(command)
        
        # Check for potential security issues
        if _is_potentially_unsafe(args):
            return {
                "success": False,
                "output": "",
                "error": "Command contains potentially unsafe operations",
                "exit_code": -1
            }
        
        # Execute the command with resource limits
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            cwd=cwd or os.getcwd(),
            timeout=timeout,
            check=False
        )
        
        # Limit output size
        output = result.stdout[:MAX_OUTPUT_SIZE]
        error = result.stderr[:MAX_OUTPUT_SIZE]
        
        return {
            "success": result.returncode == 0,
            "output": output,
            "error": error,
            "exit_code": result.returncode
        }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Command execution timed out after {timeout} seconds",
            "exit_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Error executing command: {str(e)}",
            "exit_code": -1
        }
        
def parse_file_paths_from_output(output: str) -> List[str]:
    """Parse file paths from command output.
    
    Args:
        output: Command output with one file path per line
        
    Returns:
        List of file paths
    """
    if not output:
        return []
        
    # Split by lines and filter empty lines
    lines = [line.strip() for line in output.splitlines()]
    paths = [line for line in lines if line]
    
    # Only return existing file paths
    return [path for path in paths if os.path.exists(path)]
    
def _is_potentially_unsafe(args: List[str]) -> bool:
    """Check if command arguments contain potentially unsafe operations.
    
    Args:
        args: Command arguments
        
    Returns:
        True if potentially unsafe, False otherwise
    """
    # Check for commands that could modify the system
    unsafe_commands = ['rm', 'mv', 'cp', 'chmod', 'chown', 'sudo', 'su']
    
    # Simple check for unsafe commands
    if args and args[0] in unsafe_commands:
        return True
        
    # Look for shell metacharacters that could be used for command chaining
    dangerous_chars = ['>', '<', '|', ';', '&&', '||']
    for arg in args:
        for char in dangerous_chars:
            if char in arg:
                return True
                
    return False
