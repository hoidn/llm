"""
AiderBridge: Acts as an MCP Client to interact with an external Aider MCP Server.

Refactored based on ADR 19.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, Optional, List, Set
import anyio # Add import for anyio.EndOfStream

# Import system models
# Assuming these paths are correct relative to your project structure
try:
    from src.system.models import TaskResult, TaskFailureError, TaskFailureReason, ContextGenerationInput, AssociativeMatchResult, MatchTuple, TaskFailureDetails
except ImportError as e:
    # Provide a more informative error if internal imports fail
    raise ImportError(f"Failed to import internal project modules: {e}. Ensure PYTHONPATH is set correctly or run from the project root.") from e


# Import MCP components
try:
    from mcp.client.stdio import stdio_client, StdioServerParameters
    from mcp.client.session import ClientSession
    from mcp.types import TextContent
    # --- Corrected exception import path ---
    # McpError is exported at the top level
    from mcp import McpError
    # ConnectionClosed, TimeoutError, ConnectionRefusedError are NOT defined in mcp
    # We will use standard library / asyncio exceptions instead.

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Define dummy classes/exceptions if mcp.py is not available
    StdioServerParameters = object # type: ignore
    ClientSession = object # type: ignore
    TextContent = object # type: ignore
    # Define dummy McpError based on a generic Exception
    McpError = Exception # type: ignore
    # Dummy stdio_client context manager
    class DummyStdioClient:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return (None, None) # Dummy read/write streams
        async def __aexit__(self, exc_type, exc, tb): pass
    stdio_client = DummyStdioClient # type: ignore

# Import dependencies for context methods
# Assuming these paths are correct relative to your project structure
try:
    from src.memory.memory_system import MemorySystem
    from src.handler.file_access import FileAccessManager
except ImportError as e:
     raise ImportError(f"Failed to import internal project modules: {e}. Ensure PYTHONPATH is set correctly or run from the project root.") from e


logger = logging.getLogger(__name__)

# Helper function to create a standard FAILED TaskResult dictionary
def _create_failed_result_dict(
    reason: TaskFailureReason,
    message: str,
    details_dict: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Creates a dictionary representing a FAILED TaskResult."""
    details_obj = None
    if details_dict:
        details_obj = TaskFailureDetails(notes=details_dict)

    error_obj = TaskFailureError(
        type="TASK_FAILURE",
        reason=reason,
        message=message,
        details=details_obj
    )
    task_result = TaskResult(
        status="FAILED",
        content=message,
        notes={"error": error_obj}
    )
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
            config: Configuration dictionary. Can contain MCP connection details
                    under keys 'mcp_stdio_command', 'mcp_stdio_args', 'mcp_stdio_env'.
                    If keys are missing, falls back to environment variables:
                    MCP_STDIO_COMMAND, MCP_STDIO_ARGS (JSON list), MCP_STDIO_ENV (JSON dict).
        """
        if not MCP_AVAILABLE:
            logger.error("mcp.py library not found or failed to import components. AiderBridge cannot function.")
            # Consider raising ImportError here if MCP is strictly required
            # raise ImportError("mcp.py library and its components are required for AiderBridge")

        self.memory_system = memory_system
        self.file_access_manager = file_access_manager
        self.config = config
        self._file_context: Set[str] = set()
        self._context_source: Optional[str] = None

        # --- Resolve MCP STDIO Configuration ---
        resolved_config: Dict[str, Any] = {}
        config_sources: Dict[str, str] = {}  # Track where each value came from

        # 1. Command
        cmd_from_config = config.get("mcp_stdio_command")
        if cmd_from_config:
            resolved_config["command"] = cmd_from_config
            config_sources["command"] = "config_dict"
        else:
            cmd_from_env = os.environ.get("MCP_STDIO_COMMAND")
            if cmd_from_env:
                resolved_config["command"] = cmd_from_env
                config_sources["command"] = "env_var"
            else:
                resolved_config["command"] = None  # Mark as unresolved
                config_sources["command"] = "not_found"

        # 2. Arguments
        args_from_config = config.get("mcp_stdio_args")
        if args_from_config is not None:  # Allow empty list from config
            if isinstance(args_from_config, list):
                resolved_config["args"] = args_from_config
                config_sources["args"] = "config_dict"
            else:
                logger.warning("Value for 'mcp_stdio_args' in config dict is not a list. Ignoring.")
                resolved_config["args"] = None  # Treat as unresolved if type is wrong
                config_sources["args"] = "config_invalid_type"
        else:
            args_from_env_str = os.environ.get("MCP_STDIO_ARGS")
            if args_from_env_str:
                try:
                    parsed_args = json.loads(args_from_env_str)
                    if isinstance(parsed_args, list):
                        resolved_config["args"] = parsed_args
                        config_sources["args"] = "env_var"
                    else:
                        logger.warning(f"MCP_STDIO_ARGS environment variable is not a valid JSON list: {args_from_env_str}")
                        resolved_config["args"] = None
                        config_sources["args"] = "env_var_invalid_json"
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse MCP_STDIO_ARGS environment variable as JSON list: {args_from_env_str}")
                    resolved_config["args"] = None
                    config_sources["args"] = "env_var_invalid_json"
            else:
                resolved_config["args"] = None  # Mark as unresolved
                config_sources["args"] = "not_found"
        # Default to empty list if unresolved
        if resolved_config.get("args") is None:
            resolved_config["args"] = []

        # 3. Environment Variables for Server
        env_from_config = config.get("mcp_stdio_env")
        if env_from_config is not None:  # Allow empty dict from config
            if isinstance(env_from_config, dict):
                resolved_config["env"] = env_from_config
                config_sources["env"] = "config_dict"
            else:
                logger.warning("Value for 'mcp_stdio_env' in config dict is not a dictionary. Ignoring.")
                resolved_config["env"] = None  # Treat as unresolved if type is wrong
                config_sources["env"] = "config_invalid_type"
        else:
            env_from_env_str = os.environ.get("MCP_STDIO_ENV")
            if env_from_env_str:
                try:
                    parsed_env = json.loads(env_from_env_str)
                    if isinstance(parsed_env, dict):
                        resolved_config["env"] = parsed_env
                        config_sources["env"] = "env_var"
                    else:
                        logger.warning(f"MCP_STDIO_ENV environment variable is not a valid JSON dictionary: {env_from_env_str}")
                        resolved_config["env"] = None
                        config_sources["env"] = "env_var_invalid_json"
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse MCP_STDIO_ENV environment variable as JSON dictionary: {env_from_env_str}")
                    resolved_config["env"] = None
                    config_sources["env"] = "env_var_invalid_json"
            else:
                resolved_config["env"] = None  # Mark as unresolved
                config_sources["env"] = "not_found"
        # Default to empty dict if unresolved
        if resolved_config.get("env") is None:
            resolved_config["env"] = {}

        # Store the final resolved config
        self._mcp_config = resolved_config

        # Log final config and sources
        logger.info("AiderBridge (MCP Client) initialized.")
        logger.info(f"  MCP Command Source: {config_sources.get('command', 'unknown')}")
        logger.info(f"  MCP Args Source:    {config_sources.get('args', 'unknown')}")
        logger.info(f"  MCP Env Source:     {config_sources.get('env', 'unknown')}")
        # Log resolved values carefully, masking sensitive info if necessary in real code
        logger.debug(f"  Resolved MCP Command: {self._mcp_config['command']}")
        logger.debug(f"  Resolved MCP Args:    {self._mcp_config['args']}")
        logger.debug(f"  Resolved MCP Env Keys: {list(self._mcp_config['env'].keys())}")  # Log only keys

        if not self._mcp_config.get("command"):
            logger.warning("AiderBridge initialized without 'mcp_stdio_command' from config or environment. MCP calls will fail.")

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
        logger.debug(f"Attempting MCP connection with config: {self._mcp_config}") # Log connection config

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

                    mcp_response_wrapper = await session.call_tool(name=tool_name, arguments=params) # Rename variable

                    # --- START FIX: Handle CallToolResult Wrapper ---
                    # Log the raw wrapper object received
                    logger.debug(f"Raw MCP response wrapper received: Type={type(mcp_response_wrapper)}, Value={mcp_response_wrapper!r}")

                    # Check if it's the expected wrapper type using hasattr for robustness
                    if not hasattr(mcp_response_wrapper, 'content') or not hasattr(mcp_response_wrapper, 'isError'):
                        logger.error(f"Invalid response wrapper type received. Expected object with 'content' and 'isError' attributes, got: {type(mcp_response_wrapper)}")
                        details = {"raw_response_type": str(type(mcp_response_wrapper)), "raw_response_value": repr(mcp_response_wrapper)}
                        return _create_failed_result_dict("protocol_error", f"Invalid response wrapper type from MCP server: {type(mcp_response_wrapper)}", details_dict=details)

                    # Check if the wrapper indicates an error
                    if getattr(mcp_response_wrapper, 'isError', False):
                         logger.error(f"MCP response wrapper indicates an error. isError=True. Value: {mcp_response_wrapper!r}")
                         error_content = getattr(mcp_response_wrapper, 'content', ["Unknown error content"])
                         details = {"raw_response_value": repr(mcp_response_wrapper)}
                         return _create_failed_result_dict("protocol_error", f"MCP response wrapper indicates error: {error_content}", details_dict=details)

                    # Extract the actual content list from the wrapper
                    mcp_response_content_list = getattr(mcp_response_wrapper, 'content', None)

                    # Now perform the original checks on the extracted content list
                    # Check 1: Is the extracted content a list?
                    if not isinstance(mcp_response_content_list, list):
                        logger.error(f"Invalid 'content' type inside wrapper. Expected list, got: {type(mcp_response_content_list)}. Wrapper: {mcp_response_wrapper!r}")
                        details = {"raw_response_type": str(type(mcp_response_content_list)), "raw_response_value": repr(mcp_response_wrapper)}
                        return _create_failed_result_dict("protocol_error", f"Invalid 'content' type inside wrapper: {type(mcp_response_content_list)}", details_dict=details)

                    # Check 2: Is the list empty?
                    if not mcp_response_content_list:
                        logger.error(f"Empty 'content' list received inside wrapper. Wrapper: {mcp_response_wrapper!r}")
                        details = {"raw_response_value": repr(mcp_response_wrapper)}
                        return _create_failed_result_dict("protocol_error", "Empty 'content' list from MCP server.", details_dict=details)

                    # Check 3: Is the first element None?
                    first_element = mcp_response_content_list[0]
                    if first_element is None:
                         logger.error(f"First element in 'content' list is None. Wrapper: {mcp_response_wrapper!r}")
                         details = {"raw_response_value": repr(mcp_response_wrapper)}
                         return _create_failed_result_dict("protocol_error", "First element in 'content' list is None.", details_dict=details)

                    # Check 4: Is the first element TextContent?
                    # For testing compatibility, check if the object has a 'text' attribute instead of strict type checking
                    if not hasattr(first_element, 'text'):
                         logger.error(f"Unexpected element type in 'content' list: {type(first_element)}. Expected object with 'text' attribute. Wrapper: {mcp_response_wrapper!r}")
                         details = {"raw_response_type": str(type(first_element)), "raw_response_value": repr(mcp_response_wrapper)}
                         return _create_failed_result_dict("protocol_error", f"Unexpected response type in list: {type(first_element)}", details_dict=details)
                    # --- END FIX: Handle CallToolResult Wrapper ---

                    # If all checks pass, proceed with parsing TextContent
                    response_text = first_element.text # Get text from the first element
                    logger.debug(f"Raw MCP response text from TextContent: {response_text!r}")

                    try:
                        server_payload = json.loads(response_text)
                        logger.debug(f"Parsed MCP server payload: {server_payload}")
                    except json.JSONDecodeError as json_err:
                        logger.error(f"Failed to parse JSON response from MCP server: {json_err}")
                        logger.error(f"Invalid JSON string received: {response_text!r}") # Log problematic text
                        details = {"raw_response_text": response_text} # Pass raw text in details
                        return _create_failed_result_dict("output_format_failure", f"Failed to parse JSON response: {json_err}", details_dict=details)

                    # Map server payload to TaskResult dictionary
                    # Check for explicit error reported by the server application
                    if server_payload.get("error"):
                        error_msg = server_payload["error"]
                        logger.warning(f"Aider MCP tool '{tool_name}' reported application error: {error_msg}")
                        # Include other potential fields in notes (passed as details_dict)
                        notes_for_details = {k: v for k, v in server_payload.items() if k != 'error'}
                        return _create_failed_result_dict("tool_execution_error", error_msg, details_dict=notes_for_details)

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
                            # Include all payload in notes (passed as details_dict)
                            notes_for_details = {k: v for k, v in server_payload.items()}
                            # Use the actual error from the server payload as the message
                            return _create_failed_result_dict("tool_execution_error", error_msg, details_dict=notes_for_details)
                    elif tool_name == "list_models":
                        models = server_payload.get("models", [])
                        logger.info(f"Aider MCP tool '{tool_name}' listed {len(models)} models.")
                        # Return the list as JSON string in content, and raw list in notes
                        return TaskResult(status="COMPLETE", content=json.dumps(models), notes={"models": models}).model_dump(exclude_none=True)
                    else:
                        # Generic success handling
                        logger.info(f"Aider MCP tool '{tool_name}' returned generic payload.")
                        # Assume payload itself is the content if no standard fields found
                        content_str = json.dumps(server_payload)
                        return TaskResult(status="COMPLETE", content=content_str, notes=server_payload).model_dump(exclude_none=True)

        # Catch the specific MCP protocol error
        except McpError as mcp_err:
             logger.error(f"MCP protocol error calling tool '{tool_name}': {mcp_err}")
             # Extract details if available from the McpError structure
             details = None
             if hasattr(mcp_err, 'error') and hasattr(mcp_err.error, 'data'):
                 details = mcp_err.error.data # type: ignore
             return _create_failed_result_dict("protocol_error", f"MCP protocol error: {mcp_err}", details_dict=details)

        # Catch standard connection errors
        except ConnectionRefusedError as conn_refused_err:
             logger.error(f"Connection refused calling tool '{tool_name}': {conn_refused_err}")
             return _create_failed_result_dict("connection_error", f"Connection refused: {conn_refused_err}")
        # Catch other relevant connection closed/aborted errors (adjust based on transport library)
        except (ConnectionResetError, ConnectionAbortedError, anyio.EndOfStream) as conn_closed_err:
             logger.error(f"Connection closed unexpectedly calling tool '{tool_name}': {conn_closed_err}")
             return _create_failed_result_dict("connection_error", f"Connection closed unexpectedly: {conn_closed_err}")
        # Catch standard timeout error (likely asyncio's)
        except asyncio.TimeoutError as timeout_err:
             logger.error(f"Timeout error calling tool '{tool_name}': {timeout_err}")
             # Use a more specific reason if available, e.g., 'execution_timeout'
             return _create_failed_result_dict("execution_timeout", f"MCP communication error: {timeout_err}")

        # Catch potential errors from StdioServerParameters or config issues
        except ValueError as val_err:
             logger.error(f"Configuration or parameter error calling tool '{tool_name}': {val_err}")
             return _create_failed_result_dict("configuration_error", f"Configuration error: {val_err}")

        # Catch any other unexpected errors
        except Exception as e:
            logger.exception(f"Unexpected error calling Aider MCP tool '{tool_name}': {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during MCP call: {e}")

    # --- Context Preparation Methods ---

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
            self._file_context = set(file_paths)
            self._context_source = source
            return {"status": "warning", "file_count": len(self._file_context), "context_source": source, "message": "FileAccessManager unavailable, paths stored without validation."}

        logger.debug(f"Setting file context from source '{source}' with paths: {file_paths}")
        valid_abs_paths: Set[str] = set()
        processed_count = 0
        skipped_nonexistent = 0
        skipped_unsafe = 0

        for path_str in file_paths:
             processed_count += 1
             try:
                 if os.path.isabs(path_str):
                     abs_path = os.path.abspath(path_str)
                     if not self.file_access_manager._is_path_safe(abs_path): # type: ignore [reportPrivateUsage]
                         logger.warning(f"Skipping unsafe absolute path: {path_str} (resolved to {abs_path})")
                         skipped_unsafe += 1
                         continue
                 else:
                     abs_path = self.file_access_manager._resolve_path(path_str) # type: ignore [reportPrivateUsage]
                     if not self.file_access_manager._is_path_safe(abs_path): # type: ignore [reportPrivateUsage]
                         logger.warning(f"Skipping unsafe resolved path: {path_str} (resolved to {abs_path})")
                         skipped_unsafe += 1
                         continue

                 if not os.path.exists(abs_path):
                     logger.warning(f"Skipping non-existent path: {path_str} (resolved to {abs_path})")
                     skipped_nonexistent += 1
                     continue
                 if not os.path.isfile(abs_path):
                     logger.warning(f"Skipping non-file path: {path_str} (resolved to {abs_path})")
                     skipped_nonexistent += 1
                     continue

                 valid_abs_paths.add(abs_path)
             except ValueError as e:
                 logger.warning(f"Skipping invalid path '{path_str}': {e}")
                 skipped_unsafe += 1
             except Exception as e:
                  logger.exception(f"Error processing path '{path_str}' in set_file_context: {e}")
                  skipped_unsafe += 1

        self._file_context = valid_abs_paths
        self._context_source = source
        logger.info(f"Set file context: {len(valid_abs_paths)} valid files added. Source: {source}. (Processed: {processed_count}, Skipped Non-existent: {skipped_nonexistent}, Skipped Unsafe: {skipped_unsafe})")

        status_msg = f"Added {len(valid_abs_paths)} files."
        if skipped_nonexistent > 0: status_msg += f" Skipped {skipped_nonexistent} non-existent/non-file."
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
            context_input = ContextGenerationInput(query=query)
            memory_result: AssociativeMatchResult = self.memory_system.get_relevant_context_for(context_input)

            if memory_result.error:
                logger.error(f"MemorySystem returned error for query '{query}': {memory_result.error}")
                return []

            if not memory_result.matches:
                logger.info(f"No relevant files found by MemorySystem for query: '{query}'")
                return []

            relevant_paths = [match.path for match in memory_result.matches]
            logger.debug(f"MemorySystem returned {len(relevant_paths)} potential paths.")

            # Use set_file_context to validate and update internal state
            self.set_file_context(relevant_paths, source="associative_matching")

            # Return the validated paths stored internally
            return sorted(list(self._file_context))

        except Exception as e:
            logger.exception(f"Error getting context from MemorySystem for query '{query}': {e}")
            return []
