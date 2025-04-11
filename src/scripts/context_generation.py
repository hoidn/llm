#!/usr/bin/env python3
"""
Context Generation Demo for an Actual Project

This demo uses your real project directory (which must be a git repository)
to demonstrate template‐aware context generation and file relevance matching.
It compares two scenarios that vary which input parameters affect the matching.

Usage:
    python src/scripts/context_generation.py <project_dir> [--query "Your query here"]

Example:
    python src/scripts/context_generation.py /path/to/your/project "Implement data processing feature"
"""

import os
import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import Any

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import required components from your application.
from memory.memory_system import MemorySystem
from memory.context_generation import ContextGenerationInput
from task_system.task_system import TaskSystem
# Import the REAL handler that can make LLM calls
from handler.passthrough_handler import PassthroughHandler
# Import the template registration function
from task_system.templates.associative_matching import register_template as register_associative_matching_template
# Ensure model provider is available
from handler.model_provider import ClaudeProvider


console = Console()

def initialize_components(project_dir: str):
    """
    Initialize the TaskSystem, MemorySystem, and PassthroughHandler, and index the project.

    Args:
        project_dir: The absolute path to your actual project directory.

    Returns:
        A tuple: (task_system, memory_system, handler)
    """
    # Initialize task and memory systems.
    task_system = TaskSystem()
    # Pass task_system to MemorySystem constructor
    memory_system = MemorySystem(task_system=task_system)
    
    # Instantiate the real PassthroughHandler that can make LLM calls
    try:
        handler = PassthroughHandler(task_system, memory_system)
        console.print("[green]Instantiated PassthroughHandler.[/green]")
    except Exception as e:
        console.print(f"[red]Error instantiating PassthroughHandler: {e}[/red]")
        console.print("[yellow]Ensure necessary API keys (e.g., ANTHROPIC_API_KEY) are set.[/yellow]")
        sys.exit(1)
        
    # Pass handler reference to memory system
    memory_system.handler = handler
    # Allow TaskSystem to access MemorySystem if needed
    task_system.memory_system = memory_system

    # Register the necessary template
    register_associative_matching_template(task_system)
    console.print("[bold green]Registered associative matching template.[/bold green]")

    console.print(f"[bold]Indexing project files in:[/bold] {project_dir}")

    # Use the GitRepositoryIndexer via memory_system. Adjust patterns as needed.
    try:
        # Ensure memory_system has the index_git_repository method or handle appropriately
        if hasattr(memory_system, 'index_git_repository'):
             memory_system.index_git_repository(project_dir, {
                "include_patterns": ["**/*.py", "**/*.md"], # Include Python and Markdown files
                "exclude_patterns": [
                    "**/__pycache__/**",
                    "**/.git/**",
                    "**/node_modules/**", # Example exclude
                    "**/venv/**",       # Example exclude
                    "**/.venv/**"      # Example exclude
                    ]
             })
        else:
            # Fallback or error if MemorySystem doesn't directly support indexing
            console.print("[yellow]Warning: MemorySystem does not have index_git_repository. Manual indexing might be required.[/yellow]")
            # Example of manual indexing if needed:
            # from memory.indexers.git_repository_indexer import GitRepositoryIndexer
            # indexer = GitRepositoryIndexer(project_dir)
            # indexer.include_patterns = ["**/*.py"]
            # file_metadata = indexer.index_repository(memory_system) # Pass memory_system here
            # # No need to call update_global_index again if indexer calls it
            # console.print(f"Manually indexed {len(file_metadata)} files.")


    except Exception as e:
        console.print(f"[red]Error indexing repository: {e}[/red]")
        import traceback
        traceback.print_exc() # Print full traceback for debugging
        sys.exit(1)

    return task_system, memory_system, handler

def run_scenario(scenario_name: str, query: str, inputs: dict, context_relevance: dict,
                 memory_system: MemorySystem, project_dir: str) -> Any:
    """
    Run one context-generation scenario using the actual project index.

    Args:
        scenario_name: Name for the scenario.
        query: The task query.
        inputs: Dictionary of input parameters.
        context_relevance: Dictionary specifying which inputs affect the matching.
        memory_system: MemorySystem instance.
        project_dir: Absolute project directory (for relative file display).

    Returns:
        The context result (object with 'matches' attribute).
    """
    console.print(f"\n[bold blue]Scenario: {scenario_name}[/bold blue]")

    context_input = ContextGenerationInput(
        template_description=query,
        inputs=inputs,
        context_relevance=context_relevance
    )

    # Call the memory system to get context
    result = memory_system.get_relevant_context_for(context_input)

    # Display query
    console.print(Panel(f"[bold]Query:[/bold] {query}"))

    # Display the parameters and whether they were included in the matching context.
    param_table = Table(title="Context Parameters", header_style="bold magenta")
    param_table.add_column("Parameter", style="cyan")
    param_table.add_column("Value")
    param_table.add_column("Included in Context")

    for key, value in inputs.items():
        include_flag = context_relevance.get(key, True) # Default to True if not specified
        param_table.add_row(key, str(value), "[green]Yes[/green]" if include_flag else "[red]No[/red]")

    console.print(param_table)

    # Display matched files; assume each match is a tuple: (file_path, relevance_string)
    files_table = Table(title="Relevant Files", header_style="bold cyan")
    files_table.add_column("File", min_width=30)
    files_table.add_column("Relevance Reason", min_width=50) # Updated column name

    # Check if result has 'matches' and it's iterable
    if hasattr(result, 'matches') and result.matches:
        for match in result.matches:
             # Check if match is a tuple/list with at least 2 elements
            if isinstance(match, (list, tuple)) and len(match) >= 2:
                 file_path = match[0]
                 relevance = match[1]
                 # Convert file path to a relative path (for cleaner output)
                 try:
                    rel_path = os.path.relpath(file_path, project_dir)
                 except ValueError:
                    rel_path = file_path # Keep absolute if relpath fails (e.g., different drive on Windows)
                 files_table.add_row(rel_path, relevance)
            else:
                console.print(f"[yellow]Warning: Unexpected match format: {match}[/yellow]")
    else:
        # Add a row indicating no files were found if the table would be empty
         files_table.add_row("[grey]No relevant files found[/grey]", "[grey]-[/grey]")


    console.print(files_table)

    return result

def compare_scenarios(scen1: dict, scen2: dict, memory_system: MemorySystem, project_dir: str):
    """
    Compare two scenarios and print a summary of the differences.

    Args:
        scen1: First scenario dictionary.
        scen2: Second scenario dictionary.
        memory_system: MemorySystem instance.
        project_dir: Project directory (to relativize paths).
    """
    result1 = run_scenario(
        scen1["name"],
        scen1["query"],
        scen1["inputs"],
        scen1["context_relevance"],
        memory_system,
        project_dir
    )

    result2 = run_scenario(
        scen2["name"],
        scen2["query"],
        scen2["inputs"],
        scen2["context_relevance"],
        memory_system,
        project_dir
    )

    # Collect file paths (as absolute paths) from each result.
    files1 = set()
    files2 = set()
    if hasattr(result1, 'matches') and result1.matches:
        files1 = {match[0] for match in result1.matches if isinstance(match, (list, tuple)) and len(match) > 0}
    if hasattr(result2, 'matches') and result2.matches:
         files2 = {match[0] for match in result2.matches if isinstance(match, (list, tuple)) and len(match) > 0}


    console.print("\n[bold]Comparison:[/bold]")
    if files1 == files2:
        console.print("[yellow]Both scenarios returned the same set of files.[/yellow]")
    else:
        only_in_1 = files1 - files2
        only_in_2 = files2 - files1

        if only_in_1:
            console.print(f"[green]Files only in '{scen1['name']}':[/green]")
            for file in sorted(list(only_in_1)): # Sort for consistent output
                try:
                     console.print(f"  - {os.path.relpath(file, project_dir)}")
                except ValueError:
                     console.print(f"  - {file}") # Print absolute if relpath fails
        if only_in_2:
            console.print(f"[green]Files only in '{scen2['name']}':[/green]")
            for file in sorted(list(only_in_2)): # Sort for consistent output
                 try:
                     console.print(f"  - {os.path.relpath(file, project_dir)}")
                 except ValueError:
                     console.print(f"  - {file}") # Print absolute if relpath fails

    console.print("\n[bold]Analysis:[/bold]")
    console.print(scen1.get("explanation", "No explanation provided."))

def main():
    parser = argparse.ArgumentParser(description="Context Generation Demo for Actual Projects")
    parser.add_argument("project_dir", help="Path to your project directory (must be a git repository)")
    parser.add_argument("--query", help="Query to search for relevant files",
                        default="Implement data processing feature")
    args = parser.parse_args()

    # Check for API key early if using ClaudeProvider
    if not os.environ.get("ANTHROPIC_API_KEY"):
         console.print("[yellow]Warning: ANTHROPIC_API_KEY environment variable not set. LLM calls may fail.[/yellow]")

    project_dir = os.path.abspath(args.project_dir)
    # Basic validation for project_dir
    if not os.path.isdir(project_dir):
        console.print(f"[red]Error: Project directory not found: {project_dir}[/red]")
        sys.exit(1)
    if not os.path.isdir(os.path.join(project_dir, ".git")):
         console.print(f"[red]Error: Directory is not a git repository: {project_dir}[/red]")
         sys.exit(1)

    query = args.query

    task_system, memory_system, handler = initialize_components(project_dir)

    # Define two scenarios with adjusted parameters.
    # (Replace these parameter names and values with ones relevant to your project.)
    scenario_inclusive = {
        "name": "Core Feature – Inclusive Context",
        "query": query,
        "inputs": {
            "feature": "AST node construction",
            "module": "task_system",      # Include all modules
            "max_results": 10
        },
        "context_relevance": {
            "feature": True,
            "module": True,
            "max_results": True # Even though True, it's excluded by template's context_relevance setting
        },
        "explanation": ("In this scenario, all parameters are marked as relevant in the input, "
                        "but the 'associative_matching' template itself might ignore some (like max_results) "
                        "for the *purpose of finding context*. "
                        "This may return a broader set of files if 'module' metadata matches.")
    }

    scenario_selective = {
        "name": "Core Feature – Selective Context",
        "query": query,
        "inputs": {
            "feature": "AST node construction",
            "module": "handler",
            "max_results": 10
        },
        "context_relevance": {
            "feature": True,
            "module": False,       # Exclude the 'module' input from influencing matches
            "max_results": False   # Exclude max_results (it only limits output, not content)
        },
        "explanation": ("This scenario selectively uses only the 'feature' parameter to match files "
                        "by setting context_relevance explicitly. "
                        "It should focus results more tightly on the core feature description.")
    }

    console.print("[bold underline green]Comparing Two Context Generation Scenarios[/bold underline green]")
    compare_scenarios(scenario_inclusive, scenario_selective, memory_system, project_dir)

    console.print(f"\nDemo complete. Project indexed from: {project_dir}")

if __name__ == "__main__":
    main()
