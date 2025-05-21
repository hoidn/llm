import logging
from typing import Dict, Any, List, Optional

# Ensure src.main.Application can be imported.
# If src is not in PYTHONPATH, this might need adjustment based on execution context.
# Assuming standard project structure where src is discoverable.
from src.main import Application
from src.system.models import DevelopmentPlan, TaskResult, CombinedAnalysisResult


class CodingWorkflowOrchestrator:
    def __init__(self,
                 app: Application,
                 initial_goal: str,
                 initial_context: str,
                 test_command: str,
                 max_retries: int = 3):
        self.app = app
        self.initial_goal = initial_goal
        self.initial_context = initial_context
        self.test_command = test_command
        self.max_retries = max_retries
        self.logger = logging.getLogger(self.__class__.__name__)

        # Workflow state attributes
        self.current_plan: Optional[DevelopmentPlan] = None
        self.iteration: int = 0
        self.overall_success: bool = False
        self.final_loop_result: Optional[Dict[str, Any]] = None

        self.logger.info(f"CodingWorkflowOrchestrator initialized for goal: '{initial_goal[:50]}...'")

    async def _generate_plan(self) -> bool:
        self.logger.info(f"Executing Phase: _generate_plan for goal='{self.initial_goal[:50]}...'")
        params = {
            "goal": self.initial_goal,
            "context_string": self.initial_context
        }

        try:
            result_dict = await self.app.handle_task_command("user:generate-plan-from-goal", params=params)
        except Exception as e:
            self.logger.exception(f"Exception calling app.handle_task_command for plan generation: {e}")
            self.final_loop_result = {"status": "FAILED", "reason": "Plan generation task call failed", "details": str(e)}
            return False

        if not isinstance(result_dict, dict):
            self.logger.error(f"Plan generation task returned non-dict: {type(result_dict)}. Full response: {result_dict}")
            self.final_loop_result = {"status": "FAILED", "reason": "Plan generation returned invalid type", "details": f"Expected dict, got {type(result_dict)}"}
            return False

        self.logger.debug(f"Raw plan generation result_dict: {result_dict}")

        if result_dict.get("status") == "FAILED" or not result_dict.get("parsedContent"):
            self.logger.error(f"Plan generation task failed or no parsedContent. Status: {result_dict.get('status')}, Content: {result_dict.get('content')}")
            self.final_loop_result = {"status": "FAILED", "reason": "Plan generation task failed", "details": result_dict}
            return False

        try:
            parsed_content = result_dict["parsedContent"]
            if isinstance(parsed_content, DevelopmentPlan):
                self.current_plan = parsed_content
            elif isinstance(parsed_content, dict):  # If it's a dict, try to validate
                self.current_plan = DevelopmentPlan.model_validate(parsed_content)
            else:
                # Raise TypeError if parsed_content is not a dict or DevelopmentPlan instance
                raise TypeError(f"parsedContent is not a DevelopmentPlan object or a dict, but {type(parsed_content)}")

            self.logger.info(f"Plan generated and parsed successfully: Instructions='{self.current_plan.instructions[:50]}...', Files={self.current_plan.files}")
            return True
        except Exception as e:  # Catches Pydantic's ValidationError and other parsing issues including TypeError
            self.logger.error(f"Error parsing DevelopmentPlan from parsedContent: {e}. Content: {result_dict.get('parsedContent')}")
            self.final_loop_result = {"status": "FAILED", "reason": "Plan parsing failed", "details": str(e)}
            return False

    async def _execute_code(self) -> Optional[TaskResult]:
        self.logger.info(f"Executing Phase: _execute_code (Iteration: {self.iteration})")
        if not self.current_plan:
            self.logger.error("_execute_code called without a valid self.current_plan.")
            # Option 1: Return None, let run() handle it
            # return None
            # Option 2: Return a FAILED TaskResult
            return TaskResult(status="FAILED", content="Execution phase skipped: No current plan available.", notes={})

        if not self.current_plan.instructions or self.current_plan.files is None: # Files can be empty list
            self.logger.error(f"Current plan is missing instructions or files. Plan: {self.current_plan.model_dump_json(indent=2)}")
            return TaskResult(status="FAILED", content="Execution phase skipped: Plan missing instructions or files.", notes={})

        self.logger.info(f"  Plan Instructions: '{self.current_plan.instructions[:100]}...'")
        self.logger.info(f"  Plan Files: {self.current_plan.files}")

        aider_params = {
            "prompt": self.current_plan.instructions,
            "editable_files": self.current_plan.files # This should be a list of strings
        }
        
        try:
            self.logger.debug(f"Calling app.handle_task_command for 'aider_automatic' with params: {aider_params}")
            result_dict = await self.app.handle_task_command("aider_automatic", params=aider_params)
            
            if not isinstance(result_dict, dict):
                self.logger.error(f"'aider:automatic' task returned non-dict: {type(result_dict)}. Full response: {result_dict}")
                return TaskResult(status="FAILED", content=f"Aider task returned invalid type: {type(result_dict)}", notes={})

            self.logger.debug(f"Raw 'aider:automatic' result_dict: {result_dict}")
            # Validate and convert to TaskResult object
            return TaskResult.model_validate(result_dict)

        except Exception as e:
            self.logger.exception(f"Exception calling app.handle_task_command for 'aider:automatic': {e}")
            # Return a FAILED TaskResult
            return TaskResult(status="FAILED", content=f"Aider execution task call failed: {e}", notes={
                "error": {"type": "ORCHESTRATOR_EXCEPTION", "message": str(e)}
            })

    async def _validate_code(self) -> Optional[TaskResult]: # Return Optional[TaskResult] for consistency
        self.logger.info(f"Executing Phase: _validate_code (Iteration: {self.iteration})")
        if not self.test_command:
            self.logger.warning("No test_command configured for validation. Skipping validation phase.")
            # Return a TaskResult indicating skipped validation, or handle as appropriate
            return TaskResult(status="COMPLETE", content="Validation skipped: No test command.", notes={"skipped_validation": True})

        self.logger.info(f"  Test Command: '{self.test_command}'")
        
        test_params = {"command": self.test_command}
        
        try:
            self.logger.debug(f"Calling app.handle_task_command for 'system_execute_shell_command' with params: {test_params}")
            result_dict = await self.app.handle_task_command("system_execute_shell_command", params=test_params)

            if not isinstance(result_dict, dict):
                self.logger.error(f"'system:execute_shell_command' task returned non-dict: {type(result_dict)}. Full response: {result_dict}")
                return TaskResult(status="FAILED", content=f"Shell command task returned invalid type: {type(result_dict)}", notes={})
            
            self.logger.debug(f"Raw 'system:execute_shell_command' result_dict: {result_dict}")
            # Validate and convert to TaskResult object
            return TaskResult.model_validate(result_dict)

        except Exception as e:
            self.logger.exception(f"Exception calling app.handle_task_command for 'system:execute_shell_command': {e}")
            # Return a FAILED TaskResult
            return TaskResult(status="FAILED", content=f"Shell command execution task call failed: {e}", notes={
                "error": {"type": "ORCHESTRATOR_EXCEPTION", "message": str(e)}
            })

    async def _analyze_iteration(self, aider_result: TaskResult, test_result: TaskResult) -> Optional[CombinedAnalysisResult]:
        self.logger.info(f"Executing Phase: _analyze_iteration (Iteration: {self.iteration})")

        if not self.current_plan: # Should ideally not happen if called within a valid iteration
            self.logger.error("_analyze_iteration called without a self.current_plan.")
            self.final_loop_result = {"status": "FAILED", "reason": "Analysis skipped: No current plan."}
            return None

        analysis_params = {
            "original_goal": self.initial_goal,
            "initial_task_context": self.initial_context,
            "aider_instructions": self.current_plan.instructions,
            "aider_status": aider_result.status,
            "aider_diff": aider_result.content, # Pass the diff/output from Aider
            "test_command": self.test_command, # The command that was run
            "test_stdout": test_result.content if test_result.status == "COMPLETE" else "", # stdout is in content
            "test_stderr": test_result.notes.get("stderr", ""),
            "test_exit_code": test_result.notes.get("exit_code", -1), # Default to -1 if not found
            "previous_files": self.current_plan.files, # Pass the files used in this iteration
            "iteration": self.iteration,
            "max_retries": self.max_retries
        }
        
        try:
            self.logger.debug(f"Calling app.handle_task_command for 'user:evaluate-and-retry-analysis' with params: {analysis_params}")
            result_dict = await self.app.handle_task_command("user:evaluate-and-retry-analysis", params=analysis_params)

            if not isinstance(result_dict, dict):
                self.logger.error(f"'user:evaluate-and-retry-analysis' task returned non-dict: {type(result_dict)}. Full response: {result_dict}")
                self.final_loop_result = {"status": "FAILED", "reason": "Analysis task returned invalid type", "details": f"Expected dict, got {type(result_dict)}"}
                return None
            
            self.logger.debug(f"Raw 'user:evaluate-and-retry-analysis' result_dict: {result_dict}")

            if result_dict.get("status") == "FAILED" or not result_dict.get("parsedContent"):
                self.logger.error(f"Analysis task failed or no parsedContent. Status: {result_dict.get('status')}, Content: {result_dict.get('content')}")
                self.final_loop_result = {"status": "FAILED", "reason": "Analysis task failed", "details": result_dict}
                return None
            
            parsed_content = result_dict["parsedContent"]
            if isinstance(parsed_content, CombinedAnalysisResult):
                analysis_data = parsed_content
            elif isinstance(parsed_content, dict):
                analysis_data = CombinedAnalysisResult.model_validate(parsed_content)
            else:
                raise TypeError(f"parsedContent for analysis is not a CombinedAnalysisResult object or a dict, but {type(parsed_content)}")
                
            self.logger.info(f"Analysis completed. Verdict: {analysis_data.verdict}, Message: '{analysis_data.message[:50]}...'")
            return analysis_data

        except Exception as e:
            self.logger.exception(f"Exception calling/processing app.handle_task_command for 'user:evaluate-and-retry-analysis': {e}")
            self.final_loop_result = {"status": "FAILED", "reason": "Analysis task call/parsing failed", "details": str(e)}
            return None

    async def run(self) -> Dict[str, Any]:
        self.logger.info(f"Starting coding workflow run for goal: '{self.initial_goal[:50]}...'")
        self.iteration = 0  # Reset iteration count for each run
        self.overall_success = False # Reset overall success for each run
        self.final_loop_result = None # Reset final loop result

        if not await self._generate_plan():  # Initial plan generation
            self.logger.error("Initial plan generation failed. Workflow cannot proceed.")
            # Ensure final_loop_result is set if _generate_plan failed internally and set it
            if not self.final_loop_result:
                 self.final_loop_result = {"status": "FAILED", "reason": "Initial planning failed (orchestrator error)"}
            return self.final_loop_result

        while self.iteration < self.max_retries:
            self.iteration += 1
            self.logger.info(f"--- Starting Workflow Iteration {self.iteration}/{self.max_retries} ---")

            if not self.current_plan:  # Should be set by _generate_plan or previous RETRY
                self.logger.error(f"Iteration {self.iteration}: No current plan available. Aborting.")
                self.final_loop_result = {"status": "FAILED", "reason": "Missing plan in iteration"}
                break

            aider_result = await self._execute_code()
            if not aider_result:  # Should not happen if current_plan is checked and _execute_code returns TaskResult
                self.logger.error(f"Iteration {self.iteration}: Aider execution phase failed to return a result.")
                self.final_loop_result = {"status": "FAILED", "reason": "Aider execution error (no result)"}
                break

            if aider_result.status == "FAILED":
                self.logger.warning(f"Iteration {self.iteration}: Aider execution reported FAILED status: {aider_result.content}")
                # Continue to analysis phase to let LLM decide if it's recoverable

            test_result = await self._validate_code()
            if not test_result:  # Should not happen if _validate_code returns TaskResult
                self.logger.error(f"Iteration {self.iteration}: Validation phase failed to return a result.")
                self.final_loop_result = {"status": "FAILED", "reason": "Validation phase error (no result)"}
                break

            analysis_decision = await self._analyze_iteration(aider_result, test_result)

            if not analysis_decision:
                self.logger.error(f"Iteration {self.iteration}: Analysis phase failed or returned no decision.")
                # final_loop_result might have been set by _analyze_iteration if it caught an exception
                if not self.final_loop_result:
                    self.final_loop_result = {"status": "FAILED", "reason": "Analysis phase error (no decision)"}
                break

            self.logger.info(f"Iteration {self.iteration}: Analysis verdict: {analysis_decision.verdict}. Message: {analysis_decision.message}")

            if analysis_decision.verdict == "SUCCESS":
                self.overall_success = True
                self.logger.info("Workflow iteration successful and complete based on analysis LLM verdict!")
                self.final_loop_result = {
                    "status": "COMPLETE", 
                    "content": aider_result.content if aider_result else "Aider execution result not available for successful iteration.", # <<< MODIFIED LINE
                    "criteria": None, 
                    "parsedContent": None, 
                    "notes": {
                        "reason_for_success": analysis_decision.message, # Analysis message goes into notes
                        "final_aider_result_status": aider_result.status if aider_result else "N/A",
                        # "final_aider_content": aider_result.content if aider_result else "N/A", # Redundant with top-level content
                        "final_test_result_status": test_result.status if test_result else "N/A",
                        "final_test_stdout": test_result.content if test_result and test_result.status == "COMPLETE" else "",
                        "final_test_exit_code": test_result.notes.get("exit_code", -1) if test_result and test_result.notes else -1,
                        "analysis_message": analysis_decision.message # Keep analysis message in notes too
                    }
                }
                break
            elif analysis_decision.verdict == "RETRY":
                if self.current_plan and analysis_decision.next_prompt and analysis_decision.next_files is not None:
                    self.current_plan.instructions = analysis_decision.next_prompt
                    self.current_plan.files = analysis_decision.next_files
                    self.logger.info(f"Retrying with new plan: Instr='{self.current_plan.instructions[:50]}...', Files={self.current_plan.files}")
                elif not self.current_plan:
                    self.logger.error("Analysis suggested RETRY, but current_plan is None. This should not happen. Aborting.")
                    self.final_loop_result = {"status": "FAILED", "reason": "Internal error: RETRY with no current_plan"}
                    break
                else: # Missing next_prompt or next_files
                    self.logger.error("Analysis suggested RETRY but no valid next_prompt or next_files provided. Aborting.")
                    self.final_loop_result = {"status": "FAILED", "reason": "Analysis error: RETRY without valid next plan details"}
                    break
            else:  # FAILURE or unexpected verdict
                self.logger.info(f"Analysis verdict is {analysis_decision.verdict}. Stopping workflow.")
                self.final_loop_result = {
                    "status": "FAILED",
                    "reason": f"Analysis verdict: {analysis_decision.verdict}",
                    "details": analysis_decision.message,
                    "analysis_data": analysis_decision.model_dump()
                }
                break
        # End of while loop

        if self.iteration >= self.max_retries and not self.overall_success:
            self.logger.warning(f"Max retries ({self.max_retries}) reached. Workflow did not succeed.")
            if self.final_loop_result is None: # If loop finished due to max_retries without an explicit failure verdict
                 self.final_loop_result = {"status": "FAILED", "reason": "Max retries reached"}
            elif self.final_loop_result.get("status") != "FAILED": # Don't overwrite a more specific failure from analysis
                 self.final_loop_result = {"status": "FAILED", "reason": "Max retries reached", "previous_result": self.final_loop_result}


        self.logger.info("Coding workflow run finished.")
        return self.final_loop_result if self.final_loop_result else \
               {"status": "FAILED", "reason": "Workflow ended unexpectedly without a final result."}
