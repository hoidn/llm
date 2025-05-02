"""
AiderBridge: Acts as an MCP Client to interact with an external Aider MCP Server.

Refactored based on ADR 19.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List, Set

# Import system models
from src.system.models import TaskResult, TaskFailureError, TaskFailureReason, ContextGenerationInput, AssociativeMatchResult, MatchTuple

# Import MCP components
try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.types import TextContent
    from mcp.exceptions import MCPError, ConnectionClosed, TimeoutError, ConnectionRefusedError
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Define dummy classes/exceptions if mcp.py is not available
    StdioServerParameters = object # type: ignore
    ClientSession = object # type: ignore
    TextContent = object # type: ignore
    MCPError = ConnectionClosed = TimeoutError = ConnectionRefusedError = Exception # type: ignore
    # Dummy stdio_client context manager
    class DummyStdioClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return (None, None) # Dummy read/write streams
        async def __aexit__(self, exc_type, exc, tb): pass
    stdio_client = DummyStdioClient # type: ignore

# Import dependencies for context methods
from src.memory.memory_system import MemorySystem
from src.handler.file_access import FileAccessManager

logger = logging.getLogger(__name__)

# Helper function to create a standard FAILED TaskResult dictionary
def _create_failed_result_dict(reason: TaskFailureReason, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Creates a dictionary representing a FAILED TaskResult."""
    error_obj = TaskFailureError(type="TASK_FAILURE", reason=reason, message=message, details=details or {})
    task_result = TaskResult(status="FAILED", content=message, notes={"error": error_obj})
    # Use exclude_none=True to avoid sending null fields if not set
    return task_result.model_dump(exclude_none=True)


class AiderBridge:
    """
    MCP Client for interacting with an external Aider MCP Server.

    Implements the contract defined in src/aider_bridge/bridge_IDL.md (v2+).
    Uses mcp.py library for communication.
    """

    def __init__(
        self,
        memory_system: MemorySystem,
        file_access_manager: Optional[FileAccessManager],
        config: Dict[str, Any]
    ) -> None:
        """
        Initializes the Aider Bridge MCP Client.

        Args:
            memory_system: Instance of MemorySystem.
            file_access_manager: Instance of FileAccessManager.
            config: Configuration dictionary containing MCP connection details.
                    Expected keys for STDIO: 'mcp_stdio_command', 'mcp_stdio_args', 'mcp_stdio_env'.
        """
        if not MCP_AVAILABLE:
            logger.error("mcp.py library not found. AiderBridge cannot function.")
            # Optionally raise an error here depending on desired behavior
            # raise ImportError("mcp.py library is required for AiderBridge")

        self.memory_system = memory_system
        self.file_access_manager = file_access_manager
        self.config = config
        self._mcp_config = {
            "command": config.get("mcp_stdio_command"),
            "args": config.get("mcp_stdio_args", []),
            "env": config.get("mcp_stdio_env", {})
        }
        self._file_context: Set[str] = set()
        self._context_source: Optional[str] = None

        logger.info("AiderBridge (MCP Client) initialized.")
        logger.debug(f"AiderBridge MCP STDIO config: {self._mcp_config}")
        if not self._mcp_config.get("command"):
            logger.warning("AiderBridge initialized without 'mcp_stdio_command' in config. MCP calls will fail.")

    async def call_aider_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls a specific tool on the remote Aider MCP Server.

        Args:
            tool_name: The name of the MCP tool exposed by the Aider server (e.g., "aider_ai_code").
            params: Dictionary containing parameters required by the specific Aider MCP tool.

        Returns:
            A dictionary representing the TaskResult structure, derived from the Aider MCP server's response.
        """
        if not MCP_AVAILABLE:
            return _create_failed_result_dict("dependency_error", "mcp.py library not available.")
        if not self._mcp_config.get("command"):
            return _create_failed_result_dict("configuration_error", "Aider MCP server command not configured.")

        logger.debug(f"Calling Aider MCP tool '{tool_name}' with params: {params}")

        try:
            # Create StdioServerParameters
            server_params = StdioServerParameters(
                command=self._mcp_config["command"],
                args=self._mcp_config["args"],
                env=self._mcp_config["env"]
            )

            async with stdio_client(server_params) as (read_stream, write_stream):
                if read_stream is None or write_stream is None:
                     return _create_failed_result_dict("connection_error", "Failed to establish STDIO transport.")

                async with ClientSession(read_stream, write_stream) as session:
                    logger.debug("Initializing MCP session...")
                    await session.initialize()
                    logger.debug("MCP session initialized. Calling tool...")

                    mcp_response = await session.call_tool(name=tool_name, arguments=params)
                    logger.debug(f"Received MCP response: {mcp_response}")

                    # Process response
                    if not mcp_response or not isinstance(mcp_response, list) or not mcp_response[0]:
                        logger.error("Invalid or empty response received from MCP server.")
                        return _create_failed_result_dict("protocol_error", "Invalid or empty response from MCP server.")

                    # Assuming the first part of the response contains the main result
                    # Check if it's TextContent (adjust if other types are possible)
                    if not isinstance(mcp_response[0], TextContent):
                         logger.error(f"Unexpected response type from MCP server: {type(mcp_response[0])}")
                         return _create_failed_result_dict("protocol_error", f"Unexpected response type: {type(mcp_response[0])}")

                    response_text = mcp_response[0].text
                    logger.debug(f"Raw MCP response text: {response_text}")

                    try:
                        server_payload = json.loads(response_text)
                        logger.debug(f"Parsed MCP server payload: {server_payload}")
                    except json.JSONDecodeError as json_err:
                        logger.error(f"Failed to parse JSON response from MCP server: {json_err}")
                        logger.error(f"Invalid JSON string: {response_text}")
                        return _create_failed_result_dict("output_format_failure", f"Failed to parse JSON response: {json_err}", {"raw_response": response_text})

                    # Map server payload to TaskResult dictionary
                    # Check for explicit error reported by the server application
                    if server_payload.get("error"):
                        error_msg = server_payload["error"]
                        logger.warning(f"Aider MCP tool '{tool_name}' reported application error: {error_msg}")
                        # Include other potential fields in notes
                        notes = {k: v for k, v in server_payload.items() if k != 'error'}
                        return _create_failed_result_dict("tool_execution_error", error_msg, notes)

                    # Handle specific tool formats based on aider_MCP_server.md
                    if tool_name == "aider_ai_code":
                        success = server_payload.get("success", False)
                        diff_content = server_payload.get("diff", "")
                        if success:
                            logger.info(f"Aider MCP tool '{tool_name}' completed successfully.")
                            return TaskResult(status="COMPLETE", content=diff_content, notes={"success": True, "diff": diff_content}).model_dump(exclude_none=True)
                        else:
                            # If success is false but no explicit 'error' key, use diff as error message
                            error_msg = diff_content or f"Aider tool '{tool_name}' failed without specific error message."
                            logger.warning(f"Aider MCP tool '{tool_name}' failed: {error_msg}")
                            notes = {k: v for k, v in server_payload.items()} # Include all payload in notes
                            return _create_failed_result_dict("tool_execution_error", error_msg, notes)
                    elif tool_name == "list_models":
                        models = server_payload.get("models", [])
                        logger.info(f"Aider MCP tool '{tool_name}' listed {len(models)} models.")
                        # Return the list as JSON string in content, and raw list in notes
                        return TaskResult(status="COMPLETE", content=json.dumps(models), notes={"models": models}).model_dump(exclude_none=True)
                    else:
                        # Generic success handling for unknown tools
                        logger.info(f"Aider MCP tool '{tool_name}' returned generic payload.")
                        # Assume payload itself is the content if no standard fields found
                        content_str = json.dumps(server_payload)
                        return TaskResult(status="COMPLETE", content=content_str, notes=server_payload).model_dump(exclude_none=True)

        except (MCPError, ConnectionClosed, TimeoutError, ConnectionRefusedError) as mcp_err:
            logger.error(f"MCP communication error calling tool '{tool_name}': {mcp_err}")
            return _create_failed_result_dict("connection_error", f"MCP communication error: {mcp_err}")
        except ValueError as val_err: # Catch potential errors from StdioServerParameters or config issues
             logger.error(f"Configuration or parameter error calling tool '{tool_name}': {val_err}")
             return _create_failed_result_dict("configuration_error", f"Configuration error: {val_err}")
        except Exception as e:
            logger.exception(f"Unexpected error calling Aider MCP tool '{tool_name}': {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during MCP call: {e}")

    # --- Context Preparation Methods (Retained but role clarified) ---

    def set_file_context(self, file_paths: List[str], source: Optional[str] = "explicit_specification") -> Dict[str, Any]:
        """
        Sets the file context explicitly for subsequent *preparation* of Aider calls.
        Validates file existence and safety using FileAccessManager.

        Args:
            file_paths: List of file paths (relative or absolute).
            source: Optional string indicating the origin.

        Returns:
            Dictionary indicating status and file count.
        """
        if not self.file_access_manager:
            logger.warning("FileAccessManager not available in AiderBridge. Cannot validate paths.")
            # Store paths without validation if FAM is missing
            self._file_context = set(file_paths)
            self._context_source = source
            return {"status": "warning", "file_count": len(self._file_context), "context_source": source, "message": "FileAccessManager unavailable, paths stored without validation."}

        logger.debug(f"Setting file context from source '{source}' with paths: {file_paths}")
        valid_abs_paths: Set[str] = set()
        processed_count = 0
        skipped_nonexistent = 0
        skipped_unsafe = 0

        for path_str in file_paths: # Rename variable to avoid confusion
             processed_count += 1
             try:
                 # --- START FIX: Handle absolute vs relative ---
                 if os.path.isabs(path_str):
                     # If already absolute, normalize it directly
                     abs_path = os.path.abspath(path_str)
                     # Still need to check safety relative to base_path
                     if not self.file_access_manager._is_path_safe(abs_path):
                         logger.warning(f"Skipping unsafe absolute path: {path_str} (resolved to {abs_path})")
                         skipped_unsafe += 1
                         continue
                 else:
                     # If relative, resolve using FAM's method (which includes safety check)
                     abs_path = self.file_access_manager._resolve_path(path_str)
                     # Double-check safety (resolve_path might not raise on failure)
                     if not self.file_access_manager._is_path_safe(abs_path):
                         logger.warning(f"Skipping unsafe resolved path: {path_str} (resolved to {abs_path})")
                         skipped_unsafe += 1
                         continue
                 # --- END FIX ---

                 # Check existence using os.path
                 if not os.path.exists(abs_path):
                     logger.warning(f"Skipping non-existent path: {path_str} (resolved to {abs_path})")
                     skipped_nonexistent += 1
                     continue
                 # Check if it's a file
                 if not os.path.isfile(abs_path):
                     logger.warning(f"Skipping non-file path: {path_str} (resolved to {abs_path})")
                     skipped_nonexistent += 1 # Count as non-existent for simplicity
                     continue

                 valid_abs_paths.add(abs_path)
             except ValueError as e: # Catch errors from _resolve_path or safety checks
                 logger.warning(f"Skipping invalid path '{path_str}': {e}")
                 skipped_unsafe += 1
             except Exception as e:
                  logger.exception(f"Error processing path '{path_str}' in set_file_context: {e}")
                  skipped_unsafe += 1


        self._file_context = valid_abs_paths
        self._context_source = source
        logger.info(f"Set file context: {len(valid_abs_paths)} valid files added. Source: {source}. (Processed: {processed_count}, Skipped Non-existent: {skipped_nonexistent}, Skipped Unsafe: {skipped_unsafe})")

        status_msg = f"Added {len(valid_abs_paths)} files."
        if skipped_nonexistent > 0: status_msg += f" Skipped {skipped_nonexistent} non-existent/non-file." # Clarify message
        if skipped_unsafe > 0: status_msg += f" Skipped {skipped_unsafe} unsafe/invalid."

        return {"status": "success", "file_count": len(valid_abs_paths), "context_source": source, "message": status_msg}

    def get_file_context(self) -> Dict[str, Any]:
        """
        Retrieves the current file context stored by the bridge.

        Returns:
            Dictionary containing 'file_paths', 'file_count', and 'context_source'.
        """
        paths = sorted(list(self._file_context))
        return {
            "file_paths": paths,
            "file_count": len(paths),
            "context_source": self._context_source
        }

    def get_context_for_query(self, query: str) -> List[str]:
        """
        Determines relevant file context for a query using the MemorySystem.
        Updates internal state if relevant files are found.

        Args:
            query: The query string.

        Returns:
            List of relevant absolute file paths, or empty list on error/no match.
        """
        logger.debug(f"Getting context for query: '{query[:100]}...'")
        if not self.memory_system:
            logger.error("MemorySystem not available in AiderBridge. Cannot get context for query.")
            return []

        try:
            # Use ContextGenerationInput v5.0 structure
            context_input = ContextGenerationInput(query=query)
            memory_result: AssociativeMatchResult = self.memory_system.get_relevant_context_for(context_input)

            if memory_result.error:
                logger.error(f"MemorySystem returned error for query '{query}': {memory_result.error}")
                return []

            if not memory_result.matches:
                logger.info(f"No relevant files found by MemorySystem for query: '{query}'")
                return []

            # Extract paths from matches
            # Assume paths in MatchTuple are already absolute or resolvable by FAM
            relevant_paths = [match.path for match in memory_result.matches]
            logger.debug(f"MemorySystem returned {len(relevant_paths)} potential paths.")

            # Use set_file_context to validate and update internal state
            # Pass the paths found by memory system
            status_result = self.set_file_context(relevant_paths, source="associative_matching")

            # Return the validated paths stored internally
            return sorted(list(self._file_context))

        except Exception as e:
            logger.exception(f"Error getting context from MemorySystem for query '{query}': {e}")
            return []

    # --- Deprecated Methods (Removed) ---
    # - execute_code_edit
    # - start_interactive_session
    # - create_interactive_session
    # - create_automatic_handler
