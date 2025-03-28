# Task System FAQ

This FAQ provides concise answers to common questions about the Task System.

**Q: How many Handlers should be created per task execution?**  
A: One Handler per task execution. See [Task System Requirements](requirements.md) for details.

**Q: Who is responsible for sending prompts to the LLM?**  
A: The Handler is responsible for all LLM interactions.

**Q: How are resource limits enforced?**  
A: Resource limits are passed to the Handler at initialization and enforced during execution. For more details, see [Task System Behaviors](behaviors.md).

For additional questions, please refer to system‑level documentation or contact the Task System maintainers.
