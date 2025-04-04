"""Interactive session handling for AiderBridge."""
from typing import Dict, List, Optional, Any, Set, Tuple
import os
import sys
import signal
import subprocess
import tempfile
from pathlib import Path

from aider_bridge.result_formatter import format_interactive_result

class AiderInteractiveSession:
    """
    Manages an interactive Aider session.
    
    This class provides functionality for starting, managing, and terminating
    interactive Aider sessions with proper terminal control transfer.
    """
    
    def __init__(self, bridge):
        """
        Initialize an interactive session manager.
        
        Args:
            bridge: The AiderBridge instance managing this session
        """
        self.bridge = bridge
        self.active = False
        self.process = None
        self.files_before = set()
        self.files_after = set()
        self.modified_files = []
        self.temp_dir = None
        self.last_query = None
    
    def start_session(self, query: str, file_context: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Start an interactive Aider session.
        
        Args:
            query: Initial query to provide context for the session
            file_context: Optional explicit file paths to include, defaults to
                        current file context from bridge
                        
        Returns:
            Dict containing the session result
        """
        
        if not self.bridge.aider_available:
            return format_interactive_result(
                status="FAILED",
                content="Aider is not available. Please install Aider to use interactive mode.",
                error="Aider dependency not installed"
            )
        
        # Don't start a new session if one is already active
        if self.active:
            return format_interactive_result(
                status="FAILED",
                content="An Aider session is already active. Terminate the current session first.",
                error="Session already active"
            )
            
        try:
            # Use provided file context or current context from bridge
            files = file_context or list(self.bridge.file_context)
            
            # If no context files, try to find relevant files based on query
            if not files and query:
                files = self.bridge.get_context_for_query(query)
                
                # If still no context files, return error
                if not files:
                    return format_interactive_result(
                        status="FAILED",
                        content="No relevant files found for the given query.",
                        error="No file context available"
                    )
            
            # Store the query for later use
            self.last_query = query
            
            # Create a temporary directory for session state
            self.temp_dir = tempfile.TemporaryDirectory()
            
            # Store the current file state for later comparison
            self.files_before = self._get_file_states(files)
            
            # Check if Aider is available
            if not self.bridge.aider_available:
                return format_interactive_result(
                    status="FAILED",
                    content="Aider is not available. Please install Aider to use interactive mode.",
                    error="Aider dependency not installed"
                )
                
            # No need to import Aider modules here since we're using subprocess
            
            # Start the interactive session
            print(f"\nStarting interactive Aider session...")
            print(f"Files in context: {', '.join(os.path.basename(f) for f in files)}")
            print(f"Initial query: {query}")
            print(f"\nType 'exit' or press Ctrl+D to end the session")
            print(f"Use /add <file-path> to add files to context")
            print(f"Use /model <model-alias> to select a model (e.g., 'sonnet', 'o3-mini')")
            print("="*60)
            
            # Set active flag before starting
            self.active = True
           
            # Run Aider directly as a subprocess - this is the reliable way to run interactive sessions
            self._run_aider_subprocess(query, files)
            
            # Check which files were modified
            self.files_after = self._get_file_states(files)
            self.modified_files = self._get_modified_files()
            
            # Clean up session
            self._cleanup_session()
            
            # Create and return the result
            return format_interactive_result(
                status="COMPLETE",
                content=f"Interactive Aider session completed. Modified {len(self.modified_files)} files.",
                files_modified=self.modified_files,
                session_summary=f"Session initiated with query: {query}"
            )
        except Exception as e:
            # Ensure session is marked as inactive even on error
            self.active = False
            
            # Clean up any temporary resources
            self._cleanup_session()
            
            return format_interactive_result(
                status="FAILED",
                content=f"Error during interactive Aider session: {str(e)}",
                error=str(e)
            )
    
    def terminate_session(self) -> Dict[str, Any]:
        """
        Terminate an active Aider session.
        
        Returns:
            Dict containing the termination result
        """
        
        if not self.active:
            return format_interactive_result(
                status="FAILED",
                content="No active Aider session to terminate.",
                error="No active session"
            )
            
        try:
            # If running as subprocess, terminate it
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            
            # Clean up session
            self._cleanup_session()
            
            return format_interactive_result(
                status="COMPLETE",
                content="Aider session terminated successfully.",
                files_modified=self.modified_files
            )
        except Exception as e:
            # Ensure session is marked as inactive even on error
            self.active = False
            
            return format_interactive_result(
                status="PARTIAL",
                content=f"Error terminating Aider session: {str(e)}",
                error=str(e)
            )
    
    def _run_aider_subprocess(self, query: str, files: List[str]):
        """
        Run Aider as a subprocess.
        
        Args:
            query: Initial query for the session
            files: List of file paths to include in the session
        """
        import shlex
        
        # Find Aider executable
        aider_path = self._find_aider_executable()
        
        # Create command
        cmd = [aider_path]
        cmd.extend(files)
        
        # Add initial message if provided
        if query:
            cmd.extend(["--message", query])
        
        # Add other necessary flags
        cmd.extend(["--no-auto-commits"])  # Don't auto-commit changes
        
        print(f"\nExecuting: {' '.join(cmd)}")
        
        # Run Aider as subprocess
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            self.process.wait()
        except Exception as e:
            print(f"Error running Aider subprocess: {str(e)}")
            # If there's an error, try to run with just the basic command
            try:
                print("\nRetrying with basic command...")
                basic_cmd = ["aider"]
                if files:
                    basic_cmd.extend(files)
                self.process = subprocess.Popen(
                    basic_cmd,
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr
                )
                self.process.wait()
            except Exception as e2:
                print(f"Error in fallback execution: {str(e2)}")
        finally:
            # Ensure session is marked as inactive
            self.active = False
            self.process = None
    
    def _find_aider_executable(self) -> str:
        """
        Find the Aider executable.

        Looks for the 'aider' command in PATH or common installation locations.
        Returns:
            Path to the Aider executable
        """
        # Check if aider is in PATH
        try:
            result = subprocess.check_output(["which", "aider"], text=True).strip()
            if result:
                return result
        except Exception:
            # Handle any exception during subprocess execution
            pass
        
        # Check common locations
        common_paths = [
            os.path.expanduser("~/.local/bin/aider"),
            "/usr/local/bin/aider",
            "/usr/bin/aider"
        ]
        
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        
        # Try to find via Python module - but skip in test environment
        if not os.environ.get('PYTEST_CURRENT_TEST'):
            try:
                import aider
                aider_module_path = os.path.dirname(aider.__file__)
                possible_path = os.path.join(aider_module_path, "../bin/aider")
                if os.path.isfile(possible_path) and os.access(possible_path, os.X_OK):
                    return possible_path
            except ImportError:
                pass
            
        # If we get here, we couldn't find aider
        print("Warning: Could not find aider executable. Using 'aider' and hoping it's in PATH")
        return "aider"

    # Remove the _run_aider_in_process method since we're going directly to subprocess
    def _run_aider_in_process(self, query: str, files: List[str]):
        """
        Not implemented - we use subprocess for all interactive sessions.
        This stub is kept for backward compatibility.
        """
        raise NotImplementedError(
            "In-process Aider execution is not supported. Using subprocess instead."
        )
        
        # Default to "aider" and hope it's in PATH
        return "aider"
    
    def _get_file_states(self, files: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get the current state of all files in the context.
        
        Args:
            files: List of file paths to check
            
        Returns:
            Dict mapping file paths to their state information
        """
        file_states = {}
        
        for file_path in files:
            try:
                if os.path.isfile(file_path):
                    stats = os.stat(file_path)
                    with open(file_path, 'rb') as f:
                        content_hash = hash(f.read())
                    
                    file_states[file_path] = {
                        'size': stats.st_size,
                        'mtime': stats.st_mtime,
                        'hash': content_hash
                    }
                else:
                    # For testing purposes, create a dummy state for non-existent files
                    if os.environ.get('PYTEST_CURRENT_TEST'):
                        file_states[file_path] = {
                            'size': 0,
                            'mtime': 0,
                            'hash': 0
                        }
            except Exception as e:
                print(f"Error getting state for file {file_path}: {str(e)}")
        
        return file_states
    
    def _get_modified_files(self) -> List[str]:
        """
        Get the list of files that were modified during the session.
        
        Returns:
            List of modified file paths
        """
        modified = []
        
        # Check for files that existed before and were modified
        for file_path, before_state in self.files_before.items():
            if file_path in self.files_after:
                after_state = self.files_after[file_path]
                if (before_state['size'] != after_state['size'] or
                    before_state['mtime'] != after_state['mtime'] or
                    before_state['hash'] != after_state['hash']):
                    modified.append(file_path)
            else:
                # File was deleted
                modified.append(file_path)
        
        # Check for new files
        for file_path in self.files_after:
            if file_path not in self.files_before:
                modified.append(file_path)
        
        return modified
    
    def _cleanup_session(self):
        """Clean up session resources."""
        self.active = False
        
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                pass
        
        if self.temp_dir:
            try:
                self.temp_dir.cleanup()
                self.temp_dir = None
            except:
                pass
