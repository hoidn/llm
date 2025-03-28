"""REPL interface for interactive sessions."""
from typing import Dict, Any, Optional, Callable, List
import sys

class Repl:
    """Interactive REPL (Read-Eval-Print Loop) interface.
    
    Provides an interactive command-line interface for users to
    interact with the system in passthrough or standard mode.
    """
    
    def __init__(self, task_system, memory_system):
        """Initialize the REPL interface.
        
        Args:
            task_system: The Task System instance
            memory_system: The Memory System instance
        """
        self.task_system = task_system
        self.memory_system = memory_system
        self.mode = "passthrough"  # Default mode
        from handler.passthrough_handler import PassthroughHandler
        self.passthrough_handler = PassthroughHandler(task_system, memory_system)
        self.commands = {
            "/help": self._cmd_help,
            "/mode": self._cmd_mode,
            "/exit": self._cmd_exit
        }
    
    def start(self) -> None:
        """Start the REPL interface.
        
        Begins the interactive session, accepting user input and
        providing system responses.
        """
        print("REPL started in passthrough mode")
        print("Type your queries or commands (/help for help)")
        
        while True:
            try:
                user_input = input("> ")
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
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd in self.commands:
            self.commands[cmd](parts[1:] if len(parts) > 1 else [])
        else:
            print(f"Unknown command: {cmd}")
    
    def _handle_query(self, query: str) -> None:
        """Handle a query input.
        
        Args:
            query: Query from the user
        """
        if self.mode == "passthrough":
            result = self.passthrough_handler.handle_query(query)
            print("\nResponse:")
            print(result.get("content", "No response"))
        else:
            print("Standard mode not implemented")
    
    def _cmd_help(self, args: List[str]) -> None:
        """Handle the help command.
        
        Args:
            args: Command arguments
        """
        print("Available commands:")
        print("  /help - Show this help")
        print("  /mode [passthrough|standard] - Set or show current mode")
        print("  /exit - Exit the REPL")
    
    def _cmd_mode(self, args: List[str]) -> None:
        """Handle the mode command.
        
        Args:
            args: Command arguments
        """
        if args:
            if args[0] in ["passthrough", "standard"]:
                self.mode = args[0]
                print(f"Mode set to: {self.mode}")
            else:
                print("Invalid mode. Use 'passthrough' or 'standard'")
        else:
            print(f"Current mode: {self.mode}")
    
    def _cmd_exit(self, args: List[str]) -> None:
        """Handle the exit command.
        
        Args:
            args: Command arguments
        """
        print("Exiting...")
        sys.exit(0)
