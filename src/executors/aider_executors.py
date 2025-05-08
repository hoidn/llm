"""
Executor functions for Aider Direct Tools.

These functions wrap calls to the AiderBridge (MCP Client) to interact
with an external Aider MCP Server.
"""

import json
import logging
import asyncio # Added for async
from typing import Dict, Any, List, Optional

# Import the refactored AiderBridge
from src.aider_bridge.bridge import AiderBridge
# Import system models
from src.system.models import TaskResult, TaskFailureError, TaskFailureReason

logger = logging.getLogger(__name__)

# Helper function to create a standard FAILED TaskResult dictionary
def _create_failed_result_dict(reason: TaskFailureReason, message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Creates a dictionary representing a FAILED TaskResult."""
    error_obj = TaskFailureError(type="TASK_FAILURE", reason=reason, message=message, details=details or {})
    task_result = TaskResult(status="FAILED", content=message, notes={"error": error_obj})
    # Use exclude_none=True to avoid sending null fields if not set
    return task_result.model_dump(exclude_none=True)


class AiderExecutorFunctions:
    """
    Interface aggregating Aider Direct Tool executor functions.
    These functions are typically registered with a handler and invoked programmatically.
    They interact with the AiderBridge (MCP Client).
    """

    @staticmethod
    async def execute_aider_automatic(params: Dict[str, Any], aider_bridge: AiderBridge) -> Dict[str, Any]:
        logger.debug(f"Executor execute_aider_automatic received params: {params}") # Add this
        """
        Executor logic for the 'aider:automatic' Direct Tool.
        Calls the 'aider_ai_code' tool on the Aider MCP Server via the bridge.

        Args:
            params: Dictionary containing:
                - 'prompt': string (required) - The instruction for code changes.
                - 'file_context': string (optional) - JSON string array of explicit file paths.
                - 'model': string (optional) - Specific model override for Aider.
            aider_bridge: Instance of AiderBridge (MCP Client).

        Returns:
            A TaskResult dictionary from the AiderBridge call.
        """
        logger.debug(f"Executing aider:automatic with params: {params}")

        prompt = params.get("prompt")
        if not prompt:
            return _create_failed_result_dict("input_validation_failure", "Missing required parameter: 'prompt'")

        # --- FIX: Use the correct parameter key ---
        editable_files_param = params.get("relative_editable_files")
        relative_files: List[str] = []
        if editable_files_param:
            if isinstance(editable_files_param, list) and all(isinstance(f, str) for f in editable_files_param):
                # If it's already a list of strings, use it directly
                relative_files = editable_files_param
                logger.debug(f"Using provided list for relative_editable_files: {relative_files}")
            elif isinstance(editable_files_param, str):
                # If it's a string, try to parse it as JSON (less likely for Sexp calls, but keep for robustness)
                try:
                    parsed_files = json.loads(editable_files_param)
                    if not isinstance(parsed_files, list) or not all(isinstance(f, str) for f in parsed_files):
                        raise ValueError("relative_editable_files JSON string must decode to a list of strings.")
                    relative_files = parsed_files
                    logger.debug(f"Parsed relative_editable_files from JSON string: {relative_files}")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Failed to parse 'relative_editable_files' string: {e}. Input: '{editable_files_param}'")
                    return _create_failed_result_dict("input_validation_failure", f"Failed to parse 'relative_editable_files' string: {e}")
            else:
                logger.error(f"Invalid type for 'relative_editable_files': {type(editable_files_param)}. Expected list or JSON string.")
                return _create_failed_result_dict("input_validation_failure", f"Invalid type for 'relative_editable_files': {type(editable_files_param)}. Expected list or JSON string.")
        # --- END FIX ---

        model_override = params.get("model")

        # Construct parameters for the MCP server's 'aider_ai_code' tool
        # Referencing docs/librarydocs/aider_MCP_server.md
        mcp_params = {
            "ai_coding_prompt": prompt,
            "relative_editable_files": relative_files, # Assuming context files are editable
            "relative_readonly_files": [], # Always send empty list instead of None to avoid server-side TypeError
            "model": model_override # Pass None if not provided
        }

        try:
            logger.info(f"Calling AiderBridge for 'aider_ai_code' tool...")
            bridge_result_dict = await aider_bridge.call_aider_tool( # Store result
                tool_name="aider_ai_code",
                params=mcp_params
            )
            # --- Add logging here ---
            logger.debug(f"Executor received result from AiderBridge: {bridge_result_dict}")
            # --- End logging ---

            # --- Add logging before returning ---
            logger.debug(f"Executor execute_aider_automatic returning: {bridge_result_dict}")
            # --- End logging ---
            return bridge_result_dict # Return the result directly
        except Exception as e:
            logger.exception(f"Unexpected error calling AiderBridge in execute_aider_automatic: {e}")
            # --- Add logging before returning error ---
            error_result = _create_failed_result_dict("unexpected_error", f"Unexpected error during Aider execution: {e}")
            logger.debug(f"Executor execute_aider_automatic returning ERROR: {error_result}")
            # --- End logging ---
            return error_result


    @staticmethod
    async def execute_aider_interactive(params: Dict[str, Any], aider_bridge: AiderBridge) -> Dict[str, Any]:
        """
        Executor logic for the 'aider:interactive' Direct Tool.
        Currently maps to the 'aider_ai_code' tool on the Aider MCP Server via the bridge.

        Args:
            params: Dictionary containing:
                - 'query' or 'prompt': string (required) - The initial query/instruction.
                - 'file_context': string (optional) - JSON string array of explicit file paths.
                - 'model': string (optional) - Specific model override for Aider.
            aider_bridge: Instance of AiderBridge (MCP Client).

        Returns:
            A TaskResult dictionary from the AiderBridge call.
        """
        logger.debug(f"Executing aider:interactive with params: {params}")

        # Accept either 'query' or 'prompt' for flexibility
        prompt = params.get("query") or params.get("prompt")
        if not prompt:
            return _create_failed_result_dict("input_validation_failure", "Missing required parameter: 'query' or 'prompt'")

        file_context_param = params.get("file_context")
        relative_files: List[str] = []
        if file_context_param:
            if isinstance(file_context_param, list) and all(isinstance(f, str) for f in file_context_param):
                # If it's already a list of strings, use it directly
                relative_files = file_context_param
                logger.debug(f"Using provided list for file_context: {relative_files}")
            elif isinstance(file_context_param, str):
                # If it's a string, try to parse it as JSON
                try:
                    parsed_files = json.loads(file_context_param)
                    if not isinstance(parsed_files, list) or not all(isinstance(f, str) for f in parsed_files):
                        raise ValueError("file_context JSON string must decode to a list of strings.")
                    relative_files = parsed_files
                    logger.debug(f"Parsed file_context from JSON string: {relative_files}")
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Failed to parse 'file_context' string: {e}. Input: '{file_context_param}'")
                    return _create_failed_result_dict("input_validation_failure", f"Failed to parse 'file_context' string: {e}")
            else:
                logger.error(f"Invalid type for 'file_context': {type(file_context_param)}. Expected list or JSON string.")
                return _create_failed_result_dict("input_validation_failure", f"Invalid type for 'file_context': {type(file_context_param)}. Expected list or JSON string.")

        model_override = params.get("model")

        # Construct parameters for the MCP server's 'aider_ai_code' tool
        # Assuming interactive mode also uses aider_ai_code for now
        mcp_params = {
            "ai_coding_prompt": prompt,
            "relative_editable_files": relative_files,
            "relative_readonly_files": [], # Always send empty list instead of None to avoid server-side TypeError
            "model": model_override
        }

        try:
            logger.info(f"Calling AiderBridge for 'aider_ai_code' tool (interactive mode)...")
            # Using "aider_ai_code" tool name, adjust if server uses a different one for interactive
            result = await aider_bridge.call_aider_tool(
                tool_name="aider_ai_code",
                params=mcp_params
            )
            logger.debug(f"AiderBridge call returned: {result.get('status')}")
            return result
        except Exception as e:
            logger.exception(f"Unexpected error calling AiderBridge in execute_aider_interactive: {e}")
            return _create_failed_result_dict("unexpected_error", f"Unexpected error during Aider execution: {e}")
