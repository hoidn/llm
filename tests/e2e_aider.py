import pytest
import os
import sys
import subprocess
import time
import json
import shutil
import logging
from unittest.mock import patch

# Ensure project root is in path (adjust relative path as needed)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC_PATH = os.path.join(PROJECT_ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

# Import your Application class
try:
    from src.main import Application
    from src.system.models import TaskResult
except ImportError as e:
    pytest.skip(f"Skipping E2E Aider tests: Failed to import project components - {e}", allow_module_level=True)

# --- Configuration ---
# Command to start the aider-mcp-server (adjust if needed)
# Assumes aider_mcp_server is runnable as a module
AIDER_MCP_SERVER_COMMAND = [sys.executable, "-m", "aider_mcp_server"]
# Model for Aider to use (ensure your API key supports it)
AIDER_TEST_MODEL = os.environ.get("AIDER_E2E_MODEL", "openai/gpt-4o") # Example, configurable via env var
# LLM API Key Env Var Name (e.g., OPENAI_API_KEY) - MUST be set in test environment
LLM_API_KEY_ENV_VAR = os.environ.get("AIDER_E2E_API_KEY_VAR", "OPENAI_API_KEY")

# Check for prerequisites
AIDER_MCP_SERVER_INSTALLED = shutil.which(AIDER_MCP_SERVER_COMMAND[0]) and (len(AIDER_MCP_SERVER_COMMAND) == 1 or shutil.which(AIDER_MCP_SERVER_COMMAND[1])) # Basic check
API_KEY_SET = LLM_API_KEY_ENV_VAR in os.environ and bool(os.environ[LLM_API_KEY_ENV_VAR])

# --- Fixture for Temporary Git Repo ---

@pytest.fixture(scope="function") # Function scope to ensure clean repo each time
def e2e_aider_repo(tmp_path):
    """Creates a temporary directory, initializes git, adds a file, and commits."""
    repo_path = tmp_path / "e2e_aider_test_repo"
    repo_path.mkdir()
    initial_file = repo_path / "hello.py"
    initial_content = """
def greet(name):
    print(f"Hello, {name}!")

if __name__ == "__main__":
    greet("World")
"""
    initial_file.write_text(initial_content)

    try:
        # Initialize Git Repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        # Configure dummy user for commit (needed on some CI systems)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
        subprocess.run(["git", "config", "user.name", "Pytest E2E"], cwd=repo_path, check=True)
        # Add and Commit
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True, capture_output=True)
        print(f"Created and initialized Git repo at: {repo_path}")
        yield repo_path # Provide the path to the test
    finally:
        # Cleanup happens automatically with tmp_path fixture
        print(f"Cleaning up Git repo at: {repo_path}")
        pass # shutil.rmtree(repo_path) # tmp_path handles cleanup

# --- E2E Test Function ---

#@pytest.mark.skipif(not AIDER_MCP_SERVER_INSTALLED, reason="aider-mcp-server command not found or not executable.")
#@pytest.mark.skipif(not API_KEY_SET, reason=f"Required LLM API Key environment variable '{LLM_API_KEY_ENV_VAR}' is not set.")
#@pytest.mark.e2e # Custom marker for E2E tests
@pytest.mark.slow # Mark as slow due to real API calls
def test_e2e_aider_automatic_edit(e2e_aider_repo):
    """
    Tests the full aider:automatic workflow via the Application,
    connecting to a real Aider MCP Server instance.
    """
    server_process = None
    app = None
    repo_path_str = str(e2e_aider_repo)

    # --- Environment Patching ---
    # Ensure Aider is enabled and the necessary API key is present
    # for the Application's context AND the subprocess environment
    # Explicitly list ALL keys needed by the server/aider/litellm
    # Ensure the values are correctly sourced from the test runner's environment
    env_vars_to_patch = {
        "AIDER_ENABLED": "true", # For the Application side
        # Add specific keys needed by the model/litellm
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
        # Pass the specific key var used by the test config, ensuring it's included
        LLM_API_KEY_ENV_VAR: os.environ.get(LLM_API_KEY_ENV_VAR, "dummy_key_if_not_set"),
        # Add any other relevant config aider might use from env vars
        "AIDER_DISABLE_WELCOME_MESSAGE": "1",
        "LITELLM_LOG": "DEBUG", # Optional: Increase server logging via litellm
        "LITELLM_DISABLE_TELEMETRY": "1", # Optional: Disable telemetry
    }
    # Filter out empty values to avoid potential issues with some tools/libs
    env_vars_to_patch = {k: v for k, v in env_vars_to_patch.items() if v}


    # --- Server Startup ---
    try:
        # Define the command with arguments for the server
        # Crucially, it needs to operate within our test repository
        server_command = AIDER_MCP_SERVER_COMMAND + [
            "--current-working-dir", repo_path_str, # <-- Corrected
            "--editor-model", AIDER_TEST_MODEL,
            ]
        print(f"Starting Aider MCP Server with command: {' '.join(server_command)}")

        # Combine current environment with EXPLICITLY patched vars
        server_env = {**os.environ, **env_vars_to_patch}
        print(f"Passing environment keys to server subprocess: {list(env_vars_to_patch.keys())}") # Log keys being passed

        # Start the server process using Popen for non-blocking execution
        server_process = subprocess.Popen(
            server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            env=server_env # Pass the combined environment
        )

        # Wait briefly for the server to initialize
        # A more robust check would involve reading server stdout for a specific message
        print("Waiting for Aider MCP Server to start...")
        time.sleep(5) # Adjust as needed

        # Check if server started successfully (basic check: process didn't exit immediately)
        if server_process.poll() is not None:
            stdout, stderr = server_process.communicate()
            print(f"Server STDOUT:\n{stdout}")
            print(f"Server STDERR:\n{stderr}")
            pytest.fail(f"Aider MCP Server failed to start. Exit code: {server_process.returncode}")
        print("Aider MCP Server seems to be running.")

        # --- Application Setup ---
        # Configure Application to use the running server via STDIO
        # The command here should match how AiderBridge expects it
        app_config = {
            "aider_config": {
                "mcp_stdio_command": server_command[0], # Just the executable/module path
                "mcp_stdio_args": server_command[1:],   # Pass the arguments separately
                # Pass the SAME explicit env vars to the bridge config as it uses them for StdioServerParameters
                "mcp_stdio_env": env_vars_to_patch
            },
            "file_manager_base_path": repo_path_str # IMPORTANT: Point handler to the test repo
        }

        # Patch environment ONLY using patch.dict for the Application instance scope
        with patch.dict(os.environ, env_vars_to_patch, clear=False):
            print("Instantiating Application within patched environment...") # Add log
            app = Application(config=app_config) # Instantiation happens HERE, after patch
            print("Application instantiated within patched environment.") # Add log

            # Log handler tools right after instantiation within the patch
            if app and app.passthrough_handler:
                print(f"DEBUG (in patch): Handler tool executors after app init: {list(app.passthrough_handler.tool_executors.keys())}")
            else:
                print("DEBUG (in patch): App or Handler not available to log tools.")

            # --- Test Action ---
            target_file = "hello.py"
            prompt = f"Add a python docstring to the greet function in {target_file} explaining what it does."
            params = {
                "prompt": prompt,
                # File context should be relative to the repo root (which is the server's working dir)
                "file_context": json.dumps([target_file])
            }

            print(f"Calling handle_task_command for aider:automatic with prompt: '{prompt}'")
            result_dict = app.handle_task_command("aider:automatic", params=params)
            print("handle_task_command returned.")

            # --- Assertions ---
            print("Raw Result:\n", json.dumps(result_dict, indent=2))
            assert isinstance(result_dict, dict)
            assert result_dict.get("status") == "COMPLETE"

            # Assert diff content (more robust check that doesn't depend on exact docstring content)
            diff_content = result_dict.get("content", "")
            assert "--- a/hello.py" in diff_content
            assert "+++ b/hello.py" in diff_content
            assert '+    """' in diff_content # Check for added docstring opening, regardless of content
            assert 'def greet(name):' in diff_content # Check context remains

            # Assert actual file content
            modified_file_path = e2e_aider_repo / target_file
            assert modified_file_path.exists()
            modified_content = modified_file_path.read_text()
            print(f"\nModified content of {target_file}:\n{modified_content}")
            assert '"""' in modified_content # Verify some docstring is present
            assert "def greet(name):" in modified_content # Verify function signature remains
            assert "print(f\"Hello, {name}!\")" in modified_content # Verify function body remains

    finally:
        # --- Cleanup ---
        if server_process:
            print("Terminating Aider MCP Server process...")
            server_process.terminate()
            try:
                # Wait a bit for termination, then kill if necessary
                stdout, stderr = server_process.communicate(timeout=5)
                print("Server terminated.")
                if stdout: print(f"Server Final STDOUT:\n{stdout}")
                if stderr: print(f"Server Final STDERR:\n{stderr}")
            except subprocess.TimeoutExpired:
                print("Server did not terminate gracefully, killing...")
                server_process.kill()
                print("Server killed.")
            except Exception as e:
                print(f"Error during server cleanup: {e}")
        # Repo cleanup handled by fixture

# Note: Add more tests for different scenarios (errors, different files, etc.)
# following the same pattern.
