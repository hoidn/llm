# LLM Context Management System

A comprehensive system for context-aware LLM interactions with code repositories. This project provides a framework for intelligent code assistance with automatic context management, task execution, and Aider integration.

## Features

- **Git Repository Indexing**: Automatically index Git repositories for context-aware responses
- **Memory System**: Intelligent context retrieval based on query relevance
- **Task System**: Template-based task execution with variable substitution
- **Passthrough Mode**: Process natural language queries without complex AST compilation
- **Aider Integration**: Seamless integration with Aider for code editing capabilities
- **Visual Context Feedback**: See which files are being used for context in your queries
- **Multi-turn Conversations**: Maintain conversation state between queries
- **Evaluator Component**: Evaluate function calls and template execution

## Architecture

The system consists of several key components:

- **Memory System**: Manages repository metadata and retrieves relevant context
- **Task System**: Handles task templates and execution
- **Handler Components**: Process user queries and manage LLM interactions
- **Evaluator**: Evaluates function calls and manages execution context
- **Aider Bridge**: Integrates with Aider for code editing capabilities

## Usage

### Setup

1. Install the requirements:
   ```bash
   pip install anthropic pytest
   ```

2. Set your Anthropic API key:
   ```bash
   export ANTHROPIC_API_KEY=your_api_key_here
   ```

### Running the Application

Start the application:
```bash
python src/main.py
```

### REPL Commands

- `/index REPO_PATH` - Index a Git repository
- `/help` - Show help information
- `/mode [standard|passthrough]` - Set or view current mode
- `/reset` - Reset conversation state
- `/verbose [on|off]` - Toggle verbose mode
- `/exit` - Exit the program

### Workflow Example

```
# Index a repository
(passthrough) > /index ~/projects/my-repo

# Ask a question about the repository
(passthrough) > How does the file indexing work?

Thinking...

Files in context:
  1. ~/projects/my-repo/src/memory/indexers/git_repository_indexer.py
  2. ~/projects/my-repo/src/memory/memory_system.py

Response:
The file indexing process works by scanning the Git repository...

# Ask a follow-up question
(passthrough) > Can you tell me more about the GitRepositoryIndexer class?

Thinking...

Files in context:
  1. ~/projects/my-repo/src/memory/indexers/git_repository_indexer.py
  2. ~/projects/my-repo/tests/memory/indexers/test_git_repository_indexer.py

Response:
The GitRepositoryIndexer class is responsible for...
```

## Visual Context Feedback

When you send a query, the system will:

1. Show a "Thinking..." indicator while processing
2. Display a list of files being used for context
3. Show the AI's response based on those files

This helps you understand which files the system considers relevant to your query, making the system more transparent and helping you formulate better questions.

## Aider Integration

The system integrates with Aider to provide code editing capabilities:

- **Automatic Mode**: Execute code edits without user confirmation
- **Interactive Mode**: Start an interactive Aider session for complex edits

Example:
```
(passthrough) > Update the GitRepositoryIndexer to handle binary files better

Thinking...

Files in context:
  1. ~/projects/my-repo/src/memory/indexers/git_repository_indexer.py

Response:
I'll help you update the GitRepositoryIndexer. Here's what I'm changing:

1. Improving the is_text_file method to better detect binary files
2. Adding a skip_binary_files option to the index_repository method

Changes applied to:
- src/memory/indexers/git_repository_indexer.py
```

## Development

### Running Tests

```bash
pytest
```

### Project Structure

See the project_rules.md file for detailed information about the project structure, coding guidelines, and development practices.
