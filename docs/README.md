# Documentation Structure

## Directory Layout
```
docs/
├── system/                         # System-level documentation
│   ├── README.md                   # System overview
│   ├── architecture/               # Core architecture
│   │   ├── overview.md             # High-level design
│   │   ├── decisions/              # Architecture Decision Records (ADRs)
│   │   │   ├── index.md            # ADR index
│   │   │   ├── completed/          # Implemented ADRs
│   │   │   ├── needs_update/       # ADRs requiring updates
│   │   │   └── specs/              # ADR specifications
│   │   ├── patterns/               # Core patterns & principles
│   │   │   ├── index.md            # Pattern index
│   │   │   ├── context-frames.md   # Context frame pattern
│   │   │   ├── director-evaluator.md # Director-Evaluator pattern
│   │   │   ├── error-resources.md  # Error handling pattern
│   │   │   └── tool-interface.md   # Tool interface pattern
│   │   └── qa/                     # Architecture Q&A
│   ├── contracts/                  # System-wide contracts
│   │   ├── protocols.md            # Protocol definitions
│   │   ├── resources.md            # Resource management
│   │   └── types.md                # Type definitions
│   ├── integration/                # Integration documentation
│   │   └── cross-component.md      # Cross-component integration
│   ├── planning/                   # System planning
│   │   └── implementation-plan.md  # Implementation roadmap
│   └── qa/                         # System Q&A
│       ├── index.md                # Q&A index
│       ├── architecture-questions.md # Architecture questions
│       └── component-faq.md        # Component FAQ
│
├── components/                     # Component documentation
│   ├── index.md                    # Component index
│   ├── compiler/                   # Compiler component
│   │   ├── README.md               # Compiler overview
│   │   └── spec/                   # Compiler specifications
│   │       └── requirements.md     # Compiler requirements
│   ├── evaluator/                  # Evaluator component
│   │   ├── README.md               # Evaluator overview
│   │   ├── api/                    # Evaluator API
│   │   │   └── interfaces.md       # Evaluator interfaces
│   │   ├── spec/                   # Evaluator specifications
│   │       └── types.md            # Evaluator types
│   │   └── impl/                   # Evaluator implementation
│   │       └── design.md           # Evaluator design
│   ├── handler/                    # Handler component
│   │   ├── spec/                   # Handler specifications
│   │   │   ├── behaviors.md        # Handler behaviors
│   │   │   ├── interfaces.md       # Handler interfaces
│   │   │   └── types.md            # Handler types
│   │   └── impl/                   # Handler implementation
│   │       ├── provider-integration.md # Provider integration
│   │       └── resource-tracking.md # Resource tracking
│   ├── memory/                     # Memory component
│   │   └── api/                    # Memory API
│   │       └── interfaces.md       # Memory interfaces
│   └── task-system/                # Task System component
│       ├── README.md               # Task System overview
│       ├── spec/                   # Task System specifications
│       │   ├── interfaces.md       # Task System interfaces
│       │   ├── qa.md               # Task System Q&A
│       │   ├── requirements.md     # Task System requirements
│       │   └── types.md            # Task System types
│       └── impl/                   # Task System implementation
│           ├── index.md            # Implementation index
│           ├── design.md           # Task System design
│           ├── examples.md         # Implementation examples
│           └── examples/           # Implementation examples
│               ├── context-management.md # Context management
│               ├── function-templates.md # Function templates
│               └── subtask-spawning.md # Subtask spawning
│
├── index.md                        # Documentation home
├── inconsistencies.md              # Known inconsistencies
├── misc/                           # Miscellaneous documentation
│   └── errorspec.md                # Error specifications
├── plans/                          # Planning documentation
│   └── general_improvements.md     # General improvement plans
├── process.md                      # Development process
└── spec_prompt_guide.xml           # Specification prompt guide
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

## Key Documentation

### System Documentation
- [System Overview](./system/README.md)
- [Architecture Overview](./system/architecture/overview.md)
- [Documentation Guide](./system/docs-guide.md)

### Architecture
- [Pattern Index](./system/architecture/patterns/index.md)
- [Decision Records Index](./system/architecture/decisions/index.md)
- [New ADRs](./new_adrs/README.md)
- [Core Patterns](./system/architecture/patterns)
  - [Context Frame Pattern](./system/architecture/patterns/context-frames.md)
  - [Director-Evaluator Pattern](./system/architecture/patterns/director-evaluator.md)
  - [Tool Interface Pattern](./system/architecture/patterns/tool-interface.md)
  - [Error Handling Pattern](./system/architecture/patterns/errors.md)
  - [Resource Management Pattern](./system/architecture/patterns/resource-management.md)

### Contracts & Integration
- [Interface Contracts](./system/contracts/interfaces.md)
- [Protocol Specifications](./system/contracts/protocols.md)
- [Type Definitions](./system/contracts/types.md)
- [Resource Contracts](./system/contracts/resources.md)
- [Cross-Component Integration](./system/integration/cross-component.md)

### Component Documentation
- [Component Index](./components/index.md)
- [Task System](./components/task-system/README.md)
- [Memory System](./components/memory/README.md)
- [Evaluator](./components/evaluator/README.md)
- [Handler](./components/handler/README.md)
- [Compiler](./components/compiler/README.md)

### Implementation Resources
- [Implementation Plan](./system/planning/implementation-plan.md)
- [Task System Implementation](./components/task-system/impl/design.md)
- [Examples & Patterns](./components/task-system/impl/examples.md)

### Questions & Troubleshooting
- [Q&A Index](./system/qa/index.md)
- [Architecture Questions](./system/qa/architecture-questions.md)
- [Component FAQ](./system/qa/component-faq.md)
- [Known Inconsistencies](./inconsistencies.md)

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

