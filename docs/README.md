# Documentation Structure

## Directory Layout
```
docs/
├── system/                         # System-level documentation
│   ├── [README.md](./docs/system/README.md)                   # System overview
│   ├── architecture/               # Core architecture
│   │   ├── [overview.md](./docs/system/architecture/overview.md)             # High-level design
│   │   ├── decisions/              # Architecture Decision Records (ADRs)
│   │   │   ├── [index.md](./docs/system/architecture/decisions/index.md)            # ADR index
│   │   │   ├── completed/          # Implemented ADRs
│   │   │   ├── needs_update/       # ADRs requiring updates
│   │   │   └── specs/              # ADR specifications
│   │   ├── patterns/               # Core patterns & principles
│   │   │   ├── [index.md](./docs/system/architecture/patterns/index.md)            # Pattern index
│   │   │   ├── [context-frames.md](./docs/system/architecture/patterns/context-frames.md)   # Context frame pattern
│   │   │   ├── [director-evaluator.md](./docs/system/architecture/patterns/director-evaluator.md) # Director-Evaluator pattern
│   │   │   ├── [error-resources.md](./docs/system/architecture/patterns/error-resources.md)  # Error handling pattern
│   │   │   └── [tool-interface.md](./docs/system/architecture/patterns/tool-interface.md)   # Tool interface pattern
│   │   └── qa/                     # Architecture Q&A
│   ├── contracts/                  # System-wide contracts
│   │   ├── [protocols.md](./docs/system/contracts/protocols.md)            # Protocol definitions
│   │   ├── [resources.md](./docs/system/contracts/resources.md)            # Resource management
│   │   └── [types.md](./docs/system/contracts/types.md)                # Type definitions
│   ├── integration/                # Integration documentation
│   │   └── [cross-component.md](./docs/system/integration/cross-component.md)      # Cross-component integration
│   ├── planning/                   # System planning
│   │   └── [implementation-plan.md](./docs/system/planning/implementation-plan.md)  # Implementation roadmap
│   └── qa/                         # System Q&A
│       ├── [index.md](./docs/system/qa/index.md)                # Q&A index
│       ├── [architecture-questions.md](./docs/system/qa/architecture-questions.md) # Architecture questions
│       └── [component-faq.md](./docs/system/qa/component-faq.md)        # Component FAQ
│
├── components/                     # Component documentation
│   ├── [index.md](./docs/components/index.md)                    # Component index
│   ├── compiler/                   # Compiler component
│   │   ├── [README.md](./docs/components/compiler/README.md)               # Compiler overview
│   │   └── spec/                   # Compiler specifications
│   │       └── [requirements.md](./docs/components/compiler/spec/requirements.md)     # Compiler requirements
│   ├── evaluator/                  # Evaluator component
│   │   ├── [README.md](./docs/components/evaluator/README.md)               # Evaluator overview
│   │   ├── api/                    # Evaluator API
│   │   │   └── [interfaces.md](./docs/components/evaluator/api/interfaces.md)       # Evaluator interfaces
│   │   ├── spec/                   # Evaluator specifications
│   │       └── [types.md](./docs/components/evaluator/spec/types.md)            # Evaluator types
│   │   └── impl/                   # Evaluator implementation
│   │       └── [design.md](./docs/components/evaluator/impl/design.md)           # Evaluator design
│   ├── handler/                    # Handler component
│   │   ├── spec/                   # Handler specifications
│   │   │   ├── [behaviors.md](./docs/components/handler/spec/behaviors.md)        # Handler behaviors
│   │   │   ├── [interfaces.md](./docs/components/handler/spec/interfaces.md)       # Handler interfaces
│   │   │   └── [types.md](./docs/components/handler/spec/types.md)            # Handler types
│   │   └── impl/                   # Handler implementation
│   │       ├── [provider-integration.md](./docs/components/handler/impl/provider-integration.md) # Provider integration
│   │       └── [resource-tracking.md](./docs/components/handler/impl/resource-tracking.md) # Resource tracking
│   ├── memory/                     # Memory component
│   │   └── api/                    # Memory API
│   │       └── [interfaces.md](./docs/components/memory/api/interfaces.md)       # Memory interfaces
│   └── task-system/                # Task System component
│       ├── [README.md](./docs/components/task-system/README.md)               # Task System overview
│       ├── spec/                   # Task System specifications
│       │   ├── [interfaces.md](./docs/components/task-system/spec/interfaces.md)       # Task System interfaces
│       │   ├── [qa.md](./docs/components/task-system/spec/qa.md)               # Task System Q&A
│       │   ├── [requirements.md](./docs/components/task-system/spec/requirements.md)     # Task System requirements
│       │   └── [types.md](./docs/components/task-system/spec/types.md)            # Task System types
│       └── impl/                   # Task System implementation
│           ├── [index.md](./docs/components/task-system/impl/index.md)            # Implementation index
│           ├── [design.md](./docs/components/task-system/impl/design.md)           # Task System design
│           ├── [examples.md](./docs/components/task-system/impl/examples.md)         # Implementation examples
│           └── examples/           # Implementation examples
│               ├── [context-management.md](./docs/components/task-system/impl/examples/context-management.md) # Context management
│               ├── [function-templates.md](./docs/components/task-system/impl/examples/function-templates.md) # Function templates
│               └── [subtask-spawning.md](./docs/components/task-system/impl/examples/subtask-spawning.md) # Subtask spawning
│
├── [index.md](./docs/index.md)                        # Documentation home
├── [inconsistencies.md](./docs/inconsistencies.md)              # Known inconsistencies
├── misc/                           # Miscellaneous documentation
│   └── [errorspec.md](./docs/misc/errorspec.md)                # Error specifications
├── plans/                          # Planning documentation
│   └── [general_improvements.md](./docs/plans/general_improvements.md)     # General improvement plans
├── [process.md](./docs/process.md)                      # Development process
└── [spec_prompt_guide.xml](./docs/spec_prompt_guide.xml)           # Specification prompt guide
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
