"""REPL interface for interactive sessions."""
from typing import Dict, Any, Optional, Callable, List
import sys
import os

class Repl:
    """Interactive REPL (Read-Eval-Print Loop) interface.
    
    Provides an interactive command-line interface for users to
    interact with the system in passthrough or standard mode.
    """
    
    def __init__(self, application):
        """Initialize the REPL interface.
        
        Args:
            application: The Application instance
        """
        self.application = application
        self.mode = "passthrough"  # Default mode
        self.verbose = False  # Verbose mode off by default
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
        print(f"REPL started in {self.mode} mode")
        print("Type your queries or commands (/help for help)")
        
        while True:
            try:
                user_input = input(f"({self.mode}) > ")
                self._process_input(user_input)
            except (KeyboardInterrupt, EOFError):
                print("\nExiting...")
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
            print(f"Unknown command: {cmd}")
            print("Type /help for available commands")
    
    def _handle_query(self, query: str) -> None:
        """Handle a query input.
        
        Args:
            query: Query from the user
        """
        # Check if any repositories are indexed
        if not self.application.indexed_repositories:
            print("No repositories indexed. Please index a repository first.")
            print("Usage: /index REPO_PATH")
            return
        
        if self.mode == "passthrough":
            result = self.application.handle_query(query)
            print("\nResponse:")
            print(result.get("content", "No response"))
            
            # Display metadata if verbose mode is on
            if self.verbose and "metadata" in result:
                print("\nMetadata:")
                for key, value in result["metadata"].items():
                    if isinstance(value, list) and len(value) > 0:
                        print(f"  {key}:")
                        for item in value:
                            print(f"    - {item}")
                    else:
                        print(f"  {key}: {value}")
        else:
            print("Standard mode not implemented yet")
    
    def _cmd_help(self, args: str) -> None:
        """Handle the help command.
        
        Args:
            args: Command arguments
        """
        print("Available commands:")
        print("  /help - Show this help")
        print("  /mode [passthrough|standard] - Set or show current mode")
        print("  /index REPO_PATH - Index a git repository")
        print("  /reset - Reset conversation state")
        print("  /verbose [on|off] - Toggle verbose mode")
        print("  /exit - Exit the REPL")
    
    def _cmd_mode(self, args: str) -> None:
        """Handle the mode command.
        
        Args:
            args: Command arguments
        """
        if args:
            if args in ["passthrough", "standard"]:
                self.mode = args
                print(f"Mode set to: {self.mode}")
            else:
                print(f"Invalid mode: {args}")
                print("Available modes: passthrough, standard")
        else:
            print(f"Current mode: {self.mode}")
    
    def _cmd_reset(self, args: str) -> None:
        """Handle the reset command.
        
        Args:
            args: Command arguments
        """
        self.application.reset_conversation()
        print("Conversation reset")
    
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
            print(f"Invalid option: {args}")
            print("Usage: /verbose [on|off]")
            return
        
        print(f"Verbose mode: {'on' if self.verbose else 'off'}")
    
    def _cmd_index(self, args: str) -> None:
        """Handle the index command.
        
        Args:
            args: Command arguments
        """
        if not args:
            print("Error: Repository path required")
            print("Usage: /index REPO_PATH")
            return
        
        # Expand user directory if needed
        repo_path = os.path.expanduser(args)
        
        # Index repository
        success = self.application.index_repository(repo_path)
        
        if not success:
            print(f"Failed to index repository: {repo_path}")
    
    def _cmd_exit(self, args: str) -> None:
        """Handle the exit command.
        
        Args:
            args: Command arguments
        """
        print("Exiting...")
        sys.exit(0)
