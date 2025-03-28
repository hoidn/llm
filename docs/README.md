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

### Version Management
1. Version Format: MAJOR.MINOR.PATCH
2. Update Rules:
   - MAJOR: Breaking changes
   - MINOR: New features, backward compatible
   - PATCH: Bug fixes, backward compatible

### Cross-Reference Updates
Ensure that all components referencing the Director-Evaluator pattern mention both the dynamic and static variants. In particular, update references to [Pattern:DirectorEvaluator:1.1] to include the static variant with script execution support.
