# Aider Developer Documentation

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [Core Classes](#core-classes)
3. [Context Management](#context-management)
4. [Git Integration](#git-integration)
5. [LLM Integration](#llm-integration)
6. [Commands System](#commands-system)
7. [Configuration](#configuration)
8. [Extending Aider](#extending-aider)

## System Architecture Overview

Aider is an AI pair programming tool that leverages large language models (LLMs) to help developers edit code through natural language conversations. The system is built around several key components:

![Architecture Diagram]

### Key Components

- **Main Entry Point**: `main.py` serves as the primary entry point for the application
- **Core Classes**: Various coders, commands, and context management systems
- **Git Integration**: For tracking and committing changes
- **LLM Integration**: For interfacing with language models
- **I/O Management**: For terminal interaction and file handling
- **Context Management**: For maintaining conversation and code context

### Data Flow

1. User input is processed by the `InputOutput` system
2. Commands are handled by the `Commands` class
3. Messages are sent to the LLM via the `Model` class
4. Responses are processed by the appropriate `Coder` implementation
5. File edits are applied and optionally committed via `GitRepo`

## Core Classes

### Coder Class Hierarchy

The `Coder` class (`base_coder.py`) is the central class in the system, with several specialized implementations:

```
Coder (base_coder.py)
├── EditBlockCoder (editblock_coder.py)
│   └── EditBlockFencedCoder (editblock_fenced_coder.py)
├── WholeFileCoder (wholefile_coder.py)
├── UnifiedDiffCoder (udiff_coder.py)
├── AskCoder (ask_coder.py)
├── ArchitectCoder (architect_coder.py)
├── ContextCoder (context_coder.py)
├── HelpCoder (help_coder.py)
└── EditorEditBlockCoder/EditorWholeFileCoder (editor variants)
```

Each coder implements a different approach to code editing:
- **EditBlockCoder**: Uses search/replace blocks for precise edits
- **WholeFileCoder**: Sends and receives entire files
- **UnifiedDiffCoder**: Uses unified diff format
- **AskCoder**: Just asks questions without making edits
- **ArchitectCoder**: Two-phase model with architect and editor
- **ContextCoder**: Identifies files needed for a task

#### Base Coder API

```python
class Coder:
    @classmethod
    def create(cls, main_model=None, edit_format=None, io=None, from_coder=None, **kwargs)
    
    def clone(self, **kwargs)
    def run(self, with_message=None, preproc=True)
    def run_one(self, user_message, preproc)
    def send_message(self, inp)
    def get_edits(self, mode="update")
    def apply_edits(self, edits)
    def apply_updates()
    def get_repo_map(self, force_refresh=False)
    def get_inchat_relative_files()
    def get_all_relative_files()
    def get_addable_relative_files()
    def add_rel_fname(self, rel_fname)
    def drop_rel_fname(self, fname)
```

### Other Key Classes

- **Commands** (`commands.py`): Processes user commands like `/add`, `/drop`, etc.
- **RepoMap** (`repomap.py`): Analyzes repository structure for context
- **InputOutput** (`io.py`): Handles terminal I/O and file operations
- **Model** (`models.py`): Represents an LLM and manages interactions
- **GitRepo** (`repo.py`): Handles git operations
- **ChatSummary** (`history.py`): Summarizes chat history to manage token usage

## Context Management

Context management is a crucial aspect of Aider, allowing it to maintain appropriate context for the LLM while managing token usage.

### File Context Handling

#### Adding Files to Context

Files can be added to the chat context through:

1. **Command Line Arguments**: When launching Aider
   ```bash
   aider file1.py file2.py
   ```

2. **`/add` Command**:
   ```
   /add path/to/file.py
   ```

Under the hood, this is handled by:
- `cmd_add` in `commands.py`, which calls:
- `coder.add_rel_fname()`, which adds the file path to `coder.abs_fnames`

```python
# In commands.py
def cmd_add(self, args):
    "Add files to the chat so aider can edit them or review them in detail"
    # [...implementation...]
    # Eventually calls:
    self.coder.add_rel_fname(rel_fname)
    
# In base_coder.py
def add_rel_fname(self, rel_fname):
    self.abs_fnames.add(self.abs_root_path(rel_fname))
    self.check_added_files()
```

When files are added to the context:
1. They are stored in `coder.abs_fnames`
2. Their content is included in the prompt sent to the LLM
3. The LLM can edit these files

#### Dropping Files from Context

Files can be removed from the context using the `/drop` command:
```
/drop path/to/file.py
```

Or to drop all files:
```
/drop
```

Under the hood:
- `cmd_drop` in `commands.py` handles this command
- It removes files from `coder.abs_fnames`

```python
# In commands.py
def cmd_drop(self, args=""):
    "Remove files from the chat session to free up context space"
    # [...implementation...]
    # Eventually calls:
    self.coder.drop_rel_fname(matched_file)
    
# In base_coder.py
def drop_rel_fname(self, fname):
    abs_fname = self.abs_root_path(fname)
    if abs_fname in self.abs_fnames:
        self.abs_fnames.remove(abs_fname)
        return True
```

#### Read-Only Files

Files can be added as read-only using the `/read-only` command:
```
/read-only path/to/file.py
```

These files:
- Are stored in `coder.abs_read_only_fnames` 
- Are included in the prompt for reference
- Cannot be edited by the LLM

### Repository Map

The `RepoMap` class analyzes the repository to provide context about the codebase structure:

```python
class RepoMap:
    def get_repo_map(self, chat_files, other_files, mentioned_fnames=None, 
                     mentioned_idents=None, force_refresh=False)
```

This creates a summary of:
- File structure
- Symbol definitions and references 
- Relationships between files

The repo map is included in the prompt to give the LLM context about files not directly included.

### Chat History Management

To manage token usage, Aider summarizes chat history using `ChatSummary`:

```python
class ChatSummary:
    def summarize(self, messages, depth=0)
```

This is triggered when:
- Chat history exceeds `max_chat_history_tokens`
- The estimated token count approaches the model's context limit

### Prompt Assembly

The complete context sent to the LLM is assembled in `format_messages()` using `ChatChunks`:

```python
def format_messages(self):
    chunks = self.format_chat_chunks()
    if self.add_cache_headers:
        chunks.add_cache_control_headers()
    
    return chunks

def format_chat_chunks(self):
    chunks = ChatChunks()
    chunks.system = [...]       # System prompt
    chunks.examples = [...]     # Example messages
    chunks.done = [...]         # Summarized chat history
    chunks.repo = [...]         # Repository map
    chunks.readonly_files = [...] # Read-only files
    chunks.chat_files = [...]   # Files in chat
    chunks.cur = [...]          # Current messages
    chunks.reminder = [...]     # System reminder
    return chunks
```

## Git Integration

Aider integrates with git to track and commit changes:

```python
class GitRepo:
    def __init__(self, io, fnames, git_dname, aider_ignore_file=None, 
                models=None, attribute_author=True, ...)
    
    def commit(self, fnames=None, context=None, message=None, aider_edits=False)
    def get_diffs(self, fnames=None)
    def diff_commits(self, pretty, from_commit, to_commit)
    def is_dirty(self, path=None)
    def get_tracked_files()
```

Key features:
- **Auto Commits**: LLM-generated changes can be automatically committed
- **Undo**: The `/undo` command can revert the last Aider-made commit
- **Diffs**: The `/diff` command shows changes since the last message

## LLM Integration

Aider interfaces with LLMs through the `Model` class:

```python
class Model(ModelSettings):
    def __init__(self, model, weak_model=None, editor_model=None, 
                editor_edit_format=None, verbose=False)
    
    def token_count(self, messages)
    def send_completion(self, messages, functions, stream, temperature=None)
    def simple_send_with_retries(self, messages)
```

Key aspects:
- Uses `litellm` to support multiple providers (OpenAI, Anthropic, etc.)
- Manages token counting and context windows
- Handles streaming responses
- Supports functions/tools for structured output

## Commands System

Aider implements a flexible command system through the `Commands` class:

```python
class Commands:
    def is_command(self, inp)
    def get_commands(self)
    def run(self, inp)
    def matching_commands(self, inp)
    # Plus individual command methods like cmd_add, cmd_drop, etc.
```

Commands provide functionality like:
- File management: `/add`, `/drop`, `/ls`, `/read-only`
- Git operations: `/commit`, `/diff`, `/undo`
- Context management: `/map`, `/tokens`
- Mode switching: `/ask`, `/code`, `/architect`
- Utilities: `/help`, `/web`, `/voice`, `/run`

## Configuration

Aider can be configured through:
- Command-line arguments
- Configuration files (YAML)
- Environment variables
- `.env` files

The configuration is handled in `args.py` using `configargparse`.

## Extending Aider

### Adding a New Coder

To implement a new editing format:

1. Create a new coder class that inherits from `Coder`
2. Implement required methods (`get_edits`, `apply_edits`)
3. Set `edit_format` class attribute
4. Add to `__all__` in `coders/__init__.py`

```python
class MyCoder(Coder):
    edit_format = "my-format"
    
    def get_edits(self, mode="update"):
        # Parse edits from LLM response
        
    def apply_edits(self, edits):
        # Apply the edits to files
```

### Adding a New Command

To add a new command:

1. Add a method named `cmd_xxx` to the `Commands` class
2. Provide a docstring for help text

```python
def cmd_mycommand(self, args):
    "Description of my command"
    # Implementation
```

This automatically creates a `/mycommand` command.

### Supporting a New LLM Provider

New providers can be added by:

1. Adding provider-specific settings to `model-settings.yml`
2. Ensuring `litellm` supports the provider
3. Optionally adding a model alias in `models.py`

### Creating a Custom Input/Output Handler

To customize I/O:

1. Subclass `InputOutput`
2. Override methods like `tool_output`, `tool_error`, etc.
3. Pass the custom I/O object to `Coder.create()`

```python
class MyInputOutput(InputOutput):
    def tool_output(self, msg, log_only=False):
        # Custom output handling
        
    def get_input(self, root, rel_fnames, addable_rel_fnames, commands, abs_read_only_fnames=None, edit_format=None):
        # Custom input handling
```
