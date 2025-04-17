"""REPL interface for interactive sessions."""
from typing import Dict, Any, Optional, Callable, List
import sys
import os
import shlex
import json
import logging

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
            # Ensure dispatcher is importable from the correct location
            from dispatcher import execute_programmatic_task
            self.dispatcher_func = execute_programmatic_task
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
        print("  /task <type:subtype> [param=value] [param2='[\"json\", \"list\"]'] [--use-history] [--help] - Execute a specific task programmatically", file=self.output)
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
        """Handles the /task command for programmatic task execution.
        
        Args:
            args: Command arguments in the format "<identifier> [param=value] [--flag]"
        """
        if not self.dispatcher_func:
            print("Error: Dispatcher is not available. Cannot execute /task.", file=self.output)
            return

        if not args:
            print("Usage: /task <type:subtype> [param=value] [param2='[\"json\", \"list\"]'] [--use-history] [--help]", file=self.output)
            print("Examples:", file=self.output)
            print("  /task aider:automatic prompt=\"Add docstrings\" file_context='[\"src/main.py\"]'", file=self.output)
            print("  /task aider:automatic --help", file=self.output)
            print("  /task aider:automatic prompt=\"Fix bugs\" --use-history", file=self.output)
            return

        try:
            # Parse command parts using shlex to handle quoted strings properly
            try:
                parts = shlex.split(args)
            except ValueError as e:
                print(f"Error parsing command: {e}", file=self.output)
                print("Make sure all quotes are properly closed.", file=self.output)
                return
                
            identifier = parts[0]
            raw_params = parts[1:]

            params: Dict[str, Any] = {}
            flags: Dict[str, bool] = {}

            # --- Help Flag ---
            if "--help" in raw_params:
                print(f"Fetching help for task: {identifier}...", file=self.output)
                help_text = f"Help for '{identifier}':\n"
                found_help = False

                # Check Direct Tools (registered via registerDirectTool)
                if hasattr(self.application.passthrough_handler, 'direct_tool_executors') and identifier in self.application.passthrough_handler.direct_tool_executors:
                     # For direct tools, we currently rely on templates for detailed help
                     help_text += f"\n* Found Direct Tool registration.\n"
                     # We will look for a matching template below for parameter details.
                     found_help = True # Mark that we found *something*

                # Check TaskSystem Templates (registered via register_template)
                if hasattr(self.application.task_system, 'find_template'):
                     template_info = self.application.task_system.find_template(identifier)
                     if template_info:
                         help_text += f"\n* Task Template Details:\n"
                         help_text += f"  Description: {template_info.get('description', 'N/A')}\n"
                         params_def = template_info.get('parameters', {})
                         if params_def:
                             help_text += f"  Parameters:\n"
                             for name, schema in params_def.items():
                                 req_str = "(required)" if schema.get('required') else "(optional)"
                                 type_str = f" (type: {schema.get('type', 'any')})"
                                 def_str = f" (default: {schema['default']})" if 'default' in schema else ""
                                 desc = schema.get('description', 'N/A')
                                 help_text += f"    - {name}{type_str}: {desc} {req_str}{def_str}\n"
                         else:
                             help_text += "  Parameters: Not defined in template.\n"
                         found_help = True

                if not found_help:
                    help_text = f"No help found for identifier: {identifier}. Check spelling and registration."

                print(help_text, file=self.output)
                return # Stop processing after help

            # --- Parameter Parsing ---
            for param_str in raw_params:
                if param_str.startswith("--"):
                    # Handle flags (like --use-history)
                    flags[param_str[2:]] = True
                elif "=" in param_str:
                    key, value = param_str.split("=", 1)
                    # Attempt JSON parsing for values starting with [ or { or "
                    # shlex removes outer quotes, so check start/end characters
                    if (value.startswith("[") and value.endswith("]")) or \
                       (value.startswith("{") and value.endswith("}")) or \
                       (value.startswith('"') and value.endswith('"')):
                        try:
                            # If it was originally quoted JSON, json.loads needs the quotes
                            params[key] = json.loads(value)
                        except json.JSONDecodeError as e:
                            # If JSON fails, treat as a plain string
                            print(f"Warning: Could not parse '{key}' value as JSON: {e}. Treating as string.", file=self.output)
                            params[key] = value # Store as raw string on failure
                    else:
                        # Plain string value
                        params[key] = value
                else:
                    print(f"Warning: Ignoring invalid parameter format (expected key=value or --flag): {param_str}", file=self.output)

            # --- Prepare History Context if Needed ---
            history_context = None
            if flags.get("use-history") and hasattr(self.application, "passthrough_handler"):
                # Extract recent conversation history
                if hasattr(self.application.passthrough_handler, "conversation_history"):
                    # Format the last few exchanges (up to 5)
                    history = self.application.passthrough_handler.conversation_history[-10:]  # Last 10 messages
                    history_context = "\n".join([
                        f"{msg['role'].capitalize()}: {msg['content'][:200]}{'...' if len(msg['content']) > 200 else ''}"
                        for msg in history
                    ])
                    print("Using recent conversation history for context.", file=self.output)

            # --- Call Dispatcher ---
            print(f"\nExecuting task: {identifier} with params: {params} flags: {flags}", file=self.output)
            print("Thinking...", end="", flush=True, file=self.output)
            
            try:
                result = self.dispatcher_func(
                    identifier=identifier,
                    params=params,
                    flags=flags,
                    handler_instance=self.application.passthrough_handler,
                    task_system_instance=self.application.task_system,
                    optional_history_str=history_context
                )
            except Exception as e:
                print("\r" + " " * 12 + "\r", end="", flush=True, file=self.output)  # Clear thinking message
                print(f"\nError from dispatcher: {e}", file=self.output)
                logging.exception("Dispatcher error:")
                return
                
            print("\r" + " " * 12 + "\r", end="", flush=True, file=self.output)  # Clear thinking message

            # --- Display Result ---
            print("\nResult:", file=self.output)
            print(f"Status: {result.get('status', 'UNKNOWN')}", file=self.output)
            
            # Check for error status
            if result.get('status') == "FAILED":
                print(f"Error: {result.get('content', 'Unknown error')}", file=self.output)
                if result.get('notes', {}).get('error_details'):
                    print(f"Details: {result['notes']['error_details']}", file=self.output)
                return
            
            # Pretty print content if it looks like JSON
            content = result.get('content', 'N/A')
            try:
                # Attempt to parse content as JSON only if it's a string and looks like JSON
                if isinstance(content, str) and content.strip().startswith(('[', '{')):
                    parsed_content = json.loads(content)
                    print("Content:")
                    print(json.dumps(parsed_content, indent=2))
                else:
                     print(f"Content: {content}", file=self.output)
            except json.JSONDecodeError:
                 print(f"Content: {content}", file=self.output)  # Print as is if not valid JSON

            if result.get('notes'):
                print("\nNotes:", file=self.output)
                for k, v in result['notes'].items():
                     # Pretty print complex values like lists/dicts within notes
                     if isinstance(v, (dict, list)):
                         print(f"  {k}:")
                         # Use json.dumps for consistent formatting of nested structures
                         try:
                             print(f"    {json.dumps(v, indent=2)}")
                         except TypeError:  # Handle non-serializable types gracefully
                             print(f"    (Could not serialize value of type {type(v).__name__})")
                     else:
                         print(f"  {k}: {v}", file=self.output)

        except Exception as e:
            print(f"\nError processing /task command: {e}", file=self.output)
            logging.exception("Error in _cmd_task:")  # Log full traceback
