import logging
from typing import Any, Dict, List, Optional

# Assuming Application and WorkflowStepDefinition are imported from relevant places
# from src.main import Application # Actual import will depend on final structure
from src.system.models import WorkflowStepDefinition, TaskResult # Assuming TaskResult is the type for step results

logger = logging.getLogger(__name__)

class PythonWorkflowManager:
    """
    Manages the execution of multi-step workflows defined programmatically in Python.
    Implements the contract defined in src/orchestration/python_workflow_manager_IDL.md.
    """

    def __init__(self, app_or_dispatcher_instance: Any):
        """
        Initializes the PythonWorkflowManager.
        Args:
            app_or_dispatcher_instance: An instance of the Application or a Dispatcher
                                         that can handle task execution.
        """
        self.app_or_dispatcher = app_or_dispatcher_instance
        self.workflow_steps: List[WorkflowStepDefinition] = []
        self.workflow_context: Dict[str, TaskResult] = {} # Stores TaskResult objects or dicts
        logger.info("PythonWorkflowManager initialized.")

    def add_step(self, step_definition: WorkflowStepDefinition) -> None:
        """
        Adds a step to the current workflow definition.
        Args:
            step_definition: A WorkflowStepDefinition object.
        """
        self.workflow_steps.append(step_definition)
        logger.debug(f"Added step: {step_definition.task_name} (output: {step_definition.output_name})")

    async def run(self) -> Dict[str, Any]: # Return type matches demo script expectation
        """
        Executes the defined workflow sequentially.
        Returns:
            A dictionary containing the results of all steps, keyed by their output_name.
        """
        logger.info(f"Running workflow with {len(self.workflow_steps)} steps.")
        self.workflow_context = {} # Reset context for each run

        for i, step_def in enumerate(self.workflow_steps):
            logger.info(f"Executing step {i+1}/{len(self.workflow_steps)}: {step_def.task_name} -> {step_def.output_name}")
            
            current_step_inputs: Dict[str, Any] = {}
            if step_def.static_inputs:
                current_step_inputs.update(step_def.static_inputs)
            
            if step_def.dynamic_input_mappings:
                for target_param, source_path in step_def.dynamic_input_mappings.items():
                    source_step_name, *field_parts = source_path.split('.', 1)
                    field_path = field_parts[0] if field_parts else None

                    if source_step_name not in self.workflow_context:
                        logger.error(f"Dynamic input error: Source step '{source_step_name}' not found in context for step '{step_def.task_name}'.")
                        # Create a FAILED TaskResult for this step
                        failed_task_result = TaskResult(
                            status="FAILED", 
                            content=f"Missing dynamic input from {source_step_name}", 
                            notes={} # Ensure notes is a dict
                        )
                        self.workflow_context[step_def.output_name] = failed_task_result
                        # Optionally, re-raise or stop workflow execution here
                        # For now, we'll let it continue to the next step or finish,
                        # but the current step's result will be FAILED.
                        # To stop immediately:
                        # logger.error("Workflow execution stopped due to missing dynamic input.")
                        # return {k: (v.model_dump(exclude_none=True) if isinstance(v, TaskResult) else v) for k, v in self.workflow_context.items()}
                        continue # Skip to next dynamic input mapping or next step if this was critical

                    source_task_result_obj = self.workflow_context[source_step_name]
                    
                    value_to_map = None
                    # Ensure source_task_result_obj is a TaskResult Pydantic model before accessing attributes
                    if not isinstance(source_task_result_obj, TaskResult):
                        logger.error(f"Source task result for '{source_step_name}' is not a TaskResult object. Type: {type(source_task_result_obj)}")
                        # Create a FAILED TaskResult for this step
                        failed_task_result = TaskResult(
                            status="FAILED", 
                            content=f"Invalid source data type from {source_step_name}", 
                            notes={}
                        )
                        self.workflow_context[step_def.output_name] = failed_task_result
                        continue

                    if field_path:
                        current_val_attr = source_task_result_obj
                        for part in field_path.split('.'):
                            if isinstance(current_val_attr, dict) and part in current_val_attr: # Check dict first
                                current_val_attr = current_val_attr[part]
                            elif hasattr(current_val_attr, part): # Then check attribute
                                current_val_attr = getattr(current_val_attr, part)
                            else:
                                logger.error(f"Dynamic input error: Path '{field_path}' not found in result of step '{source_step_name}'.")
                                current_val_attr = None
                                break
                        value_to_map = current_val_attr
                    else: 
                        # Default to content if no specific field_path
                        value_to_map = source_task_result_obj.content


                    if value_to_map is not None:
                        current_step_inputs[target_param] = value_to_map
                    else:
                        logger.warning(f"Could not resolve dynamic input '{source_path}' for param '{target_param}' in step '{step_def.task_name}'.")
                        # Potentially mark step as failed if input is critical and missing

            step_result_obj: Optional[TaskResult] = None
            try:
                if hasattr(self.app_or_dispatcher, 'handle_task_command'):
                    raw_result = await self.app_or_dispatcher.handle_task_command(
                        identifier=step_def.task_name,
                        params=current_step_inputs
                        # flags might be needed if your handle_task_command expects it
                    )
                    if isinstance(raw_result, TaskResult):
                        step_result_obj = raw_result
                    elif isinstance(raw_result, dict): # If it returns a dict, try to parse
                        step_result_obj = TaskResult.model_validate(raw_result)
                    else:
                        logger.error(f"Unexpected result type from handle_task_command: {type(raw_result)}")
                        step_result_obj = TaskResult(status="FAILED", content="Invalid result type from task execution", notes={})
                else:
                    logger.error(f"Cannot execute task '{step_def.task_name}': app_or_dispatcher has no suitable execution method.")
                    step_result_obj = TaskResult(status="FAILED", content="Dispatcher method not found", notes={})

            except Exception as e:
                logger.exception(f"Error executing step '{step_def.task_name}': {e}")
                step_result_obj = TaskResult(status="FAILED", content=str(e), notes={"error_details": str(e)})
            
            self.workflow_context[step_def.output_name] = step_result_obj
            logger.debug(f"Step '{step_def.task_name}' result stored as '{step_def.output_name}': {str(step_result_obj)[:100]}...")

            if step_result_obj and step_result_obj.status == "FAILED":
                logger.error(f"Workflow execution stopped at step '{step_def.task_name}' due to failure.")
                break # Stop workflow on first failure
                
        logger.info("Workflow execution finished.")
        # The demo script expects a dictionary of dictionaries/TaskResult objects
        return {k: (v.model_dump(exclude_none=True) if isinstance(v, TaskResult) else v) for k, v in self.workflow_context.items()}


    def clear_workflow(self) -> None:
        """Clears the current workflow definition and context."""
        self.workflow_steps = []
        self.workflow_context = {}
        logger.info("Workflow cleared.")

    def get_step_result(self, output_name: str) -> Optional[TaskResult]:
        """
        Retrieves the result of a specific step by its output name.
        Args:
            output_name: The output_name of the step whose result is needed.
        Returns:
            The TaskResult of the step, or None if not found or not a TaskResult.
        """
        result = self.workflow_context.get(output_name)
        if isinstance(result, TaskResult):
            return result
        elif isinstance(result, dict) and "status" in result and "content" in result : # Basic check
            try:
                # Attempt to validate if it looks like a TaskResult dict
                return TaskResult.model_validate(result)
            except Exception:
                logger.warning(f"Could not validate dict as TaskResult for step '{output_name}'")
        return None
