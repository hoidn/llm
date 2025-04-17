"""REPL interface for interactive sessions."""
from typing import Dict, Any, Optional, Callable, List
import sys
import os
import shlex # Add shlex import
import json # Add json import
import logging # Add logging import

class Repl:
    """Interactive REPL (Read-Eval-Print Loop) interface.
    
    Provides an interactive command-line interface for users to
    interact with the system in passthrough or standard mode.
    """
    
    def __init__(self, application, output_stream=None):
        """Initialize the REPL interface.
        
        Args:
            application: The Application instance
            output_stream: Optional output stream (defaults to sys.stdout)
        """
        self.application = application
        self.mode = "passthrough"  # Default mode
        self.verbose = False  # Verbose mode off by default
        self.output = output_stream or sys.stdout
        self.commands = {
            "/help": self._cmd_help,
            "/mode": self._cmd_mode,
            "/exit": self._cmd_exit,
            "/reset": self._cmd_reset,
            "/verbose": self._cmd_verbose,
            "/index": self._cmd_index,
            "/test-aider": self._cmd_test_aider,
            "/debug": self._cmd_debug,
            "/task": self._cmd_task # Add the new command
        }
        # Add dispatcher import
        try:
            # Adjust import path based on your project structure (e.g., from ..dispatcher)
            # Assuming dispatcher.py is in the parent directory (src/) relative to repl/
            from dispatcher import execute_programmatic_task
            self.dispatcher_func = execute_programmatic_task
            logging.info("Dispatcher function imported successfully.") # Add confirmation
        except ImportError:
            logging.error("Failed to import dispatcher function! /task command will not work.")
            self.dispatcher_func = None

    def start(self) -> None:
        """Start the REPL interface.
        
        Begins the interactive session, accepting user input and
        providing system responses.
        """
        print(f"REPL started in {self.mode} mode", file=self.output)
        print("Type your queries or commands (/help for help)", file=self.output)
        
        while True:
            try:
                user_input = input(f"({self.mode}) > ")
                self._process_input(user_input)
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...", file=self.output)
                break
    
    def _process_input(self, user_input: str) -> None:
        """Process user input.
        
        Handles commands and queries based on the current mode.
        
        Args:
            user_input: Input from the user
        """
        user_input = user_input.strip()
        
        if not user_input:
            return
        
        # Handle commands
        if user_input.startswith("/"):
            self._handle_command(user_input)
        else:
            # Handle query in current mode
            self._handle_query(user_input)
    
    def _handle_command(self, command: str) -> None:
        """Handle a command input.
        
        Args:
            command: Command from the user
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd in self.commands:
            self.commands[cmd](args)
        else:
            print(f"Unknown command: {cmd}", file=self.output)
            print("Type /help for available commands", file=self.output)
    
    def _handle_query(self, query: str) -> None:
        """Handle a query input.
        
        Args:
            query: Query from the user
        """
        # Check if any repositories are indexed
        if not self.application.indexed_repositories:
            print("No repositories indexed. Please index a repository first.", file=self.output)
            print("Usage: /index REPO_PATH", file=self.output)
            return
        
        if self.mode == "passthrough":
            # Show thinking indicator
            print("\nThinking...", end="", flush=True, file=self.output)
            
            # Handle query in passthrough mode
            result = self.application.handle_query(query)
            
            # Clear thinking indicator
            print("\r" + " " * 12 + "\r", end="", flush=True, file=self.output)
            
            # Display files in context
            if "metadata" in result and "relevant_files" in result["metadata"] and result["metadata"]["relevant_files"]:
                print("\nFiles in context:", file=self.output)
                for i, file_path in enumerate(result["metadata"]["relevant_files"], 1):
                    print(f"  {i}. {file_path}", file=self.output)
                print("", file=self.output)
            else:
                print("\nNo specific files were found relevant to your query.\n", file=self.output)
            
            # Display response
            print("Response:", file=self.output)
            print(result.get("content", "No response"), file=self.output)
            
            # Display metadata if verbose mode is on
            if self.verbose and "metadata" in result:
                print("\nMetadata:", file=self.output)
                for key, value in result["metadata"].items():
                    if key != "relevant_files":  # Skip files as we already displayed them
                        if isinstance(value, list) and len(value) > 0:
                            print(f"  {key}:", file=self.output)
                            for item in value:
                                print(f"    - {item}", file=self.output)
                        else:
                            print(f"  {key}: {value}", file=self.output)
        else:
            print("Standard mode not implemented yet", file=self.output)
    
    def _cmd_help(self, args: str) -> None:
        """Handle the help command.
        
        Args:
            args: Command arguments
        """
        print("Available commands:", file=self.output)
        print("  /help - Show this help", file=self.output)
        print("  /mode [passthrough|standard] - Set or show current mode", file=self.output)
        print("  /index REPO_PATH - Index a git repository", file=self.output)
        print("  /reset - Reset conversation state", file=self.output)
        print("  /verbose [on|off] - Toggle verbose mode", file=self.output)
        print("  /debug [on|off] - Toggle debug mode for tool selection", file=self.output)
        print("  /test-aider [interactive|automatic] - Test Aider tool integration", file=self.output)
        print("  /task <identifier> [param=value] [param2='<json_value>'] [--flag] [--help] - Execute a task programmatically", file=self.output)
        print("      Aider shortcuts: /task aider:automatic prompt=\"Fix bug\" file_context='[\"src/file.py\"]'", file=self.output)
        print("      Aider shortcuts: /task aider:interactive prompt=\"Help me with this code\" file_context='[\"src/file.py\"]'", file=self.output)
        print("      Aider shortcuts: /task aider:edit prompt=\"Add docstrings\" file_context='[\"src/file.py\"]'", file=self.output)
        print("  /exit - Exit the REPL", file=self.output)

    def _cmd_mode(self, args: str) -> None:
        """Handle the mode command.
        
        Args:
            args: Command arguments
        """
        if args:
            if args in ["passthrough", "standard"]:
                self.mode = args
                print(f"Mode set to: {self.mode}", file=self.output)
            else:
                print(f"Invalid mode: {args}", file=self.output)
                print("Available modes: passthrough, standard", file=self.output)
        else:
            print(f"Current mode: {self.mode}", file=self.output)
    
    def _cmd_reset(self, args: str) -> None:
        """Handle the reset command.
        
        Args:
            args: Command arguments
        """
        self.application.reset_conversation()
        print("Conversation reset", file=self.output)
    
    def _cmd_verbose(self, args: str) -> None:
        """Handle the verbose command.
        
        Args:
            args: Command arguments
        """
        if not args:
            # Toggle verbose mode
            self.verbose = not self.verbose
        elif args.lower() in ["on", "true", "yes", "1"]:
            self.verbose = True
        elif args.lower() in ["off", "false", "no", "0"]:
            self.verbose = False
        else:
            print(f"Invalid option: {args}", file=self.output)
            print("Usage: /verbose [on|off]", file=self.output)
            return
        
        print(f"Verbose mode: {'on' if self.verbose else 'off'}", file=self.output)
        
    def _cmd_debug(self, args: str) -> None:
        """Toggle debug mode for tool selection.
        
        Args:
            args: Command arguments - 'on' or 'off'
        """
        # Check if handler has set_debug_mode method
        if not hasattr(self.application.passthrough_handler, 'set_debug_mode'):
            print("Error: Handler does not support debug mode", file=self.output)
            return
            
        if not args:
            # Toggle debug mode
            current_mode = getattr(self.application.passthrough_handler, 'debug_mode', False)
            self.application.passthrough_handler.set_debug_mode(not current_mode)
        elif args.lower() in ["on", "true", "yes", "1"]:
            self.application.passthrough_handler.set_debug_mode(True)
        elif args.lower() in ["off", "false", "no", "0"]:
            self.application.passthrough_handler.set_debug_mode(False)
        else:
            print(f"Invalid option: {args}", file=self.output)
            print("Usage: /debug [on|off]", file=self.output)
            return
        
        current_mode = getattr(self.application.passthrough_handler, 'debug_mode', False)
        print(f"Debug mode: {'on' if current_mode else 'off'}", file=self.output)
    
    def _cmd_index(self, args: str) -> None:
        """Handle the index command.
        
        Args:
            args: Command arguments
        """
        if not args:
            print("Error: Repository path required", file=self.output)
            print("Usage: /index REPO_PATH", file=self.output)
            return
        
        # Expand user directory if needed
        repo_path = os.path.expanduser(args)
        
        # Index repository
        success = self.application.index_repository(repo_path)
        
        if not success:
            print(f"Failed to index repository: {repo_path}", file=self.output)
    
    def _cmd_exit(self, args: str) -> None:
        """Handle the exit command.
        
        Args:
            args: Command arguments
        """
        print("Exiting...", file=self.output)
        sys.exit(0)
        
    def _cmd_test_aider(self, args: str) -> None:
        """Test Aider tool integration.
        
        Args:
            args: Command arguments - 'interactive' or 'automatic'
        """
        # Check if Aider bridge is available
        if not hasattr(self.application, 'aider_bridge') or not self.application.aider_bridge:
            print("Error: Aider bridge not initialized", file=self.output)
            return
            
        # Parse mode from args
        mode = args.strip().lower() if args.strip() else 'interactive'
        if mode not in ['interactive', 'automatic']:
            print(f"Invalid mode: {mode}", file=self.output)
            print("Available modes: interactive, automatic", file=self.output)
            return
            
        print(f"\nTesting Aider in {mode} mode...", file=self.output)
        
        # Get test query based on mode
        if mode == 'interactive':
            test_query = "Add a docstring to this function"
        else:
            test_query = "Add type hints to this function"
            
        # Get file context
        test_files = self.application.aider_bridge.get_context_for_query(test_query)
        if not test_files:
            print("Warning: No relevant files found for test query", file=self.output)
            print("Using a sample file for testing...", file=self.output)
            # Use a sample file from the current directory
            import glob
            py_files = glob.glob("*.py")
            if py_files:
                test_files = [py_files[0]]
            else:
                print("Error: No Python files found for testing", file=self.output)
                return
                
        print(f"Using file context: {test_files}", file=self.output)
        
        # Execute test based on mode
        try:
            if mode == 'interactive':
                print("\nStarting interactive Aider session...", file=self.output)
                result = self.application.aider_bridge.start_interactive_session(test_query, test_files)
            else:
                print("\nExecuting automatic Aider task...", file=self.output)
                result = self.application.aider_bridge.execute_automatic_task(test_query, test_files)
                
            # Display result
            print("\nTest result:", file=self.output)
            print(f"Status: {result.get('status', 'unknown')}", file=self.output)
            print(f"Content: {result.get('content', 'No content')}", file=self.output)
            
            # Display additional details if available
            if 'notes' in result:
                print("\nDetails:", file=self.output)
                for key, value in result['notes'].items():
                    print(f"  {key}: {value}", file=self.output)
                    
        except Exception as e:
            print(f"\nError testing Aider: {str(e)}", file=self.output)
            import traceback
            print(traceback.format_exc(), file=self.output)

    def _cmd_task(self, args: str) -> None:
        """Handles the /task command for programmatic task execution."""
        if not self.dispatcher_func:
            print("Error: Dispatcher is not available. Cannot execute /task.", file=self.output)
            return

        if not args:
            # Print more detailed usage
            print("Usage: /task <identifier> [param=value] [param2='<json_value>'] [--flag] [--help]", file=self.output)
            print("  <identifier>: Task name (e.g., 'aider:automatic' or 'type:subtype').", file=self.output)
            print("  param=value:  Set parameter 'param' to 'value'. Value is treated as string unless it looks like JSON.", file=self.output)
            print("  param='<json_value>': Set parameter 'param' to parsed JSON value (e.g., '[\"a\", \"b\"]', '{\"key\": 1}').", file=self.output)
            print("  --flag:       Enable boolean flag 'flag'.", file=self.output)
            print("  --help:       Show help for the specified <identifier>.", file=self.output)
            print("Examples:", file=self.output)
            print("  /task aider:automatic prompt=\"Add docstrings\" file_context='[\"src/main.py\"]'", file=self.output)
            print("  /task aider:interactive --help", file=self.output)
            return

        try:
            # Parse command parts using shlex to handle quoted strings properly
            try:
                parts = shlex.split(args)
            except ValueError as e:
                print(f"Error parsing command: {e}", file=self.output)
                print("Make sure all quotes are properly closed.", file=self.output)
                return

            if not parts: # Handle case where args was just whitespace
                print("Usage: /task <identifier> ...", file=self.output)
                return

            identifier = parts[0]
            raw_params_and_flags = parts[1:]

            # --- STRICT PRECEDENCE Help Flag Handling ---
            if "--help" in raw_params_and_flags:
                print(f"Fetching help for task: {identifier}...", file=self.output)
                logging.debug(f"REPL Help: Checking help for identifier: '{identifier}'")
                help_text = f"Help for '{identifier}':\n"
                found_help = False
                template_info = None
                tool_spec = None
                
                # 1. Check TaskSystem Templates FIRST (Strict Precedence)
                logging.debug("REPL Help: Checking TaskSystem templates...")
                if hasattr(self.application.task_system, 'find_template'):
                    template_info = self.application.task_system.find_template(identifier)
                    logging.debug(f"REPL Help: Template found: {bool(template_info)}")
                    if template_info:
                        logging.debug("REPL Help: Formatting help from template.")
                        help_text += f"\n* Task Template Details:\n"
                        help_text += f"  Description: {template_info.get('description', 'N/A')}\n"
                        params_def = template_info.get('parameters', {})
                        if params_def:
                            help_text += f"  Parameters:\n"
                            for name, schema in params_def.items():
                                req_str = "(required)" if schema.get('required') else ""
                                type_str = f" (type: {schema.get('type', 'any')})"
                                def_str = ""
                                if 'default' in schema:
                                    try:
                                        def_str = f" (default: {json.dumps(schema['default'])})"
                                    except TypeError:
                                        def_str = f" (default: <unserializable>)"
                                desc = schema.get('description', 'N/A')
                                help_text += f"    - {name}{type_str}{def_str}: {desc} {req_str}\n"
                        else:
                            help_text += "    Parameters: Not defined in template.\n"
                        found_help = True

                # 2. Check Handler Tool Spec ONLY IF template wasn't found
                if not found_help and hasattr(self.application.passthrough_handler, 'registered_tools'):
                    logging.debug("REPL Help: Checking direct tool registry (template not found)...")
                    tool_spec = self.application.passthrough_handler.registered_tools.get(identifier)
                    logging.debug(f"REPL Help: Tool spec found: {bool(tool_spec)}")
                    if tool_spec:
                        logging.debug("REPL Help: Formatting help from tool spec.")
                        help_text += f"\n* Direct Tool Specification:\n"
                        help_text += f"  Description: {tool_spec.get('description', 'N/A')}\n"
                        schema = tool_spec.get('input_schema', {}).get('properties', {})
                        if schema:
                            help_text += f"  Parameters (from schema):\n"
                            required = tool_spec.get('input_schema', {}).get('required', [])
                            for name, prop_schema in schema.items():
                                req_str = "(required)" if name in required else ""
                                type_str = f" (type: {prop_schema.get('type', 'any')})"
                                desc = prop_schema.get('description', 'N/A')
                                help_text += f"    - {name}{type_str}: {desc} {req_str}\n"
                        else:
                            help_text += "  Parameters: Not defined in tool schema.\n"
                        found_help = True

                # 3. Check Handler Direct Executor ONLY IF template and spec weren't found
                if not found_help and hasattr(self.application.passthrough_handler, 'direct_tool_executors'):
                    logging.debug("REPL Help: Checking direct executor (template and spec not found)...")
                    if identifier in self.application.passthrough_handler.direct_tool_executors:
                        logging.debug("REPL Help: Found direct executor but no spec.")
                        help_text += f"\n* Found Direct Tool registration for '{identifier}', but no detailed specification was found for help display."
                        found_help = True

                # 4. Not Found
                if not found_help:
                    logging.debug("REPL Help: No template, tool spec, or executor found for help.")
                    help_text = f"No help found for identifier: {identifier}. Check spelling and registration."

                print(help_text, file=self.output)
                return # Stop processing after help
            # --- END STRICT PRECEDENCE Help Flag Handling ---

            # --- Parameter & Flag Parsing ---
            params: Dict[str, Any] = {}
            flags: Dict[str, bool] = {}

            for item in raw_params_and_flags:
                if item.startswith("--"):
                    # Handle flags
                    flag_name = item[2:]
                    if not flag_name:
                        print(f"Warning: Ignoring invalid flag format: {item}", file=self.output)
                        continue
                    flags[flag_name] = True
                elif "=" in item:
                    # Handle key=value parameters
                    key, value = item.split("=", 1)
                    key = key.strip()
                    value = value.strip() # Keep original value from shlex
                    if not key:
                        print(f"Warning: Ignoring parameter with empty key: {item}", file=self.output)
                        continue

                    # Attempt JSON parsing for values starting/ending with brackets/braces/quotes
                    # Check common JSON starts/ends
                    is_potential_json = (value.startswith("[") and value.endswith("]")) or \
                                        (value.startswith("{") and value.endswith("}")) or \
                                        (value.startswith('"') and value.endswith('"'))

                    if is_potential_json:
                        try:
                            # json.loads expects double quotes for strings within JSON.
                            params[key] = json.loads(value)
                        except json.JSONDecodeError:
                            # If JSON parsing fails, treat as a plain string
                            print(f"Warning: Could not parse value for '{key}' as JSON - treating as string.", file=self.output)
                            params[key] = value # Store the raw string value
                    else:
                        # Plain string value (shlex handles quotes)
                        params[key] = value
                else:
                    print(f"Warning: Ignoring invalid parameter format (expected key=value or --flag): {item}", file=self.output)

            # --- Call Dispatcher ---
            print(f"\nExecuting task: {identifier}...", file=self.output)
            print("Thinking...", end="", flush=True, file=self.output)

            # Prepare history context (remains None for Phase 2)
            history_context = None
            # if flags.get("use-history"): # Logic for history will be added later

            # Check for Aider-specific tasks and use the bridge directly if available
            if identifier.startswith("aider:") and hasattr(self.application, 'aider_bridge') and self.application.aider_bridge:
                aider_mode = identifier.split(":", 1)[1] if ":" in identifier else "interactive"
                prompt = params.get("prompt", "")
                query = params.get("query", "")  # Also check for query parameter
                file_context = params.get("file_context", [])
                
                print("\r" + " " * 12 + "\r", end="", flush=True, file=self.output) # Clear thinking
                print(f"\nUsing Aider Bridge directly for '{aider_mode}' mode...", file=self.output)
                
                try:
                    if aider_mode == "automatic":
                        result = self.application.aider_bridge.execute_automatic_task(prompt, file_context)
                    elif aider_mode == "interactive":
                        # Use query if provided, otherwise fall back to prompt
                        input_text = query if query else prompt
                        result = self.application.aider_bridge.start_interactive_session(input_text, file_context)
                    elif aider_mode == "edit":
                        result = self.application.aider_bridge.execute_code_edit(prompt, file_context)
                    else:
                        print(f"\nUnknown Aider mode: {aider_mode}", file=self.output)
                        return
                        
                    # Add execution metadata
                    if "notes" not in result:
                        result["notes"] = {}
                    result["notes"]["execution_path"] = "direct_aider_bridge"
                    result["notes"]["context_source"] = "explicit_request" if file_context else "none"
                    result["notes"]["context_files_count"] = len(file_context) if file_context else 0
                except Exception as e:
                    print(f"\nError using Aider Bridge: {e}", file=self.output)
                    logging.exception("Aider Bridge error:")
                    return
            else:
                # Use standard dispatcher for non-Aider tasks
                try:
                    result = self.dispatcher_func(
                        identifier=identifier,
                        params=params,
                        flags=flags,
                        handler_instance=self.application.passthrough_handler,
                        task_system_instance=self.application.task_system,
                        optional_history_str=history_context # Pass None for now
                    )
                except Exception as e:
                    # Catch errors during dispatch call itself
                    print("\r" + " " * 12 + "\r", end="", flush=True, file=self.output) # Clear thinking
                    print(f"\nError calling dispatcher: {e}", file=self.output)
                    logging.exception("Dispatcher call error:")
                    return

            print("\r" + " " * 12 + "\r", end="", flush=True, file=self.output) # Clear thinking

            # --- Display Result ---
            print("\nResult:", file=self.output)
            print(f"Status: {result.get('status', 'UNKNOWN')}", file=self.output)

            content = result.get('content', 'N/A')
            print("Content:", file=self.output)
            try:
                # Pretty print if it's valid JSON and not just a simple string
                if isinstance(content, str) and content.strip().startswith(('[', '{')):
                    parsed_content = json.loads(content)
                    print(json.dumps(parsed_content, indent=2), file=self.output)
                else:
                     print(content, file=self.output) # Print directly
            except (json.JSONDecodeError, TypeError):
                 print(content, file=self.output) # Print raw content on error

            if result.get('notes'):
                print("\nNotes:", file=self.output)
                try:
                    # Use json.dumps for consistent formatting of notes
                    print(json.dumps(result['notes'], indent=2), file=self.output)
                except TypeError: # Handle non-serializable types gracefully
                    # Fallback to str() if notes contain non-serializable items
                    print(str(result['notes']), file=self.output)


        except Exception as e:
            # Catch any unexpected errors during command processing
            print(f"\nError processing /task command: {e}", file=self.output)
            logging.exception("Error in _cmd_task:")
