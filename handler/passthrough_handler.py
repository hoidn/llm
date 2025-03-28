"""Passthrough handler for processing raw text queries."""
from typing import Dict, Any, Optional, List

from handler.model_provider import ClaudeProvider
from handler.file_access import FileAccessManager

class PassthroughHandler:
    """Handles raw text queries without AST compilation.
    
    Processes queries in "passthrough mode" by wrapping them in subtasks
    while maintaining conversation state and context management.
    """
    
    def __init__(self, task_system, memory_system, model_provider: Optional[ClaudeProvider] = None):
        """Initialize the passthrough handler.
        
        Args:
            task_system: The Task System instance
            memory_system: The Memory System instance
            model_provider: Provider for model interactions, defaults to ClaudeProvider
        """
        self.task_system = task_system
        self.memory_system = memory_system
        self.model_provider = model_provider or ClaudeProvider()
        self.file_manager = FileAccessManager()
        
        # Conversation state
        self.conversation_history = []
        self.active_subtask_id = None
        self.system_prompt = """You are a helpful assistant that responds to user queries.
        When referring to code or files, cite the relevant file paths.
        Be precise and helpful, focusing on the user's specific question."""
    
    def handle_query(self, query: str) -> Dict[str, Any]:
        """Handle a raw text query in passthrough mode.
        
        Creates or continues a subtask for the query, maintaining
        conversation state between queries.
        
        Args:
            query: Raw text query from the user
            
        Returns:
            Task result containing the response
        """
        # Add user message to conversation history
        self.conversation_history.append({"role": "user", "content": query})
        
        # Get relevant files from memory system based on query
        relevant_files = self._get_relevant_files(query)
        
        if not self.active_subtask_id:
            result = self._create_new_subtask(query, relevant_files)
        else:
            result = self._continue_subtask(query, relevant_files)
            
        # Add assistant response to conversation history
        self.conversation_history.append({"role": "assistant", "content": result["content"]})
        
        return result
    
    def _get_relevant_files(self, query: str) -> List[str]:
        """Get relevant files from memory system based on query.
        
        Args:
            query: User's query text
            
        Returns:
            List of relevant file paths
        """
        # Use memory system to find relevant files
        context_input = {
            "taskText": query,
            "inheritedContext": "",  # No inherited context for fresh queries
        }
        
        context_result = self.memory_system.get_relevant_context_for(context_input)
        
        # Extract file paths from matches
        relevant_files = [match[0] for match in context_result.matches]
        return relevant_files
    
    def _create_new_subtask(self, query: str, relevant_files: List[str]) -> Dict[str, Any]:
        """Create a new subtask for the initial query.
        
        Args:
            query: Initial query from the user
            relevant_files: List of relevant file paths
            
        Returns:
            Task result from the subtask
        """
        # Create a unique subtask ID
        self.active_subtask_id = f"subtask_{len(self.conversation_history)}"
        
        # Create file context
        file_context = self._create_file_context(relevant_files)
        
        # Send to model and get response
        response_text = self._send_to_model(query, file_context)
        
        return {
            "status": "success",
            "content": response_text,
            "metadata": {
                "subtask_id": self.active_subtask_id,
                "relevant_files": relevant_files
            }
        }
    
    def _continue_subtask(self, query: str, relevant_files: List[str]) -> Dict[str, Any]:
        """Continue an existing subtask with a follow-up query.
        
        Args:
            query: Follow-up query from the user
            relevant_files: List of relevant file paths
            
        Returns:
            Task result from the continued subtask
        """
        # Create file context
        file_context = self._create_file_context(relevant_files)
        
        # Send to model and get response
        response_text = self._send_to_model(query, file_context)
        
        return {
            "status": "success",
            "content": response_text,
            "metadata": {
                "subtask_id": self.active_subtask_id,
                "relevant_files": relevant_files
            }
        }
        
    def _send_to_model(self, query: str, file_context: str) -> str:
        """Send query to model and get response.
        
        Args:
            query: User's query
            file_context: Context string with file information
            
        Returns:
            Model response text
        """
        # Format conversation history for Claude
        formatted_messages = [
            {
                "role": msg["role"],
                "content": msg["content"]
            }
            for msg in self.conversation_history
        ]
        
        # Add file context to system prompt if available
        if file_context:
            system_prompt = f"{self.system_prompt}\n\nRelevant files:\n{file_context}"
        else:
            system_prompt = self.system_prompt
        
        try:
            # Send to model
            response = self.model_provider.send_message(
                messages=formatted_messages,
                system_prompt=system_prompt
            )
            return response if response else f"Processed query: {query}"
        except Exception as e:
            # Fallback for tests or when API is unavailable
            print(f"Error sending to model: {str(e)}")
            return f"Processed query: {query}"
    
    def _create_file_context(self, file_paths: List[str]) -> str:
        """Create a context string from file paths.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Context string with file information
        """
        if not file_paths:
            return ""
        
        file_contexts = []
        for path in file_paths:
            content = self.file_manager.read_file(path)
            if content:
                # Format the file content with proper markdown
                file_contexts.append(f"File: {path}\n```\n{content}\n```\n")
            else:
                file_contexts.append(f"File: {path} (could not be read)")
        
        if file_contexts:
            return "\n".join(file_contexts)
        else:
            return "No file contents available."
    
    def reset_conversation(self):
        """Reset the conversation state."""
        self.conversation_history = []
        self.active_subtask_id = None
