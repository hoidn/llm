# Passthrough Mode with Git Repository Context

A system for querying Git repositories with natural language using the power of Claude AI.

## Features

- **Git Repository Indexing**: Index Git repositories for context-aware responses
- **Passthrough Mode**: Process natural language queries without complex AST compilation
- **Visual Context Feedback**: See which files are being used for context in your queries
- **Multi-turn Conversations**: Maintain conversation state between queries
- **File Content Integration**: Include relevant file contents in the AI's context

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
python main.py
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
  1. /home/user/projects/my-repo/memory/indexers/git_repository_indexer.py
  2. /home/user/projects/my-repo/memory/memory_system.py

Response:
The file indexing process works by scanning the Git repository...

# Ask a follow-up question
(passthrough) > Can you tell me more about the GitRepositoryIndexer class?

Thinking...

Files in context:
  1. /home/user/projects/my-repo/memory/indexers/git_repository_indexer.py
  2. /home/user/projects/my-repo/tests/memory/indexers/test_git_repository_indexer.py

Response:
The GitRepositoryIndexer class is responsible for...
```

## Visual Context Feedback

When you send a query, the system will:

1. Show a "Thinking..." indicator while processing
2. Display a list of files being used for context
3. Show the AI's response based on those files

This helps you understand which files the system considers relevant to your query, making the system more transparent and helping you formulate better questions.

If no files are found relevant to your query, the system will explicitly tell you so.

## Verbose Mode

For additional details about the system's operation:

```
(passthrough) > /verbose on
Verbose mode: on

(passthrough) > Tell me about the project structure

Thinking...

Files in context:
  1. /home/user/projects/my-repo/README.md
  2. /home/user/projects/my-repo/main.py

Response:
The project has a simple structure with...

Metadata:
  subtask_id: subtask_1
```
