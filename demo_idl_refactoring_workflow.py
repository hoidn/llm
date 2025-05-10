"""
Demo script for an IDL Refactoring Workflow using PythonWorkflowManager.

Purpose:
Demonstrates a multi-step workflow that simulates refactoring IDL files based on an
architectural goal. It involves:
1. Initial context gathering (finding relevant IDLs based on a query).
2. Priming context with these IDLs.
3. Generating a phased implementation plan using an LLM.
4. Iteratively "executing" each plan step:
    a. Clearing previous context.
    b. Priming context relevant to the current plan step (e.g., a specific IDL file).
    c. Using an LLM to generate "changes" for the target IDL based on the plan step.
    (Note: This demo does not actually modify files; it simulates the process.)

Prerequisites:
- Python environment with project dependencies installed.
- An LLM provider configured (e.g., via environment variables for API keys)
  that the Application's PassthroughHandler can use.
- The Application and its underlying components (MemorySystem, TaskSystem, Handlers,
  PythonWorkflowManager, system:get_context, system:prime_handler_data_context,
  system:clear_handler_data_context, user:passthrough_query tasks) must be functional.

Setup:
- The script creates a subdirectory named 'demo_idls' next to itself and populates
  it with sample IDL files if they don't exist.
- Ensure the Application's FileAccessManager (especially the one used by MemorySystem
  for indexing) has a base_path that allows it to "see" and index the
  'demo_idls' directory. The script attempts to configure this.

Usage:
Run from the project root directory:
  python demo_idl_refactoring_workflow.py
(Or adjust PROJECT_ROOT if run from elsewhere, though 'scripts/' subdir is assumed)
"""
import asyncio
import json
import logging
import os
import sys

# --- BEGIN FIX: Apply nest_asyncio ---
try:
    import nest_asyncio
    nest_asyncio.apply()
    # Optional: Add a print or log statement for confirmation
    print("INFO: nest_asyncio.apply() called successfully at script startup.")
except ImportError:
    print("WARNING: nest_asyncio library not found. Event loop errors may occur.")
except Exception as e:
    print(f"WARNING: An error occurred while applying nest_asyncio: {e}")
# --- END FIX ---

from typing import List, Dict, Any, Optional # Added Optional

# Add project root to sys.path to allow imports from src
# This assumes the script is run from the project root or a 'scripts/' subdirectory.
# Adjust if the script is placed elsewhere.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.main import Application
# Ensure this path is correct for your project structure
from src.orchestration.python_workflow_manager import PythonWorkflowManager
from src.system.models import WorkflowStepDefinition, TaskResult, AssociativeMatchResult, MatchItem

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__) # Script-level logger

# Define Constants
DEMO_IDLS_DIR_NAME = "demo_idls" # Just the subdir name
# Full path will be relative to the script's location
BASE_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEMO_IDLS_FULL_PATH = os.path.join(BASE_SCRIPT_DIR, DEMO_IDLS_DIR_NAME)

ARCHITECTURAL_TASK_GOAL = "Refactor BaseHandler to use a new DataContext object for managing file context, separating it from conversation history. Update relevant dependent IDLs."
INITIAL_IDL_SEARCH_QUERY = "IDL files related to BaseHandler context management and MemorySystem interactions"

LLM_PLAN_GENERATION_PROMPT_TEMPLATE = """
Given the following IDL files as context:
[Context will be automatically injected by PassthroughHandler from primed DataContext]

And the architectural refactoring goal:
"{refactoring_goal}"

Please generate a detailed, phased implementation plan.
Each phase should clearly state:
1. Phase Title (e.g., "Phase 1: Define DataContext Structure")
2. Specific IDL files to be modified in this phase.
3. A concise summary of changes for each file in that phase.
4. The primary deliverable/outcome of the phase.

Output the plan in a numbered list format for phases. For example:
Phase 1: Title
- Files: file1_IDL.md, file2_IDL.md
- Summary:
    - file1_IDL.md: Add new method X.
    - file2_IDL.md: Update parameter Y in method Z.
- Deliverable: Updated IDL specifications for DataContext.

Phase 2: Title
...
"""

LLM_STEP_EXECUTION_PROMPT_TEMPLATE = """
Current Implementation Plan Step:
"{current_plan_step_details}"

Relevant Context (if any):
[Context from primed DataContext, potentially including a specific IDL file mentioned in the plan step]

Based on this step, what are the precise changes needed for the file '{target_file_for_this_step}'?
Provide the changes in a clear, actionable format. If the step is about analysis, list key considerations.
"""

# II. Helper Functions
def create_sample_idls(base_dir_for_idls_subdir: str):
    """Creates sample IDL files in a subdirectory if they don't exist."""
    idl_dir = base_dir_for_idls_subdir # Already constructed as DEMO_IDLS_FULL_PATH
    os.makedirs(idl_dir, exist_ok=True)

    base_handler_content = "module src.handler.base_handler { interface BaseHandler { void __init__(object task_system, object memory_system); string _build_system_prompt(optional string template_specific_instructions); void prime_data_context(optional string query, optional list<string> initial_files); void clear_data_context(); } }"
    memory_system_content = "module src.memory.memory_system { interface MemorySystem { object get_relevant_context_for(object input_data); } struct MatchItem { id: string; content: string; relevance_score: float; content_type: string; source_path: optional string; } struct AssociativeMatchResult { context_summary: string; matches: list<MatchItem>; error: optional string; } }"
    types_content = "module docs.system.contracts.types { struct DataContext { retrieved_at: string; items: list<MatchItem>; } struct MatchItem { id: string; content: string; } }" # Simplified MatchItem for demo

    sample_idls = {
        "base_handler_IDL.md": base_handler_content,
        "memory_system_IDL.md": memory_system_content,
        "types_IDL.md": types_content
    }

    for filename, content in sample_idls.items():
        file_path = os.path.join(idl_dir, filename)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write(content)
            logger.info(f"Created sample IDL: {file_path}")
        else:
            logger.info(f"Sample IDL already exists: {file_path}")

def parse_llm_plan(plan_str: str) -> List[str]:
    """Simplified parsing of LLM plan into phases for demo."""
    logger.info(f"Raw LLM Plan:\n{plan_str}")
    if not plan_str:
        return []
    
    phases = []
    potential_phases = plan_str.split('\n')
    current_phase_lines = []
    for line in potential_phases:
        if line.strip().lower().startswith("phase ") and ":" in line:
            if current_phase_lines: # Save previous phase
                phases.append("\n".join(current_phase_lines).strip())
            current_phase_lines = [] # Reset for new phase
        if line.strip(): # Collect non-empty lines for the current phase
            current_phase_lines.append(line)
    
    if current_phase_lines: # Save the last phase
         phases.append("\n".join(current_phase_lines).strip())

    if not phases: # Fallback if no "Phase X:" found
        logger.warning("Could not parse distinct phases. Treating entire plan as one step.")
        return [plan_str.strip()]
        
    logger.info(f"Parsed {len(phases)} plan phases.")
    return phases

def determine_target_file_and_context_for_plan_step(plan_step_details: str, demo_idls_path: str) -> Dict[str, Any]:
    """Determines target file and context parameters for a plan step."""
    logger.info(f"Determining context for plan step: {plan_step_details[:100]}...")
    target_file = None
    context_params: Dict[str, Any] = {"initial_files": [], "query": None} # Ensure type for initial_files

    plan_step_details_lower = plan_step_details.lower()

    if "types.md" in plan_step_details_lower or "datacontext" in plan_step_details_lower or "matchitem" in plan_step_details_lower:
        target_file = os.path.join(demo_idls_path, "types_IDL.md")
        if target_file not in context_params["initial_files"]:
             context_params["initial_files"].append(target_file)
    elif "basehandler" in plan_step_details_lower or "base_handler_idl.md" in plan_step_details_lower:
        target_file = os.path.join(demo_idls_path, "base_handler_IDL.md")
        if target_file not in context_params["initial_files"]:
            context_params["initial_files"].append(target_file)
    elif "memorysystem" in plan_step_details_lower or "memory_system_idl.md" in plan_step_details_lower:
        target_file = os.path.join(demo_idls_path, "memory_system_IDL.md")
        if target_file not in context_params["initial_files"]:
            context_params["initial_files"].append(target_file)

    if not context_params["initial_files"]: # No specific file identified for priming
        context_params["query"] = plan_step_details # Use the whole step as a query
        logger.info("No specific IDL file identified for priming; using plan step as query.")
    
    if target_file is None: # Default for demo if no specific target identified
        target_file = os.path.join(demo_idls_path, "types_IDL.md")
        logger.info(f"Target file heuristically defaulted to: {target_file}")
        # Optionally add this default to context_params if not already there
        if target_file not in context_params["initial_files"] and context_params["query"] is None:
            context_params["initial_files"].append(target_file)


    logger.info(f"Determined target file: {target_file}, context_params: {context_params}")
    return {"target_file": target_file, "context_params": context_params}

# III. Main Asynchronous Function
async def main():
    """Main asynchronous function to run the demo workflow."""
    create_sample_idls(DEMO_IDLS_FULL_PATH)

    logger.info("Initializing Application and PythonWorkflowManager...")
    app_config = {
        "memory_system": { # This structure depends on how Application parses config
            "file_access_manager_config": {
                "base_path": BASE_SCRIPT_DIR # Allow FAM to see demo_idls subdir
            }
        },
        # Ensure your LLM provider (e.g., Anthropic) API key is set in the environment
        # or add relevant LLM provider config here if Application expects it.
        # Example for Anthropic if Application supports direct config:
        # "llm_providers": {
        #     "anthropic": {
        #         "api_key": os.environ.get("ANTHROPIC_API_KEY"), # Or hardcode for isolated demo
        #         "default_model": "claude-3-opus-20240229" # Or your preferred model
        #     }
        # },
        # "default_model_identifier": "anthropic:claude-3-opus-20240229" # If app uses this
    }
    app = Application(config=app_config)
    workflow_manager = PythonWorkflowManager(app_or_dispatcher_instance=app)
    logger.info("Application and PythonWorkflowManager initialized.")

    logger.info(f"Indexing demo IDL directory: {DEMO_IDLS_FULL_PATH}")
    # Assuming app.index_repository is synchronous and logs its own status
    # If it's async: await app.index_repository(DEMO_IDLS_FULL_PATH)
    # If it returns a TaskResult, you might want to check its status.
    # For this demo, we'll assume it's called and proceeds.
    app.index_repository(DEMO_IDLS_FULL_PATH) # Adjusted based on typical signature
    logger.info("Demo IDL directory indexing initiated/completed.")

    # Part A: Initial Context Gathering and Plan Generation
    logger.info("\n--- Starting Part A: Initial Context Gathering and Plan Generation ---")
    workflow_manager.clear_workflow()

    # Step 1: Find Relevant IDLs
    step1_def = WorkflowStepDefinition(
        task_name="system_get_context", # This task should be registered in Application
        static_inputs={"query": INITIAL_IDL_SEARCH_QUERY},
        output_name="found_idls_result"
    )
    workflow_manager.add_step(step1_def)
    logger.info(f"Running Step 1: Find relevant IDLs with query: '{INITIAL_IDL_SEARCH_QUERY}'")
    pt1_context = workflow_manager.run()
    logger.info(f"Step 1 Result Context: {pt1_context}")

    found_idls_task_result_dict = pt1_context.get("found_idls_result")
    idl_paths_to_prime: List[str] = []
    if found_idls_task_result_dict and found_idls_task_result_dict.get("status") == "COMPLETE":
        parsed_content_dict = found_idls_task_result_dict.get("parsedContent")
        if parsed_content_dict:
            try:
                assoc_match_result = AssociativeMatchResult.model_validate(parsed_content_dict)
                if assoc_match_result.matches:
                    for item in assoc_match_result.matches:
                        if item.id: # Ensure id is not None
                            idl_paths_to_prime.append(item.id)
                    logger.info(f"Extracted IDL paths to prime: {idl_paths_to_prime}")
                else:
                    logger.warning("No matches found in AssociativeMatchResult from system:get_context.")
            except Exception as e:
                logger.error(f"Error validating/processing parsedContent from system:get_context: {e}")
        else:
            logger.warning("system:get_context did not return parsedContent.")
    else:
        logger.error(f"Step 1 (system:get_context) failed or missing. Result: {found_idls_task_result_dict}")

    if not idl_paths_to_prime:
        logger.warning("No IDL paths extracted to prime. Using all sample IDLs as fallback for demo.")
        if os.path.exists(DEMO_IDLS_FULL_PATH):
            idl_paths_to_prime = [os.path.join(DEMO_IDLS_FULL_PATH, f) for f in os.listdir(DEMO_IDLS_FULL_PATH) if f.endswith("_IDL.md")]
        if not idl_paths_to_prime:
            logger.error("Fallback failed: No IDL files found in demo_idls directory. Cannot generate plan. Exiting.")
            return
    
    workflow_manager.clear_workflow() # Clear previous step

    # Step 2: Prime Context with Found IDLs
    step2_def = WorkflowStepDefinition(
        task_name="system_prime_handler_data_context", # This task should be registered
        static_inputs={"initial_files": idl_paths_to_prime},
        output_name="idls_primed_result"
    )
    workflow_manager.add_step(step2_def)

    # Step 3: Generate Phased Implementation Plan
    # The user:generate-plan task template in src/main.py expects 'user_prompts' and 'initial_context'.
    # The ARCHITECTURAL_TASK_GOAL will be our 'user_prompts'.
    # The primed data context (which is implicitly available to the LLM via the handler
    # when user:generate-plan is executed) will serve as the 'initial_context'.
    # The LLM_PLAN_GENERATION_PROMPT_TEMPLATE is not directly used here as the
    # user:generate-plan task's own template contains the detailed instructions for the LLM.

    # We need to ensure the primed context from Step 2 is available to the 'user:generate-plan' task.
    # The PassthroughHandler, when executing an atomic task that calls an LLM,
    # should automatically use its primed self.data_context to build the system prompt.
    # So, we just need to provide the 'user_prompts' (our goal) and 'initial_context' (a reference or summary).
    # For 'initial_context', we can pass a placeholder string, as the actual IDL content
    # is already in the handler's data_context due to the preceding prime_handler_data_context step.
    # The 'user:generate-plan' template in main.py uses {{initial_context}} in its prompt.
    # The PassthroughHandler's _build_system_prompt will inject the actual primed data.

    step3_def = WorkflowStepDefinition(
        task_name="user:generate-plan", # Use the registered task for plan generation
        static_inputs={
            "user_prompts": ARCHITECTURAL_TASK_GOAL,
            # The 'initial_context' param for 'user:generate-plan' task template
            # will be supplemented by the handler's primed data_context.
            # We can provide a brief reference here.
            "initial_context": "Refactoring IDL files. Context provided in primed data context."
        },
        output_name="generated_plan_result"
    )
    workflow_manager.add_step(step3_def)

    logger.info("Running Steps 2 & 3: Prime context with IDLs and Generate Plan...")
    pt2_context = workflow_manager.run()
    logger.info(f"Steps 2 & 3 Result Context: {pt2_context}")

    generated_plan_task_result_dict = pt2_context.get("generated_plan_result")
    implementation_plan_str: Optional[str] = None
    if generated_plan_task_result_dict and generated_plan_task_result_dict.get("status") == "COMPLETE":
        implementation_plan_str = generated_plan_task_result_dict.get("content")
        logger.info(f"Generated Implementation Plan:\n{implementation_plan_str}")
    else:
        logger.error(f"Plan generation failed. Result: {generated_plan_task_result_dict}")
        logger.info("Stopping demo due to plan generation failure.")
        return

    parsed_plan_phases = parse_llm_plan(implementation_plan_str) if implementation_plan_str else []
    if not parsed_plan_phases:
        logger.warning("LLM Plan parsing yielded no phases or plan was empty. Using hardcoded phases for demo loop.")
        parsed_plan_phases = [
            "Phase 1: Define DataContext struct in types_IDL.md and update AssociativeMatchResult to use MatchItem.",
            "Phase 2: Refactor BaseHandler in base_handler_IDL.md to use DataContext for primed context, separating from conversation_history.",
            "Phase 3: Update MemorySystem in memory_system_IDL.md to ensure get_relevant_context_for returns AssociativeMatchResult with MatchItems."
        ]

    # Part B: Iterative Execution of Plan Steps (Loop)
    logger.info("\n--- Starting Part B: Iterative Execution of Plan Steps ---")
    for i, plan_step_details in enumerate(parsed_plan_phases[:2]): # Demo first 2 phases for brevity
        logger.info(f"\n--- Executing Plan Step {i+1}: {plan_step_details[:150]}... ---")
        workflow_manager.clear_workflow()

        # Step 4 (Loop Iteration): Clear Previous Context
        step4_def = WorkflowStepDefinition(
            task_name="system_clear_handler_data_context", # This task should be registered
            static_inputs={}, 
            output_name=f"context_cleared_step{i+1}"
        )
        workflow_manager.add_step(step4_def)
        
        # Python Glue: Determine Context for Current Plan Step
        step_details = determine_target_file_and_context_for_plan_step(plan_step_details, DEMO_IDLS_FULL_PATH)
        target_file_for_this_step = step_details["target_file"]
        current_step_context_params = step_details["context_params"]
        logger.info(f"Context for step {i+1}: Target file='{target_file_for_this_step}', Params='{current_step_context_params}'")

        # Step 5 (Loop Iteration): Prime Context for Current Plan Step
        step5_def = WorkflowStepDefinition(
            task_name="system_prime_handler_data_context",
            static_inputs=current_step_context_params,
            output_name=f"step{i+1}_context_primed"
        )
        workflow_manager.add_step(step5_def)

        # Step 6 (Loop Iteration): "Execute" Plan Step (LLM generates changes)
        step_execution_prompt = LLM_STEP_EXECUTION_PROMPT_TEMPLATE.format(
            current_plan_step_details=plan_step_details,
            target_file_for_this_step=os.path.basename(target_file_for_this_step) if target_file_for_this_step else "relevant IDL"
        )
        step6_def = WorkflowStepDefinition(
            task_name="user:passthrough_query",
            static_inputs={"query": step_execution_prompt},
            output_name=f"step{i+1}_execution_result"
        )
        workflow_manager.add_step(step6_def)

        logger.info(f"Running workflow for plan step {i+1} (Clear, Prime, Execute)...")
        loop_iter_context = workflow_manager.run()
        logger.info(f"Plan step {i+1} Result Context: {loop_iter_context}")

        step_execution_task_result_dict = loop_iter_context.get(f"step{i+1}_execution_result")
        if step_execution_task_result_dict and step_execution_task_result_dict.get("status") == "COMPLETE":
            step_output_content = step_execution_task_result_dict.get("content")
            logger.info(f"LLM Output for Plan Step {i+1} (Simulated IDL Changes/Analysis):\n{step_output_content}")
        else:
            logger.error(f"Execution of plan step {i+1} failed. Result: {step_execution_task_result_dict}")
            # Optionally break or continue demo loop on failure

    # Final Cleanup (Optional)
    logger.info("\n--- Demo Workflow Complete. Optional Final Cleanup ---")
    workflow_manager.clear_workflow()
    final_clear_def = WorkflowStepDefinition(
        task_name="system_clear_handler_data_context",
        static_inputs={},
        output_name="final_context_cleared"
    )
    workflow_manager.add_step(final_clear_def)
    final_clear_context_result = workflow_manager.run()
    logger.info(f"Final context clear result: {final_clear_context_result}")
    logger.info("--- End of Demo ---")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"Demo script encountered a critical error: {e}", exc_info=True)
