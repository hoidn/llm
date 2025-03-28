"""REPL interface for interactive sessions."""
from typing import Dict, Any, Optional, Callable, List
import sys
import os

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
            "/index": self._cmd_index
        }
    
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
