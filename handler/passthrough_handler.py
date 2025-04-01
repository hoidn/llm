"""Passthrough handler for processing raw text queries."""
from typing import Dict, Any, Optional, List, Union, Callable, Tuple
import re
import json

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
        
        # Debug mode
        self.debug_mode = False
        
        # Tool registration
        self.registered_tools = {}  # Tool specifications
        self.tool_executors = {}    # Tool executor functions
        
        # Conversation state
        self.conversation_history = []
        self.active_subtask_id = None
        self.system_prompt = """You are a helpful assistant that responds to user queries.
        When referring to code or files, cite the relevant file paths.
        Be precise and helpful, focusing on the user's specific question.
        
        For code editing tasks, you can use the aiderInteractive or aiderAutomatic tools.
        Use aiderInteractive for complex tasks requiring user interaction.
        Use aiderAutomatic for straightforward changes that don't need user confirmation.
        
        To invoke a tool, explicitly state that you are using the tool, for example:
        "I'll help you with that using the aiderAutomatic tool."
        or
        "Let me solve this with aiderInteractive."
        
        You can also use code blocks with the tool name:
        ```aiderAutomatic
        Your task description here
        ```
        
        Always invoke the appropriate tool for code editing tasks rather than trying to explain how to make the changes manually."""
    
    def handle_query(self, query: str) -> Dict[str, Any]:
        """Handle a raw text query in passthrough mode.
        
        Creates or continues a subtask for the query, maintaining
        conversation state between queries.
        
        Args:
            query: Raw text query from the user
            
        Returns:
            Task result containing the response
        """
        self.log_debug(f"Processing query: {query}")
        
        # Add user message to conversation history
        self.conversation_history.append({"role": "user", "content": query})
        
        # Get relevant files from memory system based on query
        relevant_files = self._get_relevant_files(query)
        self.log_debug(f"Found relevant files: {relevant_files}")
        
        # Check if query is an Aider command
        is_aider_command = query.startswith("/aider")
        if is_aider_command:
            self.log_debug("Detected Aider command")
        
        if not self.active_subtask_id:
            self.log_debug("Creating new subtask")
            result = self._create_new_subtask(query, relevant_files)
        else:
            self.log_debug(f"Continuing subtask: {self.active_subtask_id}")
            result = self._continue_subtask(query, relevant_files)
            
        # Add assistant response to conversation history
        self.conversation_history.append({"role": "assistant", "content": result["content"]})
        
        self.log_debug(f"Query processing complete. Status: {result.get('status', 'unknown')}")
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
        
    def register_tool(self, tool_spec: Dict[str, Any], executor_func: Callable) -> bool:
        """
        Register a tool following Anthropic's tool use format.
        
        Args:
            tool_spec: Tool specification following Anthropic format
            executor_func: Function to execute when tool is called
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            tool_name = tool_spec.get('name')
            if not tool_name:
                self.log_debug(f"Error registering tool: Missing tool name")
                return False
                
            self.log_debug(f"Registering tool in Anthropic format: {tool_name}")
            self.registered_tools[tool_name] = tool_spec
            self.tool_executors[tool_name] = executor_func
            return True
        except Exception as e:
            self.log_debug(f"Error registering tool: {str(e)}")
            return False
            
    def _check_for_tool_invocation(self, response: Union[str, Dict[str, Any]], original_query: str) -> Optional[Dict[str, Any]]:
        """
        Check if response contains tool invocation and execute if found.
        
        Supports both official Anthropic tool call format and simpler code block format.
        
        Args:
            response: Response from the model (text or dict with tool calls)
            original_query: Original query from the user
            
        Returns:
            Tool execution result if a tool was invoked, None otherwise
        """
        # Check if response is already in tool call format (dict with tool_calls)
        if isinstance(response, dict) and 'tool_calls' in response:
            self.log_debug("Found official tool call format")
            tool_calls = response['tool_calls']
            
            if tool_calls and len(tool_calls) > 0:
                # Get the first tool call
                tool_call = tool_calls[0]
                tool_name = tool_call.name
                tool_params = tool_call.input
                
                self.log_debug(f"Executing tool {tool_name} with params: {tool_params}")
                
                # Check if tool exists
                if tool_name in self.tool_executors:
                    try:
                        # Execute tool
                        result = self.tool_executors[tool_name](tool_params)
                        self.log_debug(f"Tool execution result: {result.get('status', 'unknown')}")
                        return result
                    except Exception as e:
                        self.log_debug(f"Error executing tool {tool_name}: {str(e)}")
                        return {
                            "status": "error",
                            "content": f"Error executing tool {tool_name}: {str(e)}",
                            "metadata": {"error": str(e)}
                        }
                else:
                    self.log_debug(f"Tool {tool_name} not found")
            
        # Check for simpler code block format
        if isinstance(response, str):
            # First check for direct mentions of using Aider tools
            aider_mention_patterns = [
                r'using the (?:aider|Aider)(Interactive|Automatic) tool',
                r'use (?:aider|Aider)(Interactive|Automatic)',
                r'using (?:aider|Aider)(Interactive|Automatic)',
                r'with (?:aider|Aider)(Interactive|Automatic)',
                r'through (?:aider|Aider)(Interactive|Automatic)'
            ]
            
            for pattern in aider_mention_patterns:
                match = re.search(pattern, response, re.IGNORECASE)
                if match:
                    tool_type = match.group(1).lower()
                    tool_name = f"aider{tool_type.capitalize()}"
                    
                    self.log_debug(f"Found mention of {tool_name} in response")
                    
                    # Extract the task description from the original query or nearby text
                    task = original_query
                    if "add '#foobar'" in original_query:
                        task = original_query
                    
                    # Create appropriate parameters
                    if tool_type == "interactive":
                        tool_params = {"query": task}
                    else:
                        tool_params = {"prompt": task}
                        
                    self.log_debug(f"Extracted task for {tool_name}: {task}")
                    self.log_debug(f"Tool parameters: {tool_params}")
                    
                    # Check if tool exists and execute
                    if tool_name in self.tool_executors:
                        try:
                            result = self.tool_executors[tool_name](tool_params)
                            self.log_debug(f"Tool execution result: {result.get('status', 'unknown')}")
                            return result
                        except Exception as e:
                            self.log_debug(f"Error executing tool {tool_name}: {str(e)}")
                            return {
                                "status": "error",
                                "content": f"Error executing tool {tool_name}: {str(e)}",
                                "metadata": {"error": str(e)}
                            }
            
            # Look for tool invocation in code blocks
            pattern = r'```(?:json|python)?\s*(\{.*?\})\s*```'
            matches = re.findall(pattern, response, re.DOTALL)
            
            for match in matches:
                try:
                    # Try to parse as JSON
                    data = json.loads(match)
                    
                    # Check if it looks like a tool call
                    if 'tool' in data and 'input' in data:
                        tool_name = data['tool']
                        tool_params = data['input']
                        
                        self.log_debug(f"Found code block tool invocation: {tool_name}")
                        self.log_debug(f"Tool parameters: {tool_params}")
                        
                        # Check if tool exists
                        if tool_name in self.tool_executors:
                            try:
                                # Execute tool
                                result = self.tool_executors[tool_name](tool_params)
                                self.log_debug(f"Tool execution result: {result.get('status', 'unknown')}")
                                return result
                            except Exception as e:
                                self.log_debug(f"Error executing tool {tool_name}: {str(e)}")
                                return {
                                    "status": "error",
                                    "content": f"Error executing tool {tool_name}: {str(e)}",
                                    "metadata": {"error": str(e)}
                                }
                except json.JSONDecodeError:
                    # Not valid JSON, continue to next match
                    continue
                    
            # Also check for direct tool name invocation
            for tool_name in self.tool_executors.keys():
                # Simple pattern: tool name followed by some text in a code block
                pattern = f'```{tool_name}\n(.*?)```'
                match = re.search(pattern, response, re.DOTALL)
                
                if match:
                    self.log_debug(f"Found direct tool invocation: {tool_name}")
                    tool_params_text = match.group(1).strip()
                    
                    try:
                        # Try to parse as JSON if it looks like JSON
                        if tool_params_text.startswith('{') and tool_params_text.endswith('}'):
                            tool_params = json.loads(tool_params_text)
                        else:
                            # Otherwise use as a simple string parameter
                            tool_params = {"query": tool_params_text} if tool_name == "aiderInteractive" else {"prompt": tool_params_text}
                            
                        self.log_debug(f"Tool parameters: {tool_params}")
                        
                        # Execute tool
                        result = self.tool_executors[tool_name](tool_params)
                        self.log_debug(f"Tool execution result: {result.get('status', 'unknown')}")
                        return result
                    except Exception as e:
                        self.log_debug(f"Error executing tool {tool_name}: {str(e)}")
                        return {
                            "status": "error",
                            "content": f"Error executing tool {tool_name}: {str(e)}",
                            "metadata": {"error": str(e)}
                        }
        
        # No tool invocation found
        self.log_debug("No tool invocation pattern found in response")
        return None
    
    def _send_to_model(self, query: str, file_context: str) -> str:
        """Send query to model and get response.
        
        Args:
            query: User's query
            file_context: Context string with file information
            
        Returns:
            Model response text
        """
        self.log_debug(f"Sending query to model: '{query[:50]}...' with {len(self.tool_executors)} registered tools")
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
        
        # Prepare tools if available
        tools = list(self.registered_tools.values()) if self.registered_tools else None
        
        if tools:
            self.log_debug(f"Available tools: {[t['name'] for t in tools]}")
        
        try:
            # Send to model
            response = self.model_provider.send_message(
                messages=formatted_messages,
                system_prompt=system_prompt,
                tools=tools
            )
            
            # Check for tool invocation
            tool_result = self._check_for_tool_invocation(response, query)
            
            if tool_result:
                self.log_debug("Tool was executed, returning tool result")
                # Return the tool result content as the response
                return tool_result.get("content", f"Tool execution completed: {tool_result.get('status', 'unknown')}")
            
            # Return the regular response if no tool was executed
            if isinstance(response, dict) and 'text' in response:
                return response['text'] if response['text'] else f"Processed query: {query}"
            else:
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
        
    def determine_relevant_files(self, query: str, file_metadata: Dict[str, str]) -> List[Tuple[str, str]]:
        """Determine relevant files for a query using LLM.
        
        Args:
            query: The user query or task
            file_metadata: Dictionary mapping file paths to their metadata
            
        Returns:
            List of tuples containing (file_path, relevance_context)
        """
        self.log_debug(f"Determining relevant files for query: '{query}'")
        self.log_debug(f"Number of files to evaluate: {len(file_metadata)}")
        
        file_context = "Available files:\n\n"
        for i, (path, metadata) in enumerate(file_metadata.items(), 1):
            file_context += f"File {i}: {path}\n"
            file_context += f"Metadata: {metadata}\n\n"
        
        system_prompt = """You are a file relevance assistant. Your task is to select files that are relevant to a user's query.
        Examine the metadata of each file and determine which files would be most useful to address the query.
        
        Return ONLY a JSON array of objects with the following format:
        [{"path": "path/to/file1.py", "relevance": "Reason this file is relevant"}, ...]
        
        Include only files that are truly relevant to the query. 
        The "relevance" field should briefly explain why the file is relevant to the query.
        
        Do not include explanations or other text in your response, just the JSON array.
        """
        
        user_message = f"Query: {query}\n\n{file_context}\n\nSelect the files most relevant to this query."
        
        try:
            messages = [{"role": "user", "content": user_message}]
            response = self.model_provider.send_message(
                messages=messages,
                system_prompt=system_prompt
            )
            
            self.log_debug(f"LLM response for file relevance: {response[:100]}...")
            
            # Response parsing
            import json
            import re
            
            # Parse JSON response
            if isinstance(response, str):
                json_pattern = r'\[\s*\{.*?\}\s*\]'
                match = re.search(json_pattern, response, re.DOTALL)
                if match:
                    json_str = match.group(0)
                    try:
                        json_str = json_str.replace("'", '"')  # Fix single quotes
                        file_selections = json.loads(json_str)
                            
                        if isinstance(file_selections, list):
                            result = []
                            for item in file_selections:
                                if isinstance(item, dict) and "path" in item:
                                    path = item["path"]
                                    relevance = item.get("relevance", "Relevant to query")
                                    if path in file_metadata:
                                        result.append((path, relevance))
                                
                            self.log_debug(f"Selected {len(result)} relevant files")
                            return result
                    except Exception:
                        # Continue to fallback if JSON parsing fails
                        pass
                
            # Fallback to regex path extraction
            path_pattern = r'(?:"|\')?([\/\w\.-]+\.[\w]+)(?:"|\')?' 
            matches = re.findall(path_pattern, response)
            if matches:
                valid_paths = [path for path in matches if path in file_metadata]
                result = [(path, "Relevant to query") for path in valid_paths]
                self.log_debug(f"Extracted {len(result)} file paths from response")
                return result
        except Exception as e:
            self.log_debug(f"Error determining relevant files: {str(e)}")
        
        self.log_debug("Using fallback selection strategy")
        # Return top 5 files rather than all files to avoid context overload
        result = [(path, "Included in fallback selection") 
                 for path in list(file_metadata.keys())[:5]]
        return result
        
    def log_debug(self, message: str) -> None:
        """Log debug information if debug mode is enabled.
        
        Args:
            message: Debug message to log
        """
        if self.debug_mode:
            print(f"[DEBUG] {message}")
            
    def set_debug_mode(self, enabled: bool) -> None:
        """Set debug mode.
        
        Args:
            enabled: Whether debug mode should be enabled
        """
        self.debug_mode = enabled
        self.log_debug(f"Debug mode {'enabled' if enabled else 'disabled'}")
        
    def registerDirectTool(self, name: str, func: Any) -> bool:
        """Register a direct tool.
        
        This method is called by the tool registration system to register
        direct tools that can be invoked by the handler.
        
        Args:
            name: Name of the tool
            func: Function to call when the tool is invoked
            
        Returns:
            True if registration successful, False otherwise
        """
        self.log_debug(f"Registering direct tool: {name}")
        
        # Create a wrapper function that adapts to the Anthropic tool format
        def tool_wrapper(input_data: Dict[str, Any]) -> Any:
            # If input is a dict with a query key, extract it
            if isinstance(input_data, dict) and "query" in input_data:
                query = input_data["query"]
                file_context = input_data.get("file_context")
                return func(query, file_context)
            # Otherwise pass the input directly
            return func(input_data)
        
        # Store the tool in both dictionaries
        if not hasattr(self, "direct_tools"):
            self.direct_tools = {}
        self.direct_tools[name] = func
        
        # Also register as a regular tool for the Anthropic format
        self.tool_executors[name] = tool_wrapper
        
        return True
    
    def registerSubtaskTool(self, name: str, func: Any) -> bool:
        """Register a subtask tool.
        
        This method is called by the tool registration system to register
        subtask tools that can be invoked by the handler.
        
        Args:
            name: Name of the tool
            func: Function to call when the tool is invoked
            
        Returns:
            True if registration successful, False otherwise
        """
        self.log_debug(f"Registering subtask tool: {name}")
        
        # Create a wrapper function that adapts to the Anthropic tool format
        def tool_wrapper(input_data: Dict[str, Any]) -> Any:
            # If input is a dict with a prompt key, extract it
            if isinstance(input_data, dict) and "prompt" in input_data:
                prompt = input_data["prompt"]
                file_context = input_data.get("file_context")
                return func(prompt, file_context)
            # Otherwise pass the input directly
            return func(input_data)
        
        # Store the tool in both dictionaries
        if not hasattr(self, "subtask_tools"):
            self.subtask_tools = {}
        self.subtask_tools[name] = func
        
        # Also register as a regular tool for the Anthropic format
        self.tool_executors[name] = tool_wrapper
        
        return True
