# Documentation Structure

## Directory Layout
```
docs/
├── system/                         # System-level documentation
│   ├── [README.md](./system/README.md)                   # System overview
│   ├── architecture/               # Core architecture
│   │   ├── [overview.md](./system/architecture/overview.md)             # High-level design
│   │   ├── decisions/              # Architecture Decision Records (ADRs)
│   │   │   ├── [index.md](./system/architecture/decisions/index.md)            # ADR index
│   │   │   ├── completed/          # Implemented ADRs
│   │   │   ├── needs_update/       # ADRs requiring updates
│   │   │   └── specs/              # ADR specifications
│   │   ├── patterns/               # Core patterns & principles
│   │   │   ├── [index.md](./system/architecture/patterns/index.md)            # Pattern index
│   │   │   ├── [context-frames.md](./system/architecture/patterns/context-frames.md)   # Context frame pattern
│   │   │   ├── [director-evaluator.md](./system/architecture/patterns/director-evaluator.md) # Director-Evaluator pattern
│   │   │   ├── [error-resources.md](./system/architecture/patterns/error-resources.md)  # Error handling pattern
│   │   │   └── [tool-interface.md](./system/architecture/patterns/tool-interface.md)   # Tool interface pattern
│   │   └── qa/                     # Architecture Q&A
│   ├── contracts/                  # System-wide contracts
│   │   ├── [protocols.md](./system/contracts/protocols.md)            # Protocol definitions
│   │   ├── [resources.md](./system/contracts/resources.md)            # Resource management
│   │   └── [types.md](./system/contracts/types.md)                # Type definitions
│   ├── integration/                # Integration documentation
│   │   └── [cross-component.md](./system/integration/cross-component.md)      # Cross-component integration
│   ├── planning/                   # System planning
│   │   └── [implementation-plan.md](./system/planning/implementation-plan.md)  # Implementation roadmap
│   └── qa/                         # System Q&A
│       ├── [index.md](./system/qa/index.md)                # Q&A index
│       ├── [architecture-questions.md](./system/qa/architecture-questions.md) # Architecture questions
│       └── [component-faq.md](./system/qa/component-faq.md)        # Component FAQ
│
├── components/                     # Component documentation
│   ├── [index.md](./components/index.md)                    # Component index
│   ├── compiler/                   # Compiler component
│   │   ├── [README.md](./components/compiler/README.md)               # Compiler overview
│   │   └── spec/                   # Compiler specifications
│   │       └── [requirements.md](./components/compiler/spec/requirements.md)     # Compiler requirements
│   ├── evaluator/                  # Evaluator component
│   │   ├── [README.md](./components/evaluator/README.md)               # Evaluator overview
│   │   ├── api/                    # Evaluator API
│   │   │   └── [interfaces.md](./components/evaluator/api/interfaces.md)       # Evaluator interfaces
│   │   ├── spec/                   # Evaluator specifications
│   │       └── [types.md](./components/evaluator/spec/types.md)            # Evaluator types
│   │   └── impl/                   # Evaluator implementation
│   │       └── [design.md](./components/evaluator/impl/design.md)           # Evaluator design
│   ├── handler/                    # Handler component
│   │   ├── spec/                   # Handler specifications
│   │   │   ├── [behaviors.md](./components/handler/spec/behaviors.md)        # Handler behaviors
│   │   │   ├── [interfaces.md](./components/handler/spec/interfaces.md)       # Handler interfaces
│   │   │   └── [types.md](./components/handler/spec/types.md)            # Handler types
│   │   └── impl/                   # Handler implementation
│   │       ├── [provider-integration.md](./components/handler/impl/provider-integration.md) # Provider integration
│   │       └── [resource-tracking.md](./components/handler/impl/resource-tracking.md) # Resource tracking
│   ├── memory/                     # Memory component
│   │   └── api/                    # Memory API
│   │       └── [interfaces.md](./components/memory/api/interfaces.md)       # Memory interfaces
│   └── task-system/                # Task System component
│       ├── [README.md](./components/task-system/README.md)               # Task System overview
│       ├── spec/                   # Task System specifications
│       │   ├── [interfaces.md](./components/task-system/spec/interfaces.md)       # Task System interfaces
│       │   ├── [qa.md](./components/task-system/spec/qa.md)               # Task System Q&A
│       │   ├── [requirements.md](./components/task-system/spec/requirements.md)     # Task System requirements
│       │   └── [types.md](./components/task-system/spec/types.md)            # Task System types
│       └── impl/                   # Task System implementation
│           ├── [index.md](./components/task-system/impl/index.md)            # Implementation index
│           ├── [design.md](./components/task-system/impl/design.md)           # Task System design
│           ├── [examples.md](./components/task-system/impl/examples.md)         # Implementation examples
│           └── examples/           # Implementation examples
│               ├── [context-management.md](./components/task-system/impl/examples/context-management.md) # Context management
│               ├── [function-templates.md](./components/task-system/impl/examples/function-templates.md) # Function templates
│               └── [subtask-spawning.md](./components/task-system/impl/examples/subtask-spawning.md) # Subtask spawning
│
├── [index.md](./index.md)                        # Documentation home
├── [inconsistencies.md](./inconsistencies.md)              # Known inconsistencies
├── misc/                           # Miscellaneous documentation
│   └── [errorspec.md](./misc/errorspec.md)                # Error specifications
├── plans/                          # Planning documentation
│   └── [general_improvements.md](./plans/general_improvements.md)     # General improvement plans
├── [process.md](./process.md)                      # Development process
└── [spec_prompt_guide.xml](./spec_prompt_guide.xml)           # Specification prompt guide
```

## Document Standards

### Documentation Principles
1. Single Responsibility
   - Each document covers one concern
   - Clear boundaries between concerns
   - Explicit dependencies

2. Contract Completeness
   - All requirements stated
   - All guarantees explicit
   - All resources documented

3. Resource Clarity
   - Ownership explicit
   - Lifecycle documented
   - Cleanup requirements specified

### Writing Style
1. Active voice
2. One sentence per line
3. Explicit section numbering
4. Consistent terminology

### Version Management
1. Version Format: MAJOR.MINOR.PATCH
2. Update Rules:
   - MAJOR: Breaking changes
   - MINOR: New features, backward compatible
   - PATCH: Bug fixes, backward compatible

### Cross-Reference Updates
Ensure that all components referencing the Director-Evaluator pattern mention both the dynamic and static variants. In particular, update references to [Pattern:DirectorEvaluator:1.1] to include the static variant with script execution support.
